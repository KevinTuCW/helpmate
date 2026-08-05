# helpmate 评测报告

- 样本数: 50  ·  k=5  ·  模型: glm-4.7
- 生成类指标(引用/RAGAS): 本次跳过 (eval_generate=False，glm 生成过慢)

## 汇总指标

| 指标 | 值 | 阈值 | 结果 |
| --- | --- | --- | --- |
| recall_at_k | 0.9111 | 0.7 | ✅ |
| tool_routing | 1 | 0.9 | ✅ |
| faithfulness | None | 0.7 | — |
| answer_relevancy | None | 0.7 | — |
| mrr | 0.7926 |  |  |
| ndcg_at_k | 0.8226 |  |  |
| citation_precision | None |  |  |

## 门禁: PASS ✅