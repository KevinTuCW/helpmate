def rrf_fuse(rankings: list[list], k: int = 60) -> list:
    """Reciprocal Rank Fusion: merge ranked id lists into one, higher = better.

    score(id) = sum over rankings of 1/(k + rank), rank starting at 1.
    Ties broken by first appearance for determinism.
    """
    score: dict = {}
    order: list = []
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            if item not in score:
                score[item] = 0.0
                order.append(item)
            score[item] += 1.0 / (k + rank)
    return sorted(order, key=lambda it: (-score[it], order.index(it)))
