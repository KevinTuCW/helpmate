import fitz  # pymupdf
from bs4 import BeautifulSoup

_DROP = ["script", "style", "nav", "footer", "header", "aside", "noscript"]


def clean_html(html: str) -> str:
    """Extract readable main text from an HTML page, dropping chrome."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(_DROP):
        tag.decompose()
    root = soup.find("main") or soup.body or soup
    text = root.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def table_to_markdown(rows: list[list[str]]) -> str:
    """Serialize a table (list of rows) to GitHub-flavored Markdown."""
    if not rows:
        return ""
    header, *body = rows
    out = ["| " + " | ".join(header) + " |",
           "| " + " | ".join("---" for _ in header) + " |"]
    for r in body:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def load_pdf(path: str) -> list[dict]:
    """Extract text and tables from a PDF as ordered blocks.

    Each block: {"type": "text"|"table", "text": str, "page": int}.
    Tables are serialized to Markdown so they survive chunking intact.
    """
    blocks: list[dict] = []
    doc = fitz.open(path)
    for pno, page in enumerate(doc):
        try:
            tables = page.find_tables()
            for t in tables.tables:
                md = table_to_markdown([[c or "" for c in row] for row in t.extract()])
                if md:
                    blocks.append({"type": "table", "text": md, "page": pno})
        except Exception:
            pass  # find_tables can fail on odd layouts; text still captured below
        text = page.get_text().strip()
        if text:
            blocks.append({"type": "text", "text": text, "page": pno})
    doc.close()
    return blocks
