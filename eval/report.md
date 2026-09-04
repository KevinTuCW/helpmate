# helpmate 评测报告

- 样本数: 53  ·  k=5  ·  生成模型: glm-4.7  ·  路由模型: Qwen/Qwen3-8B
- 生成类指标(引用/RAGAS): 本次跳过 (eval_generate=False，glm 生成过慢)

## 汇总指标

| 指标 | 值 | 阈值 | 结果 |
| --- | --- | --- | --- |
| recall_at_k | 0.9333 | 0.88 | ✅ |
| tool_routing | 1 | 0.95 | ✅ |
| tenant_isolation | 1.0 | 1.0 | ✅ |
| faithfulness | None | 0.7 | — |
| answer_relevancy | None | 0.7 | — |
| mrr | 0.8 |  |  |
| ndcg_at_k | 0.8337 |  |  |
| citation_precision | None |  |  |

## 门禁: PASS ✅