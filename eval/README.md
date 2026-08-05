# helpmate 评测集（golden set）

`golden.jsonl` — 每行一个 JSON 对象，人工校验定稿。字段：

| 字段 | 含义 |
| --- | --- |
| `id` | 唯一 id，如 `policy-001` |
| `category` | `spec` \| `policy` \| `troubleshoot` \| `howto` \| `order` |
| `question` | 中文问题（可含英文专有名词，如 OcuSync/RTH/DJI Care） |
| `expected_points` | `list[str]`，答案应覆盖的要点 |
| `gold_chunk_ids` | `list[int]`，应被检索命中的 chunk id（order 类可为空） |
| `expected_tool` | `null` \| `"query_order"` \| `"query_logistics"` |
| `notes` | 人工校验备注 |

流程：`build_golden.py`（GLM 从真实 chunk 起草，gold 来源即起草所据 chunk）→ **人工校验** → `golden.jsonl`。
评测：`run_eval.py`（检索 recall@k/MRR/nDCG + 工具路由 + 引用正确率）+ `ragas_eval.py`（RAGAS 生成质量）→ `report.md` / `report.json`。
