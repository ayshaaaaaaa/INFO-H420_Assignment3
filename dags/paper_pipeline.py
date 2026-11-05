import glob
import os
import pathlib
import sys
from datetime import datetime, timedelta

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from airflow.sdk import dag, task  # Airflow 3.x

from src.db import init_db, is_processed, save_paper, get_all_papers
from src.pdf_convert import convert_pdf
from src.llm_metadata import extract_metadata
from src.html_gen import generate_html
from src.notify import send_discord

MD_DIR = pathlib.Path(
    os.environ.get("MD_DIR", os.path.expanduser("~/airflow_data/markdown"))
)


@dag(
    dag_id="paper_pipeline",
    schedule=timedelta(minutes=15),
    start_date=datetime(2026, 11, 1),
    catchup=False,
    max_active_runs=1,
    tags=["INFO-H420"],
)
def paper_pipeline():

    @task
    def find_new_pdfs() -> list[str]:
        """Return the PDFs in the papers folder that are not in the database yet."""
        init_db()
        pdfs = sorted(glob.glob(os.path.join(os.environ["PAPERS_DIR"], "*.pdf")))
        return [p for p in pdfs if not is_processed(os.path.basename(p))]

    @task
    def to_markdown(pdf_path: str) -> dict:
        """Convert one PDF to Markdown and save it to disk."""
        md = convert_pdf(pdf_path)
        if len(md.strip()) < 200:
            raise ValueError(f"Almost no text extracted from {pdf_path} (scanned PDF?)")
        MD_DIR.mkdir(parents=True, exist_ok=True)
        md_file = MD_DIR / (pathlib.Path(pdf_path).stem + ".md")
        md_file.write_text(md, encoding="utf-8")
        return {"filename": os.path.basename(pdf_path), "md_file": str(md_file)}

    @task(max_active_tis_per_dag=1, retries=1, retry_delay=timedelta(seconds=30))
    def get_metadata(item: dict) -> dict:
        """Ask the local LLM for title, summary, keywords and category."""
        md = pathlib.Path(item["md_file"]).read_text(encoding="utf-8")
        return {"filename": item["filename"], "meta": extract_metadata(md)}

    @task
    def store(item: dict) -> dict:
        """Save one paper's metadata to SQLite."""
        save_paper(item["filename"], item["meta"])
        return item

    @task
    def build_html(stored: list[dict]) -> str:
        """Regenerate the static HTML page from the whole database."""
        return str(generate_html(get_all_papers()))

    @task
    def notify(stored: list[dict], html_path: str) -> None:
        """Send one Discord message per newly processed paper."""
        for item in stored:
            title = item["meta"]["title"]
            category = item["meta"]["category"]
            send_discord(f"📄 New paper processed: **{title}** ({category})")

    new_pdfs = find_new_pdfs()
    converted = to_markdown.expand(pdf_path=new_pdfs)
    with_meta = get_metadata.expand(item=converted)
    stored = store.expand(item=with_meta)
    html_path = build_html(stored)
    notify(stored, html_path)


paper_pipeline()