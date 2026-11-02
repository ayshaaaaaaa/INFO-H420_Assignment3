import pymupdf4llm


def convert_pdf(path: str) -> str:
    """Convert a PDF file to Markdown text."""
    return pymupdf4llm.to_markdown(path)
