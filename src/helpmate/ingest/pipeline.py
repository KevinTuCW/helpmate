from pathlib import Path
from helpmate.ingest.loaders import clean_html, load_pdf
from helpmate.ingest.chunking import split_sections, chunk_document
from helpmate import db


def _html_to_blocks(html: str) -> list[dict]:
    text = clean_html(html)
    return [{"type": "text", "section": s["title"], "text": s["text"]}
            for s in split_sections(text) if s["text"]]


def _pdf_to_blocks(path: str) -> list[dict]:
    # PDF blocks carry no section titles; use the file stem as a coarse section.
    stem = Path(path).stem
    return [{"type": b["type"], "section": stem, "text": b["text"]}
            for b in load_pdf(path)]


def ingest_source(*, kind: str, path_or_html: str, meta: dict,
                  size: int = 800, overlap: int = 100) -> dict:
    """Ingest one source (kind='html'|'pdf') into documents+chunks.

    meta must carry: source_url, title, doc_type, product, lang.
    Chunks are written with embedding left NULL (backfilled in phase 2).
    """
    blocks = (_html_to_blocks(path_or_html) if kind == "html"
              else _pdf_to_blocks(path_or_html))
    chunks = chunk_document(blocks, meta, size, overlap)
    doc_id = db.insert_document(meta["source_url"], meta["title"],
                                meta["doc_type"], meta.get("product"), meta.get("lang", "zh"))
    for ch in chunks:
        db.insert_chunk_row(doc_id, ch)
    return {"document_id": doc_id, "chunks": len(chunks)}
