"""Draft a golden set from real chunks: GLM writes a Q whose answer is in the
chunk, plus expected_points. gold_chunk_ids = the source chunk (reliable).
Order-category tool questions are appended from a fixed template.
Outputs eval/golden.draft.jsonl for HUMAN VERIFICATION."""
import json
import re
import psycopg
from pathlib import Path
from helpmate.config import get_settings
from helpmate.providers import OpenAILLM

ROOT = Path(__file__).resolve().parents[1]
# how many drafts per doc_type -> maps to categories
PLAN = {"spec": ("spec", 25), "policy": ("policy", 25),
        "faq": ("troubleshoot", 25), "manual": ("howto", 20)}

PROMPT = (
    "你是 DJI 客服知识库的测试出题人。仅依据下面这段资料，写 1 个中文用户提问，"
    "以及答案应覆盖的 2-4 个要点。问题要具体、像真实用户问法，可含英文专有名词。"
    "严格输出 JSON：{{\"question\":\"...\",\"expected_points\":[\"...\"]}}。\n\n资料：\n{chunk}"
)


def _sample_chunks(doc_type: str, n: int) -> list[tuple[int, str]]:
    s = get_settings()
    with psycopg.connect(s.database_url) as c, c.cursor() as cur:
        cur.execute(
            "SELECT id, content FROM chunks WHERE doc_type=%s AND length(content)>120 "
            "ORDER BY id LIMIT %s", (doc_type, n))
        return [(r[0], r[1]) for r in cur.fetchall()]


def main() -> None:
    llm = OpenAILLM()
    out = (ROOT / "eval" / "golden.draft.jsonl").open("w", encoding="utf-8")
    i = 0
    for doc_type, (category, n) in PLAN.items():
        for cid, content in _sample_chunks(doc_type, n):
            raw = llm.complete(PROMPT.format(chunk=content[:1500]))
            m = re.search(r"\{.*\}", raw, re.S)
            if not m:
                continue
            try:
                obj = json.loads(m.group(0))
            except json.JSONDecodeError:
                continue
            i += 1
            rec = {"id": f"{category}-{i:03d}", "category": category,
                   "question": obj.get("question", "").strip(),
                   "expected_points": obj.get("expected_points", []),
                   "gold_chunk_ids": [cid], "expected_tool": None, "notes": ""}
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"{rec['id']}: {rec['question'][:40]}")
    # order/tool questions (fixed, gold via expected_tool)
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
    print(f"\nDONE: wrote eval/golden.draft.jsonl")


if __name__ == "__main__":
    main()
