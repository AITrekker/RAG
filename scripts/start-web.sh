#!/usr/bin/env bash
# Serve the web page on 127.0.0.1:8080 inside WSL. Safe to repeat.
# From the Mac: ssh -N -L 8080:127.0.0.1:8080 desktop-wsl, then open http://localhost:8080
set -eu
cd "$(dirname "$0")/.."
if curl -sf http://127.0.0.1:8080/api/books >/dev/null; then echo "web already running"; exit 0; fi
curl -sf http://127.0.0.1:8001/v1/models >/dev/null || echo "note: vLLM is not running; start it with scripts/start-vllm.sh"
mkdir -p logs
setsid nohup uv run uvicorn rag.web:app --host 127.0.0.1 --port 8080 >>logs/web.log 2>&1 </dev/null &
echo $! > logs/web.pid
for i in $(seq 1 60); do
  curl -sf http://127.0.0.1:8080/api/books >/dev/null && { echo "web up on 127.0.0.1:8080"; exit 0; }
  sleep 1
done
echo "web did not start; see logs/web.log"; tail -20 logs/web.log; exit 1
