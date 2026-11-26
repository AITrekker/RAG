#!/usr/bin/env bash
# Stop only the web server this project started (its whole process group).
cd "$(dirname "$0")/.."
[ -f logs/web.pid ] && kill -- -"$(cat logs/web.pid)" 2>/dev/null && echo stopped || echo "not running"
rm -f logs/web.pid
