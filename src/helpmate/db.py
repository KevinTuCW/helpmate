import hashlib
import json
import psycopg
from contextlib import contextmanager
from typing import Optional
from helpmate.config import get_settings

_POOL = None


def _pool():
    """Lazily build a process-wide connection pool.

    A single `/chat` touches the DB 5–7 times (retrieve, order, audit, turns,
    sampling); opening a fresh TCP+TLS connection each time is the first thing
    that falls over under concurrency. `psycopg_pool` is optional — without it
    we fall back to per-call connections so the repo still runs.
    """
    global _POOL
    if _POOL is None:
        try:
            from psycopg_pool import ConnectionPool
        except ImportError:      # pragma: no cover - optional dependency
            return None
        _POOL = ConnectionPool(get_settings().database_url, min_size=1,
                               max_size=10, open=True)
    return _POOL


@contextmanager
def _conn():
    pool = _pool()
    if pool is None:             # pragma: no cover - fallback path
        with psycopg.connect(get_settings().database_url) as conn:
            yield conn
        return
    with pool.connection() as conn:
        yield conn


def insert_document(source_url: str, title: str, doc_type: str,
                    product: str | None, lang: str = "zh",
                    tenant_id: str = "public") -> int:
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "INSERT INTO documents (tenant_id, source_url, title, doc_type, product, lang) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (tenant_id, source_url, title, doc_type, product, lang),
        )
        return cur.fetchone()[0]


def insert_chunk_row(document_id: int, ch: dict) -> None:
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "INSERT INTO chunks (document_id, tenant_id, chunk_index, content, section_title, "
            "doc_type, product, source_url, lang) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (document_id, ch.get("tenant_id", "public"), ch["chunk_index"], ch["content"],
             ch.get("section_title"), ch["doc_type"], ch.get("product"),
             ch.get("source_url"), ch.get("lang", "zh")),
        )


def get_order(order_id: str, *, tenant_id: str,
              customer_id: Optional[str]) -> Optional[dict]:
    """Look up an order **the caller owns**.

    Ownership is enforced in SQL, not in the prompt: a caller with no bound
    customer gets nothing, and a bound caller only ever sees their own rows.
    A foreign order is indistinguishable from a missing one (both return None)
    so the tool cannot be used to enumerate order ids.
    """
    if not customer_id:
        return None
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT order_id, customer, status, total FROM orders "
            "WHERE order_id = %s AND tenant_id = %s AND customer_id = %s",
            (order_id, tenant_id, customer_id),
        )
        r = cur.fetchone()
        return None if r is None else {
            "order_id": r[0], "customer": r[1], "status": r[2], "total": float(r[3])
        }


def get_shipment(order_id: str, *, tenant_id: str,
                 customer_id: Optional[str]) -> Optional[dict]:
    """Shipment for an order the caller owns (ownership lives on `orders`)."""
    if not customer_id:
        return None
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT s.order_id, s.carrier, s.tracking_no, s.status, s.eta "
            "FROM shipments s JOIN orders o ON o.order_id = s.order_id "
            "WHERE s.order_id = %s AND o.tenant_id = %s AND o.customer_id = %s",
            (order_id, tenant_id, customer_id),
        )
        r = cur.fetchone()
        return None if r is None else {
            "order_id": r[0], "carrier": r[1], "tracking_no": r[2],
            "status": r[3], "eta": str(r[4]) if r[4] else None,
        }


def fetch_unembedded(limit: int = 64,
                     document_id: Optional[int] = None) -> list[tuple[int, str]]:
    """Chunks still missing an embedding, optionally scoped to one document.

    `/ingest` scopes to the document it just wrote — an ingest request must not
    drag every other tenant's pending chunks through the embedding API.
    """
    doc_clause = "AND document_id = %s " if document_id is not None else ""
    params = [] + ([document_id] if document_id is not None else []) + [limit]
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT id, content FROM chunks WHERE embedding IS NULL " + doc_clause +
            "ORDER BY id LIMIT %s",
            tuple(params),
        )
        return [(r[0], r[1]) for r in cur.fetchall()]


def update_embedding(chunk_id: int, embedding: list[float]) -> None:
    with _conn() as c, c.cursor() as cur:
        cur.execute("UPDATE chunks SET embedding = %s WHERE id = %s",
                    (json.dumps(embedding), chunk_id))


def _hit_row(r) -> dict:
    return {"chunk_id": r[0], "content": r[1], "section_title": r[2],
            "source_url": r[3], "doc_title": r[4], "doc_type": r[5]}


def dense_search(embedding: list[float], n: int, tenant_id: Optional[str] = None) -> list[dict]:
    tenant_clause = "AND ch.tenant_id = %s " if tenant_id else ""
    params = ([tenant_id] if tenant_id else []) + [json.dumps(embedding), n]
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT ch.id, ch.content, ch.section_title, ch.source_url, d.title, ch.doc_type "
            "FROM chunks ch JOIN documents d ON d.id = ch.document_id "
            "WHERE ch.embedding IS NOT NULL " + tenant_clause +
            "ORDER BY ch.embedding <=> %s::vector LIMIT %s",
            tuple(params),
        )
        return [_hit_row(r) for r in cur.fetchall()]


