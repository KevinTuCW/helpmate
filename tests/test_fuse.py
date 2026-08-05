from helpmate.retrieve.fuse import rrf_fuse


def test_rrf_rewards_agreement_across_rankings():
    dense = [10, 20, 30]   # ids ranked by dense
    sparse = [20, 40, 10]  # ids ranked by fts
    fused = rrf_fuse([dense, sparse], k=60)
    # 20 appears high in both -> should rank first
    assert fused[0] == 20
    # every id present, deduplicated
    assert set(fused) == {10, 20, 30, 40}


def test_rrf_single_ranking_preserves_order():
    assert rrf_fuse([[3, 1, 2]], k=60) == [3, 1, 2]
