"""Step 6: Postgres and pgvector storage.

`ingest` chunks and embeds a document, then writes the document row, its chunks, and
their embeddings in a single transaction. If anything fails partway, nothing is
written. Ingest is idempotent: a document whose file hash, chunking, and model are
already stored is skipped, so re-running it costs nothing.
"""

import hashlib
import os
from functools import lru_cache
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector

from .chunk import load_units
from .corpus import CORPUS, Paragraph

ROOT = Path(__file__).resolve().parent.parent


def database_url() -> str:
    if "DATABASE_URL" in os.environ:
        return os.environ["DATABASE_URL"]
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("DATABASE_URL is not set in the environment or .env")


@lru_cache
def connect() -> psycopg.Connection:
    conn = psycopg.connect(database_url(), autocommit=True)
    conn.execute((Path(__file__).parent / "schema.sql").read_text())
    register_vector(conn)
    return conn


def ingest(chunking: str, path: Path = CORPUS) -> str:
    from .search_vector import MODEL_NAME, embed

    conn = connect()
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    done = conn.execute(
        """SELECT count(*) FROM documents d JOIN chunks c ON c.doc_id = d.id
           JOIN embeddings_384 e ON e.chunk_id = c.id AND e.model = %s
           WHERE d.path = %s AND d.sha256 = %s AND c.chunking = %s""",
        (MODEL_NAME, str(path), sha, chunking),
    ).fetchone()[0]
    if done:
        return f"skipped: {path.name} {chunking} already ingested ({done} chunks)"

    # Do the slow work (chunking and embedding) before opening the transaction, so
    # the transaction itself stays short.
    units = load_units(chunking)
    vectors = embed([u.text for u in units])

    with conn.transaction():
        doc_id = conn.execute(
            """INSERT INTO documents (path, sha256) VALUES (%s, %s)
               ON CONFLICT (path) DO UPDATE SET sha256 = EXCLUDED.sha256, ingested_at = now()
               RETURNING id""",
            (str(path), sha),
        ).fetchone()[0]
        conn.execute("DELETE FROM chunks WHERE doc_id = %s AND chunking = %s", (doc_id, chunking))
        with conn.cursor() as cur:
            for u, v in zip(units, vectors):
                chunk_id = cur.execute(
                    """INSERT INTO chunks (doc_id, chunking, idx, chapter, text)
                       VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                    (doc_id, chunking, u.id, u.chapter, u.text),
                ).fetchone()[0]
                cur.execute(
                    "INSERT INTO embeddings_384 (chunk_id, model, vec) VALUES (%s, %s, %s)",
                    (chunk_id, MODEL_NAME, v),
                )
    return f"ingested: {path.name} {chunking} ({len(units)} chunks)"


def load_chunks(chunking: str, path: Path = CORPUS) -> list[Paragraph]:
    rows = connect().execute(
        """SELECT c.idx, c.chapter, c.text FROM chunks c JOIN documents d ON d.id = c.doc_id
           WHERE d.path = %s AND c.chunking = %s ORDER BY c.idx""",
        (str(path), chunking),
    ).fetchall()
    if not rows:
        raise RuntimeError(f"no {chunking} chunks in the database; run `rag ingest --chunking {chunking}`")
    return [Paragraph(idx, chapter, text) for idx, chapter, text in rows]


def vector_search(query_vec, chunking: str, limit: int, exact: bool = False,
                  path: Path = CORPUS) -> list[int]:
    """Return chunk idx values nearest the query. HNSW is approximate unless exact=True."""
    from .search_vector import MODEL_NAME

    conn = connect()
    with conn.transaction():
        # HNSW returns at most ef_search rows, so raise it to cover the limit.
        conn.execute(f"SET LOCAL hnsw.ef_search = {max(limit, 40)}")
        if exact:
            conn.execute("SET LOCAL enable_indexscan = off")
        rows = conn.execute(
            """SELECT c.idx FROM embeddings_384 e JOIN chunks c ON c.id = e.chunk_id
               JOIN documents d ON d.id = c.doc_id
               WHERE e.model = %s AND c.chunking = %s AND d.path = %s
               ORDER BY e.vec <=> %s LIMIT %s""",
            (MODEL_NAME, chunking, str(path), query_vec, limit),
        ).fetchall()
    return [r[0] for r in rows]
