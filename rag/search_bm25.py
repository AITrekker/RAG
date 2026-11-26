"""Step 2: rank paragraphs with BM25.

BM25 gives each paragraph a score for each query word it contains. Rare words count
for more than common ones, repeated words count for less each time, and long
paragraphs are discounted so they don't win just by containing more words. A
paragraph no longer has to contain every word to be returned.
"""

from rank_bm25 import BM25Okapi

from .corpus import Paragraph
from .search_substring import query_terms, tokens

_index: dict[int, BM25Okapi] = {}


def search(query: str, paragraphs: list[Paragraph]) -> list[Paragraph]:
    key = id(paragraphs)
    if key not in _index:
        _index[key] = BM25Okapi([tokens(p.text) for p in paragraphs])
    terms = query_terms(query)
    if not terms:
        return []
    scores = _index[key].get_scores(terms)
    ranked = sorted(range(len(paragraphs)), key=lambda i: scores[i], reverse=True)
    return [paragraphs[i] for i in ranked if scores[i] > 0]
