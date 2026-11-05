import html
import os


def generate_html(papers: list[dict], output_path: str | None = None) -> str:
    """Write a static, searchable HTML page listing all papers. Returns the file path."""
    if output_path is None:
        output_path = os.path.join(os.environ["OUTPUT_DIR"], "index.html")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    categories = sorted({p["category"] for p in papers if p.get("category")})
    options = "".join(
        f'<option value="{html.escape(c)}">{html.escape(c)}</option>' for c in categories
    )

    cards = []
    for p in papers:
        keywords = "".join(
            f'<span class="kw">{html.escape(k)}</span>' for k in p.get("keywords", [])
        )
        cards.append(
            f'<article class="card" data-category="{html.escape(p.get("category") or "")}">'
            f'<h2>{html.escape(p.get("title") or p["filename"])}</h2>'
            f'<p class="meta">{html.escape(p.get("category") or "")} · '
            f'{html.escape(p["filename"])}</p>'
            f'<p>{html.escape(p.get("summary") or "")}</p>'
            f'<div>{keywords}</div></article>'
        )

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Research Library</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 860px; margin: 2rem auto; padding: 0 1rem; color: #222; }}
  .controls {{ display: flex; gap: .5rem; margin-bottom: 1rem; }}
  input, select {{ padding: .5rem; font-size: 1rem; }}
  input {{ flex: 1; }}
  .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }}
  .card h2 {{ margin: 0 0 .25rem; font-size: 1.15rem; }}
  .meta {{ color: #666; font-size: .85rem; margin: 0 0 .5rem; }}
  .kw {{ display: inline-block; background: #eef; border-radius: 12px; padding: .1rem .6rem; margin: .1rem; font-size: .8rem; }}
</style>
</head>
<body>
<h1>Research Library</h1>
<p id="count">{len(papers)} papers</p>
<div class="controls">
  <input id="search" type="search" placeholder="Search title, summary, keywords...">
  <select id="category"><option value="">All categories</option>{options}</select>
</div>
{"".join(cards)}
<script>
  const search = document.getElementById('search');
  const category = document.getElementById('category');
  const cards = document.querySelectorAll('.card');
  function filter() {{
    const q = search.value.toLowerCase();
    const c = category.value;
    let shown = 0;
    cards.forEach(card => {{
      const ok = card.textContent.toLowerCase().includes(q) &&
                 (c === '' || card.dataset.category === c);
      card.style.display = ok ? '' : 'none';
      if (ok) shown++;
    }});
    document.getElementById('count').textContent = shown + ' papers';
  }}
  search.addEventListener('input', filter);
  category.addEventListener('change', filter);
</script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(page)
    return output_path