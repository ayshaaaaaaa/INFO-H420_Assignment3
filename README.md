# INFO-H420 Assignment 3: Pipeline

## 1. What does this project do?

You drop research PDFs into a folder. The pipeline then, by itself:

1. finds the new PDFs,
2. turns each one into text (Markdown),
3. asks an AI model running on your own laptop to write a title, summary, keywords and category,
4. saves that information in a small database,
5. builds a web page where you can search and filter your papers,
6. sends a message to Discord saying "a new paper was processed".

Everything is run on a schedule by **Apache Airflow**, a tool that runs tasks in a set order.

## 2. How it works (the pipeline)

```
  PDF files in the Google Drive "papers" folder
                    |
                    v
  [1] Find new PDFs        (skip the ones already in the database)
                    |
                    v
  [2] PDF -> Markdown      (PyMuPDF4LLM)
                    |
                    v
  [3] Ask the local AI     (Ollama + Llama 3.2) -> JSON with title, summary, keywords, category
                    |       check the JSON, retry once if it is broken
                    v
  [4] Save to database     (SQLite file on your own computer)
                    |
                    v
  [5] Build the web page   (index.html in the Google Drive "output" folder)
                    |
                    v
  [6] Send a Discord message
```

## 3. What does each file do? (the simple version)

| File | What it does, in plain words |
|---|---|
| `dags/paper_pipeline.py` | The **boss**. It tells Airflow which steps to run, in which order, and how often. It calls the functions below. |
| `src/pdf_convert.py` | **Reader.** Takes a PDF and returns its text as Markdown. One function: `convert_pdf(path)`. |
| `src/llm_metadata.py` | **Librarian.** Sends the text to the local AI and asks for a title, summary, keywords and category as JSON. Checks the answer and retries once if it is broken. One function: `extract_metadata(markdown)`. |
| `src/db.py` | **Memory.** Creates the database table and has helpers: `is_processed(filename)` ("did we already do this PDF?"), `save_paper(...)`, `get_all_papers()`. |
| `src/html_gen.py` | **Web page maker.** Takes all papers from the database and writes `index.html` with a search box and a category dropdown. One function: `generate_html(papers)`. |
| `src/notify.py` | **Messenger.** Sends a text message to Discord through a webhook. One function: `send_discord(message)`. |
| `src/__init__.py` | Empty file. It just lets Python treat `src/` as a package so the imports work. |
| `requirements.txt` | The list of Python libraries the project needs (Airflow is installed separately, see Step 3). |
| `.env.example` | A template that shows which settings exist. Copy the idea, never commit real secrets. |
| `.gitignore` | Tells Git which files **not** to upload (secrets, the database, caches). |
| `data/` | Local data folder. The database file is gitignored. |
| `README.md` | This guide. |

Think of it like a small office: the **boss** (DAG) tells the **reader**, the **librarian**, the **memory**, the **web page maker** and the **messenger** what to do, one after another.

## 4. What is separate on each person's computer?

| Thing | Shared or separate? |
|---|---|
| Code | **Shared** through GitHub |
| SQLite database (`papers.db`) | **Separate**, a local file on each laptop (never committed) |
| Ollama + Llama model | **Separate**, each person installs their own |
| Airflow | **Separate**, each person runs their own |
| Python virtual environment | **Separate** |
| Google Drive folders | **Separate** (each person's own Drive, unless you share one folder) |
| Discord webhook | **Your choice**: one shared URL or one each. It lives in each person's own environment variable and is never committed. |

Tip: only **one** person should keep the DAG scheduled for the final demo, otherwise you will get duplicate Discord messages and processing.

## 5. Setup from scratch

### Step 0: What you need

- **Windows:** WSL2 with Ubuntu (Airflow does not run directly on Windows). In PowerShell: `wsl --install -d Ubuntu`. Mac and Linux users can skip WSL.
- At least 8 GB RAM (16 GB+ is better).
- Google Drive for desktop, set to **"Mirror files"** (not "Stream files") so WSL can read the files.
- A GitHub account that was invited to this repo.

Run every command below in the **Ubuntu (WSL) terminal**, not in PowerShell.

### Step 1: Get the code

```bash
cd ~
git clone https://github.com/ayshaaaaaaa/INFO-H420_Assignment3.git
cd INFO-H420_Assignment3
```

(You can clone it somewhere else, such as `/mnt/d/...`. Just remember the path for Step 7. If the path has spaces, keep it in quotes.)

### Step 2: Install basic tools and Python 3.12

We use Python 3.12 because the newest system Python is often not supported by Airflow yet. The tool `uv` downloads it for us.

```bash
sudo apt update && sudo apt install -y python3-pip sqlite3 zstd curl

curl -LsSf https://astral.sh/uv/install.sh | sh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

mkdir -p ~/.venvs
uv venv ~/.venvs/info-h420 --python 3.12
source ~/.venvs/info-h420/bin/activate
python --version        # must say 3.12.x
```

You should now see `(info-h420)` at the start of your prompt. **Every time you open a new terminal, run this first:**

```bash
source ~/.venvs/info-h420/bin/activate
```

### Step 3: Install Airflow and the libraries

```bash
AIRFLOW_VERSION=3.0.6
CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-3.12.txt"

uv pip install "apache-airflow==${AIRFLOW_VERSION}" --constraint "${CONSTRAINT_URL}"
uv pip install pymupdf4llm openai requests
```

Check it:

```bash
airflow version                                             # prints 3.0.6
python -c "import pymupdf4llm, openai, requests; print('libs ok')"
```

(A message saying "RapidOCR is missing" later on is harmless. It only matters for scanned PDFs.)

### Step 4: Install Ollama and the AI model

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:3b
ollama list             # llama3.2:3b should be listed
```

If a later step says it cannot connect to Ollama, start the server in a **second terminal**:

```bash
ollama serve
```

Quick test that the AI answers with JSON:

```bash
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"llama3.2:3b","response_format":{"type":"json_object"},
       "messages":[{"role":"user","content":"Return JSON with keys title and summary about cats."}]}'
