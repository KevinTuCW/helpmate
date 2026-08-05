import math
import re


def recall_at_k(retrieved: list[int], gold: list[int], k: int) -> float:
    g = set(gold)
    if not g:
        return 0.0
    return len(set(retrieved[:k]) & g) / len(g)


def mrr(retrieved: list[int], gold: list[int]) -> float:
    g = set(gold)
    for i, r in enumerate(retrieved, start=1):
        if r in g:
            return 1.0 / i
    return 0.0


def ndcg_at_k(retrieved: list[int], gold: list[int], k: int) -> float:
    g = set(gold)
    dcg = sum(1.0 / math.log2(i + 1) for i, r in enumerate(retrieved[:k], start=1) if r in g)
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(g), k) + 1))
    return dcg / ideal if ideal else 0.0


def tool_correct(predicted, expected) -> bool:
    return (predicted or None) == (expected or None)


def parse_citations(answer: str, hits: list[dict]) -> list[int]:
    idxs = sorted({int(m) for m in re.findall(r"\[(\d+)\]", answer)})
    return [hits[i - 1]["chunk_id"] for i in idxs if 1 <= i <= len(hits)]


def citation_precision(cited_chunk_ids: list[int], gold: list[int]) -> float:
    if not cited_chunk_ids:
        return 0.0
    g = set(gold)
    return sum(1 for c in cited_chunk_ids if c in g) / len(cited_chunk_ids)
