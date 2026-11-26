"""Rescore every step tag against the current eval.yaml.

Each step-N tag is checked out into a temporary git worktree, the current eval.yaml
is copied in, and that tag's own code runs `rag eval`. The summaries land in
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
STEP_MODES = {
    "step-1": ["substring"],
    "step-2": ["substring", "bm25"],
}


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
                for mode in STEP_MODES[tag]:
                    print(f"scoring {tag} {mode}", flush=True)
                    subprocess.run(["uv", "run", "-q", "rag", "eval", "--step", tag, "--mode", mode],
                                   cwd=wt, check=True, capture_output=True, text=True)
                    detail = wt / "runs" / f"{tag}-{mode}.json"
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