```

`llama3.2:3b` needs only about 4 GB of RAM, so it runs on any laptop. With 16 GB+ RAM you may try `llama3.1:8b` (change `LLM_MODEL` in Step 7).

### Step 5: Google Drive folders

1. In Google Drive create `ResearchLibrary/papers/` and `ResearchLibrary/output/`.
2. Put 2-3 PDFs into `papers/`.
3. Find the folder from WSL. Your Drive usually shows up under `/mnt/<letter>/`:

```bash
ls /mnt
ls "/mnt/g/My Drive/ResearchLibrary/papers"        # adjust the letter and path
```

If `/mnt/g` is empty, mount it (use the drive letter Windows shows):

```bash
sudo mkdir -p /mnt/g && sudo mount -t drvfs G: /mnt/g
```

Write down the full paths of `papers/` and `output/`. You need them in Step 7.

### Step 6: Discord webhook

1. Create a Discord server (or use one you have).
2. Open a channel: **Edit Channel, Integrations, Webhooks, New Webhook, Copy Webhook URL**.
3. Keep the URL secret. Never put it in Git.

### Step 7: Environment variables (the settings)

Open `~/.bashrc` with `nano ~/.bashrc` and add this block at the bottom. **Change the three values marked `<<<`.**

```bash
# --- INFO-H420 Assignment 3 ---
export AIRFLOW_HOME=~/airflow_home
export PROJECT_DIR="$HOME/INFO-H420_Assignment3"                      # <<< path of the cloned repo
export AIRFLOW__CORE__DAGS_FOLDER="$PROJECT_DIR/dags"
export AIRFLOW__CORE__LOAD_EXAMPLES=False
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

export DB_PATH=~/airflow_data/papers.db
export LLM_BASE_URL=http://localhost:11434/v1
export LLM_MODEL=llama3.2:3b

export PAPERS_DIR="/mnt/g/My Drive/ResearchLibrary/papers"            # <<< your papers folder
export OUTPUT_DIR="/mnt/g/My Drive/ResearchLibrary/output"            # <<< your output folder
export DISCORD_WEBHOOK_URL="paste-your-webhook-url-here"              # <<< your webhook
```

Save (`Ctrl+O`, Enter, `Ctrl+X`), then:

```bash
mkdir -p ~/airflow_data
source ~/.bashrc
source ~/.venvs/info-h420/bin/activate
```

What each setting means:

| Setting | Meaning |
|---|---|
| `AIRFLOW_HOME` | Where Airflow keeps its own files (keep it inside WSL, not on a Windows drive) |
| `PROJECT_DIR` | Where this repo is on your computer |
| `AIRFLOW__CORE__DAGS_FOLDER` | Tells Airflow where to find `paper_pipeline.py` |
| `PYTHONPATH` | Lets the DAG do `from src.db import ...` |
| `DB_PATH` | Where the SQLite database file is saved |
| `LLM_BASE_URL` / `LLM_MODEL` | Address and name of the local AI model |
| `PAPERS_DIR` / `OUTPUT_DIR` | Your Google Drive input and output folders |
| `DISCORD_WEBHOOK_URL` | Where Discord messages are sent |

### Step 8: Check that every piece works

Run these from the repo folder with the virtual environment active. Each one has a "you should see" line.

```bash
cd "$PROJECT_DIR"
ls "$PAPERS_DIR"                    # you should see your PDFs
```

**PDF to AI to database (the core):**

```bash
python -c "
import os, glob, json
from src.pdf_convert import convert_pdf
from src.llm_metadata import extract_metadata
from src.db import save_paper, get_all_papers

