"""Step 3: search by meaning with embeddings.

An embedding model turns each paragraph into a list of 384 numbers that places it in
a "meaning space," where paragraphs about similar things land close together. The
question is embedded the same way, and paragraphs are ranked by cosine similarity
to it. Shared words no longer matter, only how close the meanings are.
"""

import numpy as np

from .corpus import Paragraph

MODEL_NAME = "BAAI/bge-small-en-v1.5"
# bge models expect this prefix on queries (not on passages).
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

_model = None
_index: dict[int, np.ndarray] = {}


def model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME, device="cuda")
    return _model


def embed(texts: list[str]) -> np.ndarray:
    return model().encode(texts, batch_size=64, normalize_embeddings=True, convert_to_numpy=True)


def search(query: str, paragraphs: list[Paragraph]) -> list[Paragraph]:
    key = id(paragraphs)
    if key not in _index:
        _index[key] = embed([p.text for p in paragraphs])
    q = embed([QUERY_PREFIX + query])[0]
    scores = _index[key] @ q  # vectors are unit length, so a dot product is cosine similarity
    return [paragraphs[i] for i in np.argsort(-scores)]
