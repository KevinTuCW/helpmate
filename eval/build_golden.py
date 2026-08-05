"""Draft a golden set from real chunks: GLM writes a Q whose answer is in the
chunk, plus expected_points. gold_chunk_ids = the source chunk (reliable).
Categories map to the Chinese corpus's actual doc_types (policy/faq/manual);
order-category tool questions are appended from a fixed template.
Runs GLM calls concurrently. Outputs eval/golden.draft.jsonl for HUMAN VERIFICATION."""
import json
import re
import time
import psycopg
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from helpmate.config import get_settings
from helpmate.providers import OpenAILLM

ROOT = Path(__file__).resolve().parents[1]
# (category, doc_type, n) — categories match the Chinese corpus's real doc_types
PLAN = [("policy", "policy", 8), ("faq", "faq", 15), ("manual", "manual", 27)]

PROMPT = (
    "你是 DJI 客服知识库的测试出题人。仅依据下面这段资料，写 1 个中文用户提问，"
    "以及答案应覆盖的 2-4 个要点。问题要具体、像真实用户问法，可含英文专有名词。"
    "严格只输出 JSON：{{\"question\":\"...\",\"expected_points\":[\"...\"]}}。\n\n资料：\n{chunk}"
)

_llm = OpenAILLM()


def _sample(doc_type: str, n: int) -> list[tuple[int, str]]:
    s = get_settings()
    with psycopg.connect(s.database_url) as c, c.cursor() as cur:
        cur.execute(
            "SELECT id, content FROM chunks WHERE doc_type=%s AND length(content)>120 "
            "ORDER BY id LIMIT %s", (doc_type, n))
        return cur.fetchall()


def _extract_json(raw: str) -> dict | None:
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.S)
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _draft(task: tuple) -> dict | None:
    category, cid, content = task
    prompt = PROMPT.format(chunk=content[:1500])
    obj = None
    for attempt in range(4):
        try:
            obj = _extract_json(_llm.complete(prompt))
            break
        except Exception as e:  # retry on 429 rate limits with backoff
            if "429" in str(e) and attempt < 3:
                time.sleep(4 * (attempt + 1) + (cid % 5))
                continue
            print(f"skip {category} {cid}: {str(e)[:60]}")
            return None
    if not obj or not obj.get("question"):
        return None
    return {"category": category, "gold_chunk_ids": [cid],
            "question": obj["question"].strip(),
            "expected_points": obj.get("expected_points", []),
            "expected_tool": None, "notes": ""}


def main() -> None:
    tasks = [(cat, cid, content) for cat, dt, n in PLAN for cid, content in _sample(dt, n)]
    with ThreadPoolExecutor(max_workers=3) as ex:
        results = [r for r in ex.map(_draft, tasks) if r]

    out = (ROOT / "eval" / "golden.draft.jsonl").open("w", encoding="utf-8")
    counters: dict = {}
    for r in results:
        counters[r["category"]] = counters.get(r["category"], 0) + 1
        r["id"] = f"{r['category']}-{counters[r['category']]:03d}"
        out.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(r["id"], r["question"][:36])
    for j, (q, tool) in enumerate([
            ("我的订单 A1001 到哪了？", "query_logistics"),
            ("订单 A1001 的物流状态是什么？", "query_logistics"),
            ("帮我查一下订单 A1002 的状态", "query_order"),
            ("A1001 这个订单发货了吗？", "query_logistics"),
            ("订单 A1002 多少钱？", "query_order")], start=1):
        rec = {"id": f"order-{j:03d}", "category": "order", "question": q,
               "expected_points": [], "gold_chunk_ids": [], "expected_tool": tool, "notes": ""}
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
    out.close()
    print(f"\nDONE: {len(results)} content drafts + 5 order = {len(results)+5}")


if __name__ == "__main__":
    main()
