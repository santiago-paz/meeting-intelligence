"""Embeddings behind one small interface.

The default runs locally on CPU (BAAI/bge-small-en-v1.5 through ONNX), so
retrieval needs no second vendor and no second API key. A hosted model such as
Voyage is a drop-in replacement: implement the two methods, change the vector
dimension in a migration.
"""

from typing import Protocol

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


class Embedder(Protocol):
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class FastEmbedEmbedder:
    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL) -> None:
        from fastembed import TextEmbedding  # slow import, keep it out of module load

        self._model = TextEmbedding(model_name)
        self.dimensions = len(next(iter(self._model.embed(["dimension probe"]))))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [vector.tolist() for vector in self._model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        # query_embed applies the model's query instruction, which bge expects.
        return next(iter(self._model.query_embed([text]))).tolist()
