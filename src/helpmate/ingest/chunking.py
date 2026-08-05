def chunk_text(text: str, size: int = 800, overlap: int = 100) -> list[dict]:
    """Split text into fixed-size windows with overlap. Pure, deterministic."""
    if size <= 0:
        raise ValueError("size must be > 0")
    if overlap >= size:
        raise ValueError("overlap must be < size")
    if len(text) <= size:
        return [{"chunk_index": 0, "content": text}]
    step = size - overlap
    chunks: list[dict] = []
    for i, start in enumerate(range(0, len(text), step)):
        window = text[start:start + size]
        if not window:
            break
        chunks.append({"chunk_index": i, "content": window})
        if start + size >= len(text):
            break
    return chunks


def split_sections(text: str) -> list[dict]:
    """Split markdown-ish text into sections by '#'-prefixed headings."""
    sections: list[dict] = []
    title, buf = "", []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            if buf:
                sections.append({"title": title, "text": "\n".join(buf).strip()})
                buf = []
            title = line.lstrip("#").strip()
        else:
            buf.append(line)
    if buf:
        sections.append({"title": title, "text": "\n".join(buf).strip()})
    return sections or [{"title": "", "text": text.strip()}]


def chunk_document(blocks: list[dict], meta: dict, size: int = 800,
                   overlap: int = 100) -> list[dict]:
    """Turn ordered blocks into metadata-tagged chunks.

    Text blocks are windowed via chunk_text; table blocks are kept whole.
    chunk_index runs globally across the document.
    """
    chunks: list[dict] = []
    idx = 0
    for b in blocks:
        section = b.get("section", "")
        pieces = ([b["text"]] if b.get("type") == "table"
                  else [c["content"] for c in chunk_text(b["text"], size, overlap)])
        for content in pieces:
            chunks.append({
                "chunk_index": idx,
                "content": content,
                "section_title": section,
                "doc_type": meta.get("doc_type", ""),
                "product": meta.get("product"),
                "source_url": meta.get("source_url"),
                "lang": meta.get("lang", "zh"),
                "tenant_id": meta.get("tenant_id", "public"),
            })
            idx += 1
    return chunks
