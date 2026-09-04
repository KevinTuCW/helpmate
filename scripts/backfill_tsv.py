"""Recompute content_tsv for every chunk after 003_cjk_fts.sql.

Pure local work — no embedding calls, no API cost. Safe to re-run: it simply
overwrites each row with the current output of `segment()`, so it doubles as the
way to reindex after changing the segmentation rules.
"""
from helpmate import db
from helpmate.retrieve.segment import segment

BATCH = 200


def main() -> None:
    done = 0
    with db._conn() as c:
        while True:
            with c.cursor() as cur:
                cur.execute(
                    "SELECT id, content FROM chunks WHERE content_tsv IS NULL LIMIT %s",
                    (BATCH,),
                )
                rows = cur.fetchall()
            if not rows:
                break
            with c.cursor() as cur:
                for cid, content in rows:
                    cur.execute(
                        "UPDATE chunks SET content_tsv = to_tsvector('simple', %s) WHERE id = %s",
                        (segment(content), cid),
                    )
            done += len(rows)
            print(f"  {done} chunks")
    print(f"backfilled {done} chunks")


if __name__ == "__main__":
    main()
