"""Steps 10 and 11: query rewriting (HyDE) and reranking, on top of pg-hybrid.

HyDE (step 10). A question like "What did Fedallah predict?" shares few words with
the passage that answers it. Qwen first writes a short hypothetical passage that
would answer the question in the novel's style, and the vector side searches with
that passage. BM25 still searches with the original question, and the two lists
fuse with RRF as before. The hypothetical passage draws on what the model already
knows about the book, so it can be wrong; it only steers retrieval, and the answer
still comes from real passages.

Reranking (step 11). The fused list is good at recall but its order is rough. A
cross-encoder (bge-reranker-base) reads the question and each of the top RERANK_DEPTH
chunks together and scores how well the chunk answers it, which is slower but much
more precise than comparing two separate embeddings. The top chunks are reordered by
that score, and the rest keep their fused order.
"""

from collections import defaultdict
from functools import lru_cache

from . import db, search_bm25
from .corpus import Paragraph
from .search_hybrid import K
from .search_pg import DEPTH
from .search_vector import QUERY_PREFIX, embed

RERANKER = "BAAI/bge-reranker-base"
RERANK_DEPTH = 20

HYDE_PROMPT = """Write a passage of about 100 words in the style of the novel Moby-Dick that would answer this question. Write only the passage.

Question: {question}"""


@lru_cache(maxsize=512)
def hypothetical(question: str) -> str:
    from .generate import chat
    return chat([{"role": "user", "content": HYDE_PROMPT.format(question=question)}], max_tokens=200)


def fused(query: str, units: list[Paragraph], chunking: str, hyde: bool) -> list[Paragraph]:
    by_id = {u.id: u for u in units}
    # A hypothetical passage is a passage, so it is embedded without the query prefix.
    qvec = embed([hypothetical(query)])[0] if hyde else embed([QUERY_PREFIX + query])[0]
    vector = [by_id[i] for i in db.vector_search(qvec, chunking, DEPTH)]
    scores: dict[int, float] = defaultdict(float)
    for ranked in (search_bm25.search(query, units), vector):
        for rank, p in enumerate(ranked, start=1):
            scores[p.id] += 1 / (K + rank)
    return [by_id[i] for i in sorted(scores, key=scores.get, reverse=True)]


@lru_cache
def reranker():
    from sentence_transformers import CrossEncoder
    model = CrossEncoder(RERANKER, device="cuda")
    model.model.half()  # fp16 halves memory next to vLLM on the 12 GB card
    return model


def rerank(query: str, results: list[Paragraph]) -> list[Paragraph]:
    head, tail = results[:RERANK_DEPTH], results[RERANK_DEPTH:]
    scores = reranker().predict([(query, p.text) for p in head], batch_size=20)
    order = sorted(range(len(head)), key=lambda i: scores[i], reverse=True)
    return [head[i] for i in order] + tail


def make(chunking: str, hyde: bool, rerank_top: bool):
    def search(query: str, units: list[Paragraph]) -> list[Paragraph]:
        results = fused(query, units, chunking, hyde)
        return rerank(query, results) if rerank_top else results
    return search
