#!/usr/bin/env bash
# Stop only the vLLM server this project started.
cd "$(dirname "$0")/.."
[ -f logs/vllm.pid ] && kill "$(cat logs/vllm.pid)" 2>/dev/null && echo stopped || echo "not running"
rm -f logs/vllm.pid
