"""Chinese has to reach the FTS index through a detour.

PostgreSQL's default parser classifies characters with the database's ctype. On
macOS (`en_US.UTF-8`) `iswalpha()` returns false for CJK, so `ts_debug` reports a
whole Chinese run as `blank` and `to_tsvector('simple', …)` comes back **empty** —
segmenting the text first does not help, because each Chinese word is still
`blank`. On glibc the same text collapses into one useless token instead.

So words are segmented in Python and non-ASCII ones are mapped to an ASCII
surrogate the parser cannot refuse. Latin/digit tokens are kept verbatim, because
exact matches on model names and specs ("Mini 4 Pro") are the one thing the FTS
leg was actually contributing.
"""
from helpmate.retrieve.segment import segment, segment_query


def test_chinese_words_become_ascii_surrogates():
    out = segment("限飞区解禁").split()
    assert len(out) == 2
    assert all(t.startswith("z") and t[1:].isalnum() and t.isascii() for t in out)


def test_the_same_word_always_maps_to_the_same_surrogate():
    a = segment("限飞区怎么解禁")
    b = segment("解禁流程说明")
    shared = set(a.split()) & set(b.split())
    assert shared, "解禁 must produce the same surrogate in both texts"


def test_different_words_do_not_collide():
    assert segment("限飞") != segment("保修")


def test_latin_and_digits_survive_verbatim_lowercased():
    out = segment("DJI Mini 4 Pro 的图传距离").split()
    assert "dji" in out and "mini" in out and "4" in out and "pro" in out


def test_punctuation_and_whitespace_are_dropped():
    out = segment("限飞区，解禁！（需要 提交）\n申请。").split()
    assert all(t.isascii() and t.strip() for t in out)
    assert not any(t in "，！（）。" for t in out)


def test_a_query_is_segmented_the_same_way_as_the_document():
    # A query term must land on the surrogate the document produced, or the
    # index is populated but unsearchable.
    doc = set(segment("限飞区解禁需要提交申请").split())
    assert set(segment_query("解禁").split()) <= doc
    assert set(segment_query("限飞区").split()) <= doc


def test_empty_and_whitespace_input_are_safe():
    assert segment("") == ""
    assert segment("   \n ") == ""
    assert segment_query("") == ""
