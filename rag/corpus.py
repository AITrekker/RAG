"""Load Moby Dick and split it into paragraphs tagged with their chapter."""

import re
from dataclasses import dataclass
from pathlib import Path

CORPUS = Path(__file__).resolve().parent.parent / "corpus" / "mobydick.txt"
CHAPTER_RE = re.compile(r"^CHAPTER (\d+)\.")


@dataclass
class Paragraph:
    id: int
    chapter: str  # "1".."135" or "epilogue"
    text: str


def load_paragraphs(path: Path = CORPUS) -> list[Paragraph]:
    lines = path.read_text(encoding="utf-8").splitlines()

    # The book body starts at the second "CHAPTER 1." line, since the first one is
    # in the table of contents. It ends at the Project Gutenberg footer.
    starts = [i for i, line in enumerate(lines) if line.startswith("CHAPTER 1. ")]
    end = next(i for i, line in enumerate(lines) if line.startswith("*** END OF"))
    body = lines[starts[1]:end]

    paragraphs, chapter, buf = [], "0", []

    def flush():
        if buf:
            paragraphs.append(Paragraph(len(paragraphs), chapter, " ".join(buf)))
            buf.clear()

    for line in body:
        line = line.strip()
        m = CHAPTER_RE.match(line)
        if m or line == "Epilogue":
            flush()
            chapter = m.group(1) if m else "epilogue"
            buf.append(line)  # keep the heading as its own paragraph
            flush()
        elif not line:
            flush()
        else:
            buf.append(line)
    flush()
    return paragraphs
