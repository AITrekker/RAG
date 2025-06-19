#!/bin/bash

# Enterprise RAG Pipeline Docker Entrypoint Script

set -e

echo "Starting Enterprise RAG Pipeline..."

# Check GPU availability
if command -v nvidia-smi &> /dev/null; then
    echo "GPU detected:"
    nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader,nounits
else
    echo "Warning: GPU not detected, running in CPU mode"
fi

# Check if database needs initialization
if [ ! -f "/app/data/db/enterprise_rag.db" ]; then
    echo "Initializing database..."
    # Database initialization will be handled by alembic when we implement it
fi

# Create log directory if it doesn't exist
mkdir -p /app/data/logs

# Set permissions for data directories
chown -R $(id -u):$(id -g) /app/data/

echo "Starting application server..."
# Start the FastAPI application
exec python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload 