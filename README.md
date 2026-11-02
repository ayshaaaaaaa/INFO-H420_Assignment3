# INFO-H420 Assignment 3: Research Paper Pipeline

An Apache Airflow pipeline that turns research PDFs into a searchable study library.
New PDFs dropped into a Google Drive-synced folder are converted to Markdown, described
by a locally served LLM (title, summary, keywords, category), stored in SQLite, and
published as a static HTML page. A Discord message announces each new paper.

## Pipeline

```
Google Drive: papers/*.pdf
          |
          v
 [1] find_new_pdfs        list PDFs not yet in the database
          |
          v
 [2] convert_pdf          PDF -> Markdown (PyMuPDF4LLM)
          |
          v
 [3] extract_metadata     local LLM (Ollama, OpenAI-compatible API) -> JSON
          |               parse with json.loads, validate fields, retry once
          v
 [4] save_paper           SQLite (local, outside the synced folder)
          |
          v
 [5] generate_html        static index.html with search + category filter
          |               written to Google Drive: output/
          v
 [6] send_discord         webhook notification for each new paper
```

The whole chain is one scheduled Airflow DAG (`dags/paper_pipeline.py`).
Google Drive syncs the PDFs and the generated HTML; the SQLite database stays on the
local machine.

## Project status

| Component | File | Status |
|---|---|---|
| Repo structure, `.gitignore`, `.env.example` | - | Done |
| Environment (WSL2, Python 3.12 venv, Airflow 3.0.6, Ollama + llama3.2:3b) | - | Done |
| PDF to Markdown | `src/pdf_convert.py` | Written, being tested |
| SQLite storage | `src/db.py` | Written, being tested |
| LLM metadata extraction (JSON, retry, validation) | `src/llm_metadata.py` | Written, being tested |
| HTML generator | `src/html_gen.py` | To do |
| Discord notification | `src/notify.py` | To do |
| Airflow DAG | `dags/paper_pipeline.py` | To do |
| Report with screenshots | - | To do |

## Repository layout

```
.
├── dags/
│   └── paper_pipeline.py     # Airflow DAG (scheduled)
├── src/
│   ├── pdf_convert.py        # convert_pdf(path) -> markdown
│   ├── llm_metadata.py       # extract_metadata(markdown) -> dict
│   ├── db.py                 # init_db, is_processed, save_paper, get_all_papers
│   ├── html_gen.py           # generate_html(papers, output_path)
│   └── notify.py             # send_discord(message)
├── data/                     # local data (database is gitignored)
├── requirements.txt
├── .env.example
└── README.md
```

External folders (not in the repo):

```
Google Drive/ResearchLibrary/
├── papers/    # input PDFs (synced)
└── output/    # generated index.html (synced)

~/airflow_data/papers.db      # SQLite database, local only
```

## Tools

| Purpose | Tool |
|---|---|
| Orchestration | Apache Airflow 3.0.6 (`airflow standalone`) |
| PDF to Markdown | PyMuPDF4LLM |
| Local LLM | Ollama with `llama3.2:3b` (OpenAI-compatible endpoint) |
| LLM client | Python `openai` package |
| Storage | Python built-in `sqlite3` |
| Notifications | Discord webhook (`requests`) |

## LLM output

The model is asked for JSON in this shape:

```json
{
  "title": "Paper title",
  "summary": "A short summary of the paper.",
  "keywords": ["keyword one", "keyword two"],
  "category": "Data Engineering"
}
```

- JSON mode is requested via `response_format={"type": "json_object"}`.
- The response is parsed with `json.loads()`; on failure it is retried once.
- Required fields and basic types are checked. Categories are restricted to a fixed
  list; anything else becomes `Other`.
- Only the first ~8000 characters of the Markdown are sent, because the title and
  abstract are at the start and the default context window is small.

## Database

Table `papers` (one row per PDF, filenames assumed unique):

| Column | Type | Notes |
|---|---|---|
| filename | TEXT UNIQUE | used to skip already processed PDFs |
| title | TEXT | |
| summary | TEXT | |
| keywords | TEXT | JSON string, e.g. `["a", "b"]` |
| category | TEXT | |

## Setup

These steps were done on Windows with WSL2 (Ubuntu). Airflow does not run natively
on Windows.

### 1. System packages and Python 3.12 virtual environment

```bash
sudo apt update && sudo apt install -y python3-pip sqlite3 zstd curl

curl -LsSf https://astral.sh/uv/install.sh | sh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

mkdir -p ~/.venvs
uv venv ~/.venvs/info-h420 --python 3.12
source ~/.venvs/info-h420/bin/activate
```

Python 3.12 is used because the newest system Python may not be supported by Airflow yet.

### 2. Install Airflow and the project libraries

```bash
AIRFLOW_VERSION=3.0.6
CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-3.12.txt"

uv pip install "apache-airflow==${AIRFLOW_VERSION}" --constraint "${CONSTRAINT_URL}"
uv pip install pymupdf4llm openai requests
```

### 3. Install Ollama and pull the model

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:3b
```

Make sure the Ollama server is running (`ollama serve`) before running the pipeline.
Any model can be used by changing `LLM_MODEL` (for example `llama3.1:8b` on machines
with 16 GB+ RAM).

### 4. Environment variables

Add to `~/.bashrc` and adapt the paths. Never commit real secrets; see `.env.example`.

```bash
export AIRFLOW_HOME=~/airflow_home
export PROJECT_DIR="/path/to/INFO-H420_Assignment3"
export AIRFLOW__CORE__DAGS_FOLDER="$PROJECT_DIR/dags"
export AIRFLOW__CORE__LOAD_EXAMPLES=False
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

export DB_PATH=~/airflow_data/papers.db
export LLM_BASE_URL=http://localhost:11434/v1
export LLM_MODEL=llama3.2:3b

export PAPERS_DIR="/path/to/GoogleDrive/ResearchLibrary/papers"
export OUTPUT_DIR="/path/to/GoogleDrive/ResearchLibrary/output"
export DISCORD_WEBHOOK_URL="your-webhook-url"
```

Then:

```bash
mkdir -p ~/airflow_data
source ~/.bashrc
```

### 5. Discord webhook

In a Discord channel: Edit Channel, Integrations, Webhooks, New Webhook, Copy URL.
Put it in `DISCORD_WEBHOOK_URL`.

## Testing the building blocks

Each step is a plain Python function and can be tested before wiring it into Airflow:

```bash
source ~/.venvs/info-h420/bin/activate
cd /path/to/INFO-H420_Assignment3

python -c "
import os, json
from src.pdf_convert import convert_pdf
from src.llm_metadata import extract_metadata
from src.db import save_paper, get_all_papers

name = 'your-paper.pdf'
md = convert_pdf(os.path.join(os.environ['PAPERS_DIR'], name))
meta = extract_metadata(md)
print(json.dumps(meta, indent=2))
save_paper(name, meta)
print(get_all_papers())
"
```

## Running the pipeline

(To be completed once the DAG is finished.)

```bash
source ~/.venvs/info-h420/bin/activate
airflow standalone
```

Open http://localhost:8080, log in with the credentials printed in the terminal,
un-pause `paper_pipeline`, and trigger it.

## Team workflow

- One branch per feature (`feature/...`), merged into `main` through pull requests.
- Never commit `.env`, the database, or the Discord webhook URL.
- Agreed function interfaces:
  - `convert_pdf(path) -> str`
  - `extract_metadata(markdown) -> dict`
  - `init_db()`, `is_processed(filename) -> bool`, `save_paper(filename, meta)`, `get_all_papers() -> list[dict]`
  - `generate_html(papers, output_path)`
  - `send_discord(message)`

## Deadline

Report (PDF) due on UV: 9 November 2026.
