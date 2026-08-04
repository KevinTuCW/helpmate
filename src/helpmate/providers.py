import json
from typing import Optional
from helpmate.config import get_settings


class OpenAIEmbedder:
    def __init__(self) -> None:
        from openai import OpenAI
        self._c = OpenAI()
        self._model = get_settings().embed_model

    def embed(self, text: str) -> list[float]:
        return self._c.embeddings.create(model=self._model, input=text).data[0].embedding


class OpenAILLM:
    def __init__(self) -> None:
        from openai import OpenAI
        self._c = OpenAI()
        self._model = get_settings().llm_model

    def complete(self, prompt: str) -> str:
        r = self._c.chat.completions.create(
            model=self._model, messages=[{"role": "user", "content": prompt}]
        )
        return r.choices[0].message.content or ""

    def select_tool(self, question: str, schemas: list[dict]) -> Optional[dict]:
        r = self._c.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": question}],
            tools=schemas,
            tool_choice="auto",
        )
        msg = r.choices[0].message
        if msg.tool_calls:
            tc = msg.tool_calls[0]
            return {"name": tc.function.name, "args": json.loads(tc.function.arguments)}
        return None
