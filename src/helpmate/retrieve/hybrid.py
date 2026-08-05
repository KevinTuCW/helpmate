from helpmate.config import get_settings
from helpmate.retrieve.embed import get_embedder
from helpmate.retrieve.fuse import rrf_fuse
from helpmate.retrieve.rerank import rerank
from helpmate import db


def hybrid_retrieve(query: str) -> list[dict]:
    """dense + FTS → RRF fuse → Qwen3 rerank → top_k hits (with citation metadata)."""
    s = get_settings()
    n = s.retrieve_candidates
    dense = db.dense_search(get_embedder().embed(query), n)
    fts = db.fts_search(query, n)
    by_id = {h["chunk_id"]: h for h in (dense + fts)}
    fused_ids = rrf_fuse([[h["chunk_id"] for h in dense], [h["chunk_id"] for h in fts]])
    candidates = [by_id[i] for i in fused_ids]
    return rerank(query, candidates, s.top_k)
