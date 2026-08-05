def format_context(hits: list[dict]) -> str:
    """Turn retrieved chunks into a numbered, citable context block."""
    if not hits:
        return "(no relevant context found)"
    lines = []
    for i, h in enumerate(hits, start=1):
        title = h.get("doc_title") or h.get("title") or "untitled"
        section = h.get("section_title") or ""
        head = f"{title} · {section}".strip(" ·")
        lines.append(f"[{i}] ({head}) {h['content']}")
    return "\n".join(lines)
