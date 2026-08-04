from helpmate.ingest import chunk_text


def test_chunk_text_splits_by_size_with_overlap():
    chunks = chunk_text("abcdefghij", size=4, overlap=1)
    assert [c["content"] for c in chunks] == ["abcd", "defg", "ghij"]
    assert [c["chunk_index"] for c in chunks] == [0, 1, 2]


def test_chunk_text_short_input_single_chunk():
    assert chunk_text("hi", size=4, overlap=1) == [{"chunk_index": 0, "content": "hi"}]
