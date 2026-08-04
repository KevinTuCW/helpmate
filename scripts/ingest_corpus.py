"""Ingest every source in corpus/manifest.jsonl via ingest.pipeline."""
import json
from pathlib import Path
from helpmate.ingest.pipeline import ingest_source

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    manifest = ROOT / "corpus" / "manifest.jsonl"
    total_docs = total_chunks = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        path = ROOT / rec["path"]
        meta = {"source_url": rec["url"], "title": rec["title"] or rec["url"],
                "doc_type": rec["doc_type"], "product": rec["product"] or None, "lang": "zh"}
        if rec["kind"] == "pdf":
            r = ingest_source(kind="pdf", path_or_html=str(path), meta=meta)
        else:
            r = ingest_source(kind="html", path_or_html=path.read_text(encoding="utf-8", errors="ignore"), meta=meta)
        total_docs += 1
        total_chunks += r["chunks"]
        print(f"{rec['doc_type']:7} {rec['title'][:40]:40} -> {r['chunks']} chunks")
    print(f"\nTOTAL: {total_docs} docs, {total_chunks} chunks")


if __name__ == "__main__":
    main()
