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
  body { font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; color: #222; }
  h1 { margin-bottom: 0.2rem; }
  .meta { color: #666; font-size: 0.85rem; margin-bottom: 1.5rem; }
  .controls { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; }
  input, select { padding: 0.5rem; font-size: 1rem; border: 1px solid #bbb; border-radius: 6px; }
  input { flex: 1; }
  .card { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }
  .card h2 { margin: 0 0 0.3rem; font-size: 1.15rem; }
  .file { color: #888; font-size: 0.8rem; }
  .tag { display: inline-block; background: #eef; border-radius: 12px; padding: 2px 10px; margin: 4px 4px 0 0; font-size: 0.8rem; }
  .cat { background: #dfd; }
  #count { color: #666; margin-bottom: 1rem; }
</style>
</head>
<body>
<h1>Research Library</h1>
<div class="meta">Last updated: __UPDATED__</div>
<div class="controls">
  <input id="search" type="search" placeholder="Search title, summary, keywords...">
  <select id="category"><option value="">All categories</option></select>
</div>
<div id="count"></div>
<div id="list"></div>
<script>
const papers = __DATA__;
const list = document.getElementById("list");
const search = document.getElementById("search");
const category = document.getElementById("category");
const count = document.getElementById("count");

[...new Set(papers.map(p => p.category))].sort().forEach(c => {
  const o = document.createElement("option");
  o.value = c; o.textContent = c; category.appendChild(o);
});

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
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
    card.appendChild(el("h2", "", p.title));
    card.appendChild(el("div", "file", p.filename));
    card.appendChild(el("p", "", p.summary));
    card.appendChild(el("span", "tag cat", p.category));
    p.keywords.forEach(k => card.appendChild(el("span", "tag", k)));
    list.appendChild(card);
  });
  count.textContent = shown.length + " of " + papers.length + " papers";
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

    data = json.dumps(papers).replace("</", "<\\/")  # keep </script> from breaking the page
    html = TEMPLATE.replace("__DATA__", data).replace(
        "__UPDATED__", datetime.now().strftime("%Y-%m-%d %H:%M")
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path
