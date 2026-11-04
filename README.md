# INFO-H420 Assignment 3: Research Paper Pipeline

An automatic "paper library" built with **Apache Airflow** and a **local AI model**.
Drop a research PDF into a folder and the pipeline reads it, writes a summary, files it in a
database, updates a searchable web page, and sends you a Discord message.

This guide is written so that anyone in the class can follow it from a blank computer.
If a word is new to you, see the [glossary](#10-glossary-all-the-words-in-simple-english).

---

## Table of contents

1. [What does this project do?](#1-what-does-this-project-do)
2. [How it works (the pipeline)](#2-how-it-works-the-pipeline)
3. [What each file does](#3-what-each-file-does)
4. [What is shared and what is separate](#4-what-is-shared-and-what-is-separate)
5. [Setup from scratch](#5-setup-from-scratch)
6. [Check that every piece works](#6-check-that-every-piece-works)
7. [Run the pipeline with Airflow](#7-run-the-pipeline-with-airflow)
8. [Look inside the database](#8-look-inside-the-database)
9. [Troubleshooting](#9-troubleshooting)
10. [Glossary](#10-glossary-all-the-words-in-simple-english)
11. [Team rules](#11-team-rules)
12. [Project status](#12-project-status)

---

## 1. What does this project do?

You put research PDFs into a folder. The pipeline then, by itself:

1. finds the new PDFs,
2. turns each one into plain text (Markdown),
3. asks an AI model running **on your own laptop** for a title, summary, keywords and category,
4. saves that information in a small database,
5. builds a web page where you can search and filter your papers,
6. sends a message to Discord: "a new paper was processed".

Airflow runs all of this on a schedule (every 10 minutes), so nobody has to click anything.

## 2. How it works (the pipeline)

```
  PDF files in the Google Drive "papers" folder
                    |
                    v
  [1] find_new_pdfs     Which PDFs are not in the database yet?
                    |
                    v     (one copy of this step per new PDF)
  [2] process_paper     PDF -> text (Markdown)
                    |   text -> local AI -> JSON (title, summary, keywords, category)
                    |   check the JSON, retry once if it is broken
                    |   save to the SQLite database
                    v
  [3] build_html        Rewrite index.html from the whole database
                    |   (saved in the Google Drive "output" folder)
                    v
  [4] notify            Send a Discord message
```

If there are **no new PDFs**, steps 2 to 4 have nothing to do and are skipped automatically.

A kitchen picture that may help:

| Kitchen | This project |
|---|---|
| Head chef who decides who does what and when | Airflow (the DAG) |
| Ingredients delivered | PDFs in the Drive folder |
| Prep cook who chops | `pdf_convert.py` |
| Assistant who tastes and describes the dish | The local AI (Llama 3.2 via Ollama) |
| Recipe notebook | SQLite database |
| Menu board for customers | `index.html` |
| Waiter who rings a bell | Discord webhook |

## 3. What each file does

| File | What it does, in plain words |
|---|---|
| `dags/paper_pipeline.py` | The **boss**. Defines the steps, their order and the schedule. Calls the functions below. |
| `src/pdf_convert.py` | **Reader.** `convert_pdf(path)` turns a PDF into Markdown text. |
| `src/llm_metadata.py` | **Librarian.** `extract_metadata(markdown)` asks the AI for a title, summary, keywords and category as JSON, checks the answer and retries once if it is broken. |
| `src/db.py` | **Memory.** Creates the database table. `is_processed(filename)` asks "did we already do this PDF?", `save_paper(...)` stores a paper, `get_all_papers()` reads them all. |
| `src/html_gen.py` | **Web page maker.** `generate_html(papers)` writes `index.html` with a search box and a category filter. |
| `src/notify.py` | **Messenger.** `send_discord(message)` posts a message to Discord. |
| `src/__init__.py` | Empty on purpose. It lets Python import from the `src` folder. |
| `requirements.txt` | The Python libraries the project needs (Airflow is installed separately, see Step 3). |
| `.env.example` | A template listing the settings the project uses. Never put real secrets in the repo. |
| `.gitignore` | Tells Git which files **not** to upload (secrets, database, caches). |
| `data/` | Local data folder. The database file itself is not uploaded. |
| `README.md` | This guide. |

Folders outside the repo:

```
Google Drive/ResearchLibrary/
├── papers/    <- you put PDFs here
└── output/    <- index.html is written here

~/airflow_data/papers.db   <- the SQLite database (stays on your own computer)
```

## 4. What is shared and what is separate

| Thing | Shared or separate? |
|---|---|
| Code | **Shared** through GitHub |
| SQLite database (`papers.db`) | **Separate**, a local file on each computer (never uploaded) |
| Ollama and the AI model | **Separate**, everyone installs their own |
| Airflow | **Separate**, everyone runs their own |
| Python virtual environment | **Separate** |
| Google Drive folders | **Separate** (each person's own Drive, unless you share one folder) |
| Discord webhook | **Your choice**: one shared URL or one each. It is stored in each person's own settings, never in Git. |

Tip: for the final demo, only **one** person should keep the DAG switched on. Otherwise you get duplicate Discord messages and several computers writing the same `index.html`.

## 5. Setup from scratch

Run every command in the **Ubuntu (WSL) terminal**, not in PowerShell. Mac and Linux users can use their normal terminal.

### Step 0: What you need

- **Windows:** WSL2 with Ubuntu (Airflow does not run directly on Windows). In PowerShell: `wsl --install -d Ubuntu`.
- At least 8 GB of RAM (16 GB or more is better).
- **Google Drive for desktop**, set to **"Mirror files"** (not "Stream files"), so WSL can read the files.
- A GitHub account that has been invited to the repo.

### Step 1: Get the code

```bash
cd ~
git clone https://github.com/ayshaaaaaaa/INFO-H420_Assignment3.git
cd INFO-H420_Assignment3
```

You may clone it somewhere else (for example under `/mnt/d/...`). Remember the path for Step 7, and keep paths with spaces in quotes.

### Step 2: Install basic tools and Python 3.12

We use Python 3.12 because the newest Python that comes with Ubuntu is often not supported by Airflow yet. The tool `uv` downloads 3.12 for us.

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

You should see `(info-h420)` at the start of your prompt. **Every time you open a new terminal, run this first:**

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
airflow version                                              # prints 3.0.6
python -c "import pymupdf4llm, openai, requests; print('libs ok')"
```

(Messages about `graphviz`, `flask_appbuilder` or "RapidOCR is missing" are harmless.)

### Step 4: Install Ollama and the AI model

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:3b
ollama list             # llama3.2:3b should be listed
```

If a later step cannot connect to Ollama, start it in a **second terminal** and leave it open:

```bash
ollama serve
```

Test that the AI answers with JSON:

```bash
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"llama3.2:3b","response_format":{"type":"json_object"},
       "messages":[{"role":"user","content":"Return JSON with keys title and summary about cats."}]}'
```

`llama3.2:3b` needs about 4 GB of RAM, so it runs on almost any laptop. With 16 GB or more you may try `llama3.1:8b` (change `LLM_MODEL` in Step 7).

### Step 5: Google Drive folders

1. In Google Drive create `ResearchLibrary/papers/` and `ResearchLibrary/output/`. (Create them from Windows or the Drive website, not from WSL.)
2. Put 2 or 3 PDFs into `papers/`. At least one should be a real research paper.
3. Find the folder from WSL. Drive usually appears under `/mnt/<drive letter>/`:

```bash
ls /mnt
ls "/mnt/g/My Drive/ResearchLibrary/papers"        # adjust letter and path
```

If `/mnt/g` is empty, mount it (use the letter Windows shows in File Explorer):

```bash
sudo mkdir -p /mnt/g
sudo mount -t drvfs G: /mnt/g
```

The mount can disappear after a restart. Optional automatic mount:

```bash
echo 'G: /mnt/g drvfs defaults 0 0' | sudo tee -a /etc/fstab
```

Write down the full paths of `papers/` and `output/`. You need them in Step 7.

### Step 6: Discord webhook

1. Create a Discord server (or use one you have).
2. Open a channel: **Edit Channel, Integrations, Webhooks, New Webhook, Copy Webhook URL**.
3. Keep the URL secret. Never put it in Git. If it leaks, delete the webhook in Discord and make a new one.

### Step 7: Environment variables (your settings)

Open `~/.bashrc` with `nano ~/.bashrc` and add this block at the bottom. **Change the values marked `<<<`.**

```bash
# --- INFO-H420 Assignment 3 ---
export AIRFLOW_HOME=~/airflow_home
export PROJECT_DIR="$HOME/INFO-H420_Assignment3"                      # <<< where you cloned the repo
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
| `AIRFLOW__CORE__LOAD_EXAMPLES` | `False` hides Airflow's many example DAGs |
| `PYTHONPATH` | Lets the DAG do `from src.db import ...` |
| `DB_PATH` | Where the SQLite database file is saved |
| `LLM_BASE_URL`, `LLM_MODEL` | Address and name of the local AI model |
| `PAPERS_DIR`, `OUTPUT_DIR` | Your Google Drive input and output folders |
| `DISCORD_WEBHOOK_URL` | Where Discord messages are sent |

### Step 8: Make sure no file is empty

Some files are created empty at the start. If a file is empty, Python cannot import from it. Check:

```bash
cd "$PROJECT_DIR"
wc -c src/*.py dags/*.py
```

Every file must have a size above 0, except `src/__init__.py`, which is empty on purpose. If a file shows `0`, run `git pull origin main` to get the latest version.

## 6. Check that every piece works

Run these from the repo folder with the virtual environment active. Test one piece at a time, so you know which piece breaks.

```bash
cd "$PROJECT_DIR"
ls "$PAPERS_DIR"          # you should see your PDFs
```

**A. PDF, then AI, then database (the core):**

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

**B. Web page:**

```bash
python -c "
from src.db import get_all_papers
from src.html_gen import generate_html
print(generate_html(get_all_papers()))
"
```
You should see a path ending in `index.html`. Open the file in your browser. You should see a card for each paper, and the search box and category dropdown should filter them.

**C. Discord:**

```bash
python -c "
from src.notify import send_discord
send_discord('Test message from the pipeline')
"
```
The message should appear in your Discord channel.

## 7. Run the pipeline with Airflow

### First, a quick check that Airflow can read the DAG

```bash
airflow dags reserialize
airflow dags list                  # paper_pipeline should be listed
airflow dags list-import-errors    # "No data found" means no errors
```

### Run it once in the terminal (best for testing)

Before you start, make sure:
- Ollama is running (`ollama serve` in another terminal),
- `ls "$PAPERS_DIR"` shows your PDFs,
- you want the PDFs to count as new. Empty the table first:

```bash
sqlite3 ~/airflow_data/papers.db "DELETE FROM papers;"
airflow dags test paper_pipeline
```

This runs every task once and prints the logs. With a few PDFs it can take several minutes on a laptop CPU, and it can look quiet while the AI is thinking. You should see:

- `Found N PDFs, N new: [...]`
- `Saved <file>: <title> [<category>]` once per PDF
- `Wrote .../index.html`
- every task ending in `success`, one Discord message, and an updated `index.html`

### Run it in the Airflow web page (best for screenshots)

Start Airflow from a terminal where your settings are loaded, because the tasks inherit them:

```bash
source ~/.bashrc
source ~/.venvs/info-h420/bin/activate
airflow standalone
```

1. Wait until it prints a username and password (the password is also saved in `~/airflow_home/simple_auth_manager_passwords.json.generated`).
2. Open http://localhost:8080 and log in.
3. Find `paper_pipeline`, switch it on (un-pause), and click the play button (Trigger).
4. Open the run to see the graph, the task states and the logs.

**A good demo for the report:**

1. Trigger once: all tasks turn green.
2. Trigger again with no new PDFs: the later tasks show as **skipped**. This proves only new papers are processed.
3. Add one new PDF to `papers/` and trigger again: only that paper is processed, and a new Discord message arrives.

## 8. Look inside the database

The database is one file: `~/airflow_data/papers.db`.

```bash
sqlite3 -header -column ~/airflow_data/papers.db "SELECT filename, title, category FROM papers;"
sqlite3 -line ~/airflow_data/papers.db "SELECT * FROM papers;"
sqlite3 ~/airflow_data/papers.db "SELECT COUNT(*) FROM papers;"
```

Delete everything (so the pipeline processes the PDFs again):

```bash
sqlite3 ~/airflow_data/papers.db "DELETE FROM papers;"
```

Table `papers` (one row per PDF):

| Column | Meaning |
|---|---|
| `filename` | The PDF's file name. Must be unique, which is how repeats are avoided. |
| `title` | Title written by the AI |
| `summary` | 2 or 3 sentence summary |
| `keywords` | A list stored as text, like `["a", "b"]` |
| `category` | One category from a fixed list (otherwise `Other`) |

## 9. Troubleshooting

| Problem | What it means and how to fix it |
|---|---|
| `ImportError: cannot import name 'convert_pdf'` (or `generate_html`, `send_discord`) | The file in `src/` is empty. Run `wc -c src/*.py`. A size of 0 means no code. Run `git pull origin main`. |
| `ModuleNotFoundError: No module named 'src'` | You are not in the repo folder, or `PYTHONPATH` is not set. Run `cd "$PROJECT_DIR"` and `source ~/.bashrc`. |
| `python: command not found` | The virtual environment is not active. Run `source ~/.venvs/info-h420/bin/activate`. |
| `model 'llama3.2:3b' not found` | The model was not downloaded. Run `ollama pull llama3.2:3b`. |
| Cannot connect to `localhost:11434` | Ollama is not running. Run `ollama serve` in a second terminal. |
| The AI call takes very long or times out | Normal on the first run (the model is loading). Run it again. |
| `PermissionError: ... '/mnt/g/My Drive'` | The Google Drive is not mounted in WSL. Make sure Drive is running in Windows, then `sudo mount -t drvfs G: /mnt/g`. |
| `ls "$PAPERS_DIR"` shows nothing or "No such file" | Check the path and the drive letter (`ls /mnt`). Mount the drive. Set Drive to "Mirror files". |
| `DISCORD_WEBHOOK_URL is not set` | Add it to `~/.bashrc` (Step 7), then `source ~/.bashrc`. |
| `airflow dags list` says "No data found" | The DAG has not been parsed yet. Run `airflow dags reserialize`, then list again. |
| Airflow asks "Please confirm database initialize" | Normal the first time. Answer `y`. |
| DAG is listed but not running | New DAGs start **paused**. Switch it on in the web page. |
| Airflow page does not open | Another program may be using port 8080 (for example another Airflow, or another database tool). Stop it and restart Airflow. |
| Airflow install fails with a constraints 404 | Look up the latest 3.x version on pypi.org/project/apache-airflow and change `AIRFLOW_VERSION`. |
| Tasks fail only inside Airflow but work in the terminal | Airflow was started from a terminal without your settings. Close it, run `source ~/.bashrc`, and start it again. |

## 10. Glossary (all the words in simple English)

**Airflow**

| Word | Easy meaning |
|---|---|
| **Apache Airflow** | A tool that runs a list of jobs in the right order, on a timer, and shows what worked or failed. |
| **Pipeline / workflow** | A chain of steps where the output of one step feeds the next. |
| **DAG** | "Directed Acyclic Graph". The recipe card of the whole pipeline: which steps exist and which comes after which. Directed means the arrows have a direction, acyclic means no loops. Ours is `dags/paper_pipeline.py`. |
| **Task** | One step inside a DAG (for example `find_new_pdfs`). It is just a Python function with `@task` above it. |
| **Task dependency** | The arrows between tasks, such as "do not build the page until all papers are saved". |
| **Schedule** | How often the DAG runs. Ours is every 10 minutes (`*/10 * * * *`, written in "cron" style). |
| **DAG run** | One execution of the whole pipeline. |
| **Dynamic task mapping (`.expand()`)** | Airflow makes one copy of a task per item. With 3 new PDFs you get 3 `process_paper` tasks. |
| **XCom** | How tasks pass small values (like a list of file names) to each other. |
| **Skipped** | A task that was left out on purpose because there was nothing to do. |
| **`airflow standalone`** | One command that starts everything Airflow needs on your laptop, with a built-in login. |
| **`catchup=False`** | "Do not run all the missed past runs, only run from now." |
| **`max_active_runs=1`** | "Never run two pipelines at the same time", because the AI is slow. |
| **Pause / un-pause** | A new DAG is off by default. Un-pausing switches on its schedule. |
| **`airflow dags test`** | Runs the whole DAG once in the terminal so you can see errors directly. |

**AI**

| Word | Easy meaning |
|---|---|
| **LLM** | Large Language Model: an AI that reads and writes text, like ChatGPT. |
| **Llama 3.2 3B** | The small model we use. "3B" means 3 billion parameters (its size). |
| **Ollama** | A program that downloads and runs AI models on your own computer. |
| **Local** | Runs on your machine. No cloud, no paid service. |
| **Prompt** | The instructions we send to the AI. |
| **JSON** | A text format for structured data, like `{"title": "...", "keywords": ["a", "b"]}`. |
| **JSON mode** | A setting that makes the AI answer in valid JSON. |
| **Parsing (`json.loads`)** | Turning the AI's JSON text into a Python dictionary. |
| **Validation** | Checking that the required fields exist and have the right types. |
| **Retry** | If the answer is broken, ask once more. |
| **API / OpenAI-compatible** | A standard way for programs to talk to the AI. Ollama copies OpenAI's format, so the `openai` library works with it. |
| **Truncating** | Cutting the text to its first ~8000 characters, because the AI can only read so much at once and the title and abstract come first. |
| **Temperature 0** | "Be consistent, do not be creative." |

**Data and files**

| Word | Easy meaning |
|---|---|
| **Markdown** | Plain text with simple formatting marks. Much easier for a program to read than a PDF. |
| **PyMuPDF4LLM** | The Python library that converts PDF to Markdown. |
| **SQLite** | A database stored in **one file** that needs no server. Built into Python. |
| **SQL / relational** | A database made of tables with rows and columns, queried with the SQL language. SQLite is a SQL database. |
| **Static HTML page** | A web page that is just a file. The paper data is written into it, and a little JavaScript does the searching in your browser. |
| **Webhook** | A secret URL that lets a program post a message to a Discord channel. |
| **Google Drive sync** | Keeps your Drive folders mirrored on your computer. |

**Setup and tools**

| Word | Easy meaning |
|---|---|
| **WSL / WSL2** | Windows Subsystem for Linux: a real Ubuntu running inside Windows. Airflow needs Linux. |
| **Terminal** | The text window where you type commands. |
| **Virtual environment (venv)** | A private box of Python libraries just for this project. You see `(info-h420)` when it is active. |
| **`uv`** | A fast tool that creates the venv and installs packages. It also fetched Python 3.12. |
| **Environment variable** | A setting stored outside the code (like `PAPERS_DIR`), so secrets and personal paths stay out of GitHub. |
| **`~/.bashrc`** | A file that sets your variables every time you open a terminal. |
| **Mounting a drive** | Making a Windows drive (like G:) visible inside WSL at `/mnt/g`. |
| **Placeholder file** | An empty file made with `touch`. Importing from one gives "cannot import name" errors. |

**Git and teamwork**

| Word | Easy meaning |
|---|---|
| **Git** | A tool that tracks every change to your code. |
| **GitHub / repo** | The website that stores the shared project (the "repository"). |
| **Clone** | Download a copy of the repo. |
| **Commit** | Save a snapshot of your changes with a message. |
| **Push / pull** | Push uploads your commits, pull downloads your teammates' commits. |
| **`.gitignore`** | A list of files Git must never upload. |
| **README** | The instruction page of the project (this file). |
| **`requirements.txt`** | The list of Python libraries the project needs. |

## 11. Team rules

- Run `git pull origin main` before you start working and before you push.
- Never commit `.env`, the database, or the Discord webhook URL. Check `git status` before every commit.
- Make small commits with clear messages, for example `Add Discord webhook notifier`.
- Keep the function names as they are, so the pieces fit together:
  - `convert_pdf(path) -> str`
  - `extract_metadata(markdown) -> dict`
  - `init_db()`, `is_processed(filename) -> bool`, `save_paper(filename, meta)`, `get_all_papers() -> list[dict]`
  - `generate_html(papers, output_path=None)`
  - `send_discord(message)`
- Everyone uses the same model name (`llama3.2:3b`) while testing, so results look similar.

## 12. Project status

| Part | File | Status |
|---|---|---|
| Repo and README | `README.md` | Done |
| PDF to Markdown | `src/pdf_convert.py` | Done, tested |
| SQLite storage | `src/db.py` | Done, tested |
| AI metadata (JSON, retry, checks) | `src/llm_metadata.py` | Done, tested |
| HTML page with search and filter | `src/html_gen.py` | Done, tested |
| Discord notification | `src/notify.py` | Written, confirm test message |
| Airflow DAG | `dags/paper_pipeline.py` | Written, parsed by Airflow, full run still to do |
| Screenshots (graph view, run, page, database, Discord) | - | To do |
| Short report (PDF) with repo link | - | To do |

## Deadline

The report (PDF, with a link to this repo) must be uploaded to "Assignment 3" on UV by **9 November 2026**.