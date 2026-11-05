# INFO-H420 Assignment 3 — Start, Run, Verify, and Stop

This README is a practical **daily runbook** for the existing macOS setup: **Docker Desktop + Apache Airflow 3.0.6 in Docker Compose + Ollama on the Mac + SQLite + generated HTML + Discord**.

The DAG is named **`paper_pipeline`** (`dags/paper_pipeline.py`) and checks for new PDFs **every 10 minutes** using `schedule="*/10 * * * *"`. The DAG must be **unpaused** and Airflow's scheduler must be running for automatic executions.

> **Where to run commands:** Unless a section says otherwise, use your **Mac terminal in the `INFO-H420_Assignment3` project folder**, where `docker-compose.yml` and `.env.docker` are located. You do not need to rebuild Docker or delete your SQLite database for normal start/stop cycles.

## 1. Start everything (in order)

### 1.1 Start Docker Desktop

```bash
open -a Docker
```

Wait until Docker Desktop is ready, then check:

```bash
docker info >/dev/null && echo 'Docker is ready'
```

### 1.2 Start Ollama on the Mac — Terminal 1

First check whether it is already running:

```bash
curl http://localhost:11434/api/tags
```

If you receive JSON listing models, **do not start a second Ollama server**. Otherwise, start it:

```bash
ollama serve
```

**Leave Terminal 1 open** while using the pipeline. `ollama serve` runs in the foreground; it is normal not to get a shell prompt back until you stop it. If it says the port is already in use, check the `curl` command again.

### 1.3 Start Airflow in Docker — Terminal 2

Open a **second terminal**. Move into the project directory (change the path to your actual location):

```bash
cd /path/to/INFO-H420_Assignment3
```

Start the Compose services in the background:

```bash
docker compose --env-file .env.docker up -d
```

Verify the container is running:

```bash
docker compose --env-file .env.docker ps
```

`up -d` starts the services; you **do not** need to keep this terminal open for Airflow to run.

### 1.4 Verify that Docker can reach Ollama

From the same project directory:

```bash
docker compose --env-file .env.docker exec airflow python -c \
  "import requests; r=requests.get('http://host.docker.internal:11434/api/tags', timeout=10); print('Status:', r.status_code); print(r.text[:500]); r.raise_for_status()"
```

**Expected:** `Status: 200` and a response containing the Ollama models. This proves the **Airflow container** can reach Ollama (checking Ollama from the Mac alone is not enough).

### 1.5 Open the Airflow UI

Open <http://localhost:8080> in your browser. Find **`paper_pipeline`** and make sure it is **unpaused / enabled**.

## 2. How to run the pipeline

There are **two ways** to run it. Both use the same tasks and the same existing SQLite database, output folder, and Discord configuration.

### Option A — Automatic execution every 10 minutes (normal use)

1. Keep **Docker Desktop**, the **Airflow Compose service**, and **Ollama** running.
2. In the Airflow UI, ensure **`paper_pipeline` is unpaused**.
3. Put one or more **new PDF files** in the **host input folder mounted into `PAPERS_DIR`**. Use a filename not already recorded in SQLite.
4. Airflow checks automatically at the next scheduled interval (every 10 minutes).
5. In the Airflow UI, click `paper_pipeline` and open the latest DAG run to inspect the task statuses and logs.

To inspect the container's configured input directory:

```bash
docker compose --env-file .env.docker exec airflow printenv PAPERS_DIR
```

This path is **inside the container**. Add PDFs to the **corresponding Mac folder** defined by your Docker Compose bind mount, not by writing into a read-only container path. You can inspect mounts using:

```bash
docker compose --env-file .env.docker config
```

**Note:** The filename-based SQLite check means simply triggering the DAG again will **not reprocess** already-recorded PDFs.

### Option B — Trigger a run immediately (manual test)

**In Airflow UI:** Open <http://localhost:8080> → `paper_pipeline` → **Trigger DAG** (the label may appear as *Trigger* or *Run*). The DAG should be unpaused to allow queued work to execute.

**Or from the Mac terminal**, in the project directory:

```bash
docker compose --env-file .env.docker exec airflow airflow dags trigger paper_pipeline
```

If the DAG is paused, unpause it first in the Airflow UI or use:

```bash
docker compose --env-file .env.docker exec airflow airflow dags unpause paper_pipeline
```

Manual triggering **does not disable** the automatic 10-minute schedule; it adds a run. Because the DAG has `max_active_runs=1`, do not repeatedly trigger it while a previous run is still active.

### Expected task workflow

```text
find_new_pdfs
    |
    v
process_paper (one mapped task per new PDF)
    |  PDF -> Markdown -> local Ollama metadata -> SQLite
    v
build_html (regenerate HTML from all stored papers)
    |
    v
notify (send Discord message)
```

**If no new PDFs are found:** `find_new_pdfs` succeeds with an empty list, the mapped `process_paper` step has zero instances, and the downstream steps are normally shown as **skipped**. This is **expected**, not a broken pipeline.

**For an end-to-end test:** add a genuinely new PDF, trigger a run manually, and check that the database, HTML page, and Discord notification are updated. The processing task in the updated DAG has a **15-minute timeout per attempt**, so exceptionally slow PDFs can time out.

## 3. Verify the pipeline is healthy

### 3.1 Check services

```bash
docker compose --env-file .env.docker ps
```

### 3.2 Check that Airflow sees the DAG

```bash
docker compose --env-file .env.docker exec airflow airflow dags list
```

