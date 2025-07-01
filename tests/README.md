# RAG System API Test Suite

**API-only testing for the Enterprise RAG Platform - no business logic, pure API calls.**

## 🎯 Test Suite Overview

This test suite contains **4 focused API test files** that validate the RAG system through HTTP API calls only, ensuring proper separation between testing and business logic.

## Quick Start

### Install Test Dependencies
```bash
cd /mnt/d/GitHub/RAG

# Install minimal test requirements
pip install -r tests/requirements-minimal.txt
```

### Prerequisites
1. Backend services running: `docker-compose up -d`
2. Demo tenants set up: `python scripts/workflow/setup_demo_tenants.py`
3. API keys available in `demo_tenant_keys.json`

### Run Tests

**Option 1: Use the comprehensive test runner (Recommended)**
```bash
# Run all tests with comprehensive reporting
python3 run_all_tests.py

# Run specific category
python3 run_all_tests.py --category health
python3 run_all_tests.py --category sync
python3 run_all_tests.py --category query

# Fast mode (stop on first failure)
python3 run_all_tests.py --fast

# Verbose output with detailed logs
python3 run_all_tests.py --verbose
```

**Option 2: Use pytest directly**
```bash
# Run all API tests
python3 -m pytest tests/ -v

# Run specific test categories
python3 -m pytest tests/test_api_health.py -v
python3 -m pytest tests/test_api_sync.py -v
python3 -m pytest tests/test_api_query.py -v
python3 -m pytest tests/test_api_multitenancy.py -v
```

## 🧪 API Test Files

### 1. **`test_api_health.py`**
**Health check and system status validation**
- Health endpoint: `GET /api/v1/health/`
- Liveness endpoint: `GET /api/v1/health/liveness`
- OpenAPI documentation accessibility
- Basic system connectivity

### 2. **`test_api_sync.py`**
**Sync operation API validation**
- Trigger sync: `POST /api/v1/sync/trigger`
- Sync status: `GET /api/v1/sync/status`
- Sync history: `GET /api/v1/sync/history`
- Change detection: `POST /api/v1/sync/detect-changes`
- Authentication and authorization testing

### 3. **`test_api_query.py`**
**RAG query API validation**
- Basic RAG query: `POST /api/v1/query/`
- Semantic search: `POST /api/v1/query/search`
- Query validation: `POST /api/v1/query/validate`
- Query suggestions: `GET /api/v1/query/suggestions`
- Multi-tenant result isolation
- Error handling (empty queries, invalid requests)

### 4. **`test_api_multitenancy.py`**
**Multi-tenancy isolation validation**
- Cross-tenant sync isolation
- Cross-tenant query isolation
- API key validation and security
- Tenant-specific document verification

## 🔧 Test Configuration

### Environment Variables
```bash
# Required in .env file
BACKEND_URL=http://localhost:8000
ADMIN_API_KEY=your_admin_key
```

### Test Data
- Uses `demo_tenant_keys.json` for tenant API keys
- Tests against real demo tenant data
- No test data setup required (uses existing tenant files)

### API Endpoints Tested
```
Health:
- GET /api/v1/health/
- GET /api/v1/health/liveness

Sync:
- POST /api/v1/sync/trigger
- GET /api/v1/sync/status
- GET /api/v1/sync/history
- POST /api/v1/sync/detect-changes

Query:
- POST /api/v1/query/
- POST /api/v1/query/search
- POST /api/v1/query/validate
- GET /api/v1/query/suggestions
```

## 🎯 Key Validations

### 1. **API Response Structure**
```python
# Query response validation
assert "query" in data
assert "answer" in data
assert "sources" in data
assert "confidence" in data
assert "processing_time" in data
```

### 2. **Multi-Tenant Isolation**
```python
# Different tenants get different documents
tenant1_sources = [s["filename"] for s in response1["sources"]]
tenant2_sources = [s["filename"] for s in response2["sources"]]
# Should have different document sets
```

### 3. **Authentication Security**
```python
# Unauthorized access rejected
response = requests.post(url, headers=no_auth)
assert response.status_code == 401
```

### 4. **Error Handling**
```python
# Empty query properly rejected
response = requests.post(url, json={"query": ""})
assert response.status_code == 400
```

## 📊 Test Results

### Success Criteria
- ✅ **Health Checks**: System status and connectivity
- ✅ **Sync Operations**: File processing and change detection
- ✅ **RAG Queries**: Answer generation with source attribution
- ✅ **Multi-Tenancy**: Complete tenant isolation
- ✅ **Security**: Proper authentication and authorization
- ✅ **Error Handling**: Graceful error responses

### Performance Expectations
- Health checks: < 1 second
- Sync operations: < 10 seconds
- RAG queries: < 5 seconds
- API response times: < 1 second

## 🚀 Running Specific Scenarios

### Quick System Validation
```bash
# Basic health check
python3 -m pytest tests/test_api_health.py::TestAPIHealth::test_health_endpoint -v

# Test API authentication
python3 -m pytest tests/test_api_sync.py::TestAPISync::test_sync_unauthorized -v
```

### RAG Functionality
```bash
# Basic RAG query test
python3 -m pytest tests/test_api_query.py::TestAPIQuery::test_basic_rag_query -v

# Tenant isolation test
python3 -m pytest tests/test_api_query.py::TestAPIQuery::test_tenant_isolation -v
```

### Multi-Tenancy Validation
```bash
# Cross-tenant isolation
python3 -m pytest tests/test_api_multitenancy.py::TestAPIMultitenancy::test_tenant_isolation_query -v

# API key security
python3 -m pytest tests/test_api_multitenancy.py::TestAPIMultitenancy::test_api_key_validation -v
```

## 🔍 Troubleshooting

### Common Issues

1. **Backend Not Running**:
   ```bash
   docker-compose up -d
   curl http://localhost:8000/api/v1/health/
   ```

2. **Missing API Keys**:
   ```bash
   python scripts/workflow/setup_demo_tenants.py --env development
   cat demo_tenant_keys.json
   ```

3. **Authentication Errors**:
   ```bash
   # Check API key format
   python3 -c "
   import json
   with open('demo_tenant_keys.json') as f:
       keys = json.load(f)
   print(keys['tenant1']['api_key'])
   "
   ```

### Debug Mode
```bash
# Verbose output with full details
python3 -m pytest tests/ -v -s --tb=long

# Single test with debugging
python3 -m pytest tests/test_api_query.py::TestAPIQuery::test_basic_rag_query -v -s
```

## ✅ Benefits of API-Only Testing

- **Clear Separation**: No business logic mixed with tests
- **True Integration**: Tests actual API endpoints users will call
- **Environment Agnostic**: Works with any deployment (local, staging, production)
- **Minimal Dependencies**: Only requires `requests`, `pytest`, and `python-dotenv`
- **Fast Execution**: No heavy ML model loading in tests
- **Realistic**: Tests the same paths external clients use

## 🎯 Bottom Line

**Pure API testing that validates the RAG system from the outside, exactly how it will be used in production.**

This approach ensures the API contracts work correctly while keeping tests independent of internal implementation details.