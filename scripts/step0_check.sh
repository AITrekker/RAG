#!/usr/bin/env bash
# Step 0 smoke test. Run inside WSL from ~/rag.
set -u
ok(){ echo "OK   $1"; }; bad(){ echo "FAIL $1"; }
grep -qi microsoft /proc/version && ok "running in WSL" || bad "not WSL"
case "$PWD" in /mnt/*) bad "repo is on /mnt (slow); move it to ~/rag";; *) ok "repo on Linux filesystem";; esac
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader && ok "GPU visible" || bad "nvidia-smi"
command -v uv >/dev/null && ok "uv $(uv --version)" || bad "uv missing: curl -LsSf https://astral.sh/uv/install.sh | sh"
command -v docker >/dev/null && ok "$(docker --version)" || bad "docker missing"
free -g | awk '/Mem:/{print "INFO WSL memory total " $2 "G"}'
[ -f .env ] || { cp .env.example .env; sed -i "s/change-me/$(openssl rand -hex 16)/g" .env; ok "created .env with random password"; }
docker compose up -d db && sleep 5
docker compose exec -T db psql -U rag -d rag -c "CREATE EXTENSION IF NOT EXISTS vector; SELECT extversion FROM pg_extension WHERE extname='vector';" && ok "pgvector" || bad "pgvector"
uv sync -q && ok "uv sync" || bad "uv sync"
