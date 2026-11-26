"""One question through the whole pipeline, keeping every intermediate step.

The web page's "Under the hood" tab shows what each stage produced: BM25's ranking,
the vector ranking, the RRF fusion, the context handed to the reader, the exact
prompt, and how long each stage took.
"""

import time
from collections import defaultdict
from functools import lru_cache

from . import db, search_bm25
from .books import TITLES, describe
from .generate import chat, citations, expand, library_messages, select_context
from .search_hybrid import K
from .search_pg import DEPTH
from .search_vector import QUERY_PREFIX, embed

SHOW = 10  # how many results per ranking the page shows


@lru_cache(maxsize=32)
def units_for(chunking: str, book: str | None):
    units = db.load_library(chunking, book)
    return units, {u.id: u for u in units}


def card(p, **extra):
    return {"id": p.id, "label": p.chapter, "where": describe(p.chapter), "text": p.text, **extra}


def run(question: str, book: str | None = None, mode: str = "hybrid",
        window: int = 2, summaries: bool = False) -> dict:
    chunking = "r128sum" if summaries and book == "mobydick" else "r128"
    units, by_id = units_for(chunking, book)
    t = {}

    start = time.perf_counter()
    bm25 = search_bm25.search(question, units)
    t["bm25_ms"] = (time.perf_counter() - start) * 1000

    start = time.perf_counter()
    qvec = embed([QUERY_PREFIX + question])[0]
    vector = [by_id[i] for i in db.library_vector_search(qvec, chunking, DEPTH, book) if i in by_id]
    t["vector_ms"] = (time.perf_counter() - start) * 1000

    start = time.perf_counter()
    bm25_rank = {p.id: r for r, p in enumerate(bm25, 1)}
    vector_rank = {p.id: r for r, p in enumerate(vector, 1)}
    scores: dict[int, float] = defaultdict(float)
    for ranked in (bm25, vector):
        for r, p in enumerate(ranked, 1):
            scores[p.id] += 1 / (K + r)
    fused = [by_id[i] for i in sorted(scores, key=scores.get, reverse=True)]
    t["fusion_ms"] = (time.perf_counter() - start) * 1000

    chosen = {"hybrid": fused, "vector": vector, "bm25": bm25}[mode]
    retrieved = select_context(chosen)
    context = expand(retrieved, units, window)
    messages = library_messages(question, context)

    start = time.perf_counter()
    answer = chat(messages)
    t["generate_ms"] = (time.perf_counter() - start) * 1000
    cited = {p.id for p in citations(answer, context)}

    ranks = lambda p: {"bm25_rank": bm25_rank.get(p.id), "vector_rank": vector_rank.get(p.id),
                       "rrf": round(scores.get(p.id, 0.0), 5)}
    return {
        "question": question, "book": book, "mode": mode, "window": window, "chunking": chunking,
        "answer": answer,
        "passages": [card(p, n=i, cited=p.id in cited) for i, p in enumerate(context, 1)],
        "rankings": {
            "bm25": [card(p, **ranks(p)) for p in bm25[:SHOW]],
            "vector": [card(p, **ranks(p)) for p in vector[:SHOW]],
            "fused": [card(p, **ranks(p)) for p in fused[:SHOW]],
        },
        "retrieved_ids": [p.id for p in retrieved],
        "prompt": messages,
        "timings": {k: round(v) for k, v in t.items()},
        "counts": {"chunks_searched": len(units), "context_words": sum(len(p.text.split()) for p in context)},
    }


def books() -> list[dict]:
    return [{"slug": s, "title": TITLES.get(s, s), "chunks": n} for s, n in db.library_books()]
