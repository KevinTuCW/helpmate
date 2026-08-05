from langfuse import observe
from helpmate.config import get_settings
from helpmate.retrieve.embed import get_embedder
from helpmate.retrieve.fuse import rrf_fuse
from helpmate.retrieve.rerank import rerank
from helpmate import db


@observe(as_type="retriever", name="retrieve-context")
def hybrid_retrieve(query: str, tenant_id: str | None = None) -> list[dict]:
    """dense + FTS → RRF fuse → Qwen3 rerank → top_k hits (with citation metadata).

    When tenant_id is given, both retrieval legs are scoped to that tenant so a
    caller can only ever see documents it's entitled to.
    """
    s = get_settings()
    n = s.retrieve_candidates
    dense = db.dense_search(get_embedder().embed(query), n, tenant_id)
    fts = db.fts_search(query, n, tenant_id)
    by_id = {h["chunk_id"]: h for h in (dense + fts)}
    fused_ids = rrf_fuse([[h["chunk_id"] for h in dense], [h["chunk_id"] for h in fts]])
    candidates = [by_id[i] for i in fused_ids]
    return rerank(query, candidates, s.top_k)
