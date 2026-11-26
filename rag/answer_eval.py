"""Score generated answers for every eval question.

Automatic checks, per question:
- in_context: the 800-word context contains a chunk from a gold chapter
- cites_gold: the answer cites at least one gold-chapter chunk
- abstained: the answer says "I don't know"

Correctness needs a reader. Each run writes runs/<step>-<config>-answers.md with the
question, expected answer, and generated answer side by side. Grades go in
runs/grades/<step>-<config>.yaml as `qNN: correct | partial | wrong`, and
`rag grade --step ... --mode ... --chunking ...` folds them into the saved run
without regenerating any answers. For unanswerable questions, "correct" means the
answer says the book doesn't give it, whatever the exact wording.
"""

import csv
import json
import time

import yaml

from .eval import RUNS, load_questions
from .generate import abstained, chat_many, citations, expand, messages_for, select_context


def run(search_fn, step: str, config: str, units=None, window: int = 0) -> dict:
    qs = load_questions()
    contexts = [expand(select_context(search_fn(q["question"])), units, window) for q in qs]
    answers = chat_many([messages_for(q["question"], c) for q, c in zip(qs, contexts)])
    rows = []
    for q, ctx, ans in zip(qs, contexts, answers):
        rows.append({
            "id": q["id"], "category": q["category"], "question": q["question"],
            "expected": q["answer"], "answer": ans,
            "context_chapters": [p.chapter for p in ctx],
            "cited_chapters": [p.chapter for p in citations(ans, ctx)],
            "abstained": abstained(ans),
        })
    return finish(rows, step, config)


def grade(step: str, config: str) -> dict:
    data = json.loads((RUNS / f"{step}-{config}-answers.json").read_text())
    return finish(data["questions"], step, config)


def finish(rows: list[dict], step: str, config: str) -> dict:
    """Recompute checks against the current eval.yaml, apply grades, and write outputs."""
    gold_by_id = {q["id"]: {str(c) for c in q["gold_chapters"]} for q in load_questions()}
    grades_file = RUNS / "grades" / f"{step}-{config}.yaml"
    grades = yaml.safe_load(grades_file.read_text()) if grades_file.exists() else {}
    for r in rows:
        gold = gold_by_id[r["id"]]
        r["in_context"] = any(c in gold for c in r["context_chapters"]) if gold else None
        r["cites_gold"] = any(c in gold for c in r["cited_chapters"]) if gold else None
        r["grade"] = grades.get(r["id"])

    answerable = [r for r in rows if r["in_context"] is not None]
    unanswerable = [r for r in rows if r["in_context"] is None]
    count = lambda rs, f: f"{sum(1 for r in rs if f(r))}/{len(rs)}"
    graded = bool(grades)
    summary = {
        "step": step, "config": config, "time": time.strftime("%Y-%m-%d %H:%M"),
        "in_context": count(answerable, lambda r: r["in_context"]),
        "cites_gold": count(answerable, lambda r: r["cites_gold"]),
        "false_abstain": count(answerable, lambda r: r["abstained"]),
        "abstain_unanswerable": count(unanswerable, lambda r: r["abstained"]),
        "correct": count(answerable, lambda r: r["grade"] == "correct") if graded else "",
        "partial": count(answerable, lambda r: r["grade"] == "partial") if graded else "",
        "wrong_with_gold_in_context": count(
            answerable, lambda r: r["grade"] == "wrong" and r["in_context"]) if graded else "",
        "unanswerable_correct": count(unanswerable, lambda r: r["grade"] == "correct") if graded else "",
    }

    base = RUNS / f"{step}-{config}-answers"
    base.with_suffix(".json").write_text(json.dumps({"summary": summary, "questions": rows}, indent=2))
    lines = [f"# Answers: {step} {config}\n", f"{summary}\n"]
    for r in rows:
        lines += [f"## {r['id']} ({r['category']}) {r['question']}\n",
                  f"Expected: {r['expected']}\n",
                  f"Answer: {r['answer']}\n",
                  f"Context chapters {r['context_chapters']}, cited {r['cited_chapters']}, "
                  f"gold in context {r['in_context']}, grade {r['grade']}\n"]
    base.with_suffix(".md").write_text("\n".join(lines))

    # answers.csv keeps one row per step and config, replaced on each run or regrade.
    out = RUNS / "answers.csv"
    old = list(csv.DictReader(out.open())) if out.exists() else []
    keep = [r for r in old if (r["step"], r["config"]) != (step, config)]
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary), extrasaction="ignore")
        w.writeheader()
        w.writerows(keep + [summary])
    return {"summary": summary, "questions": rows}
