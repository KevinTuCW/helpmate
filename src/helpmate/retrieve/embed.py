from helpmate.config import get_settings


class Qwen3Embedder:
    """SiliconFlow-hosted Qwen3-Embedding (OpenAI-compatible), fixed to embed_dim."""

    def __init__(self) -> None:
        from openai import OpenAI
        s = get_settings()
        self._c = OpenAI(base_url=s.embed_base_url(), api_key=s.embed_api_key() or None)
        self._model = s.embed_model
        self._dim = s.embed_dim

    def embed(self, text: str) -> list[float]:
        r = self._c.embeddings.create(model=self._model, input=text, dimensions=self._dim)
        return r.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        # SiliconFlow accepts a list input; keep batches modest to stay under limits.
        r = self._c.embeddings.create(model=self._model, input=texts, dimensions=self._dim)
        return [d.embedding for d in r.data]


def get_embedder():
    """Embedder backend: SiliconFlow Qwen3 by default; 'local' hashing for offline tests."""
    if get_settings().embed_provider == "local":
        from helpmate.providers import LocalHashingEmbedder
        return LocalHashingEmbedder()
    return Qwen3Embedder()
