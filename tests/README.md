# Test Suite

Comprehensive testing for the Enterprise RAG Platform.

## Quick Start

```bash
# Prerequisites
docker-compose up -d
python scripts/workflow/setup_demo_tenants.py

# Run all tests
python run_all_tests.py

# Run specific tests
python -m pytest tests/test_api_health.py -v
python -m pytest tests/test_api_query.py -v
```

## Test Categories

### API Tests
- **`test_api_health.py`** - Health checks and system status
- **`test_api_sync.py`** - Sync operations and file processing
- **`test_api_query.py`** - RAG queries and semantic search
- **`test_api_multitenancy.py`** - Tenant isolation and security
- **`test_api_templates.py`** - Template management
- **`test_analytics_api.py`** - Analytics and metrics

### Service Tests
- **`test_sync_service.py`** - Sync service functionality
- **`test_embedding_service.py`** - Document processing and embeddings
- **`test_rag_comprehensive.py`** - End-to-end RAG pipeline
- **`test_comprehensive_sync_embeddings.py`** - Complete sync workflow

## Configuration

Tests use the `demo_tenant_keys.json` file created by the setup script. Ensure your `.env` file has:

```bash
BACKEND_URL=http://localhost:8000
ADMIN_API_KEY=your_admin_key
```

See [docs/GUIDE.md](../docs/GUIDE.md) for complete testing documentation.