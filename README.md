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

## Step 5: hybrid search

`uv run rag search "..." --mode hybrid --chunking r128` merges BM25 and vector rankings with reciprocal rank fusion (K = 60).

## Step 6: Postgres and pgvector

`docker compose up -d db` starts Postgres with pgvector (it restarts with Docker). `uv run rag ingest --chunking r128` stores chunks and embeddings in one transaction and skips work already done. The `pg-vector`, `pg-vector-exact`, and `pg-hybrid` modes search from the database, and `pg-hybrid` is now the default.

## Step 7: generation

`./scripts/start-vllm.sh` serves Qwen3-8B AWQ on 127.0.0.1:8001 (stop it with `./scripts/stop-vllm.sh`). `uv run rag ask "Who was Ahab?"` answers with numbered citations. `uv run rag answer-eval --step step-7` answers every eval question and writes `runs/<step>-<config>-answers.md`, and `uv run rag grade --step step-7` applies hand grades from `runs/grades/`. `--window 2` (the default) widens each retrieved chunk by two neighbors for the reader.

## Steps 8 and 9: headers and summaries

`uv run rag contextualize --chunking r128` writes a Qwen header for every chunk to `data/contexts-r128.jsonl`, and `--chunking r128ctx` indexes chunks with their headers. `uv run rag summarize` writes chapter summaries to `data/summaries.jsonl`, and a `sum` suffix (`r128sum`, `r128ctxsum`) adds them to the index. Both data files are committed, so rebuilding the index needs no GPU time for generation.
