# Docker Configuration - RAG Platform

## Overview

The RAG platform uses a **simplified, 3-service Docker architecture** after removing Redis and Nginx dependencies:

- **Qdrant** - Vector database (only database)
- **Backend** - FastAPI application  
- **Frontend** - React/Vite development server

## Services

### 1. Qdrant Vector Database
- **Image**: `qdrant/qdrant:v1.7.4`
- **Ports**: 6333 (HTTP), 6334 (gRPC)
- **Storage**: Named volume `qdrant_storage`
- **Purpose**: Single source of truth for all data storage

### 2. Backend API
- **Build**: `docker/Dockerfile.backend`
- **Base**: NVIDIA PyTorch container for GPU support
- **Port**: 8000
- **Features**:
  - Hot reload for development
  - Optimized requirements installation (base + app packages)
  - Non-root user for security
  - Volume mounts for development

### 3. Frontend
- **Build**: `docker/Dockerfile.frontend`  
- **Base**: Node.js 20 Alpine
- **Port**: 3000
- **Features**:
  - Vite development server with HMR
  - Health checks
  - Volume mounts for development

## Quick Start

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Rebuild after changes
docker-compose build --no-cache
```

## Development Workflow

```bash
# Start with live reloading
docker-compose up

# Backend only (for API development)
docker-compose up qdrant backend

# Frontend only (with external API)
docker-compose up frontend
```

## Environment Variables

The system uses a clean `.env` file without Redis/Nginx references:

- **QDRANT_URL**: Vector database connection
- **EMBEDDING_MODEL**: HuggingFace model for embeddings
- **LLM_MODEL**: Language model for generation
- **VITE_API_BASE_URL**: Frontend → Backend communication

## Volume Mounts

**Development**:
- `./src/backend` → `/app/src/backend` (hot reload)
- `./src/frontend` → `/app` (hot reload)
- `./cache` → `/app/cache` (model caching)
- `./logs` → `/app/logs` (logging)

**Production**: 
- `qdrant_storage` → `/qdrant/storage` (data persistence)

## Removed Components

✅ **Eliminated**:
- ❌ Redis (caching layer)
- ❌ Nginx (reverse proxy)
- ❌ PostgreSQL (relational database)
- ❌ ChromaDB (vector database)

✅ **Benefits**:
- Simpler architecture
- Faster startup times
- Easier debugging
- Reduced resource usage
- Single database (Qdrant) for all data

## Troubleshooting

**Container won't start**: Check `.env` file exists
**Build fails**: Verify requirements files are clean
**Port conflicts**: Ensure ports 3000, 6333, 8000 are available
**Volume issues**: Check file permissions and paths 