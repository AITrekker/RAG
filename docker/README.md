# Docker Configuration

Simplified 3-service Docker architecture for the RAG platform.

## Services

- **PostgreSQL** - Database with pgvector extension (port 5432)
- **Backend** - FastAPI application (port 8000)  
- **Frontend** - React development server (port 3000)

## Quick Start

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f backend

# Rebuild backend
make backend-build
```

## Architecture

The platform uses PostgreSQL + pgvector for unified storage, eliminating the need for separate vector databases or caching layers.

See [docs/GUIDE.md](../docs/GUIDE.md) for complete deployment documentation.