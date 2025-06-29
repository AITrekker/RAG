#!/bin/bash
# Shortcut to run delta sync in Docker container

echo "🚀 Delta Sync"

# Check if Docker containers are running
if ! docker ps | grep -q "rag_backend"; then
    echo "❌ Backend container not running"
    echo "💡 Run: docker-compose up -d"
    exit 1
fi

# Run the delta sync script with clean output
echo "⚡ Processing..."
docker exec rag_backend python scripts/delta-sync.py 2>/dev/null | grep -E "🚀|📊|✅|❌|⚠️|💡|🎉"

echo "✅ Complete!"