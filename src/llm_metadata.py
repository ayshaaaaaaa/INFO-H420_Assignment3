import json
import os

from openai import OpenAI

BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")
MODEL = os.environ.get("LLM_MODEL", "llama3.2:3b")
MAX_CHARS = 8000  # keeps the prompt inside the 4096-token context window

CATEGORIES = [
    "Data Engineering",
    "Machine Learning",
    "Process Mining",
    "Responsible AI",
    "Databases",
    "Software Engineering",
    "Other",
]

client = OpenAI(base_url=BASE_URL, api_key="ollama", timeout=300)


def _build_prompt(markdown: str) -> str:
    return f"""You are a research librarian. Read the beginning of this paper and
return ONLY a JSON object with exactly these keys:
- "title": the paper's title, copied exactly as written in the text
- "summary": a short summary of 2-3 sentences
- "keywords": a list of 3 to 6 short keywords
- "category": the single best-fitting one of {CATEGORIES}. Use "Machine Learning" for papers about learning algorithms, "Process Mining" for event logs and process models, "Data Engineering" only for pipelines and data infrastructure

Paper text:
{markdown[:MAX_CHARS]}
"""


def _check(data: dict) -> dict:
    """Basic check that required fields exist and have the expected types."""
    if not isinstance(data, dict):
        raise ValueError("Response is not a JSON object")
    for key in ("title", "summary", "keywords", "category"):
        if key not in data:
            raise ValueError(f"Missing field: {key}")
    if not isinstance(data["title"], str) or not isinstance(data["summary"], str):
        raise ValueError("title and summary must be strings")
    if not isinstance(data["keywords"], list):
        raise ValueError("keywords must be a list")
    data["keywords"] = [str(k) for k in data["keywords"]]
    if data["category"] not in CATEGORIES:
        data["category"] = "Other"  # small models sometimes invent categories
    return data


def extract_metadata(markdown: str) -> dict:
    """Ask the local LLM for metadata as JSON; retry once if parsing/validation fails."""
    last_error = None
    for attempt in range(2):
        response = client.chat.completions.create(
            model=MODEL,
            temperature=0 if attempt == 0 else 0.5,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": _build_prompt(markdown)}],
        )
        content = response.choices[0].message.content
        try:
            return _check(json.loads(content))
        except (json.JSONDecodeError, ValueError) as err:
            last_error = err
            print(f"Attempt {attempt + 1} failed: {err}")
    raise RuntimeError(f"LLM output invalid after retry: {last_error}")
