from helpmate.ingest.chunking import split_sections, chunk_document


def test_split_sections_by_headings():
    text = "# DJI Care\nCovers damage.\n# Warranty\nOne year."
    assert split_sections(text) == [
        {"title": "DJI Care", "text": "Covers damage."},
        {"title": "Warranty", "text": "One year."},
    ]


def test_split_sections_no_heading():
    assert split_sections("just text") == [{"title": "", "text": "just text"}]


def test_chunk_document_windows_text_keeps_table_whole():
    blocks = [
        {"type": "text", "section": "Specs", "text": "abcdefghij"},
        {"type": "table", "section": "Specs", "text": "| a | b |"},
    ]
    meta = {"doc_type": "spec", "product": "Mini 4", "source_url": "http://x", "lang": "zh"}
    chunks = chunk_document(blocks, meta, size=4, overlap=1)
    assert [c["content"] for c in chunks] == ["abcd", "defg", "ghij", "| a | b |"]
    assert [c["chunk_index"] for c in chunks] == [0, 1, 2, 3]
    assert all(c["section_title"] == "Specs" for c in chunks)
    assert chunks[0]["product"] == "Mini 4" and chunks[0]["doc_type"] == "spec"
