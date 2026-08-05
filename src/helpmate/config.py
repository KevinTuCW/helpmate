from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

GLM_BASE_URL = "https://api.z.ai/api/paas/v4/"  # z.ai international endpoint


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://helpmate:helpmate@localhost:5432/helpmate"
    llm_provider: str = "openai"          # "openai" | "glm" (any OpenAI-compatible)
    llm_base_url: str = ""                 # explicit override; blank = provider default
    llm_model: str = "glm-4.7"             # z.ai; thinking-on (disabling it corrupts output)
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

    # governance & ops
    default_tenant: str = "public"               # tenant used when a request omits one
    guardrails_enabled: bool = True              # input/output guardrails on /chat
    session_history_turns: int = 6               # turns loaded for multi-turn rewrite
    online_sample_rate: int = 10                 # % of /chat captured into online_eval (0=off)

    # evaluation
    eval_recall_k: int = 5                        # k for recall@k / ndcg@k
    eval_generate: bool = False                   # run generation-dependent metrics (citation/RAGAS); slow with glm-4.7
    eval_thresholds: dict = {"recall_at_k": 0.7, "tool_routing": 0.9,
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

    def embed_base_url(self) -> str:
        return self.siliconflow_base_url

    def embed_api_key(self) -> str:
        return self.siliconflow_api_key


def get_settings() -> Settings:
    return Settings()
