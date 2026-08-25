from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

GLM_BASE_URL = "https://api.z.ai/api/paas/v4/"  # z.ai international endpoint
SILICONFLOW_ROUTER_MODEL = "Qwen/Qwen3-8B"      # small, fast, reliable tool-calling


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://helpmate:helpmate@localhost:5432/helpmate"
    llm_provider: str = "openai"          # "openai" | "glm" (any OpenAI-compatible)
    llm_base_url: str = ""                 # explicit override; blank = provider default
    llm_model: str = "glm-4.7"             # z.ai; thinking-on (disabling it corrupts output)
    # Tool routing is classification, not generation: a small model picks the same
    # branch as glm-4.7 on the golden set at a quarter of the latency.
    router_provider: str = "siliconflow"   # "siliconflow" | "llm" (reuse the answer model)
    router_model: str = ""                 # blank = the provider's default, see router_model_name()
    embed_provider: str = "siliconflow"          # "siliconflow" | "local"
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.com/v1"
    embed_model: str = "Qwen/Qwen3-Embedding-8B"
    embed_dim: int = 1024
    rerank_model: str = "Qwen/Qwen3-Reranker-8B"
    retrieve_candidates: int = 20                # per-retriever top-N before fusion
    openai_api_key: str = ""
    glm_api_key: str = ""
    top_k: int = 4                               # final chunks handed to the LLM
    llm_timeout_s: float = 120.0                 # per-call timeout for the LLM provider
    llm_max_retries: int = 2                     # provider-side retries on transient errors

    # identity & authorization
    # API key -> "tenant" or "tenant:customer"; empty = dev mode (see auth.py).
    api_keys: dict = {}
    default_customer: str = "Alice"              # dev-mode order identity (matches db/seed.sql)

    # governance & ops
    default_tenant: str = "public"               # tenant used in dev mode
    guardrails_enabled: bool = True              # input/output guardrails on /chat
    ingest_max_chunks: int = 2000                # cap on chunks embedded per /ingest call
    session_history_turns: int = 6               # turns loaded for multi-turn rewrite
    online_sample_rate: int = 10                 # % of /chat captured into online_eval (0=off)

    # evaluation
    eval_recall_k: int = 5                        # k for recall@k / ndcg@k
    eval_generate: bool = False                   # run generation-dependent metrics (citation/RAGAS); slow with glm-4.7
    # Thresholds sit ~3 points under the current baseline (recall@5 0.91 /
    # tool_routing 1.00) so a real regression fails the gate. A loose threshold
    # (the old 0.70) passes even after a 20-point drop — that is not a gate.
    eval_thresholds: dict = {"recall_at_k": 0.88, "tool_routing": 0.95,
                             "tenant_isolation": 1.0,
                             "faithfulness": 0.7, "answer_relevancy": 0.7}

    # observability (Langfuse)
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://us.cloud.langfuse.com"

    def resolved_base_url(self) -> Optional[str]:
        """Base URL for the OpenAI-compatible client; None uses the SDK default."""
        if self.llm_base_url:
            return self.llm_base_url
        if self.llm_provider == "glm":
            return GLM_BASE_URL
        return None

    def resolved_api_key(self) -> str:
        """Pick the key matching the provider, tolerating either env var."""
        if self.llm_provider == "glm":
            return self.glm_api_key or self.openai_api_key
        return self.openai_api_key or self.glm_api_key

    def router_model_name(self) -> str:
        """Routing model; blank `router_model` means "whatever this provider uses".

        Without the fallback, flipping only `ROUTER_PROVIDER=llm` would send the
        SiliconFlow model name to z.ai and every /chat would 400 on `route`.
        """
        if self.router_model:
            return self.router_model
        if self.router_provider == "siliconflow":
            return SILICONFLOW_ROUTER_MODEL
        return self.llm_model

    def router_base_url(self) -> Optional[str]:
        """Base URL for the routing model; falls back to the answer model's provider."""
        if self.router_provider == "siliconflow":
            return self.siliconflow_base_url
        return self.resolved_base_url()

    def router_api_key(self) -> str:
        if self.router_provider == "siliconflow":
            return self.siliconflow_api_key
        return self.resolved_api_key()

    def embed_base_url(self) -> str:
        return self.siliconflow_base_url

    def embed_api_key(self) -> str:
        return self.siliconflow_api_key


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings. Cached: `/chat` reads settings a dozen times per
    request and re-parsing `.env` each time is pure waste. Call
    `get_settings.cache_clear()` after mutating the environment (tests do)."""
    return Settings()
