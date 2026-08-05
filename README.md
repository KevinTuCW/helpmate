<div align="center">

# 🛟 helpmate

**生产级企业知识库智能客服** —— 真实中文语料 · 混合检索 + 重排 · 带引用问答 · 全链路可观测 · 可复现评测（工具调用为辅）

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](#-许可证)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-orchestration-1C3C3C.svg)](https://langchain-ai.github.io/langgraph/)
[![pgvector](https://img.shields.io/badge/pgvector-HNSW-336791.svg?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Langfuse](https://img.shields.io/badge/Langfuse-tracing-fbbf24.svg)](https://langfuse.com/)
[![recall@5](https://img.shields.io/badge/recall%405-0.91-brightgreen.svg)](#-评测)

「武道AI / AI Engineering Dojo」**以阵制胜**系列 · 阵 01 · 从 0 到 1 的真实业务系统

</div>

---

helpmate 是一个能「上线」的企业知识库客服系统。<strong>主线是知识问答</strong>：以 **DJI 大疆公开中文文档**（用户手册 / FAQ / 售后政策）为知识库，用**混合检索 + 重排**把问题答准并给出引用。<strong>Function Calling 是辅助</strong>，只为「查订单、查物流」这类少数实时问题补一条旁路，绝大多数问题走问答主路径。全流程在 **Langfuse** 可观测，并配一套**人工校验 golden set + 评测门禁**。它不是 demo —— 语料是真的，检索是混合的，指标是量化的。

## 📑 目录

- [✨ 特性](#-特性)
- [🏗️ 架构](#️-架构)
- [🧱 技术栈](#-技术栈)
- [🚀 快速开始](#-快速开始)
- [💬 使用示例](#-使用示例)
- [📊 评测](#-评测)
- [🔭 可观测](#-可观测)
- [📁 项目结构](#-项目结构)
- [🧩 配置](#-配置)
- [🗺️ 路线图](#️-路线图)
- [📄 许可证](#-许可证)

## ✨ 特性

- 🗂️ **真实中文语料** —— 17 篇 DJI 文档 → 926 个 chunk，中文为主、夹杂大量英文专有名词（OcuSync、RTH、DJI Care…）。
- 📄 **结构化 ingestion** —— HTML 清洗保留标题层级、PDF 表格用 PyMuPDF 抽取并转 Markdown、按章节切块并附元数据。
- 🔍 **混合检索** —— dense（Qwen3-Embedding）+ sparse（Postgres 全文）经 **RRF 融合**，再由 **Qwen3-Reranker** 重排。中文语义靠向量，英文专有名词靠全文，各司其职。
- 📌 **带引用的回答** —— 每条知识库回答都标注来源 `[n]`，无上下文即拒答。
- 🧰 **Function Calling（辅助）** —— 订单/物流类少数实时问题自动旁路到 `query_order` / `query_logistics` 工具，其余走知识问答主路径。
- 🔭 **全链路 Trace** —— 每次请求在 Langfuse 记录 route / retrieve / rerank / tool / generate，含模型、token、延迟。
- 📊 **可复现评测** —— 50 条人工校验 golden set + recall@k / MRR / nDCG / 工具路由 / 引用指标 + 阈值门禁。

## 🏗️ 架构

```text
用户问题 ─▶ route（GLM 判意图）
              ├─ 知识类（主）─▶ retrieve 混合检索 ─▶ rerank（Qwen3）─┐
              │      dense pgvector(HNSW) + sparse tsvector(GIN) → RRF 融合
              └─ 订单/物流（辅）─▶ act：query_order / query_logistics ─┤
                                                                       ▼
                                                   generate（GLM）─▶ 带[n]引用的答案
```

- **摄取路径**：`loaders → chunking → pipeline → Qwen3 embed → Postgres`
- **应答路径**：`route → (act | retrieve → rerank) → generate`，由 LangGraph 编排，Langfuse 全程埋点。

> 详细系统设计见 [`docs/architecture.md`](docs/architecture.md)，产品需求见 [`docs/prd.md`](docs/prd.md)。

## 🧱 技术栈

| 关注点 | 选型 |
| --- | --- |
| API / 编排 | FastAPI · LangGraph |
| 大模型 | **GLM-4.7**（z.ai，OpenAI 兼容） |
| 向量嵌入 | **Qwen3-Embedding-8B**（1024 维，SiliconFlow） |
| 重排 | **Qwen3-Reranker-8B**（SiliconFlow） |
| 存储 / 检索 | Postgres 16 + **pgvector**（HNSW）+ `tsvector`（GIN） |
| 摄取 | BeautifulSoup（HTML）· PyMuPDF（PDF + 表格）· 结构感知切块 |
| 可观测 | **Langfuse**（v4） |
| 评测 | 自建指标 + **RAGAS**（可选） |

> 所有 provider 均为 OpenAI 兼容，可通过 `.env` 平滑切换。

## 🚀 快速开始

**前置**：Python 3.12 · Postgres 16 + pgvector · GLM(z.ai) / SiliconFlow / Langfuse 三个 key。

```bash
# 1. 建库并应用 schema（维度需与 EMBED_DIM 一致）
psql "$DATABASE_URL" -v dim=1024 -f db/schema.sql
psql "$DATABASE_URL" -f db/seed.sql

# 2. 配置密钥
cp .env.example .env        # 填入 GLM / SiliconFlow / Langfuse key

# 3. 安装并构建知识库
pip install -e ".[dev]"
python scripts/fetch_corpus.py         # 抓取 DJI 语料（corpus/sources.tsv）
python scripts/ingest_corpus.py        # 摄取 → chunks
python scripts/backfill_embeddings.py  # Qwen3 回填向量 + 建 HNSW 索引

# 4. 启动服务
uvicorn helpmate.app:app --reload
```

打开 <http://localhost:8000>，问一个知识库问题，或者「我的订单 A1001 到哪了？」。

## 💬 使用示例

```bash
curl -X POST localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"question":"DJI Care 随心换进水了能保修吗？"}'
```

```jsonc
// 知识类 → 混合检索，带引用
{ "answer": "DJI Care 随心换支持进水保修：保障场景明确包含意外进水 [3]…",
  "tool_call": null }

// 规格类 → 命中中文 PDF 手册的规格表
{ "answer": "DJI Mini 4 Pro 的最大起飞重量为 ＜249 g [1][2]。" }

// 订单类 → Function Calling
{ "answer": "订单 A1001 目前运输中，预计送达 2026-08-06 [1]。",
  "tool_call": { "name": "query_logistics", "args": { "order_id": "A1001" } } }
```

## 📊 评测

golden set 驱动的可复现评测闭环，一条命令出报告与门禁：

```bash
python eval/run_eval.py     # → eval/report.md
```

**最新基线**（50 条，`glm-4.7`，k=5）：

| 指标 | 值 | 阈值 | 结果 |
| --- | --- | --- | --- |
| recall@5 | **0.91** | 0.70 | ✅ |
| tool_routing | **1.00** | 0.90 | ✅ |
| MRR | 0.79 | — | — |
| nDCG@5 | 0.82 | — | — |
| **门禁** | | | **PASS ✅** |

> 生成类指标（引用正确率 + RAGAS faithfulness/answer_relevancy）由 `eval_generate=True` 开启（judge=GLM、embeddings=Qwen3）。golden set 见 [`eval/golden.jsonl`](eval/golden.jsonl)。

## 🔭 可观测

每次 `/chat` 都是 Langfuse 里的一条 `chat-response` trace，观测树类型清晰：

- `generation` —— GLM 的 route / generate（自动记模型 + token）
- `embedding` —— Qwen3 向量化
- `retriever` —— `retrieve-context`（混合检索）
- `span` —— `rerank-candidates`
- `tool` —— `tool:query_logistics` / `tool:query_order`

trace 带 `session_id`、`tags`、`environment`，并对 PII/密钥递归脱敏。

## 📁 项目结构

```text
helpmate/
├── README.md
├── pyproject.toml
├── docker-compose.yml
├── .env.example
├── corpus/                    # DJI 语料来源清单 + manifest（raw 抓取物 gitignore）
│   ├── sources.tsv
│   └── manifest.jsonl
├── db/
│   ├── schema.sql             # documents / chunks(vector+tsvector) / orders / shipments
│   └── seed.sql
├── docs/
│   ├── prd.md                 # 产品需求
│   └── architecture.md        # 系统设计
├── scripts/
│   ├── fetch_corpus.py        # 抓取语料
│   ├── ingest_corpus.py       # 批量摄取
│   └── backfill_embeddings.py # 回填向量 + 建 HNSW
├── src/helpmate/
│   ├── app.py                 # FastAPI：/ingest /chat
│   ├── config.py              # pydantic-settings 配置
│   ├── obs.py                 # Langfuse 初始化 + 脱敏
│   ├── providers.py           # GLM LLM 客户端（langfuse.openai drop-in）
│   ├── tools.py               # Function Calling 工具 + 分发
│   ├── graph.py               # LangGraph 应答流
│   ├── db.py                  # 检索 / 订单 / 写入
│   ├── ingest/
│   │   ├── loaders.py         # HTML 清洗 · PDF+表格抽取 · 表格转 MD
│   │   ├── chunking.py        # 分节 + 元数据分块
│   │   └── pipeline.py        # 摄取编排
│   └── retrieve/
│       ├── embed.py           # Qwen3 嵌入客户端
│       ├── fuse.py            # RRF 融合
│       ├── rerank.py          # Qwen3 重排
│       ├── hybrid.py          # dense+FTS→RRF→rerank 编排
│       └── context.py         # 带引用的上下文拼装
├── eval/
│   ├── golden.jsonl           # 50 条人工校验评测集
│   ├── metrics.py             # recall@k / MRR / nDCG / 工具 / 引用（TDD）
│   ├── run_eval.py            # 评测 runner + 报告 + 门禁
│   ├── ragas_eval.py          # RAGAS 生成质量指标
│   └── report.md              # 最新评测报告
├── web/
│   └── index.html             # 极简聊天前端
└── tests/                     # pytest 单元测试
```

## 🧩 配置

`.env`（见 [`.env.example`](.env.example)）关键项：

| 变量 | 说明 |
| --- | --- |
| `DATABASE_URL` | Postgres 连接串 |
| `LLM_PROVIDER` / `LLM_MODEL` | `glm` / `glm-4.7`（z.ai，base URL 内置默认） |
| `GLM_API_KEY` | GLM(z.ai) 密钥 |
| `EMBED_MODEL` / `EMBED_DIM` | `Qwen/Qwen3-Embedding-8B` / `1024` |
| `RERANK_MODEL` | `Qwen/Qwen3-Reranker-8B` |
| `SILICONFLOW_API_KEY` | SiliconFlow 密钥 |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_BASE_URL` | Langfuse |
| `TOP_K` / `retrieve_candidates` | 最终/候选检索条数 |
| `eval_recall_k` / `eval_generate` / `eval_thresholds` | 评测参数 |

## 🗺️ 路线图

- [x] **阶段①** 真实 DJI 中文语料 + 结构化 ingestion
- [x] **阶段②** Qwen3 嵌入回填 + HNSW + dense/FTS/RRF + Qwen3 重排
- [x] **阶段③** 50 条 golden set + 指标 + 报告门禁（recall@5=0.91）
- [x] **阶段④** Langfuse v4 全链路 trace
- [ ] 生成类指标默认开启（需更快的 judge 模型）
- [ ] 语料 boilerplate 清洗 · 多轮会话 · 真多模态（图像/视频）

## 📄 许可证

[MIT](LICENSE) © helpmate