Check for DAG import errors:

```bash
docker compose --env-file .env.docker exec airflow airflow dags list-import-errors
```

### 3.3 View Airflow logs (optional)

```bash
docker compose --env-file .env.docker logs -f airflow
```

Press **Control + C** to **stop following logs**; this **does not stop Airflow**.

For a one-time snapshot of recent logs:

```bash
docker compose --env-file .env.docker logs --tail=100 airflow
```

Task-specific details are most easily viewed in the Airflow UI by opening the latest DAG run and clicking a task instance.

### 3.4 Check Ollama on both sides

On the Mac:

```bash
curl http://localhost:11434/api/tags
```

From Airflow Docker:

```bash
docker compose --env-file .env.docker exec airflow python -c \
  "import requests; r=requests.get('http://host.docker.internal:11434/api/tags', timeout=10); print('Status:',r.status_code); r.raise_for_status()"
```

Expect `Status: 200` from Docker.

## 4. Stop everything safely (in order)

**Before stopping:** check in Airflow that no paper is currently being processed, if possible. Stopping services during a task can interrupt processing; the task may retry on a future run.

### 4.1 Optional: pause scheduled future runs

In the Airflow UI, pause `paper_pipeline` **only if you want it to remain paused after restarting**. For routine daily shutdown, pausing is usually unnecessary because the scheduler stops with Compose.

### 4.2 Stop the Compose services — Terminal 2

From the project directory:

```bash
docker compose --env-file .env.docker stop
```

This stops the Compose services but keeps containers and their volumes. Do **not** use `down -v` for routine shutdowns: that can remove persistent volumes.

### 4.3 Stop Ollama — Terminal 1

If you started Ollama with `ollama serve`, return to that terminal and press **Control + C**. If you started Ollama through the macOS app instead, quit the app.

### 4.4 Verify nothing is still running

Check Compose services:

```bash
docker compose --env-file .env.docker ps
```

Check Ollama's listener:

```bash
lsof -nP -iTCP:11434 -sTCP:LISTEN
```

No output from `lsof` means nothing is listening on Ollama's usual API port. For an additional check:

```bash
pgrep -fl ollama
```

A `pgrep` match can include auxiliary processes; the port check is more useful for confirming the server has stopped.

### 4.5 Optional: quit Docker Desktop

You can quit Docker Desktop after stopping your Compose services, if you are not using it for other projects.

## 5. If Ollama connection is refused

If the Docker connectivity test reports `Connection refused`:

1. Make sure Ollama runs on the **Mac** by checking `curl http://localhost:11434/api/tags`.
2. Check the listening address:

   ```bash
   lsof -nP -iTCP:11434 -sTCP:LISTEN
   ```

3. If Ollama is running but Docker still cannot connect, stop the existing **command-line** `ollama serve` server with **Control + C**, and only then try:

   ```bash
   OLLAMA_HOST=0.0.0.0:11434 ollama serve
   ```

4. Repeat the Docker connectivity test from Section 1.4.

**Security:** `0.0.0.0` can expose Ollama on your network. Only use this when needed, on a trusted network, with appropriate firewall restrictions. The original `ollama serve` command is preferable if Docker already connects successfully. **Do not launch two Ollama servers on the same port.**

## 6. Quick commands

| Goal | Command / action |
|---|---|
| Start Docker Desktop | `open -a Docker` |
| Start Ollama (if not already running) | `ollama serve` in Terminal 1 |
| Start Airflow | `docker compose --env-file .env.docker up -d` |
| Check Airflow container | `docker compose --env-file .env.docker ps` |
| Open Airflow | <http://localhost:8080> |
| Run automatically | Unpause `paper_pipeline` in UI; it runs every 10 minutes |
| Run immediately | `docker compose --env-file .env.docker exec airflow airflow dags trigger paper_pipeline` |
| Watch logs | `docker compose --env-file .env.docker logs -f airflow` |
| Stop watching logs | **Control + C** (does not stop Airflow) |
| Stop Airflow services | `docker compose --env-file .env.docker stop` |
| Stop command-line Ollama | **Control + C** in Terminal 1 |
| Check Ollama stopped | `lsof -nP -iTCP:11434 -sTCP:LISTEN` |

## 7. Things to remember

- **Your configured SQLite file and Docker volumes are preserved** across normal `stop` / `up -d` cycles, provided the database is on persistent storage.
- The database initialization call in the DAG is **not a request to reset the database**; actual behavior depends on the implementation of `src/db.py`.
- **You do not need to rebuild**, reinstall packages, redownload models, or run database initialization manually each day.
- **Closing the MacBook so it sleeps** prevents normal scheduled processing. With `catchup=False`, missed scheduled intervals are not typically replayed; the next scan still finds any unprocessed PDFs left in the input folder.
- The **Airflow logs command is optional**, but **the running Airflow service and Ollama server are required** when processing a PDF.
- If you change the **Dockerfile, dependencies, Compose configuration, or image**, additional rebuild/recreation steps may be required; those are not part of the normal start/stop routine.
- Keep `.env.docker` and any credentials or webhook secrets **out of public GitHub repositories**.

## Official references

- [Airflow 3.0.6 — DAG runs and manual triggering](https://airflow.apache.org/docs/apache-airflow/3.0.6/core-concepts/dag-run.html)
- [Airflow command-line reference](https://airflow.apache.org/docs/apache-airflow/stable/cli-ref.html)
