from eval.metrics import (recall_at_k, mrr, ndcg_at_k, tool_correct,
                          parse_citations, citation_precision)


def test_recall_at_k():
    assert recall_at_k([1, 2, 3, 4], [2, 9], 3) == 0.5   # 2 in top3, 9 not
    assert recall_at_k([1, 2], [], 3) == 0.0


def test_mrr():
    assert mrr([5, 2, 7], [2]) == 0.5                     # gold at rank 2
    assert mrr([5, 7], [2]) == 0.0


def test_ndcg_at_k_perfect_is_one():
    assert round(ndcg_at_k([2, 3], [2, 3], 2), 6) == 1.0
    assert ndcg_at_k([9, 8], [2], 2) == 0.0


def test_tool_correct():
    assert tool_correct("query_order", "query_order") is True
    assert tool_correct(None, None) is True
    assert tool_correct("query_order", None) is False


def test_parse_and_citation_precision():
    hits = [{"chunk_id": 10}, {"chunk_id": 20}, {"chunk_id": 30}]
    cited = parse_citations("答案见 [1] 和 [3]。", hits)
    assert cited == [10, 30]
    assert citation_precision([10, 30], [10]) == 0.5
    assert citation_precision([], [10]) == 0.0
