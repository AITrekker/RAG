# rag

A RAG prototype built in graduated steps. Each step builds the simplest thing that could work, measures where it fails, and lets that failure pick the next step. The plan lives in `../plan.md`.

## Step 0

Run `scripts/step0_check.sh` inside WSL from `~/rag`. It checks the GPU, uv, and Docker, creates `.env` with a random Postgres password, starts pgvector, and syncs the Python environment.

## Step 1: substring search

`uv run rag search "Who was Ahab?"` returns every paragraph containing all the non-filler words of the question, in book order. `uv run rag eval --step step-1` scores it against `eval.yaml` and appends a row to `runs/results.csv`. Results and notes are in `runs/log.md`.

## Step 2: BM25

`uv run rag search "..." --mode bm25` ranks paragraphs with BM25, and BM25 is now the default mode. `uv run python scripts/rescore.py` rescores every step tag against the current eval set and writes `runs/rescore.csv`.
