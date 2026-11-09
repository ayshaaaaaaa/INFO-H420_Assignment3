import json
import os
from datetime import datetime

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output")

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Research Library</title>
<style>
  :root {
    --pink: #ff8fb8;
    --pink-soft: #ffe3ee;
    --lavender: #b8a1ff;
    --lavender-soft: #efe9ff;
    --ink: #3b2f4a;
    --muted: #8a7d99;
    --card: #ffffff;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: "Poppins", "Segoe UI", system-ui, -apple-system, sans-serif;
    color: var(--ink);
    background: linear-gradient(160deg, #fff0f6 0%, #f4eeff 55%, #eaf4ff 100%);
    min-height: 100vh;
  }
  .wrap { max-width: 920px; margin: 0 auto; padding: 2.5rem 1.2rem 3rem; }

  header { text-align: center; margin-bottom: 2rem; }
  h1 {
    margin: 0;
    font-size: 2.4rem;
    letter-spacing: -0.5px;
    background: linear-gradient(90deg, var(--pink), var(--lavender));
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }
  .subtitle { margin-top: 0.4rem; color: var(--muted); font-size: 0.95rem; }
  .pill-stat {
    display: inline-block;
    margin-top: 0.9rem;
    padding: 0.3rem 0.9rem;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.8);
    color: var(--muted);
    font-size: 0.8rem;
    box-shadow: 0 2px 10px rgba(184, 161, 255, 0.18);
  }

  .controls { display: flex; gap: 0.7rem; margin-bottom: 1rem; flex-wrap: wrap; }
  .search-box { position: relative; flex: 1 1 260px; }
  .search-box span {
    position: absolute; left: 14px; top: 50%; transform: translateY(-50%);
    font-size: 1rem; opacity: 0.6;
  }
  input, select {
    width: 100%;
    padding: 0.75rem 1rem;
    font-size: 0.95rem;
    font-family: inherit;
    color: var(--ink);
    border: 2px solid transparent;
    border-radius: 16px;
    background: var(--card);
    box-shadow: 0 4px 16px rgba(184, 161, 255, 0.18);
    outline: none;
    transition: border-color 0.15s, box-shadow 0.15s;
  }
  input { padding-left: 2.6rem; }
  select { width: auto; cursor: pointer; }
  input:focus, select:focus {
    border-color: var(--pink);
    box-shadow: 0 4px 18px rgba(255, 143, 184, 0.3);
  }

  .chips { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1.2rem; }
  .chip {
    border: none;
    cursor: pointer;
    font-family: inherit;
    font-size: 0.8rem;
    padding: 0.35rem 0.9rem;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.85);
    color: var(--muted);
    box-shadow: 0 2px 8px rgba(184, 161, 255, 0.15);
    transition: transform 0.12s, background 0.12s, color 0.12s;
  }
  .chip:hover { transform: translateY(-1px); }
  .chip.active {
    background: linear-gradient(90deg, var(--pink), var(--lavender));
    color: #fff;
  }

  #count { color: var(--muted); font-size: 0.85rem; margin: 0 0 0.9rem 0.3rem; }

  .card {
    background: var(--card);
    border-radius: 22px;
    padding: 1.3rem 1.5rem;
    margin-bottom: 1.1rem;
    box-shadow: 0 6px 22px rgba(184, 161, 255, 0.2);
    border-left: 6px solid var(--accent, var(--pink));
    transition: transform 0.15s, box-shadow 0.15s;
  }
  .card:hover { transform: translateY(-3px); box-shadow: 0 10px 28px rgba(255, 143, 184, 0.28); }
  .card h2 { margin: 0 0 0.25rem; font-size: 1.15rem; line-height: 1.35; }
  .file { color: var(--muted); font-size: 0.78rem; margin-bottom: 0.7rem; }
  .card p { margin: 0 0 0.9rem; line-height: 1.6; font-size: 0.93rem; }

  .tag {
    display: inline-block;
    margin: 0 0.4rem 0.4rem 0;
    padding: 0.22rem 0.75rem;
    border-radius: 999px;
    font-size: 0.75rem;
    background: var(--lavender-soft);
    color: #6d5bb0;
  }
  .tag.cat { color: #fff; font-weight: 600; background: var(--accent, var(--pink)); }

  .empty {
    text-align: center; color: var(--muted); padding: 2.5rem 1rem;
    background: rgba(255, 255, 255, 0.7); border-radius: 22px;
  }
  footer { text-align: center; color: var(--muted); font-size: 0.78rem; margin-top: 2rem; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>&#127800; Research Library</h1>
    <div class="subtitle">Your cozy little corner for papers, summaries and ideas</div>
    <div class="pill-stat" id="stat"></div>
  </header>

  <div class="controls">
    <div class="search-box">
      <span>&#128269;</span>
      <input id="search" type="search" placeholder="Search title, summary or keywords...">
    </div>
    <select id="category"><option value="">All categories</option></select>
  </div>
  <div class="chips" id="chips"></div>
  <div id="count"></div>
  <div id="list"></div>
  <footer>Last updated: __UPDATED__ &#10084;</footer>
</div>

<script>
const papers = __DATA__;
const list = document.getElementById("list");
const search = document.getElementById("search");
const category = document.getElementById("category");
const chips = document.getElementById("chips");
const count = document.getElementById("count");
document.getElementById("stat").textContent =
  papers.length + (papers.length === 1 ? " paper" : " papers") + " in your library";

const ACCENTS = ["#ff8fb8", "#b8a1ff", "#7ec8e3", "#ffb38a", "#8fd9b6", "#f5a3e0"];
const cats = [...new Set(papers.map(p => p.category))].sort();
const accentFor = c => ACCENTS[cats.indexOf(c) % ACCENTS.length];

cats.forEach(c => {
  const o = document.createElement("option");
  o.value = c; o.textContent = c; category.appendChild(o);
});

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function buildChips() {
  chips.innerHTML = "";
  ["", ...cats].forEach(c => {
    const b = el("button", "chip" + (category.value === c ? " active" : ""), c || "All");
    b.addEventListener("click", () => { category.value = c; render(); });
    chips.appendChild(b);
  });
}

function render() {
  const q = search.value.toLowerCase();
  const cat = category.value;
  list.innerHTML = "";
  const shown = papers.filter(p => {
    const hay = (p.title + " " + p.summary + " " + p.keywords.join(" ")).toLowerCase();
    return (!cat || p.category === cat) && hay.includes(q);
  });
  shown.forEach(p => {
    const card = el("div", "card");
    card.style.setProperty("--accent", accentFor(p.category));
    card.appendChild(el("h2", "", p.title));
    card.appendChild(el("div", "file", "\\uD83D\\uDCC4 " + p.filename));
    card.appendChild(el("p", "", p.summary));
    card.appendChild(el("span", "tag cat", p.category));
    p.keywords.forEach(k => card.appendChild(el("span", "tag", k)));
    list.appendChild(card);
  });
  if (!shown.length) {
    list.appendChild(el("div", "empty", "No papers match your search yet \\u2728"));
  }
  count.textContent = "Showing " + shown.length + " of " + papers.length;
  buildChips();
}
search.addEventListener("input", render);
category.addEventListener("change", render);
render();
</script>
</body>
</html>
"""


def generate_html(papers: list[dict], output_path: str | None = None) -> str:
    """Write a static HTML page listing all papers, with search and category filter."""
    if output_path is None:
        output_path = os.path.join(OUTPUT_DIR, "index.html")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    data = json.dumps(papers).replace("</", "<\\/")  
    html = TEMPLATE.replace("__DATA__", data).replace(
        "__UPDATED__", datetime.now().strftime("%Y-%m-%d %H:%M")
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path
