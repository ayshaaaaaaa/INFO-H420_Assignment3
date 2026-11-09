# INFO-H420 Assignment 3: Research Paper Pipeline

An automatic "paper library" built with **Apache Airflow** and a **local AI model**.
Drop a research PDF into a folder and the pipeline reads it, writes a summary, files it in a
database, updates a searchable web page, and sends you a Discord message.

This guide is written so that anyone in the class can follow it from a blank computer.
It describes **two ways to run the same project**:

- **Option A: native setup** on Windows (WSL2 / Ubuntu), Linux or Mac, with `airflow standalone`.
- **Option B: Docker setup** (Docker Compose), tested on macOS.

If a word is new to you, see the [glossary](#12-glossary-all-the-words-in-simple-english).

---

## Table of contents

1. [What does this project do?](#1-what-does-this-project-do)
2. [How it works (the pipeline)](#2-how-it-works-the-pipeline)
3. [What each file does](#3-what-each-file-does)
4. [Which option should I use?](#4-which-option-should-i-use)
5. [What is shared and what is separate](#5-what-is-shared-and-what-is-separate)
6. [Option A: native setup (WSL2 / Linux / Mac)](#6-option-a-native-setup-wsl2--linux--mac)
7. [Option A: check that every piece works](#7-option-a-check-that-every-piece-works)
8. [Option A: daily runbook (start, run, verify, stop)](#8-option-a-daily-runbook-start-run-verify-stop)
9. [Option B: Docker setup and daily runbook](#9-option-b-docker-setup-and-daily-runbook)
10. [Look inside the database](#10-look-inside-the-database)
11. [Troubleshooting](#11-troubleshooting)
12. [Glossary](#12-glossary-all-the-words-in-simple-english)
13. [Team rules](#13-team-rules)
14. [Project status](#14-project-status)

---

## 1. What does this project do?

You put research PDFs into a folder. The pipeline then, by itself:

1. finds the new PDFs,
2. turns each one into plain text (Markdown),
3. asks an AI model running **on your own computer** for a title, summary, keywords and category,
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

If there are **no new PDFs**, `find_new_pdfs` succeeds with an empty list, `process_paper` has zero
copies, and steps 3 and 4 are **skipped**. This is expected, not a broken pipeline.

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
| `dags/paper_pipeline.py` | The **boss**. Defines the steps, their order and the schedule (every 10 minutes). Includes input checks, logging, retries and a 15-minute timeout per paper. |
| `src/pdf_convert.py` | **Reader.** `convert_pdf(path)` turns a PDF into Markdown text. |
| `src/llm_metadata.py` | **Librarian.** `extract_metadata(markdown)` asks the AI for a title, summary, keywords and category as JSON, checks the answer and retries once if it is broken. |
| `src/db.py` | **Memory.** Creates the database table. `is_processed(filename)` asks "did we already do this PDF?", `save_paper(...)` stores a paper, `get_all_papers()` reads them all. |
| `src/html_gen.py` | **Web page maker.** `generate_html(papers)` writes `index.html` with a search box and category filter. |
| `src/notify.py` | **Messenger.** `send_discord(message)` posts a message to Discord. |
| `src/__init__.py` | Empty on purpose. It lets Python import from the `src` folder. |
| `Dockerfile`, `docker-compose.yml`, `.dockerignore` | The recipe to run Airflow inside Docker (Option B). |
| `.env.docker.example` | Template for the Docker settings (copy it to `.env.docker`). |
| `requirements.txt` | The Python libraries the project needs (Airflow is installed separately in Option A, see Step 3). |
| `.env.example` | Template listing the settings used by the native setup. Never put real secrets in the repo. |
| `.gitignore` | Tells Git which files **not** to upload (secrets, database, caches, `.env.docker`). |
| `data/` | Local data folder. The database file itself is not uploaded. |
| `README.md` | This guide. |

Folders outside the repo:

```
Google Drive/ResearchLibrary/
├── papers/    <- you put PDFs here
└── output/    <- index.html is written here

~/airflow_data/papers.db   <- the SQLite database in Option A (stays on your own computer)
```

## 4. Which option should I use?

| | Option A: native | Option B: Docker |
|---|---|---|
| Tested on | Windows with WSL2 (Ubuntu 26.04) | macOS |
| Airflow runs as | `airflow standalone` in a terminal | A Docker Compose service |
| Ollama runs | On the same computer | On the Mac (the container reaches it through `host.docker.internal`) |
| Database | `~/airflow_data/papers.db` | Inside persistent Docker storage, set up by `docker-compose.yml` |
| Start command | `airflow standalone` | `docker compose --env-file .env.docker up -d` |
| Best for | Windows users, screenshots of the Airflow UI | Mac users who prefer one command and no Python setup |

Pick **one** option per computer. Do not run both at the same time: both use port 8080 for the
Airflow web page.

## 5. What is shared and what is separate

| Thing | Shared or separate? |
|---|---|
| Code | **Shared** through GitHub |
| SQLite database | **Separate**, a local file on each computer (never uploaded) |
| Ollama and the AI model | **Separate**, everyone installs their own |
| Airflow | **Separate**, everyone runs their own |
| Python environment (Option A) or Docker image (Option B) | **Separate** |
| Google Drive folders | **Separate** (each person's own Drive, unless you share one folder) |
| Discord webhook | **Your choice**: one shared URL or one each. It is stored in each person's own settings, never in Git. |

Tip: for the final demo, only **one** person should keep the DAG switched on. Otherwise you get
duplicate Discord messages and several computers writing the same `index.html`.

---

## 6. Option A: native setup (WSL2 / Linux / Mac)

Run every command in the **Ubuntu (WSL) terminal**, not in PowerShell. Mac and Linux users can use
their normal terminal.

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

You may clone it somewhere else (for example under `/mnt/d/...`). Remember the path for Step 7,
and keep paths with spaces in quotes.

### Step 2: Install basic tools and Python 3.12

We use Python 3.12 because the newest Python that comes with Ubuntu is often not supported by
Airflow yet. The tool `uv` downloads 3.12 for us.

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

`llama3.2:3b` needs about 4 GB of RAM, so it runs on almost any laptop. With 16 GB or more you may
try `llama3.1:8b` (change `LLM_MODEL` in Step 7).

### Step 5: Google Drive folders

1. In Google Drive create `ResearchLibrary/papers/` and `ResearchLibrary/output/`. (Create them from Windows or the Drive website, not from WSL.)
2. Put 2 or 3 PDFs into `papers/`. At least one should be a real research paper. Only files ending in **`.pdf`** are processed (an `.html` or `.docx` file is ignored), and file names must be unique.
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
3. Keep the URL secret. Never put it in Git or paste it in chats. If it leaks, delete the webhook in Discord and make a new one.

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

Every file must have a size above 0, except `src/__init__.py`, which is empty on purpose. If a file
shows `0`, run `git pull origin main` to get the latest version.

## 7. Option A: check that every piece works

Run these from the repo folder with the virtual environment active. Test one piece at a time, so you
know which piece breaks.

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
You should see a JSON object (title, summary, keywords, category) and then one saved row. The first
run is slow because the model has to load. Be patient.

**B. Web page:**

```bash
python -c "
from src.db import get_all_papers
from src.html_gen import generate_html
print(generate_html(get_all_papers()))
"
```
You should see a path ending in `index.html`. Open the file in your browser. You should see a card
for each paper, and the search box, category dropdown and category chips should filter them.

**C. Discord:**

```bash
python -c "
from src.notify import send_discord
send_discord('Test message from the pipeline')
"
```
The message should appear in your Discord channel.

## 8. Option A: daily runbook (start, run, verify, stop)

### 8.1 Start everything, in this order

1. **Ollama** (leave this terminal open if you start it by hand):
   ```bash
   curl -s http://localhost:11434/api/tags | head -c 80     # prints JSON if Ollama is already running
   ollama serve                                             # only if the line above printed nothing
   ```
2. **Google Drive visible in WSL:**
   ```bash
   ls "$PAPERS_DIR"                       # must list your PDFs
   sudo mount -t drvfs G: /mnt/g          # only if the folder is empty
   ```
3. **Airflow** (in a new terminal, in the repo folder):
   ```bash
   source ~/.venvs/info-h420/bin/activate
   source ~/.bashrc
   cd "$PROJECT_DIR"
   airflow standalone
   ```
   Wait for `standalone | Airflow is ready`, and leave this terminal open. Airflow stops when this
   terminal closes.
4. **Log in:** open http://localhost:8080. The username is `admin`. In a **second terminal**, read
   the password and copy-paste it:
   ```bash
   cat ~/airflow_home/simple_auth_manager_passwords.json.generated
   ```
   If you get "401 Invalid credentials", use a private/incognito window.

### 8.2 Check that Airflow can read the DAG

```bash
airflow dags reserialize
airflow dags list                  # paper_pipeline should be listed
airflow dags list-import-errors    # "No data found" means no errors
```

### 8.3 Run the pipeline

**In the web page (best for screenshots):**

1. Open **Dags**, then **paper_pipeline**, and switch the toggle **on** (new DAGs start paused).
2. Click the play button and choose **Trigger**. Use Trigger, not Clear: Clear re-runs old task states.
3. Open the run and watch the **Graph** view. One paper takes about 1 to 2 minutes on a laptop CPU.
4. While Airflow is on, it also runs by itself every 10 minutes.

**In the terminal only (works without the web page):**

```bash
sqlite3 ~/airflow_data/papers.db "DELETE FROM papers;"     # optional: makes all PDFs count as new
airflow dags test paper_pipeline
```

You should see:

- `Found N PDFs, N new: [...]`
- `Saved <file>: <title> [<category>]` once per PDF
- `Wrote HTML page: .../index.html`
- `Discord notification sent for N papers`
- every task ending in `success`

**A good demo for the report:**

1. Trigger once with new PDFs: all tasks turn green, one Discord message arrives.
2. Trigger again with no new PDFs: `process_paper`, `build_html` and `notify` show as **skipped**, and no message is sent. This proves only new papers are processed.
3. Add one new PDF to `papers/` and trigger again: only that paper is processed, and a new Discord message arrives.

### 8.4 Verify the results

```bash
sqlite3 -header -column ~/airflow_data/papers.db "SELECT filename, title, category FROM papers;"
ls -la "$OUTPUT_DIR"
explorer.exe "$(wslpath -w "$OUTPUT_DIR/index.html")"      # opens the page from WSL
```

- **Database:** one row per processed paper.
- **Page:** open `index.html` and refresh with Ctrl+F5. The "Last updated" time at the bottom should be current.
- **Discord:** one message per run that processed new papers.

### 8.5 Stop everything

1. Check in Airflow that no paper is being processed.
2. In the Airflow terminal press **Ctrl+C**.
3. If you started Ollama by hand, press **Ctrl+C** in its terminal.

Your database, run history and DAG are saved, so you can start again later with Section 8.1.

---

## 9. Option B: Docker setup and daily runbook

This option runs **Apache Airflow 3.0.6 in Docker Compose**, with **Ollama on the Mac**, SQLite, the
generated HTML and Discord. It was tested on macOS.

> **Where to run commands:** use your **Mac terminal in the project folder** (`INFO-H420_Assignment3`),
> where `docker-compose.yml` and `.env.docker` are located. You do not need to rebuild Docker or
> delete your SQLite database for normal start/stop cycles.

### 9.1 One-time setup

1. Install **Docker Desktop** and **Ollama** on the Mac.
2. Download the model:
   ```bash
   ollama pull llama3.2:3b
   ```
3. Clone the repo and enter the folder:
   ```bash
   git clone https://github.com/ayshaaaaaaa/INFO-H420_Assignment3.git
   cd INFO-H420_Assignment3
   ```
4. Create your private settings file from the template:
   ```bash
   cp .env.docker.example .env.docker
   ```
   Open `.env.docker` and fill in:
   - `PAPERS_DIR_HOST`: the Mac folder with your PDFs (Google Drive `ResearchLibrary/papers`)
   - `OUTPUT_DIR_HOST`: the Mac folder for `index.html` (Google Drive `ResearchLibrary/output`)
   - `DISCORD_WEBHOOK_URL`: your own webhook URL

   **Never commit `.env.docker`.** It is listed in `.gitignore`, and only `.env.docker.example` is in the repo.

### 9.2 Start everything (in order)

**Start Docker Desktop:**

```bash
open -a Docker
docker info >/dev/null && echo 'Docker is ready'
```

**Start Ollama on the Mac, in Terminal 1.** First check whether it is already running:

```bash
curl http://localhost:11434/api/tags
```

If you receive JSON listing models, **do not start a second Ollama server**. Otherwise:

```bash
ollama serve
```

Leave Terminal 1 open. `ollama serve` runs in the foreground, so it is normal not to get a prompt back.

**Start Airflow in Docker, in Terminal 2:**

```bash
cd /path/to/INFO-H420_Assignment3
docker compose --env-file .env.docker up -d
docker compose --env-file .env.docker ps
```

The first time, Docker builds the image, which takes a few minutes. `up -d` starts Airflow in the
background, so you do not need to keep this terminal open.

**Check that the Airflow container can reach Ollama** (checking Ollama from the Mac alone is not enough):

```bash
docker compose --env-file .env.docker exec airflow python -c \
  "import requests; r=requests.get('http://host.docker.internal:11434/api/tags', timeout=10); print('Status:', r.status_code); print(r.text[:500]); r.raise_for_status()"
```

Expected: `Status: 200` and a response listing the Ollama models.

**Open the Airflow page:** http://localhost:8080. Find `paper_pipeline` and make sure it is
**unpaused**. If the page asks for a password, look in the container logs:

```bash
docker compose --env-file .env.docker logs --tail=100 airflow
```

### 9.3 Run the pipeline

**Option 1: automatic, every 10 minutes (normal use).** Keep Docker Desktop, the Airflow service and
Ollama running, make sure `paper_pipeline` is unpaused, and put new PDFs in the **Mac folder you set as
`PAPERS_DIR_HOST`**. Use a file name that is not already in the database. Airflow checks at the next
10-minute interval. Open the latest DAG run in the UI to see task states and logs.

To see which container folder is used and how it maps to your Mac:

```bash
docker compose --env-file .env.docker exec airflow printenv PAPERS_DIR
docker compose --env-file .env.docker config
```

**Option 2: run immediately (manual test).** In the Airflow page open `paper_pipeline` and click
**Trigger**, or from the Mac terminal in the project folder:

```bash
docker compose --env-file .env.docker exec airflow airflow dags trigger paper_pipeline
```

If the DAG is paused, unpause it first:

```bash
docker compose --env-file .env.docker exec airflow airflow dags unpause paper_pipeline
```

Manual triggering does not disable the 10-minute schedule; it adds a run. Because the DAG has
`max_active_runs=1`, do not trigger repeatedly while a run is still active.

Remember: simply triggering again will **not reprocess** a PDF whose file name is already in the
database.

### 9.4 Verify that the pipeline is healthy

```bash
docker compose --env-file .env.docker ps                                       # is the container running?
docker compose --env-file .env.docker exec airflow airflow dags list           # is the DAG visible?
docker compose --env-file .env.docker exec airflow airflow dags list-import-errors
docker compose --env-file .env.docker logs --tail=100 airflow                  # recent logs
docker compose --env-file .env.docker logs -f airflow                          # follow logs (Ctrl+C stops following, not Airflow)
```

Task details are easiest to read in the Airflow page: open the latest run and click a task.

### 9.5 Stop everything safely (in order)

1. Check in Airflow that no paper is being processed, if possible.
2. Stop the Compose services, from the project folder:
   ```bash
   docker compose --env-file .env.docker stop
   ```
   This keeps containers and their volumes. **Do not use `down -v` for routine shutdowns**: it can remove persistent volumes, including the database.
3. Stop Ollama: press **Ctrl+C** in Terminal 1 (or quit the Ollama app).
4. Verify:
   ```bash
   docker compose --env-file .env.docker ps
   lsof -nP -iTCP:11434 -sTCP:LISTEN        # no output means Ollama has stopped
   ```
5. Optional: quit Docker Desktop.

### 9.6 If Ollama connection is refused

If the container test reports `Connection refused`:

1. Check Ollama on the Mac: `curl http://localhost:11434/api/tags`.
2. Check what is listening: `lsof -nP -iTCP:11434 -sTCP:LISTEN`.
3. If Ollama runs but Docker still cannot connect, stop the command-line server with **Ctrl+C** and start it listening on all interfaces:
   ```bash
   OLLAMA_HOST=0.0.0.0:11434 ollama serve
   ```
4. Repeat the container test from Section 9.2.

**Security:** `0.0.0.0` can expose Ollama on your network. Use it only when needed, on a trusted
network. Never start two Ollama servers on the same port.

### 9.7 Docker quick commands

| Goal | Command / action |
|---|---|
| Start Docker Desktop | `open -a Docker` |
| Start Ollama (if not running) | `ollama serve` in Terminal 1 |
| Start Airflow | `docker compose --env-file .env.docker up -d` |
| Check the container | `docker compose --env-file .env.docker ps` |
| Open Airflow | http://localhost:8080 |
| Run immediately | `docker compose --env-file .env.docker exec airflow airflow dags trigger paper_pipeline` |
| Watch logs | `docker compose --env-file .env.docker logs -f airflow` |
| Stop Airflow | `docker compose --env-file .env.docker stop` |
| Check Ollama stopped | `lsof -nP -iTCP:11434 -sTCP:LISTEN` |

### 9.8 Things to remember (Docker)

- Your database and Docker volumes are preserved across normal `stop` and `up -d` cycles. You do not need to rebuild, reinstall or re-download models each day.
- Closing the MacBook so it sleeps pauses processing. With `catchup=False`, missed intervals are not replayed, but the next scan still finds any unprocessed PDFs.
- The running Airflow service and the Ollama server are both required while a PDF is processed. Watching logs is optional.
- If you change the Dockerfile, dependencies or Compose configuration, you need to rebuild or recreate the containers (`docker compose --env-file .env.docker up -d --build`).

---

## 10. Look inside the database

In **Option A** the database is one file: `~/airflow_data/papers.db`.

```bash
sqlite3 -header -column ~/airflow_data/papers.db "SELECT filename, title, category FROM papers;"
sqlite3 -line ~/airflow_data/papers.db "SELECT * FROM papers;"
sqlite3 ~/airflow_data/papers.db "SELECT COUNT(*) FROM papers;"
```

Delete everything (so the pipeline processes the PDFs again):

```bash
sqlite3 ~/airflow_data/papers.db "DELETE FROM papers;"
```

In **Option B** the database lives in the container's persistent storage (see `docker-compose.yml`).
Do not reset it with `down -v` unless you really want to delete all stored papers.

Table `papers` (one row per PDF):

| Column | Meaning |
|---|---|
| `filename` | The PDF's file name. Must be unique, which is how repeats are avoided. |
| `title` | Title written by the AI |
| `summary` | 2 or 3 sentence summary |
| `keywords` | A list stored as text, like `["a", "b"]` |
| `category` | One category from a fixed list (otherwise `Other`) |

SQLite is a normal **SQL (relational)** database. It is just stored in one file and needs no server.

## 11. Troubleshooting

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
| A new paper is never picked up (`Found N PDFs, 0 new`) | The file is not a real `.pdf`, has the same name as a processed paper, is in a subfolder, or has not synced yet. List the folder with `ls -la "$PAPERS_DIR"`. Convert HTML or Word files to PDF and use a new file name. |
| `DISCORD_WEBHOOK_URL is not set` | Add it to `~/.bashrc` (Step 7), then `source ~/.bashrc`. For Docker, put it in `.env.docker`. |
| `airflow dags list` says "No data found" | The DAG has not been parsed yet. Run `airflow dags reserialize`, then list again. |
| Airflow asks "Please confirm database initialize" | Normal the first time. Answer `y`. |
| Airflow login says "401 Invalid credentials" | Copy-paste the password from `~/airflow_home/simple_auth_manager_passwords.json.generated`, or use an incognito window. |
| The Airflow page stopped working | Airflow stops when its terminal closes. Open a new terminal, activate the environment, run `source ~/.bashrc`, and start `airflow standalone` again. If the port is busy: `pkill -f airflow`, wait a few seconds, start again. |
| DAG is listed but not running | New DAGs start **paused**. Switch it on in the web page. |
| Airflow page does not open | Another program may be using port 8080 (for example another Airflow, Option A and Option B at the same time, or another database tool). Stop it and restart. |
| Airflow install fails with a constraints 404 | Look up the latest 3.x version on pypi.org/project/apache-airflow and change `AIRFLOW_VERSION`. |
| Tasks fail only inside Airflow but work in the terminal | Airflow was started from a terminal without your settings. Close it, run `source ~/.bashrc`, and start it again. |
| Red `XCom not found ... offset=N` lines in a task log | Harmless. Airflow keeps asking for the next result until it gets "not found", which is how it knows the list ended. |
| Docker: `Connection refused` to Ollama | See Section 9.6. |
| Docker: the container cannot see your PDFs | Check the folders in `.env.docker` (`PAPERS_DIR_HOST`, `OUTPUT_DIR_HOST`) and that they exist on the Mac. Inspect mounts with `docker compose --env-file .env.docker config`. |

## 12. Glossary (all the words in simple English)

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
| **Docker / Docker Compose** | Docker runs a program in an isolated "container" with everything it needs. Compose starts one or more containers from a file (`docker-compose.yml`). |
| **`.env.docker`** | Your private Docker settings file (paths and webhook). Never committed. |
| **Placeholder file** | An empty file made with `touch`. Importing from one gives "cannot import name" errors. |

**Git and teamwork**

| Word | Easy meaning |
|---|---|
| **Git** | A tool that tracks every change to your code. |
| **GitHub / repo** | The website that stores the shared project (the "repository"). |
| **Clone** | Download a copy of the repo. |
| **Commit** | Save a snapshot of your changes with a message. |
| **Push / pull** | Push uploads your commits, pull downloads your teammates' commits. |
| **Merge / conflict** | Merging combines two branches. A conflict means both changed the same lines and you must pick one. |
| **`.gitignore`** | A list of files Git must never upload. |
| **README** | The instruction page of the project (this file). |
| **`requirements.txt`** | The list of Python libraries the project needs. |

## 13. Team rules

- Run `git pull origin main` before you start working and before you push.
- Never commit `.env`, `.env.docker`, the database, or the Discord webhook URL. Check `git status` before every commit.
- If a webhook URL is ever shared or committed, delete that webhook in Discord and create a new one.
- Make small commits with clear messages, for example `Add Discord webhook notifier`.
- Keep the function names as they are, so the pieces fit together:
  - `convert_pdf(path) -> str`
  - `extract_metadata(markdown) -> dict`
  - `init_db()`, `is_processed(filename) -> bool`, `save_paper(filename, meta)`, `get_all_papers() -> list[dict]`
  - `generate_html(papers, output_path=None)`
  - `send_discord(message)`
- Everyone uses the same model name (`llama3.2:3b`) while testing, so results look similar.

## 14. Project status

| Part | File | Status |
|---|---|---|
| Repo and README | `README.md` | Done |
| PDF to Markdown | `src/pdf_convert.py` | Done, tested |
| SQLite storage | `src/db.py` | Done, tested |
| AI metadata (JSON, retry, checks) | `src/llm_metadata.py` | Done, tested |
| HTML page with search and filter | `src/html_gen.py` | Done, tested |
| Discord notification | `src/notify.py` | Done, tested |
| Airflow DAG (schedule, mapping, checks, logging) | `dags/paper_pipeline.py` | Done, run from the Airflow UI, "nothing new" skip verified |
| Docker setup | `Dockerfile`, `docker-compose.yml` | Done, tested on macOS |
| Screenshots (graph view, run, page, database, Discord) | - | To do |
| Short report (PDF) with repo link | - | To do |

## Deadline

The report (PDF, with a link to this repo) must be uploaded to "Assignment 3" on UV by **9 November 2026**.