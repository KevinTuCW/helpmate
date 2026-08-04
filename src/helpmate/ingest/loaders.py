import fitz  # pymupdf
from bs4 import BeautifulSoup

_DROP = ["script", "style", "nav", "footer", "header", "aside", "noscript"]


_HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


def clean_html(html: str) -> str:
    """Extract readable main text from an HTML page, dropping chrome.

    Headings <h1>..<h6> are emitted as Markdown-style '#'-prefixed lines
    (level = heading number) so downstream section splitting can detect them.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(_DROP):
        tag.decompose()
    root = soup.find("main") or soup.body or soup

    # Turn each heading into a Markdown-style '#'-prefixed line in place, so
    # get_text() renders it as e.g. "# DJI Care" instead of a bare line.
    for h in root.find_all(_HEADINGS):
        level = int(h.name[1])
        h.string = "#" * level + " " + h.get_text(separator=" ").strip()

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
