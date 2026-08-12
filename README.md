<div align="center">

# 🛟 helpmate

**生产级企业知识库智能客服** —— 真实中文语料 · 混合检索 + 重排 · 带引用问答 · 安全护栏 + 多租户 + 审计 · 多轮会话 · 全链路可观测 · 可复现评测（工具调用为辅）

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
- 📊 **可复现评测** —— 50 条人工校验 golden set（+3 条跨租户负例）+ recall@k / MRR / nDCG / 工具路由 / 租户隔离 / 引用指标 + 贴基线阈值；golden 支持内容锚点，重灌库不失效。CI 硬门禁是单测（pytest），指标门禁跑本地/夜跑。
- 🛡️ **安全护栏** —— 输入拦注入 / 越狱 / 越权诱导，输出脱敏 + 违规内容拦截；纯规则、零额外延迟。
- 🧾 **审计留痕** —— 每次 `/chat` 落一条不可变审计（租户 / 会话 / 决策 / 护栏结果 + 答案哈希）；问题侧先脱敏再入库，可回溯而不留明文 PII。
- 🏢 **身份与授权** —— 调用方身份来自 API Key（`X-API-Key`）而非请求体：检索按 `tenant_id` 过滤，**订单/物流按 `customer_id` 做行级归属校验**，报一个陌生单号只会得到「未找到」。未配 `API_KEYS` 时为本地 dev 身份，克隆即跑。
- 💬 **多轮会话** —— 会话历史改写指代（「它 / 这款」），改写只喂检索、不多花一次思考调用。
- 🧹 **语料清洗 + 在线采样** —— 摄取阶段剥离导航/页脚 boilerplate；按比例采样线上流量回流待评。

## 🏗️ 架构

```text
用户问题 ─▶ 输入护栏 ─▶ [多轮改写] ─▶ route（GLM 判意图）
              ├─ 知识类（主）─▶ retrieve 混合检索（按 tenant 过滤）─▶ rerank（Qwen3）─┐
              │      dense pgvector(HNSW) + sparse tsvector(GIN) → RRF 融合
              └─ 订单/物流（辅）─▶ act：query_order / query_logistics ─┤
                                                                       ▼
                    generate（GLM）─▶ 输出护栏 ─▶ 带[n]引用的答案 ─▶ 审计留痕 + 在线采样
```

- **摄取路径**：`loaders → clean → chunking → pipeline → Qwen3 embed → Postgres`
- **应答路径**：`护栏(in) → [多轮改写] → route → (act | retrieve → rerank) → generate → 护栏(out) → 审计`，由 LangGraph 编排，Langfuse 全程埋点。

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
# 1. 建库并应用 schema（含 governance/ops 表；维度需与 EMBED_DIM 一致）
psql "$DATABASE_URL" -v dim=1024 -f db/schema.sql
psql "$DATABASE_URL" -f db/seed.sql
# 已有旧库、不想重灌语料？改用非破坏迁移：
# psql "$DATABASE_URL" -f db/migrations/001_governance_ops.sql
# psql "$DATABASE_URL" -f db/migrations/002_order_ownership.sql   # 订单归属列

# 2. 配置密钥
cp .env.example .env        # 填入 GLM / SiliconFlow / Langfuse key

# 3. 安装并构建知识库
pip install -e ".[dev]"
python scripts/fetch_corpus.py         # 抓取 DJI 语料（corpus/sources.tsv）
python scripts/ingest_corpus.py        # 摄取 → chunks
python scripts/backfill_embeddings.py  # Qwen3 回填向量 + 建 HNSW 索引

# 4. 启动服务
uvicorn helpmate.app:app --reload

# （可选）跑测试 —— CI 的硬门禁
make test        # 等价于 pytest -q
```

打开 <http://localhost:8000>，问一个知识库问题，或者「我的订单 A1001 到哪了？」。

## 💬 使用示例

```bash
# dev 模式（未配 API_KEYS）：身份 = DEFAULT_TENANT / DEFAULT_CUSTOMER
curl -X POST localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"question":"DJI Care 随心换进水了能保修吗？"}'

# 配了 API_KEYS 之后，身份走凭证（请求体不再接受 tenant_id）
curl -X POST localhost:8000/chat -H 'X-API-Key: sk-dji-alice' \
  -H 'Content-Type: application/json' -d '{"question":"我的订单 A1001 到哪了？"}'
```

```jsonc
// 知识类 → 混合检索，带引用
{ "answer": "DJI Care 随心换支持进水保修：保障场景明确包含意外进水 [3]…",
  "tool_call": null }

// 规格类 → 命中中文 PDF 手册的规格表
{ "answer": "DJI Mini 4 Pro 的最大起飞重量为 ＜249 g [1][2]。" }

// 订单类 → Function Calling（仅限调用方自己的订单）
{ "answer": "订单 A1001 目前运输中，预计送达 2026-08-06 [1]。",
  "tool_call": { "name": "query_logistics", "args": { "order_id": "A1001" } } }

