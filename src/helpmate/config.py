from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

GLM_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://helpmate:helpmate@localhost:5432/helpmate"
    llm_provider: str = "openai"          # "openai" | "glm" (any OpenAI-compatible)
    llm_base_url: str = ""                 # explicit override; blank = provider default
    llm_model: str = "gpt-4o-mini"
    embed_model: str = "text-embedding-3-small"
    embed_dim: int = 1536
    openai_api_key: str = ""
    glm_api_key: str = ""
    top_k: int = 4

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


def get_settings() -> Settings:
    return Settings()
