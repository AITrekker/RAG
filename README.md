# rag

A RAG prototype built in graduated steps. Each step builds the simplest thing that could work, measures where it fails, and lets that failure pick the next step. The plan lives in `../plan.md`.

## Step 0

Run `scripts/step0_check.sh` inside WSL from `~/rag`. It checks the GPU, uv, and Docker, creates `.env` with a random Postgres password, starts pgvector, and syncs the Python environment.

## Step 1: substring search

`uv run rag search "Who was Ahab?"` returns every paragraph containing all the non-filler words of the question, in book order. `uv run rag eval --step step-1` scores it against `eval.yaml` and appends a row to `runs/results.csv`. Results and notes are in `runs/log.md`.

## Step 2: BM25

`uv run rag search "..." --mode bm25` ranks paragraphs with BM25, and BM25 is now the default mode. `uv run python scripts/rescore.py` rescores every step tag against the current eval set and writes `runs/rescore.csv`.

## Step 3: embeddings

`uv run rag search "..." --mode vector` ranks paragraphs by embedding similarity with bge-small-en-v1.5 on the GPU. PyTorch comes from the CUDA 12.8 wheel index, which includes sm_120 kernels for the RTX 5070, and the project is pinned to Python 3.12 in `.venv`.

## Step 4: chunking

`--chunking r128` (or r256, r384, r512) switches from paragraphs to token-sized recursive chunks, for example `uv run rag eval --step step-4 --mode vector --chunking r128`. The eval reports recall@800w alongside recall@5, which compares chunk sizes at an equal amount of retrieved text.
