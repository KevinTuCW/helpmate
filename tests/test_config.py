from helpmate.config import Settings, GLM_BASE_URL


def test_settings_defaults():
    s = Settings(_env_file=None)
    assert s.top_k == 4
    assert s.embed_dim == 1024
    assert s.llm_provider == "openai"


def test_resolved_defaults_openai():
    s = Settings(_env_file=None, openai_api_key="ok")
    assert s.resolved_base_url() is None
    assert s.resolved_api_key() == "ok"


def test_resolved_glm_uses_glm_base_url_and_key():
    s = Settings(_env_file=None, llm_provider="glm", glm_api_key="gk")
    assert s.resolved_base_url() == GLM_BASE_URL
    assert s.resolved_api_key() == "gk"


def test_explicit_base_url_overrides_provider_default():
    s = Settings(_env_file=None, llm_provider="glm", llm_base_url="http://x/v1")
    assert s.resolved_base_url() == "http://x/v1"
