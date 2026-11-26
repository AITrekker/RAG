"""Children's books from Project Gutenberg, split into chapters.

The texts come from Project Gutenberg's pglaf.org mirror (see scripts/fetch_books.sh)
and live in corpus/books/<slug>.txt. Each book marks its chapters differently, so
each has a heading style:

- "chapter": lines like "CHAPTER I." or "Chapter 3", possibly with a title after
- "numbered": lines like "11 Plain Speaking" at the start of the line (Black Beauty)
- "roman": a Roman numeral alone on a line (Treasure Island)
- "toc": story titles listed under "Contents" (The Jungle Book)
- "titles": the contents list "CHAPTER I. THE RIVER BANK" and the body heads each
  chapter with the title alone (The Wind in the Willows)

Tables of contents repeat the headings, so for each chapter number the last
occurrence is taken as the real heading. Chunk chapter labels look like
"alice-in-wonderland:3".
"""

import re
from pathlib import Path

from .chunk import chunk_chapter
from .corpus import Paragraph

ROOT = Path(__file__).resolve().parent.parent
BOOK_DIR = ROOT / "corpus" / "books"

# slug: (title, author, Gutenberg id, heading style)
BOOKS = {
    "alice-in-wonderland": ("Alice's Adventures in Wonderland", "Lewis Carroll", 11, "chapter"),
    "through-the-looking-glass": ("Through the Looking-Glass", "Lewis Carroll", 12, "chapter"),
    "peter-pan": ("Peter Pan", "J. M. Barrie", 16, "chapter"),
    "wizard-of-oz": ("The Wonderful Wizard of Oz", "L. Frank Baum", 55, "chapter"),
    "jungle-book": ("The Jungle Book", "Rudyard Kipling", 236, "toc"),
    "wind-in-the-willows": ("The Wind in the Willows", "Kenneth Grahame", 289, "titles"),
    "secret-garden": ("The Secret Garden", "Frances Hodgson Burnett", 113, "chapter"),
    # The Gutenberg text has no heading line for chapter XVII, so XVI and XVII parse as one.
    "treasure-island": ("Treasure Island", "Robert Louis Stevenson", 120, "roman"),
    "pinocchio": ("The Adventures of Pinocchio", "Carlo Collodi", 500, "chapter"),
    "black-beauty": ("Black Beauty", "Anna Sewell", 271, "numbered"),
}
TITLES = {"mobydick": "Moby-Dick"} | {slug: b[0] for slug, b in BOOKS.items()}

CHAPTER_RE = re.compile(r"^(?:CHAPTER|Chapter)\s+([IVXLC]+|\d+)\b\.?")
NUMBERED_RE = re.compile(r"^(\d{1,2})\s+[A-Z][^.]{0,60}$")
ROMAN_RE = re.compile(r"^([IVXLC]+)\.?$")


def body_lines(slug: str) -> list[str]:
    lines = (BOOK_DIR / f"{slug}.txt").read_text(encoding="utf-8-sig").replace("\r", "").split("\n")
    start = next(i for i, l in enumerate(lines) if l.startswith("*** START OF"))
    end = next(i for i, l in enumerate(lines) if l.startswith("*** END OF"))
    return lines[start + 1:end]


def heading_positions(slug: str, lines: list[str]) -> list[int]:
    style = BOOKS[slug][3]
    found: dict[str, int] = {}
    if style == "toc":
        i = next(i for i, l in enumerate(lines) if l.strip() == "Contents")
        titles = []
        for l in lines[i + 1:]:
            if not l.strip():
                if titles:
                    break
                continue
            titles.append(l.strip())
        # songs between stories are listed too; keep every title that heads a section
        for n, t in enumerate(titles):
            for j in range(len(lines) - 1, i, -1):
                if lines[j].strip() == t:
                    found[str(n)] = j
                    break
    elif style == "titles":
        contents = [CHAPTER_RE.sub("", l.strip()).strip() for l in lines[:200] if CHAPTER_RE.match(l.strip())]
        for n, t in enumerate(contents):
            for j in range(len(lines) - 1, -1, -1):
                if lines[j].strip() == t:
                    found[str(n)] = j
                    break
    else:
        for j, l in enumerate(lines):
            if style == "chapter":
                m = CHAPTER_RE.match(l.strip())
            elif style == "numbered":
                m = NUMBERED_RE.match(l)  # body headings start at column 0; the contents are indented
            else:
                m = ROMAN_RE.match(l)
            if m:
                found[m.group(1)] = j  # last occurrence wins, which skips the contents
    return sorted(found.values())


def chapters(slug: str) -> list[tuple[int, list[str]]]:
    lines = body_lines(slug)
    starts = heading_positions(slug, lines)
    out = []
    for n, (a, b) in enumerate(zip(starts, starts[1:] + [len(lines)]), start=1):
        blocks = re.split(r"\n\s*\n", "\n".join(lines[a:b]))
        paras = [" ".join(x.split()) for x in blocks if x.strip()]
        if paras:
            out.append((n, paras))
    return out


def book_units(slug: str, size: int = 128) -> list[Paragraph]:
    units = []
    for n, paras in chapters(slug):
        label = f"{slug}:{n}"
        for text in chunk_chapter([Paragraph(i, label, t) for i, t in enumerate(paras)], size, size // 8):
            units.append(Paragraph(len(units), label, text))
    return units


def describe(label: str) -> str:
    """'alice-in-wonderland:3' -> "Alice's Adventures in Wonderland, chapter 3"."""
    slug, _, ch = label.rpartition(":")
    return f"{TITLES.get(slug, slug)}, chapter {ch}"
