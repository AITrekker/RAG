# Enterprise RAG Platform - Test Suite

This directory contains a comprehensive test suite for the Enterprise RAG Platform backend, ensuring robust testing of all core functionality.

## 🚀 **Quick Start**

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src/backend --cov-report=html

# Run specific test file
python -m pytest tests/test_api_endpoints.py -v

# Run API endpoint tests using the quick script
python tests/quick_api_test.py
```

## 📁 **Test Files Overview**

| Test File | Purpose | Key Coverage |
|-----------|---------|--------------|
| **`test_api_endpoints.py`** | **Complete API Testing** | All REST endpoints, authentication, validation |
| **`test_core_components.py`** | **Core Services** | Embeddings, vector store, monitoring |
| **`test_document_processing.py`** | **Document Pipeline** | Ingestion, processing, chunking |
| **`test_tenant_isolation.py`** | **Multi-tenant Security** | Data isolation, access controls |
| **`test_middleware_and_db.py`** | **Infrastructure** | Auth middleware, database models |
| **`test_delta_sync.py`** | **Synchronization** | File sync, change detection |
| **`test_embedding_config.py`** | **Embedding Configuration** | Model setup, GPU optimization |
| **`test_auditing.py`** | **Audit System** | Event logging, compliance |
| **`conftest.py`** | **Test Configuration** | Fixtures, setup, teardown |
| **`quick_api_test.py`** | **Live API Testing** | Endpoint validation against running server |
| **`test_sync.ps1`** | **Sync Testing** | PowerShell sync functionality tests |

## 🎯 **Test Categories**

### **🔗 API Integration Tests**
- **File**: `test_api_endpoints.py`
- **Coverage**: All REST API endpoints with authentication
- **Endpoints Tested**:
  - Document Management (upload, list, get, delete)
  - Query Processing (RAG queries, history)
  - Health Checks (basic, detailed, readiness, liveness)
  - Tenant Management (CRUD operations)
  - Sync Operations (trigger, status)
  - Audit Logs (events, history)

### **🧪 Unit Tests**
- **Files**: `test_core_components.py`, `test_embedding_config.py`
- **Coverage**: Individual services and utilities
- **Components**: Embedding service, vector store, monitoring

### **🛡️ Security Tests**
- **File**: `test_tenant_isolation.py`
- **Coverage**: Multi-tenant data separation
- **Scenarios**: Cross-tenant access prevention, data isolation

### **⚙️ Infrastructure Tests**
- **File**: `test_middleware_and_db.py`
- **Coverage**: Database models, authentication, middleware
- **Components**: Auth validation, session management, API security

### **📄 Document Processing Tests**
- **File**: `test_document_processing.py`
- **Coverage**: Document ingestion pipeline
- **Features**: File processing, chunking, metadata extraction

### **🔄 Synchronization Tests**
- **File**: `test_delta_sync.py`
- **Coverage**: File monitoring and sync operations
- **Features**: Change detection, sync triggers, status tracking

### **📊 Audit Tests**
- **File**: `test_auditing.py`
- **Coverage**: Audit logging and compliance tracking
- **Features**: Event logging, audit trails, reporting

## 🔧 **Running Tests**

### **Basic Commands**

```bash
# Run all tests with verbose output
python -m pytest tests/ -v

# Run tests with coverage reporting
python -m pytest tests/ --cov=src/backend --cov-report=html

# Run specific test file
python -m pytest tests/test_api_endpoints.py -v

# Run specific test method
python -m pytest tests/test_api_endpoints.py::TestAPIEndpoints::test_upload_document -v
```

### **Coverage Analysis**

```bash
# Generate HTML coverage report
python -m pytest tests/ --cov=src/backend --cov-report=html

# View coverage in terminal
python -m pytest tests/ --cov=src/backend --cov-report=term

# Coverage with missing line numbers
python -m pytest tests/ --cov=src/backend --cov-report=term-missing
```

### **Debugging Tests**

```bash
# Run with debugging output
python -m pytest tests/test_api_endpoints.py -v -s

