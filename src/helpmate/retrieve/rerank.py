import httpx
from langfuse import observe, get_client
from helpmate.config import get_settings


@observe(as_type="span", name="rerank-candidates", capture_input=False)
def rerank(query: str, hits: list[dict], top_k: int) -> list[dict]:
    """Reorder hits by Qwen3-Reranker relevance; return the top_k hits.

    hits are dicts carrying a 'content' field. Falls back to the original
    order (truncated) if the rerank endpoint returns nothing.
    """
    if not hits:
        return []
    s = get_settings()
    get_client().update_current_span(
        input={"query": query, "n_candidates": len(hits), "top_k": top_k},
        metadata={"model": s.rerank_model},
    )
    r = httpx.post(
        s.embed_base_url() + "/rerank",
        headers={"Authorization": "Bearer " + s.embed_api_key(),
                 "Content-Type": "application/json"},
        json={"model": s.rerank_model, "query": query,
              "documents": [h["content"] for h in hits], "top_n": top_k},
        timeout=60,
    )
    r.raise_for_status()
    results = r.json().get("results", [])
    if not results:
        return hits[:top_k]
    return [hits[item["index"]] for item in results][:top_k]
