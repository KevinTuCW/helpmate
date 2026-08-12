"""Relink the golden set from serial chunk ids to stable content anchors.

Why this exists
---------------
`gold_chunk_ids` are `chunks.id` values — a serial primary key. Re-ingesting the
corpus, changing the chunk size, or moving to another machine renumbers them,
and 50 hand-verified labels silently become wrong (recall looks like it fell off
a cliff, but nothing about retrieval changed). Anchors key on content instead:

    {"source_url": ..., "section_title": ..., "chunk_index": ...}

`run_eval` prefers `gold_anchors` when present and falls back to the recorded
ids, so this script is safe to run once against a populated database and then
forget about.

Usage (needs a live DB with the corpus ingested):
    python -m eval.relink_golden          # write gold_anchors into golden.jsonl
    python -m eval.relink_golden --check  # report coverage, change nothing
"""
import argparse
import json
from pathlib import Path

from helpmate import db

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "eval" / "golden.jsonl"


def load() -> list[dict]:
    return [json.loads(line) for line in
            GOLDEN.read_text(encoding="utf-8").splitlines() if line.strip()]


def save(items: list[dict]) -> None:
    GOLDEN.write_text(
        "".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items),
        encoding="utf-8")


def relink(items: list[dict], check_only: bool = False) -> dict:
    linked = missing = skipped = 0
    for item in items:
        ids = item.get("gold_chunk_ids") or []
        if not ids:
            skipped += 1
            continue
        anchors = db.anchors_for_chunk_ids(ids)
        if len(anchors) != len(ids):
            missing += 1
            print(f"! {item['id']}: resolved {len(anchors)}/{len(ids)} chunk ids "
                  f"— re-ingest first, or fix the label by hand")
            continue
        if not check_only:
            item["gold_anchors"] = anchors
        linked += 1
    return {"linked": linked, "unresolved": missing, "no_gold": skipped}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="report coverage without writing the file")
    args = ap.parse_args()

    items = load()
    stats = relink(items, check_only=args.check)
    if not args.check:
        save(items)
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
