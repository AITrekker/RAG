"""Step 5: hybrid search with reciprocal rank fusion (RRF).

BM25 and vector search fail on different questions, so this runs both and merges
the two ranked lists. RRF ignores the raw scores, which are on different scales, and
uses only rank positions. A chunk's fused score is the sum over both lists of
1 / (K + rank), so a chunk ranked near the top of either list rises, and a chunk
near the top of both rises most. K = 60 is the constant from the original RRF paper
(Cormack, Clarke, and Buettcher, 2009); it keeps the first few ranks from
dominating.
"""

from collections import defaultdict

from . import search_bm25, search_vector
from .corpus import Paragraph

K = 60


def search(query: str, paragraphs: list[Paragraph]) -> list[Paragraph]:
    scores: dict[int, float] = defaultdict(float)
    by_id = {}
    for ranked in (search_bm25.search(query, paragraphs), search_vector.search(query, paragraphs)):
        for rank, p in enumerate(ranked, start=1):
            scores[p.id] += 1 / (K + rank)
            by_id[p.id] = p
    return [by_id[i] for i in sorted(scores, key=scores.get, reverse=True)]
