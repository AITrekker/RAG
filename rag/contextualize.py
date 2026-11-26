"""Step 8: contextual chunk headers.

A 128-token chunk often doesn't say where it is or who is talking. Before indexing,
Qwen reads the part of the chapter around each chunk and writes one or two sentences
placing it: the chapter, who is involved, and what is happening. The header is
prepended to the chunk, so BM25, the embedding, and the reader all see it. This is
Anthropic's contextual retrieval technique.

Chapters longer than WINDOW_WORDS are split into windows, and each chunk is shown
with the window it falls in. Every chunk in a window shares the same prompt prefix,
so vLLM's prefix cache reads each window once.

Headers are written to data/contexts-<chunking>.jsonl. The job resumes where it
stopped, and the finished file is committed so the index can be rebuilt without a
GPU.
"""

import json
from pathlib import Path

from .chunk import load_units
from .corpus import Paragraph, load_paragraphs
from .generate import chat_many

ROOT = Path(__file__).resolve().parent.parent
WINDOW_WORDS = 2000

PROMPT = """<chapter>
{window}
</chapter>

Here is a passage from that part of Moby-Dick:
<passage>
{chunk}
</passage>

Write one or two sentences that situate this passage for search: name the chapter, the characters or ship involved, who is speaking if it is dialogue, and what is happening. Answer with only those sentences."""


def cache_path(chunking: str) -> Path:
    return ROOT / "data" / f"contexts-{chunking}.jsonl"


def chapter_windows() -> dict[str, list[str]]:
    by_chapter: dict[str, list[str]] = {}
    for p in load_paragraphs():
        by_chapter.setdefault(p.chapter, []).append(p.text)
    windows = {}
    for chapter, paras in by_chapter.items():
        words = " ".join(paras).split()
        windows[chapter] = [" ".join(words[i:i + WINDOW_WORDS]) for i in range(0, len(words), WINDOW_WORDS)]
    return windows


def window_for(chunk: Paragraph, windows: list[str]) -> str:
    """Pick the window that shares the most words with the chunk's opening."""
    probe = " ".join(chunk.text.split()[:12])
    for w in windows:
        if probe in w:
            return w
    head = set(chunk.text.split()[:40])
    return max(windows, key=lambda w: len(head & set(w.split())))


def run(chunking: str = "r128", batch_size: int = 64) -> str:
    units = load_units(chunking)
    out = cache_path(chunking)
    out.parent.mkdir(exist_ok=True)
    done = {json.loads(line)["idx"] for line in out.open()} if out.exists() else set()
    todo = [u for u in units if u.id not in done]
    windows = chapter_windows()
    chapter_titles = {p.chapter: p.text for p in load_paragraphs() if p.text.startswith(("CHAPTER", "Epilogue"))}

    with out.open("a") as f:
        for start in range(0, len(todo), batch_size):
            batch = todo[start:start + batch_size]
            prompts = [[{"role": "user", "content": PROMPT.format(
                window=chapter_titles.get(u.chapter, "") + "\n" + window_for(u, windows[u.chapter]),
                chunk=u.text)}] for u in batch]
            headers = chat_many(prompts, concurrency=16, max_tokens=90)
            for u, h in zip(batch, headers):
                f.write(json.dumps({"idx": u.id, "chapter": u.chapter, "context": h}) + "\n")
            f.flush()
            print(f"{len(done) + start + len(batch)}/{len(units)}", flush=True)
    return f"wrote {out}"


def load_contextual(chunking: str) -> list[Paragraph]:
    """Chunks with their header prepended, for chunking names like 'r128ctx'."""
    base = chunking.removesuffix("ctx")
    path = cache_path(base)
    if not path.exists():
        raise RuntimeError(f"no headers at {path}; run `rag contextualize --chunking {base}`")
    headers = {json.loads(line)["idx"]: json.loads(line)["context"] for line in path.open()}
    units = load_units(base)
    missing = [u.id for u in units if u.id not in headers]
    if missing:
        raise RuntimeError(f"{len(missing)} chunks have no header yet; rerun contextualize")
    return [Paragraph(u.id, u.chapter, f"{headers[u.id]}\n{u.text}") for u in units]
