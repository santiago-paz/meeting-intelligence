-- Context headers and embeddings for chunks, plus the index that makes
-- similarity search cheap. 384 dimensions is BAAI/bge-small-en-v1.5, the
-- local embedding model; swapping models means a new migration.
CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE chunks
    ADD COLUMN context_header text,
    ADD COLUMN embedding vector(384);

CREATE INDEX chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);
