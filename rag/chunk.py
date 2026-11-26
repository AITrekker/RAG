"""Step 4: chunks sized to the embedding model's window.

Paragraphs make poor chunks because some are too long for the model to read and many
are one-line dialogue with no context. This chunker works chapter by chapter, so a
chunk never mixes two chapters:

1. Break the chapter into units. A unit is a paragraph, or, when a paragraph is too
   long, its sentences, or, when a sentence is too long, a run of tokens.
2. Pack units in order into chunks of up to `size` tokens.
3. Start each new chunk with the last few units of the previous one, up to `overlap`
   tokens, so an idea that straddles a boundary appears whole in at least one chunk.

Token counts use the embedding model's own tokenizer, so "256 tokens" means exactly
what the model will see.
"""

import re
from functools import lru_cache

from .corpus import Paragraph, load_paragraphs

TOKENIZER = "BAAI/bge-small-en-v1.5"
SENTENCE_RE = re.compile(r"(?<=[.!?”])\s+")


@lru_cache
def tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(TOKENIZER)


def n_tokens(text: str) -> int:
    return len(tokenizer()(text, add_special_tokens=False)["input_ids"])


def split_unit(text: str, size: int) -> list[str]:
    """Return text as one unit if it fits, else as sentence- or token-sized pieces."""
    if n_tokens(text) <= size:
        return [text]
    pieces = []
    for sentence in SENTENCE_RE.split(text):
        if n_tokens(sentence) <= size:
            pieces.append(sentence)
        else:
            ids = tokenizer()(sentence, add_special_tokens=False)["input_ids"]
            pieces += [tokenizer().decode(ids[i:i + size]) for i in range(0, len(ids), size)]
    return pieces


def chunk_chapter(paragraphs: list[Paragraph], size: int, overlap: int) -> list[str]:
    units = [u for p in paragraphs for u in split_unit(p.text, size)]
    chunks, current, current_len = [], [], 0
    for unit in units:
        n = n_tokens(unit)
        if current and current_len + n > size:
            chunks.append(" ".join(current))
            # carry trailing units forward as overlap
            carry, carry_len = [], 0
            for u in reversed(current):
                if carry_len + n_tokens(u) > overlap:
                    break
                carry.insert(0, u)
                carry_len += n_tokens(u)
            current, current_len = carry, carry_len
        current.append(unit)
        current_len += n
    if current:
        chunks.append(" ".join(current))
    return chunks


@lru_cache
def load_chunks(size: int, overlap: int) -> list[Paragraph]:
    by_chapter: dict[str, list[Paragraph]] = {}
    for p in load_paragraphs():
        by_chapter.setdefault(p.chapter, []).append(p)
    chunks = []
    for chapter, paragraphs in by_chapter.items():
        for text in chunk_chapter(paragraphs, size, overlap):
            chunks.append(Paragraph(len(chunks), chapter, text))
    return chunks


def load_units(chunking: str) -> list[Paragraph]:
    """'paragraph' for steps 1 to 3, or 'r<size>' such as 'r256' for recursive chunks."""
    if chunking == "paragraph":
        return load_paragraphs()
    size = int(chunking.removeprefix("r"))
    return list(load_chunks(size, size // 8))
