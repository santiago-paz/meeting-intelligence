"""Stand-ins for the model-backed services, for tests that must stay offline."""

import random

from app.models import Chunk


class FakeEmbedder:
    """Deterministic vectors: same text, same vector; no meaning beyond that."""

    dimensions = 384

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    def _vector(self, text: str) -> list[float]:
        rng = random.Random(text)
        return [rng.uniform(-1.0, 1.0) for _ in range(self.dimensions)]


class FakeEnricher:
    async def context_headers(self, transcript: str, chunks: list[Chunk]) -> list[str]:
        return [f"Context for chunk {chunk.idx}" for chunk in chunks]


class FakeAnswerer:
    """Returns a fixed answer text; records the prompt it was given."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.prompts: list[str] = []

    async def answer(self, prompt: str):
        from app.answering import AnswerResult

        self.prompts.append(prompt)
        return AnswerResult(
            text=self.text, model="fake-model", stop_reason="end_turn",
            input_tokens=100, output_tokens=20, cache_read_tokens=0, cache_write_tokens=0,
        )
