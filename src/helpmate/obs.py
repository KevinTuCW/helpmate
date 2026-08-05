"""Langfuse observability setup.

Import this module before any OpenAI client is used so the `langfuse.openai`
drop-in can auto-trace GLM chat and Qwen3 embedding calls as generations.
"""
import os
import re
from helpmate.config import get_settings

_SECRET_KEYS = {"customer", "api_key", "authorization", "secret_key", "password"}


def mask(data):
    """Redact obvious PII/secrets from traced inputs/outputs (recursive)."""
    if isinstance(data, dict):
        return {k: ("***" if k.lower() in _SECRET_KEYS else mask(v)) for k, v in data.items()}
    if isinstance(data, list):
        return [mask(x) for x in data]
    if isinstance(data, str):
        return re.sub(r"(?i)(bearer\s+)\S+", r"\1***", data)
    return data


_client = None


def init():
    """Initialize the global Langfuse client from settings (idempotent)."""
    global _client
    if _client is not None:
        return _client
    s = get_settings()
    # Expose creds to the langfuse.openai drop-in, which resolves via get_client().
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", s.langfuse_public_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", s.langfuse_secret_key)
    os.environ.setdefault("LANGFUSE_HOST", s.langfuse_base_url)
    from langfuse import Langfuse
    _client = Langfuse(
        public_key=s.langfuse_public_key,
        secret_key=s.langfuse_secret_key,
        host=s.langfuse_base_url,
        environment="development",
        mask=mask,
    )
    return _client


def client():
    return init()


# Initialize on import so tracing is active everywhere the app imports helpmate.obs.
init()