pdf = sorted(glob.glob(os.path.join(os.environ['PAPERS_DIR'], '*.pdf')))[0]
name = os.path.basename(pdf)
meta = extract_metadata(convert_pdf(pdf))
print(json.dumps(meta, indent=2))
save_paper(name, meta)
print(get_all_papers())
"
```
You should see a JSON object (title, summary, keywords, category) and then one saved row. The first run is slow because the model has to load. Be patient.

**Web page:**

```bash
python -c "
from src.db import get_all_papers
from src.html_gen import generate_html
print(generate_html(get_all_papers()))
"
```
You should see a path ending in `index.html`. Open that file in your browser: you should see your paper card, and the search box and category dropdown should filter it.

**Discord:**

```bash
python -c "
from src.notify import send_discord
send_discord('Test message from the pipeline')
"
```
The message should appear in your Discord channel.

## 6. Running the pipeline with Airflow

(The DAG file is the last piece we are building. This section will be finalised when it is done.)

```bash
source ~/.venvs/info-h420/bin/activate
airflow standalone
```

1. Wait until it prints a username and password (also saved in `~/airflow_home/simple_auth_manager_passwords.json.generated`).
2. Open http://localhost:8080 in your browser and log in.
3. Find `paper_pipeline`, switch it on (un-pause) and click the play button to run it.
4. Click the run to see the graph, task states and logs.

Useful checks:

```bash
airflow dags list                        # is the DAG visible?
airflow dags list-import-errors          # why is it not visible?
airflow dags test paper_pipeline         # run once in the terminal and show errors
```

## 7. Looking at the database

The database is a single file: `~/airflow_data/papers.db`.

```bash
sqlite3 -header -column ~/airflow_data/papers.db "SELECT filename, title, category FROM papers;"
sqlite3 -line ~/airflow_data/papers.db "SELECT * FROM papers;"
sqlite3 ~/airflow_data/papers.db "SELECT COUNT(*) FROM papers;"
```

Delete everything (so the pipeline will process the PDFs again):

```bash
sqlite3 ~/airflow_data/papers.db "DELETE FROM papers;"
```

SQLite is a normal **SQL (relational)** database. It is just stored in one file and needs no server.

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| `ImportError: cannot import name 'convert_pdf'` or `ModuleNotFoundError` | The file in `src/` is empty or outdated. Run `git pull`, then check `wc -c src/*.py` (size 0 means empty). Also make sure you are in the repo folder and `PYTHONPATH` is set. |
| `python: command not found` | The virtual environment is not active. Run `source ~/.venvs/info-h420/bin/activate`. |
| `model 'llama3.2:3b' not found` | Run `ollama pull llama3.2:3b`. |
| Cannot connect to `localhost:11434` | Start Ollama with `ollama serve` in a second terminal. |
| LLM call times out | Normal on the first run (model loading). Run it again. |
| `ls "$PAPERS_DIR"` shows nothing or "No such file" | Check the path and the drive letter with `ls /mnt`. Mount the drive (Step 5). Set Drive to "Mirror files". |
| `DISCORD_WEBHOOK_URL is not set` | Add it in `~/.bashrc` (Step 7) and run `source ~/.bashrc`. |
| Airflow page does not open | Another program may use port 8080. Stop it, or open http://localhost:8080 again after Airflow finishes starting. |
| DAG does not show up in Airflow | Run `airflow dags list-import-errors` and read the message. |
| Airflow install fails with "constraints 404" | Look up the latest 3.x version on pypi.org/project/apache-airflow and change `AIRFLOW_VERSION`. |

## 9. Team rules

- Pull before you start working and before you push: `git pull origin main`.
- Never commit `.env`, the database, or the Discord webhook URL. Check `git status` before every commit.
- Keep the function names as they are, so the pieces fit together:
  - `convert_pdf(path) -> str`
  - `extract_metadata(markdown) -> dict`
  - `init_db()`, `is_processed(filename) -> bool`, `save_paper(filename, meta)`, `get_all_papers() -> list[dict]`
  - `generate_html(papers, output_path=None)`
  - `send_discord(message)`
- Everyone uses the same model name (`llama3.2:3b`) while testing, so results look similar.

## 10. Project status

| Part | File | Status |
|---|---|---|
| Repo, setup guide | `README.md` | Done |
| PDF to Markdown | `src/pdf_convert.py` | Done, tested |
| SQLite storage | `src/db.py` | Done, tested |
| AI metadata (JSON, retry, checks) | `src/llm_metadata.py` | Done, tested |
| HTML page with search and filter | `src/html_gen.py` | Written, needs testing |
| Discord notification | `src/notify.py` | Written, needs testing |
| Airflow DAG | `dags/paper_pipeline.py` | To do |
| Report with screenshots (PDF) | - | To do |

## 11. Deadline

The report (PDF, with a link to this repo) must be uploaded to "Assignment 3" on UV by **9 November 2026**.
