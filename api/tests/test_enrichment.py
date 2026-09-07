"""Context headers through a fake Anthropic client: what gets sent, and in what order."""

import asyncio
import time

import pytest

from app.enrichment import CONTEXT_HEADER_MODEL, ClaudeEnricher
from app.models import Chunk

pytestmark = pytest.mark.anyio


class _TextBlock:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _Message:
    def __init__(self, text: str) -> None:
        self.content = [_TextBlock(text)]


class FakeMessages:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.spans: list[tuple[float, float]] = []
        self.in_flight = 0
        self.max_in_flight = 0

    async def create(self, **kwargs):
        started = time.monotonic()
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        await asyncio.sleep(0.02)
        self.in_flight -= 1
        self.calls.append(kwargs)
        self.spans.append((started, time.monotonic()))
        return _Message(f"Context for {kwargs['messages'][0]['content']}")


class FakeClient:
    def __init__(self) -> None:
        self.messages = FakeMessages()


def _chunks(n: int) -> list[Chunk]:
    return [
        Chunk(idx=i, turn_start=i, turn_end=i, text=f"chunk number {i}", token_estimate=3)
        for i in range(n)
    ]


TRANSCRIPT = "[00:00:01] Marco: Hello.\n[00:00:05] Ana: Hi."


async def test_returns_one_header_per_chunk_in_order():
    client = FakeClient()

    headers = await ClaudeEnricher(client).context_headers(TRANSCRIPT, _chunks(3))

    assert len(headers) == 3
    assert all(f"chunk number {i}" in headers[i] for i in range(3))


async def test_sends_the_transcript_as_cached_data_and_the_chunk_as_the_question():
    client = FakeClient()

    await ClaudeEnricher(client).context_headers(TRANSCRIPT, _chunks(1))

    call = client.messages.calls[0]
    assert call["model"] == CONTEXT_HEADER_MODEL
    cached = [block for block in call["system"] if "cache_control" in block]
    assert len(cached) == 1
    assert TRANSCRIPT in cached[0]["text"]
    assert "chunk number 0" in call["messages"][0]["content"]


async def test_warms_the_cache_with_the_first_chunk_before_fanning_out():
    client = FakeClient()

    await ClaudeEnricher(client, concurrency=4).context_headers(TRANSCRIPT, _chunks(5))

    spans = client.messages.spans
    first_finished = spans[0][1]
    assert all(start >= first_finished for start, _ in spans[1:]), "the first call must run alone"
    assert client.messages.max_in_flight >= 2, "the remaining calls should overlap"
