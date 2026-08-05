import hashlib
import json
import psycopg
from typing import Optional
from helpmate.config import get_settings


def _conn():
    return psycopg.connect(get_settings().database_url)


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


def search(embedding: list[float], top_k: int) -> list[dict]:
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT ch.content, d.title FROM chunks ch "
            "JOIN documents d ON d.id = ch.document_id "
            "ORDER BY ch.embedding <=> %s::vector LIMIT %s",
            (json.dumps(embedding), top_k),
        )
        return [{"content": r[0], "title": r[1]} for r in cur.fetchall()]


def get_order(order_id: str) -> Optional[dict]:
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT order_id, customer, status, total FROM orders WHERE order_id = %s",
            (order_id,),
        )
        r = cur.fetchone()
        return None if r is None else {
            "order_id": r[0], "customer": r[1], "status": r[2], "total": float(r[3])
        }


def get_shipment(order_id: str) -> Optional[dict]:
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT order_id, carrier, tracking_no, status, eta FROM shipments WHERE order_id = %s",
            (order_id,),
        )
        r = cur.fetchone()
        return None if r is None else {
            "order_id": r[0], "carrier": r[1], "tracking_no": r[2],
            "status": r[3], "eta": str(r[4]) if r[4] else None,
        }


def fetch_unembedded(limit: int = 64) -> list[tuple[int, str]]:
    with _conn() as c, c.cursor() as cur:
        cur.execute("SELECT id, content FROM chunks WHERE embedding IS NULL ORDER BY id LIMIT %s", (limit,))
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
    params = [json.dumps(embedding)] + ([tenant_id] if tenant_id else []) + [n]
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
