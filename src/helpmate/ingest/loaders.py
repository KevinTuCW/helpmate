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
