
"""
INFO-H420 Assignment 3
Research Paper Processing Pipeline

Workflow:
    find_new_pdfs
         |
         v
    process_paper (one task per new PDF)
         |
         v
    build_html
         |
         v
    notify

Airflow version: 3.0.6
"""

import os
import sys
import logging
from pathlib import Path
from datetime import timedelta

import pendulum
from airflow.sdk import dag, task

# Let Airflow import "src" when this file is in PROJECT_ROOT/dags/.
# The existing PYTHONPATH configuration can still be used.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)


@dag(
    dag_id="paper_pipeline",
    description="Process research PDFs using a local LLM",
    schedule="*/10 * * * *",
    start_date=pendulum.datetime(2026, 11, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    max_active_tasks=1,
    default_args={
        "owner": "info-h420",
        "retries": 1,
        "retry_delay": timedelta(minutes=1),
    },
    tags=["research", "pdf", "llm", "assignment3"],
)
def paper_pipeline():

    # --------------------------------------------------
    # TASK 1: Find new PDFs
    # --------------------------------------------------

    @task(task_id="find_new_pdfs")
    def find_new_pdfs() -> list[str]:
        from src.db import init_db, is_processed

        papers_dir = Path(os.environ["PAPERS_DIR"])

        if not papers_dir.is_dir():
            raise FileNotFoundError(
                f"Papers directory not found: {papers_dir}"
            )

        # Ensure the local database directory exists
        db_path = Path(os.environ["DB_PATH"])
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create the database table if needed
        init_db()

        # Find PDFs in the input folder
        pdf_files = sorted(
            p for p in papers_dir.iterdir()
            if p.is_file() and p.suffix.lower() == ".pdf"
        )

        new_pdfs = [
            p.name
            for p in pdf_files
            if not is_processed(p.name)
        ]

        logger.info(
            "Found %d PDFs, %d new: %s",
            len(pdf_files),
            len(new_pdfs),
            new_pdfs,
        )

        return new_pdfs

    # --------------------------------------------------
    # TASK 2: Process one research paper
    # --------------------------------------------------

    @task(
        task_id="process_paper",
        execution_timeout=timedelta(minutes=15),
        # max_active_tasks=1 above already makes all mapped papers sequential.
    )
    def process_paper(filename: str) -> dict[str, str]:
        from src.pdf_convert import convert_pdf
        from src.llm_metadata import extract_metadata
        from src.db import save_paper

        papers_dir = Path(os.environ["PAPERS_DIR"])
        pdf_path = papers_dir / filename

        if not pdf_path.is_file():
            raise FileNotFoundError(
                f"PDF not found: {pdf_path}"
            )

        logger.info("Processing PDF: %s", filename)

        # Step A: Convert PDF into Markdown
        markdown = convert_pdf(str(pdf_path))

        if not markdown or not markdown.strip():
            raise ValueError(
                f"No text extracted from {filename}"
            )

        logger.info(
            "Extracted %d characters from %s",
            len(markdown),
            filename,
        )

        # Step B: Ask the local LLM for metadata
        # The helper validates JSON and retries if needed
        metadata = extract_metadata(markdown)

        logger.info(
            "LLM metadata for %s: %s",
            filename,
            metadata,
        )

        # Step C: Save the metadata to SQLite
        save_paper(filename, metadata)

        logger.info(
            "Saved %s: %s [%s]",
            filename,
            metadata["title"],
            metadata["category"],
        )

        return {
            "filename": filename,
            "title": metadata["title"],
            "category": metadata["category"],
        }

    # --------------------------------------------------
    # TASK 3: Generate searchable HTML page
    # --------------------------------------------------

    @task(task_id="build_html")
    def build_html(processed_papers: list[dict[str, str]]) -> dict:
        from src.db import get_all_papers
        from src.html_gen import generate_html

        # Collect results from all mapped tasks
        processed_papers = list(processed_papers)

        logger.info(
            "Building HTML after processing %d new papers",
            len(processed_papers),
        )

        # Read all papers, including older ones
        all_papers = get_all_papers()

        # Generate the HTML file in OUTPUT_DIR
        output_path = generate_html(all_papers)

        logger.info(
            "Wrote HTML page: %s",
            output_path,
        )

        return {
            "count": len(processed_papers),
            "papers": processed_papers,
            "output_path": str(output_path),
        }

    # --------------------------------------------------
    # TASK 4: Send Discord notification
    # --------------------------------------------------

    @task(task_id="notify", retries=0)
    def notify(result: dict) -> None:
        from src.notify import send_discord

        count = result["count"]
        papers = result["papers"]

        lines = [
            f"Research Library: {count} new paper(s) processed!"
        ]

        for paper in papers:
            lines.append(
                f"- {paper['title']} ({paper['category']})"
            )

        message = "\n".join(lines)

        # Discord webhook messages have a size limit
        message = message[:1900]

        send_discord(message)

        logger.info(
            "Discord notification sent for %d papers",
            count,
        )

    # --------------------------------------------------
    # Define task dependencies
    # --------------------------------------------------

    new_pdfs = find_new_pdfs()

    # Dynamic task mapping:
    # one instance for each new PDF
    processed = process_paper.expand(
        filename=new_pdfs
    )

    html_result = build_html(processed)

    notify(html_result)


# Register the DAG with Airflow
paper_pipeline()
