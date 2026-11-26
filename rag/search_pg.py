"""Step 6: the same searches, served from Postgres.

Chunks and embeddings come from the database, so nothing is re-embedded except the
question. Vector search runs in SQL through the HNSW index, and BM25 still runs in
Python over chunk text loaded from the database. Hybrid fuses the two with the same
RRF as step 5.

The vector side returns the top DEPTH chunks rather than the whole book. That is
enough for the eval's 800-word budget and for RRF, since a chunk ranked below 200
adds almost nothing to a fused score.
"""

from collections import defaultdict

from . import db, search_bm25
from .corpus import Paragraph
from .search_hybrid import K
from .search_vector import QUERY_PREFIX, embed

DEPTH = 200


def _vector(query: str, units: list[Paragraph], chunking: str, exact: bool) -> list[Paragraph]:
    by_idx = {u.id: u for u in units}
    q = embed([QUERY_PREFIX + query])[0]
    return [by_idx[i] for i in db.vector_search(q, chunking, DEPTH, exact=exact)]


def vector(chunking: str, exact: bool = False):
    return lambda query, units: _vector(query, units, chunking, exact)


def hybrid(chunking: str):
    def search(query: str, units: list[Paragraph]) -> list[Paragraph]:
        scores: dict[int, float] = defaultdict(float)
        by_id = {u.id: u for u in units}
        for ranked in (search_bm25.search(query, units), _vector(query, units, chunking, False)):
            for rank, p in enumerate(ranked, start=1):
                scores[p.id] += 1 / (K + rank)
        return [by_id[i] for i in sorted(scores, key=scores.get, reverse=True)]
    return search


def library(chunking: str = "r128", book: str | None = None):
    """pg-hybrid across every ingested book, or one book when `book` is set."""
    def search(query: str, units: list[Paragraph]) -> list[Paragraph]:
        by_id = {u.id: u for u in units}
        q = embed([QUERY_PREFIX + query])[0]
        vector = [by_id[i] for i in db.library_vector_search(q, chunking, DEPTH, book) if i in by_id]
        scores: dict[int, float] = defaultdict(float)
        for ranked in (search_bm25.search(query, units), vector):
            for rank, p in enumerate(ranked, start=1):
                scores[p.id] += 1 / (K + rank)
        return [by_id[i] for i in sorted(scores, key=scores.get, reverse=True)]
    return search
