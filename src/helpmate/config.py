from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://helpmate:helpmate@localhost:5432/helpmate"
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    embed_model: str = "text-embedding-3-small"
    embed_dim: int = 1536
    openai_api_key: str = ""
    top_k: int = 4


def get_settings() -> Settings:
    return Settings()
