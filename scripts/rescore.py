"""Rescore every step tag against the current eval.yaml.

Each step-N tag is checked out into a temporary git worktree, the current eval.yaml
and eval harness (rag/eval.py) are copied in, and that tag's own search code runs
`rag eval`. The summaries land in
runs/rescore.csv, labeled with a hash of the eval set, so all steps are compared on
the same questions.

Usage: uv run python scripts/rescore.py [step-1 step-3 ...]
"""

import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# Search modes to score for each step. Add a line when a step is tagged.
# An entry is a mode, optionally followed by extra `rag eval` arguments.
STEP_MODES = {
    "step-1": ["substring"],
    "step-2": ["substring", "bm25"],
    "step-3": ["bm25", "bm25-stem", "vector"],
    "step-4": ["bm25", "vector"]
    + [f"{m} --chunking r{n}" for m in ("bm25", "vector") for n in (128, 256, 384, 512)],
    "step-5": [f"{m} --chunking r128" for m in ("bm25", "vector", "hybrid")],
    "step-6": [f"{m} --chunking r128" for m in ("pg-vector", "pg-vector-exact", "pg-hybrid")],
    "step-7": ["pg-hybrid --chunking r128"],  # retrieval only; answers are graded by hand
}


def label(spec: str) -> str:
    mode, *extra = spec.split()
    return mode if not extra else f"{mode}+{extra[1]}"


def git(*args, cwd=ROOT):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def main():
    eval_file = ROOT / "eval.yaml"
    eval_set = hashlib.sha256(eval_file.read_bytes()).hexdigest()[:8]
    n_questions = len(yaml.safe_load(eval_file.read_text())["questions"])

    tags = sys.argv[1:] or sorted(
        (t for t in git("tag", "-l", "step-*").split() if t in STEP_MODES),
        key=lambda t: int(t.split("-")[1]),
    )
    rows = []
    with tempfile.TemporaryDirectory(prefix="rag-rescore-") as tmp:
        for tag in tags:
            wt = Path(tmp) / tag
            git("worktree", "add", "--detach", str(wt), tag)
            try:
                shutil.copy(eval_file, wt / "eval.yaml")
                shutil.copy(ROOT / "rag" / "eval.py", wt / "rag" / "eval.py")
                if (ROOT / ".env").exists():
                    shutil.copy(ROOT / ".env", wt / ".env")  # database credentials for pg modes
                for chunking in sorted({s.split()[-1] for s in STEP_MODES[tag] if s.startswith("pg-")}):
                    subprocess.run(["uv", "run", "-q", "rag", "ingest", "--chunking", chunking],
                                   cwd=wt, check=True, capture_output=True, text=True)
                for spec in STEP_MODES[tag]:
                    mode, *extra = spec.split()
                    print(f"scoring {tag} {spec}", flush=True)
                    subprocess.run(["uv", "run", "-q", "rag", "eval", "--step", tag, "--mode", mode, *extra],
                                   cwd=wt, check=True, capture_output=True, text=True)
                    detail = wt / "runs" / f"{tag}-{label(spec)}.json"
                    (ROOT / "runs" / "rescore").mkdir(parents=True, exist_ok=True)
                    shutil.copy(detail, ROOT / "runs" / "rescore" / detail.name)
                    summary = json.loads(detail.read_text())["summary"]
                    rows.append({"eval_set": eval_set, "n_questions": n_questions, **summary})
            finally:
                git("worktree", "remove", "--force", str(wt))

    out = ROOT / "runs" / "rescore.csv"
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(out.read_text())


if __name__ == "__main__":
    main()
