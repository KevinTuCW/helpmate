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
