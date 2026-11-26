#!/usr/bin/env bash
# Serve Qwen3-8B (AWQ 4-bit) for generation on 127.0.0.1:8001 from the /root/vllm env.
# gpu-memory-utilization 0.85 leaves about 1.8 GB on the 12 GB card for the embedding model.
# Safe to repeat: it does nothing if the server is already up.
set -eu
cd "$(dirname "$0")/.."
if curl -sf http://127.0.0.1:8001/v1/models >/dev/null; then echo "vLLM already running"; exit 0; fi
mkdir -p logs
VLLM_USE_FLASHINFER_SAMPLER=0 setsid nohup /root/vllm/bin/vllm serve Qwen/Qwen3-8B-AWQ \
  --served-model-name qwen3-8b --host 127.0.0.1 --port 8001 \
  --max-model-len 8192 --gpu-memory-utilization 0.85 --max-num-seqs 16 \
  >>logs/vllm.log 2>&1 </dev/null &
echo $! > logs/vllm.pid
for i in $(seq 1 180); do
  curl -sf http://127.0.0.1:8001/v1/models >/dev/null && { echo "vLLM up after ${i}0s"; exit 0; }
  kill -0 "$(cat logs/vllm.pid)" 2>/dev/null || { echo "vLLM exited; see logs/vllm.log"; tail -20 logs/vllm.log; exit 1; }
  sleep 10
done
echo "vLLM not up after 30 minutes"; exit 1
