# Test Suite

Comprehensive testing for the Simplified RAG Platform.

## Quick Start

```bash
# Prerequisites
docker-compose up -d
python scripts/workflow/demo_workflow.py

# Run all tests
python run_all_tests.py

# Run new simplified architecture tests
python -m pytest tests/test_simplified_architecture.py -v

# Run specific API tests
python -m pytest tests/test_api_health.py -v
python -m pytest tests/test_api_query.py -v
```

## Test Categories

### New Architecture Tests
- **`test_simplified_architecture.py`** - **NEW**: Tests for simplified services

### API Tests (Updated for new architecture)
- **`test_api_health.py`** - Health checks and system status
- **`test_api_sync.py`** - Sync operations (may need updates)
- **`test_api_query.py`** - RAG queries (may need updates) 
- **`test_api_multitenancy.py`** - Tenant isolation and security
- **`test_api_templates.py`** - Template management
- ~~`test_analytics_api.py`~~ - Removed (analytics complexity eliminated)

### Legacy Service Tests (Need Updates)
- **`test_sync_service.py`** - ⚠️ Needs update for simplified sync service
- **`test_embedding_service.py`** - ⚠️ Needs rewrite for SimplifiedEmbeddingService
- **`test_rag_comprehensive.py`** - ⚠️ Needs update for MultiTenantRAGService
- **`test_comprehensive_sync_embeddings.py`** - ⚠️ Needs rewrite for new architecture

## Migration Notes

### New Architecture Testing
The simplified architecture introduces:
- `MultiTenantRAGService` - Single RAG service with LlamaIndex
- `UnifiedDocumentProcessor` - Single document processing path
- `SimplifiedEmbeddingService` - Simplified embedding tracking

### Legacy Tests Status
Some tests may fail until updated for the new architecture:
1. Tests using old `PgVectorEmbeddingService` → Update to `SimplifiedEmbeddingService`
2. Tests using old `RAGService` → Update to `MultiTenantRAGService`
3. Tests using complex dual-path processing → Update for unified processing

### Quick Test Commands
```bash
# Test new architecture only
python -m pytest tests/test_simplified_architecture.py -v

# Test API compatibility
python -m pytest tests/test_api_* -v

# Test specific service (may need updates)
python -m pytest tests/test_rag_comprehensive.py -v
```

## Configuration

Tests use the `demo_tenant_keys.json` file created by the setup script. Ensure your `.env` file has:

```bash
BACKEND_URL=http://localhost:8000
ADMIN_API_KEY=your_admin_key
```

See [docs/GUIDE.md](../docs/GUIDE.md) for complete testing documentation.