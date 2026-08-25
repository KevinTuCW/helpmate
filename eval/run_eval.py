"""Run the golden set through helpmate: retrieval + generation, compute custom
metrics, write eval/report.json + eval/report.md. RAGAS scores merged by
ragas_eval.py if present."""
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from helpmate.config import get_settings
from helpmate.retrieve.hybrid import hybrid_retrieve
from helpmate.retrieve.context import format_context
from helpmate import db
from helpmate.tools import TOOL_SCHEMAS
from helpmate.providers import OpenAILLM
from helpmate.graph import build_prompt
from eval.metrics import (recall_at_k, mrr, ndcg_at_k, tool_correct,
                          parse_citations, citation_precision)

ROOT = Path(__file__).resolve().parents[1]


def _load_golden():
    return [json.loads(l) for l in (ROOT / "eval" / "golden.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


def _gold_ids(item: dict, tenant_id: str) -> list[int]:
    """Ground-truth chunk ids for one golden item.

    Prefers `gold_anchors` (source_url + section_title + chunk_index), which
    survive a re-ingest, and falls back to the recorded `gold_chunk_ids` for
    items not yet relinked (see eval/relink_golden.py). Keying a golden set on
    a serial primary key means any chunking change silently invalidates it.
    """
    anchors = item.get("gold_anchors")
    if not anchors:
        return item.get("gold_chunk_ids", [])
    resolved: list[int] = []
    for a in anchors:
        resolved.extend(db.chunk_ids_for_anchor(a, tenant_id))
    return resolved or item.get("gold_chunk_ids", [])


def evaluate() -> dict:
    s = get_settings()
    k = s.eval_recall_k
    tenant = s.default_tenant
    llm = OpenAILLM()
    rows = []
    for item in _load_golden():
        q = item["question"]
        rec = {"id": item["id"], "category": item["category"]}
        if item["category"] == "order":
            call = llm.select_tool(q, TOOL_SCHEMAS)
            rec["tool_correct"] = tool_correct(call["name"] if call else None, item["expected_tool"])
        elif item["category"] == "isolation":
            # Negative case: the same question asked as a foreign tenant must
            # retrieve nothing. Tenant filtering is a v1 claim, so it is gated.
            foreign = item.get("foreign_tenant", "__no_such_tenant__")
            rec["isolation_ok"] = 0.0 if hybrid_retrieve(q, tenant_id=foreign) else 1.0
        else:
            # Retrieve as the tenant under test: the eval must exercise the same
            # tenant-filtered path production uses, not an unfiltered one.
            hits = hybrid_retrieve(q, tenant_id=tenant)
            ret_ids = [h["chunk_id"] for h in hits]
            gold = _gold_ids(item, tenant)
            rec["recall_at_k"] = recall_at_k(ret_ids, gold, k)
            rec["mrr"] = mrr(ret_ids, gold)
            rec["ndcg_at_k"] = ndcg_at_k(ret_ids, gold, k)
            if s.eval_generate:  # generation-dependent metrics (slow with glm-4.7)
                answer = llm.complete(build_prompt(q, format_context(hits)))
                rec["citation_precision"] = citation_precision(parse_citations(answer, hits), gold)
                rec["_eval_row"] = {"question": q, "answer": answer,
                                    "contexts": [h["content"] for h in hits],
                                    "ground_truth": " ".join(item.get("expected_points", []))}
        rows.append(rec)
        if item["category"] == "order":
            tag = "tool " + str(rec.get("tool_correct"))
        elif item["category"] == "isolation":
            tag = "isolation " + str(rec.get("isolation_ok"))
        else:
            tag = "recall@%d=%.2f" % (k, rec.get("recall_at_k", 0))
        print(f"{rec['id']}: {tag}")

    def agg(metric):
        vals = [r[metric] for r in rows if metric in r]
        return round(mean(vals), 4) if vals else None

    summary = {"n": len(rows),
               "recall_at_k": agg("recall_at_k"), "mrr": agg("mrr"),
               "ndcg_at_k": agg("ndcg_at_k"), "citation_precision": agg("citation_precision"),
               "tool_routing": agg("tool_correct"),
               "tenant_isolation": agg("isolation_ok")}
    eval_rows = [r.pop("_eval_row") for r in rows if "_eval_row" in r]
    try:
        from eval.ragas_eval import run_ragas
        summary["ragas"] = run_ragas(eval_rows) if eval_rows else {}
    except Exception as e:  # RAGAS is best-effort; custom metrics are the core gate
        summary["ragas"] = {"error": str(e)[:200]}
    report = {"k": k, "summary": summary, "rows": rows}
    (ROOT / "eval" / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def write_markdown(report: dict) -> list[str]:
    s = get_settings()
    summ = report["summary"]
    lines = ["# helpmate 评测报告", "",
             f"- 样本数: {summ['n']}  ·  k={report['k']}  ·  生成模型: {s.llm_model}"
             f"  ·  路由模型: {s.router_model}",
             f"- 生成类指标(引用/RAGAS): {'已启用' if s.eval_generate else '本次跳过 (eval_generate=False，glm 生成过慢)'}",
             "", "## 汇总指标", "", "| 指标 | 值 | 阈值 | 结果 |", "| --- | --- | --- | --- |"]
    fails = []
    ragas = summ.get("ragas") or {}
    checks = {"recall_at_k": summ["recall_at_k"], "tool_routing": summ["tool_routing"],
              "tenant_isolation": summ.get("tenant_isolation"),
              "faithfulness": ragas.get("faithfulness"),
              "answer_relevancy": ragas.get("answer_relevancy")}
    for name, val in checks.items():
        thr = s.eval_thresholds.get(name)
        ok = (val is not None and thr is not None and val >= thr)
        if val is not None and thr is not None and not ok:
            fails.append(name)
        lines.append(f"| {name} | {val} | {thr} | {'✅' if ok else ('—' if val is None else '❌')} |")
    for extra in ("mrr", "ndcg_at_k", "citation_precision"):
        lines.append(f"| {extra} | {summ.get(extra)} |  |  |")
    if ragas and "error" not in ragas:
        lines += ["", "## RAGAS", ""] + [f"- {m}: {v}" for m, v in ragas.items()]
    lines += ["", f"## 门禁: {'PASS ✅' if not fails else 'FAIL ❌ (' + ', '.join(fails) + ')'}"]
    (ROOT / "eval" / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return fails


if __name__ == "__main__":
    r = evaluate()
    fails = write_markdown(r)
    print("\nSUMMARY:", json.dumps(r["summary"], ensure_ascii=False))
    print("GATE:", "PASS" if not fails else f"FAIL ({fails})")
