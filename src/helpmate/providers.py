import hashlib
import json
import math
import re
from typing import Optional
from helpmate.config import get_settings


class LocalHashingEmbedder:
    """Dependency-free bag-of-words hashing embedder, L2-normalized.

    Not semantic — tokens hash into a fixed number of buckets — but it needs no
    model or API and retrieves correctly for term-overlapping queries, so the
    RAG pipeline can be exercised locally. Swap in a real embedder for prod.
    """

    def __init__(self) -> None:
        self._dim = get_settings().embed_dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        for tok in re.findall(r"\w+", text.lower()):
            bucket = int(hashlib.md5(tok.encode()).hexdigest(), 16) % self._dim
            vec[bucket] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


def _client():
    """An OpenAI-compatible client pointed at the configured provider (OpenAI or GLM).

    Uses the langfuse.openai drop-in so chat/tool-call completions are auto-traced
    as `generation` observations (model, tokens, latency) under the current trace.
    """
    from langfuse.openai import OpenAI
    s = get_settings()
    # Timeout + retries are not optional on a customer-facing path: without them
    # one hung upstream request hangs the whole /chat call.
    return OpenAI(base_url=s.resolved_base_url(), api_key=s.resolved_api_key() or None,
                  timeout=s.llm_timeout_s, max_retries=s.llm_max_retries)


class OpenAIEmbedder:
    def __init__(self) -> None:
        s = get_settings()
        self._c = _client()
        self._model = s.embed_model
        self._dim = s.embed_dim

    def embed(self, text: str) -> list[float]:
        # `dimensions` is supported by OpenAI text-embedding-3-* and GLM embedding-3,
        # letting us pin the output length to the schema's VECTOR(dim).
        r = self._c.embeddings.create(model=self._model, input=text, dimensions=self._dim)
        return r.data[0].embedding


class OpenAILLM:
    def __init__(self) -> None:
        self._c = _client()
        self._model = get_settings().llm_model

    def complete(self, prompt: str) -> str:
        r = self._c.chat.completions.create(
            model=self._model, messages=[{"role": "user", "content": prompt}],
            name="generate-answer",
        )
        return r.choices[0].message.content or ""

    def select_tool(self, question: str, schemas: list[dict]) -> Optional[dict]:
        r = self._c.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": question}],
            tools=schemas,
            tool_choice="auto",
            name="route-select-tool",
        )
        msg = r.choices[0].message
        if msg.tool_calls:
            tc = msg.tool_calls[0]
            return {"name": tc.function.name, "args": json.loads(tc.function.arguments)}
        return None


def get_embedder():
    """Pick the embedder backend: 'local' hashing, or the OpenAI-compatible one."""
    if get_settings().embed_provider == "local":
        return LocalHashingEmbedder()
    return OpenAIEmbedder()
