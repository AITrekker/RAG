-- Step 6 schema. Text, keyword index, and vectors live in one database, so a
-- document's chunks and embeddings are written in one transaction and can never
-- drift apart.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id          serial PRIMARY KEY,
    path        text UNIQUE NOT NULL,
    sha256      text NOT NULL,
    ingested_at timestamptz NOT NULL DEFAULT now()
);

-- One row per chunk per chunking strategy, so strategies sit side by side.
CREATE TABLE IF NOT EXISTS chunks (
    id       serial PRIMARY KEY,
    doc_id   int NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunking text NOT NULL,          -- 'paragraph', 'r128', ...
    idx      int NOT NULL,           -- position within the document for this strategy
    chapter  text NOT NULL,
    text     text NOT NULL,
    tsv      tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    UNIQUE (doc_id, chunking, idx)
);
CREATE INDEX IF NOT EXISTS chunks_tsv ON chunks USING gin (tsv);

-- One row per chunk per embedding model. pgvector needs a fixed dimension to build
-- an index, so this table holds 384-dimension models such as bge-small.
CREATE TABLE IF NOT EXISTS embeddings_384 (
    chunk_id int NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    model    text NOT NULL,
    vec      vector(384) NOT NULL,
    PRIMARY KEY (chunk_id, model)
);
CREATE INDEX IF NOT EXISTS embeddings_384_hnsw ON embeddings_384 USING hnsw (vec vector_cosine_ops);
