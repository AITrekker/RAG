"""Side test for step 3: BM25 with stemming.

A stemmer cuts words down to a common root, so "owned," "owners," and "owning" all
become "own." Everything else matches step 2's BM25.
"""

import snowballstemmer
from rank_bm25 import BM25Okapi

from .corpus import Paragraph
from .search_substring import query_terms, tokens

_stem = snowballstemmer.stemmer("english").stemWords
_index: dict[int, BM25Okapi] = {}


def search(query: str, paragraphs: list[Paragraph]) -> list[Paragraph]:
    key = id(paragraphs)
    if key not in _index:
        _index[key] = BM25Okapi([_stem(tokens(p.text)) for p in paragraphs])
    terms = _stem(query_terms(query))
    if not terms:
        return []
    scores = _index[key].get_scores(terms)
    ranked = sorted(range(len(paragraphs)), key=lambda i: scores[i], reverse=True)
    return [paragraphs[i] for i in ranked if scores[i] > 0]
