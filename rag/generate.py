"""Step 7: answer questions with a local LLM.

The retriever picks chunks until 800 words are used (the same budget the eval
measures), numbers them, and hands them to Qwen3-8B running in vLLM. The model must
answer only from those passages, cite them by number, and say "I don't know" when
they don't contain the answer.
"""

import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from .corpus import Paragraph
from .eval import BUDGET_WORDS

URL = "http://127.0.0.1:8001/v1/chat/completions"
MODEL = "qwen3-8b"

SYSTEM = """You answer questions about the novel Moby-Dick using only the numbered passages provided.
Rules:
- Use only facts stated in the passages. Do not use outside knowledge of the book.
- Cite the passages you used with their numbers in square brackets, like [2] or [1][4].
- If the passages do not contain the answer, reply with exactly: I don't know.
- Answer in two or three sentences."""


def chat(messages: list[dict], max_tokens: int = 300, temperature: float = 0.0) -> str:
    body = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "chat_template_kwargs": {"enable_thinking": False},  # Qwen3: skip the reasoning trace
    }
    req = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)["choices"][0]["message"]["content"].strip()


def chat_many(batch: list[list[dict]], concurrency: int = 16, **kw) -> list[str]:
    """Send many requests at once; vLLM batches them on the GPU."""
    with ThreadPoolExecutor(concurrency) as pool:
        return list(pool.map(lambda m: chat(m, **kw), batch))


def select_context(results: list[Paragraph], budget: int = BUDGET_WORDS) -> list[Paragraph]:
    picked, used = [], 0
    for p in results:
        words = len(p.text.split())
        if used + words > budget:
            break
        picked.append(p)
        used += words
    return picked


def expand(context: list[Paragraph], units: list[Paragraph], window: int) -> list[Paragraph]:
    """Widen each retrieved chunk to include `window` neighbors on each side (same
    chapter only), merging overlaps. Retrieval stays on small chunks, and the reader
    gets enough surrounding text to know who is speaking and what is going on."""
    if window == 0:
        return context
    by_idx = {u.id: u for u in units}
    spans: list[list[int]] = []
    for p in context:
        lo, hi = p.id, p.id
        while lo - 1 in by_idx and by_idx[lo - 1].chapter == p.chapter and p.id - lo < window:
            lo -= 1
        while hi + 1 in by_idx and by_idx[hi + 1].chapter == p.chapter and hi - p.id < window:
            hi += 1
        for s in spans:
            if lo <= s[1] + 1 and hi >= s[0] - 1 and by_idx[s[0]].chapter == p.chapter:
                s[0], s[1] = min(s[0], lo), max(s[1], hi)
                break
        else:
            spans.append([lo, hi])
    # Chunks overlap by design, so joined neighbors repeat a little text. That is fine for reading.
    return [Paragraph(lo, by_idx[lo].chapter, " ".join(by_idx[i].text for i in range(lo, hi + 1)))
            for lo, hi in spans]


def messages_for(question: str, context: list[Paragraph]) -> list[dict]:
    passages = "\n\n".join(f"[{i}] (Chapter {p.chapter}) {p.text}" for i, p in enumerate(context, 1))
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Passages:\n\n{passages}\n\nQuestion: {question}"},
    ]


def citations(answer: str, context: list[Paragraph]) -> list[Paragraph]:
    nums = {int(n) for n in re.findall(r"\[(\d+)\]", answer)}
    return [context[n - 1] for n in sorted(nums) if 1 <= n <= len(context)]


def abstained(answer: str) -> bool:
    return "i don't know" in answer.lower().replace("’", "'")
