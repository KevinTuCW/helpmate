import hashlib
import json
import math
import re
from typing import Optional
from helpmate.config import get_settings

# A small router left unprompted invents an order id (literally `order_id`) for
# knowledge-base questions and routes them to the tool. Spelling out the "no id,
# no tool" rule takes the golden-set routing score from 0.98 back to 1.00 and
# shortens the reply, so the call also gets faster.
ROUTER_SYSTEM = (
    "Call a tool only when the user asks about a specific order and the message "
    "contains an actual order id. Otherwise answer nothing and call no tool. "
    "Never invent or guess an order id."
)


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


def _client(base_url: Optional[str] = None, api_key: Optional[str] = None):
    """An OpenAI-compatible client pointed at the configured provider (OpenAI or GLM).

    Pass base_url/api_key to target a different OpenAI-compatible endpoint — the
    routing model lives on SiliconFlow while the answer model lives on z.ai.

    Uses the langfuse.openai drop-in so chat/tool-call completions are auto-traced
    as `generation` observations (model, tokens, latency) under the current trace.
    """
    from langfuse.openai import OpenAI
    s = get_settings()
    # Timeout + retries are not optional on a customer-facing path: without them
    # one hung upstream request hangs the whole /chat call.
    return OpenAI(base_url=base_url if base_url is not None else s.resolved_base_url(),
                  api_key=(s.resolved_api_key() if api_key is None else api_key) or None,
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
        s = get_settings()
        self._c = _client()
        self._model = s.llm_model
        # Routing runs on its own small model (see Settings.router_model), so the
        # answer model's cost and latency do not gate the branch decision.
        self._router = _client(s.router_base_url(), s.router_api_key())
        self._router_model = s.router_model_name()
        self._router_provider = s.router_provider

    def complete(self, prompt: str) -> str:
        r = self._c.chat.completions.create(
            model=self._model, messages=[{"role": "user", "content": prompt}],
            name="generate-answer",
        )
        return r.choices[0].message.content or ""

    def complete_small(self, prompt: str) -> str:
        """One-shot completion on the small routing model.

        Reused for cheap side tasks (follow-up suggestions) so they never queue
        behind — or pay for — the thinking answer model.
        """
        extra = {"enable_thinking": False} if self._router_provider == "siliconflow" else None
        r = self._router.chat.completions.create(
            model=self._router_model,
            messages=[{"role": "user", "content": prompt}],
            extra_body=extra,
            name="suggest-followups",
        )
        return r.choices[0].message.content or ""

    def complete_stream(self, prompt: str):
        """Yield answer deltas from the answer model.

        Only `delta.content` is yielded. glm-4.7 thinks by default and puts the
        chain of thought in `delta.reasoning_content`; streaming that to a
        customer would show them the model's scratchpad.
        """
        stream = self._c.chat.completions.create(
            model=self._model, messages=[{"role": "user", "content": prompt}],
            stream=True, name="generate-answer-stream",
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            text = getattr(chunk.choices[0].delta, "content", None)
            if text:
                yield text

    def select_tool(self, question: str, schemas: list[dict]) -> Optional[dict]:
        # Qwen3 is a hybrid-reasoning model and thinks by default; for a two-way
        # branch that only buys latency, so turn it off. The flag is a SiliconFlow
        # extension — sending it to z.ai/OpenAI is an error, hence the guard.
        extra = {"enable_thinking": False} if self._router_provider == "siliconflow" else None
        r = self._router.chat.completions.create(
            model=self._router_model,
            messages=[{"role": "system", "content": ROUTER_SYSTEM},
                      {"role": "user", "content": question}],
            tools=schemas,
            tool_choice="auto",
            extra_body=extra,
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