# Run failing tests only
python -m pytest tests/ --lf

# Run with timing information
python -m pytest tests/ -v --durations=10
```

## ⚙️ **Test Configuration**

### **Environment Setup**

```bash
# Set Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Test environment variables
export RAG_ENV="test"
export DATABASE_URL="postgresql://rag_user:rag_password@localhost:5432/rag_test_database"
```

### **Requirements**

```bash
# Install test dependencies
pip install pytest pytest-cov pytest-mock

# Install all dependencies
pip install -r requirements.txt
```

## 🏗️ **Test Structure**

### **Fixtures (conftest.py)**

- **`client`**: Non-authenticated test client
- **`authenticated_client`**: Authenticated test client with valid API key
- **`test_app`**: FastAPI application instance for testing
- **`db_session`**: Database session for tests
- **`auth_headers`**: Authentication headers for manual requests

### **Mocking Strategy**

```python
# Service mocking example
@patch('src.backend.core.embeddings.get_embedding_service')
def test_with_mock_embeddings(mock_service):
    mock_service.return_value.encode_texts.return_value = [[0.1, 0.2, 0.3]]

# Database mocking example  
@patch('src.backend.db.session.get_db')
def test_with_mock_db(mock_db):
    mock_db.return_value = Mock()
```

## 📊 **Coverage Targets**

| Component | Target Coverage | Status |
|-----------|-----------------|--------|
| API Routes | 95%+ | ✅ |
| Core Services | 90%+ | ✅ |
| Models | 85%+ | ✅ |
| Utilities | 80%+ | ✅ |
| **Overall** | **85%+** | **✅** |

### **🌐 Live System Tests**
- **File**: `quick_api_test.py`
- **Coverage**: Live endpoint validation against running server
- **Features**: Real HTTP requests, authentication testing, comprehensive reporting

### **🔧 Platform-Specific Tests**
- **File**: `test_sync.ps1`
- **Coverage**: PowerShell-based sync testing for Windows
- **Features**: Sync trigger validation, status monitoring

## 🚀 **Alternative Testing**

### **Live API Testing**
For rapid endpoint validation without pytest setup:

```bash
# Test all endpoints against running server
python tests/quick_api_test.py

# Test sync functionality specifically (Windows)
.\tests\test_sync.ps1
```

## 🛠️ **Development Workflow**

### **Writing New Tests**

1. **Add tests to appropriate file** based on functionality
2. **Follow existing patterns** for mocking and assertions
3. **Use descriptive test names** with clear docstrings
4. **Test both success and failure scenarios**
5. **Update coverage expectations** if needed

### **Test Patterns**

```python
class TestComponentName:
    """Test suite for ComponentName."""
    
    def test_specific_functionality(self, authenticated_client, auth_headers):
        """Test specific functionality with clear description."""
        # Arrange
        test_data = {"key": "value"}
        
        # Act  
        response = authenticated_client.post("/api/endpoint", json=test_data, headers=auth_headers)
        
        # Assert
        assert response.status_code == 200
        assert response.json()["key"] == "expected_value"
```

## 🐛 **Troubleshooting**

### **Common Issues**

| Issue | Solution |
|-------|----------|
| Import errors | Check PYTHONPATH: `export PYTHONPATH="${PYTHONPATH}:$(pwd)"` |
| Database errors | Ensure test database exists and is accessible |
| Authentication failures | Check if test tenant/API key creation is working |
| Mock failures | Verify mock paths match actual import structure |

### **Debug Commands**

```bash
# Check test discovery
python -m pytest --collect-only

# Run with detailed failure info
python -m pytest tests/ -v --tb=long

# Run with print statements visible
python -m pytest tests/ -v -s
```

## 📈 **Current Status**

- **Total Test Files**: 11 (9 pytest + 2 standalone)
- **API Endpoints Covered**: 14+
- **Test Methods**: 94+ (pytest) + live testing
- **Coverage**: 85%+ target
- **Maintenance**: Active

---

**Last Updated**: January 2025  
**Maintained By**: Enterprise RAG Platform Team 