"""Step 12: what happens to retrieval when the corpus becomes a library.

1. Distractors. Run the 30 Moby-Dick questions against the whole library (Moby-Dick,
   War and Peace, and the company docs) and against Moby-Dick only, and count how
   many top-five results come from the wrong document.
2. Tenants. Run the company questions against the whole library, then with a
   metadata filter that keeps only the asking tenant's documents. Generate answers
   both ways so wrong-company answers are visible.

Search is in-memory hybrid (BM25 plus vectors, RRF) over r128 chunks. A metadata
filter in Postgres would be a WHERE clause on the document, which is the same
operation.

Usage: uv run python scripts/step12.py
"""

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rag import search_hybrid  # noqa: E402
from rag.eval import hit_within_budget, load_questions  # noqa: E402
from rag.generate import chat_many, expand, select_context  # noqa: E402
from rag.library import doc_of, filtered, load_library  # noqa: E402

SYSTEM = """You answer questions using only the numbered passages provided.
Rules:
- Use only facts stated in the passages.
- Cite the passages you used with their numbers in square brackets, like [2].
- If the passages do not contain the answer, reply with exactly: I don't know.
- Answer in one or two sentences."""


def messages(question, context, show_source=True):
    """show_source=False hides document labels, so the model sees only the text."""
    label = lambda p: f"({p.chapter}) " if show_source else ""
    passages = "\n\n".join(f"[{i}] {label(p)}{p.text}" for i, p in enumerate(context, 1))
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Passages:\n\n{passages}\n\nQuestion: {question}"}]


def main():
    library = load_library(128)
    views = {"library": library}
    counts = {}
    for u in library:
        counts[doc_of(u.chapter)] = counts.get(doc_of(u.chapter), 0) + 1
    print("chunks per document group:", {k: counts[k] for k in sorted(counts, key=counts.get, reverse=True)[:5]},
          f"... {len(library)} total")

    def view(name):
        if name not in views:
            views[name] = filtered(library, name)
        return views[name]

    out = {"moby": {}, "tenants": {}}

    # 1. Moby-Dick questions with and without distractors
    mq = [q for q in load_questions() if q["gold_chapters"]]
    for name in ("mobydick", "library"):
        units = view(name)
        hits = top5_hits = wrong_doc = 0
        for q in mq:
            gold = {str(c) for c in q["gold_chapters"]}
            res = search_hybrid.search(q["question"], units)
            hits += hit_within_budget(res, gold)
            top5_hits += any(p.chapter in gold for p in res[:5])
            wrong_doc += sum(doc_of(p.chapter) != "mobydick" for p in res[:5])
        out["moby"][name] = {"recall@800w": round(hits / len(mq), 3), "recall@5": round(top5_hits / len(mq), 3),
                             "top5_from_other_docs": f"{wrong_doc}/{5 * len(mq)}"}
        print("moby questions on", name, out["moby"][name])

    # 2. Company questions with and without a tenant filter
    lq = yaml.safe_load((ROOT / "eval_library.yaml").read_text())["questions"]
    for mode in ("no filter", "tenant filter", "no filter, labels hidden"):
        rows, batch = [], []
        for q in lq:
            units = view(q["tenant"]) if mode == "tenant filter" else view("library")
            res = search_hybrid.search(q["question"], units)
            ctx = expand(select_context(res), units, 2)
            rows.append({"id": q["id"], "question": q["question"], "expected": q["answer"],
                         "hit_800w": hit_within_budget(res, set(q["gold"])),
                         "top5": [p.chapter for p in res[:5]],
                         "context_docs": sorted({p.chapter for p in ctx})})
            batch.append(messages(q["question"], ctx, show_source="hidden" not in mode))
        for r, a in zip(rows, chat_many(batch)):
            r["answer"] = a
        out["tenants"][mode] = rows
        print(f"\ncompany questions, {mode}: recall@800w "
              f"{sum(r['hit_800w'] for r in rows)}/{len(rows)}")
        for r in rows:
            print(f"  {r['id']} hit={r['hit_800w']} top5={r['top5'][:3]} answer={r['answer'][:150]!r}")

    (ROOT / "runs" / "step-12.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
