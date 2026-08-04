from helpmate.retrieve import format_context


def test_format_context_numbers_citations():
    hits = [
        {"content": "Cats sleep 15h.", "title": "Cat FAQ"},
        {"content": "Dogs need walks.", "title": "Dog FAQ"},
    ]
    ctx = format_context(hits)
    assert "[1] (Cat FAQ) Cats sleep 15h." in ctx
    assert "[2] (Dog FAQ) Dogs need walks." in ctx


def test_format_context_empty_returns_marker():
    assert format_context([]) == "(no relevant context found)"
