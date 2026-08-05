import json
import psycopg
from typing import Optional
from helpmate.config import get_settings


def _conn():
    return psycopg.connect(get_settings().database_url)


def insert_document(source_url: str, title: str, doc_type: str,
                    product: str | None, lang: str = "zh") -> int:
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "INSERT INTO documents (source_url, title, doc_type, product, lang) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (source_url, title, doc_type, product, lang),
        )
        return cur.fetchone()[0]


def insert_chunk_row(document_id: int, ch: dict) -> None:
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "INSERT INTO chunks (document_id, chunk_index, content, section_title, "
            "doc_type, product, source_url, lang) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (document_id, ch["chunk_index"], ch["content"], ch.get("section_title"),
             ch["doc_type"], ch.get("product"), ch.get("source_url"), ch.get("lang", "zh")),
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
