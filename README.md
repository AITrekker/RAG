# rag

A RAG prototype built in graduated steps. Each step builds the simplest thing that could work, measures where it fails, and lets that failure pick the next step. The plan lives in `../plan.md`.

## Step 0

Run `scripts/step0_check.sh` inside WSL from `~/rag`. It checks the GPU, uv, and Docker, creates `.env` with a random Postgres password, starts pgvector, and syncs the Python environment.
