"""The local embedder, run against the real model. First run downloads it (~130 MB)."""

import math

import pytest

from app.embeddings import FastEmbedEmbedder


@pytest.fixture(scope="module")
def embedder() -> FastEmbedEmbedder:
    return FastEmbedEmbedder()


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def test_embeds_documents_to_the_declared_dimension(embedder):
    vectors = embedder.embed_documents(["Pricing moved to October.", "Postgres upgrade is done."])

    assert len(vectors) == 2
    assert all(len(v) == embedder.dimensions == 384 for v in vectors)


def test_a_query_lands_closer_to_the_chunk_that_answers_it(embedder):
    docs = embedder.embed_documents([
        "Marco: New target for pricing is October fifteenth. I'll tell the board it slipped.",
        "Diego: The Postgres upgrade is done on staging. Went fine.",
    ])
    query = embedder.embed_query("When does the pricing page launch?")

    assert _cosine(query, docs[0]) > _cosine(query, docs[1])


def test_embedding_nothing_returns_nothing(embedder):
    assert embedder.embed_documents([]) == []
