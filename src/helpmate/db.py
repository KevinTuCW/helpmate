import json
import psycopg
from typing import Optional
from helpmate.config import get_settings


def _conn():
    return psycopg.connect(get_settings().database_url)


def insert_document(source: str, title: str) -> int:
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "INSERT INTO documents (source, title) VALUES (%s, %s) RETURNING id",
            (source, title),
        )
        return cur.fetchone()[0]


def insert_chunk(document_id: int, chunk_index: int, content: str, embedding: list[float]) -> None:
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "INSERT INTO chunks (document_id, chunk_index, content, embedding) "
            "VALUES (%s, %s, %s, %s)",
            (document_id, chunk_index, content, json.dumps(embedding)),
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
