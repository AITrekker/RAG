"""Step 12: a library of documents.

Moby-Dick is joined by War and Peace (566,000 words) and 21 short documents from
three fictional companies (ACMECorp, RegionalSolns, InnovateFast). Each company has
its own vacation policy, culture page, and so on, and the documents rarely say which
company they belong to. ACMECorp's policy calls itself "GlobalCorp," and
RegionalSolns' financial report says "TechFlow." Only metadata knows which tenant a
document belongs to.

Every chunk carries a `doc` label. Moby-Dick chunks keep their bare chapter numbers,
so the original eval set still works unchanged, and other chunks use labels like
"warandpeace:12" or "ACMECorp:vacation_policy".
"""

import re
from functools import lru_cache
from pathlib import Path

from .chunk import chunk_chapter
from .corpus import Paragraph, load_paragraphs

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "corpus" / "library"
TENANTS = ["ACMECorp", "RegionalSolns", "InnovateFast"]


def paragraphs_of(text: str) -> list[str]:
    return [" ".join(b.split()) for b in re.split(r"\n\s*\n", text) if b.strip()]


def war_and_peace() -> list[tuple[str, list[str]]]:
    text = (LIBRARY / "warandpeace.txt").read_text(encoding="utf-8")
    start = text.index("*** START OF")
    end = text.index("*** END OF")
    body = text[text.index("BOOK ONE: 1805", text.index("BOOK ONE: 1805") + 1):end] \
        if text.count("BOOK ONE: 1805") > 1 else text[start:end]
    sections = re.split(r"\n(?=CHAPTER [IVXLC]+\n)", body)
    return [(f"warandpeace:{i}", paragraphs_of(s)) for i, s in enumerate(sections) if s.strip()]


def company_docs() -> list[tuple[str, list[str]]]:
    out = []
    for tenant in TENANTS:
        for f in sorted((LIBRARY / tenant).glob("*.txt")):
            out.append((f"{tenant}:{f.stem}", paragraphs_of(f.read_text(encoding="utf-8"))))
    return out


def doc_of(chapter: str) -> str:
    return chapter.split(":")[0] if ":" in chapter else "mobydick"


@lru_cache
def load_library(size: int = 128) -> list[Paragraph]:
    """All documents as r<size> chunks, numbered consecutively."""
    overlap = size // 8
    sections: list[tuple[str, list[Paragraph]]] = []
    by_chapter: dict[str, list[Paragraph]] = {}
    for p in load_paragraphs():
        by_chapter.setdefault(p.chapter, []).append(p)
    sections += list(by_chapter.items())
    for label, paras in war_and_peace() + company_docs():
        sections.append((label, [Paragraph(i, label, t) for i, t in enumerate(paras)]))

    units = []
    for label, paras in sections:
        for text in chunk_chapter(paras, size, overlap):
            units.append(Paragraph(len(units), label, text))
    return units


def filtered(units: list[Paragraph], doc_filter: str | None) -> list[Paragraph]:
    """Keep chunks whose document starts with doc_filter, such as 'mobydick' or 'ACMECorp'."""
    if not doc_filter:
        return units
    return [u for u in units if doc_of(u.chapter).startswith(doc_filter)]
