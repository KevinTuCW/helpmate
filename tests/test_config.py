from helpmate.config import Settings, GLM_BASE_URL


def test_settings_defaults():
    s = Settings(_env_file=None)
    assert s.top_k == 4
    assert s.embed_dim == 1024
    assert s.embed_provider == "siliconflow"
    assert s.embed_model == "Qwen/Qwen3-Embedding-8B"
    assert s.rerank_model == "Qwen/Qwen3-Reranker-8B"


def test_eval_thresholds_sit_close_to_the_measured_baseline():
    # A threshold 20 points below the baseline is decoration, not a gate.
    s = Settings(_env_file=None)
    assert s.eval_recall_k == 5
    assert s.eval_thresholds["recall_at_k"] == 0.88
    assert s.eval_thresholds["tool_routing"] == 0.95
    assert s.eval_thresholds["tenant_isolation"] == 1.0


def test_embed_endpoint_defaults_to_siliconflow_com():
    s = Settings(_env_file=None, siliconflow_api_key="sk-x")
    assert s.embed_base_url() == "https://api.siliconflow.com/v1"
    assert s.embed_api_key() == "sk-x"


def test_router_defaults_to_a_small_siliconflow_model():
    # Routing is classification, so it deliberately does not ride the answer model.
    s = Settings(_env_file=None, llm_provider="glm", glm_api_key="gk",
                 siliconflow_api_key="sk-x")
    assert s.router_model_name() == "Qwen/Qwen3-8B"
    assert s.router_base_url() == "https://api.siliconflow.com/v1"
    assert s.router_api_key() == "sk-x"
    assert s.router_base_url() != s.resolved_base_url()


def test_router_provider_llm_falls_back_to_the_answer_model_too():
    # Endpoint *and* model have to move together: pointing routing at z.ai while
    # still naming a SiliconFlow model 400s every request on `route`.
    s = Settings(_env_file=None, router_provider="llm", llm_provider="glm",
                 glm_api_key="gk", siliconflow_api_key="sk-x")
    assert s.router_base_url() == GLM_BASE_URL
    assert s.router_api_key() == "gk"
    assert s.router_model_name() == s.llm_model


def test_explicit_router_model_overrides_the_provider_default():
    s = Settings(_env_file=None, router_provider="llm", llm_provider="glm",
                 router_model="glm-4-flash")
    assert s.router_model_name() == "glm-4-flash"


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
