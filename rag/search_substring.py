"""Step 1: the simplest possible search.

Drop the filler words from the question, then return every paragraph that contains
all of the remaining words, in book order. There is no ranking at all.
"""

import re

from .corpus import Paragraph

STOPWORDS = set("""
a an the and or but of to in on at for with by from as is was were be been are am
who what when where why how which that this these those it its he his him she her
they them their i me my you your we our do did does about into than then so not no
""".split())


def tokens(text: str) -> list[str]:
    text = text.lower().replace("’", "'").replace("‘", "'")
    words = re.findall(r"[a-z0-9']+", text)
    return [w[:-2] if w.endswith("'s") else w.strip("'") for w in words]


def query_terms(query: str) -> list[str]:
    return [t for t in tokens(query) if t and t not in STOPWORDS]


def search(query: str, paragraphs: list[Paragraph]) -> list[Paragraph]:
    terms = query_terms(query)
    if not terms:
        return []
    return [p for p in paragraphs if all(t in set(tokens(p.text)) for t in terms)]
