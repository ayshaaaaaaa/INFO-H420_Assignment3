"""Research paper pipeline.

find new PDFs -> (per PDF) convert + LLM metadata + save to SQLite
              -> regenerate static HTML -> Discord notification

If there are no new PDFs, the mapped task has nothing to do, so the HTML and
Discord tasks are skipped automatically.
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Make `src/` importable even if PYTHONPATH is not set for the Airflow process.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from airflow.sdk import dag, task

# How often Airflow looks for new PDFs (cron syntax: every 10 minutes).
SCHEDULE = "*/10 * * * *"


@dag(
    dag_id="paper_pipeline",
    schedule=SCHEDULE,
    start_date=datetime(2026, 11, 1),
    catchup=False,
    max_active_runs=1,  # never run two pipelines at once (the LLM is slow)
    default_args={"owner": "info-h420"},
    tags=["info-h420", "papers"],
)
def paper_pipeline():
    @task
    def find_new_pdfs() -> list[str]:
        """List PDFs in PAPERS_DIR that are not in the database yet."""
        from src.db import is_processed

        papers_dir = os.environ["PAPERS_DIR"]
        pdfs = sorted(f for f in os.listdir(papers_dir) if f.lower().endswith(".pdf"))
        new = [f for f in pdfs if not is_processed(f)]
        print(f"Found {len(pdfs)} PDFs, {len(new)} new: {new}")
        return new

    @task(
        retries=1,
        retry_delay=timedelta(seconds=30),
        execution_timeout=timedelta(minutes=15),
        max_active_tis_per_dagrun=1,  # one paper at a time, easy on the laptop
    )
    def process_paper(filename: str) -> dict:
        """PDF -> Markdown -> LLM JSON -> SQLite, for ONE paper."""
        from src.db import save_paper
        from src.llm_metadata import extract_metadata
        from src.pdf_convert import convert_pdf

        path = os.path.join(os.environ["PAPERS_DIR"], filename)
        markdown = convert_pdf(path)
        meta = extract_metadata(markdown)
        save_paper(filename, meta)
        print(f"Saved {filename}: {meta['title']} [{meta['category']}]")
        return {
            "filename": filename,
            "title": meta["title"],
            "category": meta["category"],
        }

    @task
    def build_html(processed: list[dict]) -> str:
        """Regenerate index.html from everything in the database."""
        from src.db import get_all_papers
        from src.html_gen import generate_html

        path = generate_html(get_all_papers())
        print(f"Wrote {path}")
        return path

    @task
    def notify(processed: list[dict], html_path: str) -> None:
        """Tell Discord which papers were processed."""
        from src.notify import send_discord

        items = list(processed)
        lines = [f"- {p['title']} ({p['category']})" for p in items]
        message = (
            f"{len(items)} new paper(s) processed:\n"
            + "\n".join(lines)
            + "\nLibrary page updated."
        )
        send_discord(message)

    new_files = find_new_pdfs()
    processed = process_paper.expand(filename=new_files)  # one task per PDF
    html_path = build_html(processed)
    notify(processed, html_path)


paper_pipeline()
