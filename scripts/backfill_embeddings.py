"""Backfill NULL chunk embeddings via Qwen3-Embedding, in batches."""
from helpmate.retrieve.embed import get_embedder
from helpmate import db

BATCH = 32


def main() -> None:
    embedder = get_embedder()
    done = 0
    while True:
        rows = db.fetch_unembedded(BATCH)
        if not rows:
            break
        ids = [r[0] for r in rows]
        vecs = embedder.embed_batch([r[1] for r in rows])
        for cid, v in zip(ids, vecs):
            db.update_embedding(cid, v)
        done += len(rows)
        print(f"embedded {done} chunks...")
    print(f"DONE: {done} chunks embedded")


if __name__ == "__main__":
    main()