def fts_search(query: str, n: int, tenant_id: Optional[str] = None) -> list[dict]:
    tenant_clause = "AND ch.tenant_id = %s " if tenant_id else ""
    params = [query] + ([tenant_id] if tenant_id else []) + [query, n]
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT ch.id, ch.content, ch.section_title, ch.source_url, d.title, ch.doc_type "
            "FROM chunks ch JOIN documents d ON d.id = ch.document_id "
            "WHERE ch.content_tsv @@ websearch_to_tsquery('simple', %s) " + tenant_clause +
            "ORDER BY ts_rank_cd(ch.content_tsv, websearch_to_tsquery('simple', %s)) DESC LIMIT %s",
            tuple(params),
        )
        return [_hit_row(r) for r in cur.fetchall()]


# --- governance: audit trail --------------------------------------------------

def write_audit(*, tenant_id: str, session_id: Optional[str], question: str,
                decision: str, tool_call: Optional[str], guard: Optional[list[str]],
                answer: str) -> None:
    """Append one immutable audit row per /chat. Stores an answer hash, not the
    answer text, so the trail is traceable without duplicating sensitive content."""
    answer_hash = hashlib.sha256(answer.encode("utf-8")).hexdigest() if answer else None
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "INSERT INTO audit_log (tenant_id, session_id, question, decision, "
            "tool_call, guard, answer_hash) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (tenant_id, session_id, question, decision, tool_call,
             ",".join(guard) if guard else None, answer_hash),
        )


# --- suggestions: the question bank ------------------------------------------
# Opening "hot" questions and typeahead both read the audit trail. Its `question`
# column is already PII-redacted on write, so replaying these back to a user
# leaks nothing — but they are still tenant-scoped data, hence the filter.

def top_questions(tenant_id: str, days: int = 7, limit: int = 4) -> list[str]:
    """Most-asked questions for one tenant in the last `days` days."""
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT question, count(*) AS n FROM audit_log "
            "WHERE tenant_id = %s "
            "AND created_at > now() - make_interval(days => %s) "
            "AND decision IN ('retrieve', 'act') "
            "AND char_length(question) BETWEEN 4 AND 40 "
            "GROUP BY question ORDER BY n DESC, max(created_at) DESC LIMIT %s",
            (tenant_id, days, limit),
        )
        return [r[0] for r in cur.fetchall()]


def _like_escape(s: str) -> str:
    """Escape LIKE wildcards so user input matches literally."""
    return s.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


def search_questions(prefix: str, tenant_id: str, limit: int = 5) -> list[str]:
    """Distinct past questions of this tenant containing `prefix`.

    Substring (not prefix) matching on purpose: Chinese users type the middle of
    a phrase as often as the start ("解禁" should find "限飞区怎么解禁").
    """
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT question FROM audit_log "
            "WHERE tenant_id = %s AND question ILIKE %s "
            "AND decision IN ('retrieve', 'act') "
            "AND char_length(question) BETWEEN 4 AND 40 "
            "ORDER BY question LIMIT %s",
            (tenant_id, f"%{_like_escape(prefix)}%", limit),
        )
        return [r[0] for r in cur.fetchall()]


# --- multi-turn: session memory ----------------------------------------------

def append_turn(session_id: str, role: str, content: str) -> None:
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "INSERT INTO session_turns (session_id, role, content) VALUES (%s, %s, %s)",
            (session_id, role, content),
        )


def recent_turns(session_id: str, limit: int = 6) -> list[dict]:
    """Last `limit` turns for a session, oldest→newest."""
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT role, content FROM session_turns WHERE session_id = %s "
            "ORDER BY id DESC LIMIT %s",
            (session_id, limit),
        )
        rows = [{"role": r[0], "content": r[1]} for r in cur.fetchall()]
    return list(reversed(rows))


# --- eval: stable golden-set anchors -----------------------------------------
# `chunks.id` is a serial that changes on every re-ingest, so a golden set keyed
# on it dies the moment chunking changes. Anchors key on content instead.

def anchors_for_chunk_ids(chunk_ids: list[int]) -> list[dict]:
    """(source_url, section_title, chunk_index) for each chunk id, in order."""
    if not chunk_ids:
        return []
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT id, source_url, section_title, chunk_index FROM chunks "
            "WHERE id = ANY(%s)",
            (list(chunk_ids),),
        )
        by_id = {r[0]: {"source_url": r[1], "section_title": r[2],
                        "chunk_index": r[3]} for r in cur.fetchall()}
    return [by_id[i] for i in chunk_ids if i in by_id]


def chunk_ids_for_anchor(anchor: dict, tenant_id: Optional[str] = None) -> list[int]:
    """Resolve one golden anchor back to current chunk ids."""
    clauses = ["source_url = %s"]
    params: list = [anchor.get("source_url")]
    if anchor.get("section_title") is not None:
        clauses.append("section_title IS NOT DISTINCT FROM %s")
        params.append(anchor["section_title"])
    if anchor.get("chunk_index") is not None:
        clauses.append("chunk_index = %s")
        params.append(anchor["chunk_index"])
    if tenant_id:
        clauses.append("tenant_id = %s")
        params.append(tenant_id)
    with _conn() as c, c.cursor() as cur:
        cur.execute("SELECT id FROM chunks WHERE " + " AND ".join(clauses) +
                    " ORDER BY id", tuple(params))
        return [r[0] for r in cur.fetchall()]


# --- ops: online sampling ----------------------------------------------------

def capture_sample(*, tenant_id: str, session_id: Optional[str], question: str,
                   answer: str, hit_ids: list) -> None:
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "INSERT INTO online_eval (tenant_id, session_id, question, answer, hit_ids) "
            "VALUES (%s, %s, %s, %s, %s)",
            (tenant_id, session_id, question, answer,
             ",".join(str(h) for h in hit_ids) if hit_ids else None),
        )