// 别人的订单 → 归属校验在 SQL 里拦下，与「不存在」返回同一句，无法枚举
{ "answer": "没有查到订单 A1002 的信息。",
  "tool_call": { "name": "query_order", "args": { "order_id": "A1002" } } }
```

## 📊 评测

golden set 驱动的可复现评测闭环，一条命令出报告与门禁：

```bash
python eval/run_eval.py     # → eval/report.md
```

**最新基线**（53 条 = 50 条问答 + 3 条跨租户负例，`glm-4.7`，k=5）：

| 指标 | 值 | 阈值 | 结果 |
| --- | --- | --- | --- |
| recall@5 | **0.91** | 0.88 | ✅ |
| tool_routing | **1.00** | 0.95 | ✅ |
| tenant_isolation | 待重跑 | 1.00 | — |
| MRR | 0.79 | — | — |
| nDCG@5 | 0.82 | — | — |

> 阈值贴着基线留 ~3 个点余量：0.70 的旧阈值退化 20 个点仍会 PASS，那不是门禁。
> `tenant_isolation` 是新增的跨租户负例（同一问题以外部租户身份检索必须零命中）。
> 单测（`make test`）是 CI 硬门禁；`make gate` 这套指标需要真库 + 真 key，跑在本地/夜跑，不在 CI 内。

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
├── .github/workflows/ci.yml  # CI：pytest 硬门禁
├── Makefile                  # make test / gate / ci
├── db/
│   ├── schema.sql             # documents / chunks(+tenant) / orders / shipments / audit_log / session_turns / online_eval
│   ├── migrations/            # 001_governance_ops · 002_order_ownership（非破坏迁移）
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
│   ├── auth.py                # API Key → Principal(tenant, customer)
│   ├── db.py                  # 检索(租户过滤) / 订单(归属校验) / 审计 / 会话 / 采样
│   ├── ops.py                 # 确定性在线采样门
│   ├── security/
│   │   └── guardrails.py      # 输入/输出护栏（注入·越狱·越权·脱敏·违规）
│   ├── session/
│   │   └── memory.py          # 多轮指代消解 · 历史改写检索查询
│   ├── ingest/
│   │   ├── loaders.py         # HTML 清洗 · PDF+表格抽取 · 表格转 MD
│   │   ├── clean.py           # 语料 boilerplate 清洗
│   │   ├── chunking.py        # 分节 + 元数据分块（含 tenant_id）
│   │   └── pipeline.py        # 摄取编排（load → clean → chunk → write）
│   └── retrieve/
│       ├── embed.py           # Qwen3 嵌入客户端
│       ├── fuse.py            # RRF 融合
│       ├── rerank.py          # Qwen3 重排
│       ├── hybrid.py          # dense+FTS→RRF→rerank 编排
│       └── context.py         # 带引用的上下文拼装
├── eval/
│   ├── golden.jsonl           # 50 条人工校验评测集 + 3 条跨租户负例
│   ├── relink_golden.py       # chunk_id → 内容锚点(重灌库不失效)
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
| `API_KEYS` | JSON：API Key → `"tenant"` 或 `"tenant:customer"`；留空 = dev 模式 |
| `default_tenant` / `default_customer` | dev 模式下的租户 / 订单归属身份 |
| `guardrails_enabled` | 是否启用输入输出护栏 |
| `llm_timeout_s` / `llm_max_retries` | LLM 单次超时 / 重试次数 |
| `ingest_max_chunks` | 单次 `/ingest` 回填向量的 chunk 上限 |
| `session_history_turns` / `online_sample_rate` | 多轮改写载入的历史轮数 / 在线采样比例(%) |

## 🗺️ 路线图

- [x] **阶段①** 真实 DJI 中文语料 + 结构化 ingestion（含 boilerplate 清洗）
- [x] **阶段②** Qwen3 嵌入回填 + HNSW + dense/FTS/RRF + Qwen3 重排
- [x] **阶段③** 50 条 golden set + 指标 + 报告门禁（recall@5=0.91）+ CI（pytest 硬门禁）
- [x] **阶段④** Langfuse v4 全链路 trace
- [x] **阶段⑤** 治理层：输入/输出护栏 · 审计留痕(问题侧脱敏) · 多租户过滤 · API Key 身份 + 订单行级归属校验
- [x] **阶段⑥** 运营层：多轮会话 + 指代消解 · 在线采样回流
- [ ] 专题：检索父子块 + 元数据过滤（拉起 manual recall）
- [ ] 专题：延迟分级路由 + 流式（p50 38s → 面客可接受）
- [ ] 生成类指标默认开启（需更快的 judge 模型）
- [ ] 真多模态（图像 OCR / 视频转写）· 完整在线 A/B —— 阵 04

## 📄 许可证

[MIT](LICENSE) © helpmate
