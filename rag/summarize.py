"""Step 9: chapter summaries as searchable chunks.

Some questions, like "Who was Ahab?", have no single passage that answers them. Qwen
writes a summary of each chapter, and the summaries are indexed alongside the
regular chunks. A summary competes in search like any chunk, and it counts as a hit
when its chapter is a gold chapter.

Chapters longer than one window (2,000 words) are summarized window by window, and
the window summaries are then merged into one chapter summary. Summaries go to
data/summaries.jsonl, which resumes where it stopped and is committed.
"""

import json
from pathlib import Path

from .contextualize import chapter_windows
from .corpus import Paragraph, load_paragraphs
from .generate import chat_many

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "data" / "summaries.jsonl"
SUMMARY_ID_BASE = 100_000  # summary ids sit far above chunk ids

WINDOW_PROMPT = """Here is part of {title} from Moby-Dick:

{text}

Summarize what happens in this part in about 100 words. Name the characters and ships involved and say what is revealed about them. Use only what this text says."""

MERGE_PROMPT = """Here are summaries of consecutive parts of {title} from Moby-Dick:

{parts}

Combine them into one summary of the whole chapter in about 150 words. Name the characters and ships involved and say what is revealed about them."""


def titles() -> dict[str, str]:
    return {p.chapter: p.text for p in load_paragraphs() if p.text.startswith(("CHAPTER", "Epilogue"))}


def run() -> str:
    PATH.parent.mkdir(exist_ok=True)
    done = {json.loads(line)["chapter"] for line in PATH.open()} if PATH.exists() else set()
    windows = {c: w for c, w in chapter_windows().items() if c not in done}
    names = titles()

    jobs = [(c, i) for c, ws in windows.items() for i in range(len(ws))]
    prompts = [[{"role": "user", "content": WINDOW_PROMPT.format(title=names.get(c, c), text=windows[c][i])}]
               for c, i in jobs]
    parts: dict[str, list[str]] = {}
    for (c, i), s in zip(jobs, chat_many(prompts, concurrency=12, max_tokens=220)):
        parts.setdefault(c, [""] * len(windows[c]))[i] = s

    multi = [c for c in parts if len(parts[c]) > 1]
    merged = chat_many([[{"role": "user", "content": MERGE_PROMPT.format(
        title=names.get(c, c), parts="\n\n".join(parts[c]))}] for c in multi], concurrency=12, max_tokens=300)
    final = {c: parts[c][0] for c in parts} | dict(zip(multi, merged))

    with PATH.open("a") as f:
        for c, s in final.items():
            f.write(json.dumps({"chapter": c, "title": names.get(c, c), "summary": s}) + "\n")
    return f"wrote {len(final)} chapter summaries to {PATH}"


def load_summaries() -> list[Paragraph]:
    if not PATH.exists():
        raise RuntimeError("no summaries yet; run `rag summarize`")
    rows = [json.loads(line) for line in PATH.open()]
    return [Paragraph(SUMMARY_ID_BASE + i, r["chapter"], f"Summary of {r['title']} {r['summary']}")
            for i, r in enumerate(rows)]
