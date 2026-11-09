import os
import sys
import logging
from pathlib import Path
from datetime import timedelta

import pendulum
from airflow.sdk import dag, task


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

    # find new df
    @task(task_id="find_new_pdfs")
    def find_new_pdfs() -> list[str]:
        from src.db import init_db, is_processed

        papers_dir = Path(os.environ["PAPERS_DIR"])

        if not papers_dir.is_dir():
            raise FileNotFoundError(
                f"Papers directory not found: {papers_dir}"
            )

        db_path = Path(os.environ["DB_PATH"])
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create new DB
        init_db()

        # Find teh PDFs
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

    # Process PDFs

    @task(
        task_id="process_paper",
        execution_timeout=timedelta(minutes=15),
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

        # PDF to markdown conversion
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

        # Extract metadata using LLM
        metadata = extract_metadata(markdown)

        logger.info(
            "LLM metadata for %s: %s",
            filename,
            metadata,
        )

        #  Save the data in sqllite DB
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

    # Builds HTML UI 
    @task(task_id="build_html")
    def build_html(processed_papers: list[dict[str, str]]) -> dict:
        from src.db import get_all_papers
        from src.html_gen import generate_html

        processed_papers = list(processed_papers)

        logger.info(
            "Building HTML after processing %d new papers",
            len(processed_papers),
        )

        all_papers = get_all_papers()

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

    # Discord Notification
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

        # Size limit for the webhook
        message = message[:1900]

        send_discord(message)

        logger.info(
            "Discord notification sent for %d papers",
            count,
        )


    new_pdfs = find_new_pdfs()


    processed = process_paper.expand(
        filename=new_pdfs
    )

    html_result = build_html(processed)

    notify(html_result)

paper_pipeline()
