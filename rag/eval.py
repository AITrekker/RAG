"""Score a search mode against eval.yaml.

A question is a hit at k when any of the top k results comes from one of its gold
chapters. MRR uses the rank of the first gold-chapter result within the top 10.

recall@800w is the fairer comparison across chunk sizes. It walks down the ranked
results until 800 words of text have been used (about 1,000 tokens, a realistic
amount of context to hand a generator) and counts a hit if any of that text comes
from a gold chapter. Five big chunks hold more text than five small ones, so
recall@5 alone favors big chunks.
Unanswerable questions are left out of the averages and reported separately.
"""

import csv
import json
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"


def load_questions():
    return yaml.safe_load((ROOT / "eval.yaml").read_text())["questions"]


BUDGET_WORDS = 800


def hit_within_budget(results, gold) -> bool:
    used = 0
    for p in results:
        used += len(p.text.split())
        if used > BUDGET_WORDS:
            return False
        if p.chapter in gold:
            return True
    return False


def score(search_fn, step: str, mode: str, k: int = 5) -> dict:
    rows = []
    for q in load_questions():
        results = search_fn(q["question"])
        gold = {str(c) for c in q["gold_chapters"]}
        ranks = [i + 1 for i, p in enumerate(results[:10]) if p.chapter in gold]
        rows.append({
            "id": q["id"],
            "category": q["category"],
            "question": q["question"],
            "n_results": len(results),
            "top_chapters": [p.chapter for p in results[:k]],
            "hit": bool(ranks and ranks[0] <= k) if gold else None,
            "rr": (1 / ranks[0] if ranks else 0.0) if gold else None,
            "hit_800w": hit_within_budget(results, gold) if gold else None,
        })

    answerable = [r for r in rows if r["hit"] is not None]
    summary = {
        "step": step,
        "mode": mode,
        "time": time.strftime("%Y-%m-%d %H:%M"),
        f"recall@{k}": round(sum(r["hit"] for r in answerable) / len(answerable), 3),
        "mrr@10": round(sum(r["rr"] for r in answerable) / len(answerable), 3),
        "recall@800w": round(sum(r["hit_800w"] for r in answerable) / len(answerable), 3),
        "n_answerable": len(answerable),
        "ahab_who": next(r["hit"] for r in rows if r["id"] == "q01"),
        "ahab_beef": next(r["hit"] for r in rows if r["id"] == "q02"),
    }

    RUNS.mkdir(exist_ok=True)
    (RUNS / f"{step}-{mode}.json").write_text(json.dumps({"summary": summary, "questions": rows}, indent=2))
    results_csv = RUNS / "results.csv"
    new = not results_csv.exists()
    with results_csv.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary))
        if new:
            w.writeheader()
        w.writerow(summary)
    return {"summary": summary, "questions": rows}
