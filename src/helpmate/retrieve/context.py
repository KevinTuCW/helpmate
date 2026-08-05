def format_context(hits: list[dict]) -> str:
    """Turn retrieved chunks into a numbered, citable context block."""
    if not hits:
        return "(no relevant context found)"
    lines = []
    for i, h in enumerate(hits, start=1):
        title = h.get("title") or "untitled"
        lines.append(f"[{i}] ({title}) {h['content']}")
    return "\n".join(lines)
