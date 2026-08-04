"""Fetch the DJI corpus listed in corpus/sources.tsv.

sources.tsv columns (tab-separated, one source per line):
    url    doc_type    product    title
Saves each page to corpus/raw/<n>.html (or .pdf) and appends a JSON line to
corpus/manifest.jsonl with its metadata + local path.
"""
import json
import sys
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "corpus"
RAW = CORPUS / "raw"


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    src = CORPUS / "sources.tsv"
    if not src.exists():
        sys.exit("corpus/sources.tsv not found — populate it with real DJI URLs first")
    manifest = (CORPUS / "manifest.jsonl").open("w", encoding="utf-8")
    with httpx.Client(follow_redirects=True, timeout=30,
                      headers={"User-Agent": "helpmate-corpus/0.1"}) as client:
        for i, line in enumerate(src.read_text(encoding="utf-8").splitlines()):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            url, doc_type, product, title = (line.split("\t") + ["", "", ""])[:4]
            ext = "pdf" if url.lower().endswith(".pdf") else "html"
            try:
                r = client.get(url)
                r.raise_for_status()
            except Exception as e:  # noqa: BLE001 — log and continue the batch
                print(f"SKIP {url}: {e}")
                continue
            path = RAW / f"{i}.{ext}"
            path.write_bytes(r.content)
            rec = {"url": url, "doc_type": doc_type, "product": product,
                   "title": title, "kind": ext, "path": str(path.relative_to(ROOT))}
            manifest.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"OK   {url} -> {path.name}")
    manifest.close()


if __name__ == "__main__":
    main()
