from helpmate.config import Settings


def test_settings_defaults():
    s = Settings(_env_file=None)
    assert s.top_k == 4
    assert s.embed_dim == 1536
    assert s.llm_provider == "openai"
