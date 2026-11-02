import json
import os
import sqlite3

DB_PATH = os.environ.get("DB_PATH", os.path.expanduser("~/airflow_data/papers.db"))


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    with _connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS papers (
                   filename TEXT UNIQUE NOT NULL,
                   title    TEXT,
                   summary  TEXT,
                   keywords TEXT,
                   category TEXT
               )"""
        )


def is_processed(filename: str) -> bool:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM papers WHERE filename = ?", (filename,)
        ).fetchone()
    return row is not None


def save_paper(filename: str, meta: dict) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO papers (filename, title, summary, keywords, category) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                filename,
                meta["title"],
                meta["summary"],
                json.dumps(meta["keywords"]),
                meta["category"],
            ),
        )


def get_all_papers() -> list[dict]:
    init_db()
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM papers ORDER BY title").fetchall()
    papers = [dict(r) for r in rows]
    for p in papers:
        p["keywords"] = json.loads(p["keywords"]) if p["keywords"] else []
    return papers
