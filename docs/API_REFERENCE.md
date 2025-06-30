# Enterprise RAG Platform - Comprehensive API Documentation

This document provides a complete overview of the Enterprise RAG Platform API, including current implementation status, coverage analysis, and critical issues.

## Table of Contents
1. [API Structure Overview](#api-structure-overview)
2. [Current Implementation Status](#current-implementation-status)
3. [Critical Issues & Orphaned Code](#critical-issues--orphaned-code)
4. [Detailed Endpoint Reference](#detailed-endpoint-reference)
5. [Authentication & Security](#authentication--security)
6. [Data Models](#data-models)
7. [Error Handling](#error-handling)
8. [Performance & Monitoring](#performance--monitoring)
9. [Usage Examples](#usage-examples)
10. [File Storage Structure](#file-storage-structure)
11. [Future Enhancements](#future-enhancements)
12. [Testing](#testing)
13. [Migration from Previous Version](#migration-from-previous-version)
14. [Support](#support)
15. [Additional Endpoints](#additional-endpoints)
16. [WebSocket Endpoints](#websocket-endpoints)
17. [File Upload Endpoints](#file-upload-endpoints)
18. [Development & Testing Endpoints](#development--testing-endpoints)
19. [Rate Limiting](#rate-limiting)
20. [Response Formats](#response-formats)

---

## API Structure Overview

The API is organized into the following route modules, all prefixed with `/api/v1`:

### Route Categories
1. **Health & Monitoring** (`/health`) - System health checks
2. **Query Processing** (`/query`) - RAG query operations
3. **Delta Sync** (`/sync`) - Document synchronization
4. **Setup & Initialization** (`/setup`) - System setup
5. **Admin Operations** (`/admin`) - Administrative functions
6. **Tenant Operations** (`/tenants`) - **ORPHANED** (not registered)

---

## Current Implementation Status

### ✅ **FULLY IMPLEMENTED & REGISTERED**

#### 1. Health & Monitoring (`/api/v1/health`)
- ✅ `GET /health` - Comprehensive health check with component status
- ✅ `GET /health/liveness` - Basic liveness check

#### 2. Query Processing (`/api/v1/queries`)
- ✅ `POST /queries` - Process RAG queries with metadata filtering
- ✅ `POST /queries/batch` - Process multiple queries in batch
- ✅ `GET /queries/documents` - List documents with metadata filtering
- ✅ `GET /queries/documents/{document_id}` - Get document details
- ✅ `GET /queries/search` - Search documents by content and metadata
- ✅ `GET /queries/history` - Get query history for a tenant
- ✅ `POST /queries/feedback` - Submit feedback for query responses
- ✅ `GET /queries/config` - Get query configuration
- ✅ `PUT /queries/config` - Update query configuration
- ✅ `GET /queries/stats` - Get query statistics
- ✅ `POST /queries/validate` - Validate a query without processing

#### 3. Delta Sync (`/api/v1/syncs`)
- ✅ `POST /syncs` - Trigger delta sync operation with hash tracking
- ✅ `GET /syncs/{sync_id}` - Get sync status and progress
- ✅ `GET /syncs/history` - Get sync history
- ✅ `DELETE /syncs/{sync_id}` - Cancel a running sync operation
- ✅ `GET /syncs/config` - Get sync configuration
- ✅ `PUT /syncs/config` - Update sync configuration
- ✅ `GET /syncs/stats` - Get sync statistics
- ✅ `POST /syncs/documents` - Process single document manually
- ✅ `DELETE /syncs/documents/{document_id}` - Remove document from Qdrant

#### 4. Setup & Initialization (`/api/v1/setup`)
- ✅ `GET /setup/status` - Check system initialization status
- ✅ `POST /setup/initialize` - Initialize the system with admin tenant

#### 5. Admin Operations (`/api/v1/admin`)
- ✅ `POST /admin/tenants` - Create new tenant (Admin only)
- ✅ `GET /admin/tenants` - List all tenants (Admin only)
- ✅ `GET /admin/tenants/{tenant_id}` - Get tenant details (Admin only)
- ✅ `PUT /admin/tenants/{tenant_id}` - Update tenant (Admin only)
- ✅ `DELETE /admin/tenants/{tenant_id}` - Delete tenant (Admin only)
- ✅ `POST /admin/tenants/{tenant_id}/api-keys` - Create API key (Admin only)
- ✅ `GET /admin/tenants/{tenant_id}/api-keys` - List API keys (Admin only)
- ✅ `DELETE /admin/tenants/{tenant_id}/api-keys/{key_id}` - Delete API key (Admin only)
- ✅ `GET /admin/system/status` - Get system status (Admin only)
- ✅ `GET /admin/system/metrics` - Get system metrics (Admin only)
- ✅ `DELETE /admin/system/embeddings/stats` - Clear embedding statistics (Admin only)
- ✅ `DELETE /admin/system/llm/stats` - Clear LLM statistics (Admin only)
- ✅ `DELETE /admin/system/llm/cache` - Clear LLM cache (Admin only)
- ✅ `PUT /admin/system/maintenance` - Update maintenance mode (Admin only)
- ✅ `GET /admin/audit/events` - Get audit events (Admin only)

### 📚 **ADDITIONAL ENDPOINTS**

#### 6. Demo Management (`/api/v1/admin/demo`)
- ✅ `POST /admin/demo/setup` - Setup demo environment with tenants
- ✅ `GET /admin/demo/tenants` - List demo tenants with API keys  
- ✅ `DELETE /admin/demo/cleanup` - Clean up demo environment

---

## RESTful API Updates

### ✅ **RECENT IMPROVEMENTS**

#### 1. RESTful Endpoint Restructuring
All endpoints have been updated to follow REST conventions:
- **Resource-based URLs**: `/queries` instead of `/query/ask`
- **HTTP Methods**: Proper use of GET, POST, PUT, DELETE
- **Consistent Patterns**: Standard resource/action patterns

#### 2. Updated Endpoint Structure
- Query endpoints moved from `/query/*` to `/queries/*`
- Sync endpoints moved from `/sync/*` to `/syncs/*` 
- Admin maintenance endpoints use proper HTTP verbs
- All endpoints follow consistent naming patterns

### 🗑️ **ORPHANED CODE**

#### 1. Utility Classes Without API Endpoints
- `ErrorTracker` class in `monitoring.py` - No API endpoints use this
- `PerformanceMonitor` class in `monitoring.py` - No API endpoints use this  
- `SystemMonitor` class in `monitoring.py` - Only used by health check
- `FileMonitor` class in `file_monitor.py` - No API endpoints use this

#### 2. Service Methods Without API Endpoints
- `TenantService.validate_api_key()` - Used by auth middleware, not API
- `TenantService.get_api_key_hash()` - No API endpoint uses this
- Various utility functions in `error_handling.py` - Some not used by APIs

#### 3. Test Files with Non-existent Endpoints
- `tests/test_api_endpoints.py` - Tests endpoints that don't exist
- `tests/quick_api_test.py` - Tests endpoints that don't exist
- `scripts/health_check.py` - External health checker

### ✅ **RESOLVED ISSUES**

#### **3.1 Missing Route Registration - FIXED**
- **Issue:** Tenant routes (`/api/v1/tenants/*`) were not registered in `main.py`
- **Solution:** Added tenant router registration
- **Status:** ✅ **RESOLVED**

#### **3.2 Missing `require_admin` Function - FIXED**
- **Issue:** `require_admin` function was imported but not defined in `auth.py`
- **Solution:** Added complete admin authentication function
- **Status:** ✅ **RESOLVED**

#### **3.3 Import Errors - FIXED**
- **Issue:** Incorrect import paths for `DocumentService` and `DeltaSyncService`
- **Solution:** Updated imports to use correct provider functions
- **Status:** ✅ **RESOLVED**

### 🆕 **NEW FEATURES ADDED**

#### **3.4 Dual-Context Authentication System**
- **New Function:** `require_admin()` - Admin-only endpoint protection
- **New Function:** `verify_tenant_access()` - Tenant access verification
- **New Function:** `get_tenant_context()` - Enhanced tenant context with permissions
- **Status:** ✅ **IMPLEMENTED**

#### **3.5 Tenant Context Management**
- **New Endpoint:** `GET /api/v1/tenants/context` - Get current tenant context
- **New Endpoint:** `POST /api/v1/tenants/switch` - Switch tenant context
- **Status:** ✅ **IMPLEMENTED**

#### **3.6 Demo Management System**
- **New Endpoint:** `POST /api/v1/admin/demo/setup` - Setup demo environment
- **New Endpoint:** `GET /api/v1/admin/demo/tenants` - List demo tenants
- **New Endpoint:** `DELETE /api/v1/admin/demo/cleanup` - Cleanup demo environment
- **Status:** ✅ **IMPLEMENTED**

#### **3.7 Enhanced Tenant Operations**
- **New Endpoint:** `GET /api/v1/tenants/{id}/documents` - List tenant documents
- **New Endpoint:** `GET /api/v1/tenants/{id}/sync/status` - Get tenant sync status
- **Enhanced Endpoint:** `POST /api/v1/tenants/{id}/api-keys` - Create tenant API keys
- **Status:** ✅ **IMPLEMENTED**

### 🔄 **UPDATED ENDPOINTS**

#### **3.8 Enhanced Admin Tenant Listing**
- **Endpoint:** `GET /api/v1/admin/tenants`
- **New Parameters:**
  - `include_api_keys: bool` - Include API keys in response
  - `demo_only: bool` - Show only demo tenants
- **Status:** ✅ **ENHANCED**

---

## Detailed Endpoint Reference

### Health & Monitoring Endpoints

#### `GET /api/v1/health`
**Comprehensive health check with all component statuses**
```json
{
  "overall_status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "components": [
    {
      "name": "vector_store",
      "status": "healthy",
      "details": {"message": "Qdrant is reachable"}
    },
    {
      "name": "embedding_service", 
      "status": "healthy",
      "details": {
        "embedding_dimension": 384,
        "model_name": "sentence-transformers/all-MiniLM-L6-v2",
        "device": "cpu"
      }
    }
  ],
  "system_metrics": {
    "cpu_percent": 15.2,
    "memory_percent": 45.8,
    "disk_usage_percent": 23.1
  }
}
```

#### `GET /api/v1/health/liveness`
**Basic liveness check**
```json
{
  "status": "alive"
}
```

### Query Processing Endpoints

#### `POST /api/v1/queries`
**Process RAG query with metadata filtering**
```json
{
  "query": "What is machine learning?",
  "max_sources": 5,
  "confidence_threshold": 0.7,
  "metadata_filters": {
    "author": "John Doe",
    "date_from": "2023-01-01",
    "date_to": "2023-12-31",
    "tags": ["AI", "research"],
    "document_type": "pdf"
  }
}
```

**Response:**
```json
{
  "query": "What is machine learning?",
  "answer": "Machine learning is a subset of artificial intelligence...",
  "sources": [
    {
      "id": "chunk_123",
      "text": "Machine learning algorithms can learn patterns...",
      "score": 0.85,
      "document_id": "doc_456",
      "document_name": "ML_Introduction.pdf",
      "page_number": 5,
      "metadata": {"author": "John Doe", "tags": ["AI"]}
    }
  ],
  "confidence": 0.82,
  "processing_time": 1.23,
  "tokens_used": 150,
  "model_used": "google/flan-t5-base"
}
```

### Delta Sync Endpoints

#### `POST /api/v1/syncs`
**Trigger delta sync operation**
```json
{
  "force_full_sync": false,
  "document_paths": ["documents/report.pdf"]
}
```

**Response:**
```json
{
  "sync_id": "sync_789",
  "tenant_id": "tenant_123",
  "status": "pending",
  "started_at": "2024-01-01T00:00:00Z",
  "progress": {"message": "Delta sync queued"}
}
```

### Admin Endpoints

#### `GET /api/v1/admin/tenants`
**List all tenants (Admin only)**
```json
{
  "tenants": [
    {
      "id": "tenant_123",
      "name": "Acme Corp",
      "description": "Acme Corporation tenant",
      "status": "active",
      "created_at": "2024-01-01T00:00:00Z",
      "api_keys": [
        {
          "id": "key_456",
          "name": "Production Key",
          "key_prefix": "sk-abc123",
          "is_active": true,
          "created_at": "2024-01-01T00:00:00Z"
        }
      ],
      "document_count": 150,
      "storage_used_mb": 45.2
    }
  ],
  "total_count": 1
}
```

### **4.1 Tenant Context Management** (`/api/v1/tenants/*`)

#### **Get Current Tenant Context**
```http
GET /api/v1/tenants/context
Authorization: Bearer <tenant_api_key>
```
**Response:**
```json
{
  "tenant_id": "tenant_123",
  "tenant_name": "Demo Company",
  "description": "Demo tenant for testing",
  "status": "active",
  "permissions": ["tenant_operations", "document_access", "query_access"],
  "api_keys": [
    {
      "id": "key_456",
      "name": "Demo API Key",
      "key_prefix": "sk-demo...",
      "is_active": true,
      "created_at": "2024-01-01T00:00:00Z",
      "expires_at": "2024-12-31T23:59:59Z"
    }
  ],
  "created_at": "2024-01-01T00:00:00Z",
  "auto_sync": true,
  "sync_interval": 60
}
```

#### **Switch Tenant Context**
```http
POST /api/v1/tenants/switch
Content-Type: application/json

{
  "tenant_id": "tenant_456",
  "api_key": "sk-tenant456-api-key"
}
```
**Response:**
```json
{
  "success": true,
  "tenant_context": {
    "tenant_id": "tenant_456",
    "tenant_name": "Another Company",
    "description": "Another demo tenant",
    "status": "active",
    "permissions": ["tenant_operations", "document_access", "query_access"],
    "api_keys": [...],
    "created_at": "2024-01-01T00:00:00Z",
    "auto_sync": true,
    "sync_interval": 60
  },
  "message": "Successfully switched to tenant: Another Company"
}
```

#### **List Tenant Documents**
```http
GET /api/v1/tenants/{tenant_id}/documents?page=1&page_size=10&document_type=pdf
Authorization: Bearer <tenant_api_key>
```
**Response:**
```json
{
  "documents": [
    {
      "id": "doc_123",
      "name": "sample.pdf",
      "file_path": "/documents/sample.pdf",
      "file_size": 1024000,
      "content_type": "application/pdf",
      "upload_timestamp": "2024-01-01T00:00:00Z",
      "last_modified": "2024-01-01T00:00:00Z",
      "chunk_count": 15,
      "status": "processed",
      "metadata": {...},
      "embedding_count": 15,
      "processing_time": 2.5
    }
  ],
  "total_count": 1,
  "page": 1,
  "page_size": 10
}
```

#### **Get Tenant Sync Status**
```http
GET /api/v1/tenants/{tenant_id}/sync/status?include_history=true&limit=10
Authorization: Bearer <tenant_api_key>
```
**Response:**
```json
{
  "sync_id": "sync_789",
  "tenant_id": "tenant_123",
  "status": "completed",
  "started_at": "2024-01-01T00:00:00Z",
  "completed_at": "2024-01-01T00:05:00Z",
  "progress": {
    "message": "Sync completed successfully",
    "files_processed": 5,
    "files_added": 2,
    "files_modified": 1,
    "files_deleted": 0
  },
  "error_message": null,
  "history": [
    {
      "sync_id": "sync_788",
      "status": "completed",
      "started_at": "2024-01-01T00:00:00Z",
      "completed_at": "2024-01-01T00:03:00Z"
    }
  ]
}
```

### **4.2 Demo Management** (`/api/v1/admin/demo/*`)

#### **Setup Demo Environment**
```http
POST /api/v1/admin/demo/setup
Authorization: Bearer <admin_api_key>
Content-Type: application/json

{
  "demo_tenants": ["tenant_123", "tenant_456", "tenant_789"],
  "demo_duration_hours": 24,
  "generate_api_keys": true
}
```
**Response:**
```json
{
  "success": true,
  "demo_tenants": [
    {
      "tenant_id": "tenant_123",
      "tenant_name": "Demo Company A",
      "description": "Demo tenant for testing",
      "api_keys": [
        {
          "api_key": "sk-demo-tenant123-key",
          "key_info": {
            "id": "key_123",
            "name": "Demo API Key",
            "key_prefix": "sk-demo...",
            "is_active": true,
            "created_at": "2024-01-01T00:00:00Z",
            "expires_at": "2024-01-02T00:00:00Z"
          }
        }
      ],
      "demo_expires_at": "2024-01-02T00:00:00Z",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "admin_api_key": "sk-admin-key",
  "message": "Demo environment setup for 3 tenants",
  "total_tenants": 3
}
```

#### **List Demo Tenants**
```http
GET /api/v1/admin/demo/tenants
Authorization: Bearer <admin_api_key>
```
**Response:**
```json
[
  {
    "tenant_id": "tenant_123",
    "tenant_name": "Demo Company A",
    "description": "Demo tenant for testing",
    "api_keys": [
      {
        "api_key": "sk-demo-tenant123-key",
        "key_info": {
          "id": "key_123",
          "name": "Demo API Key",
          "key_prefix": "sk-demo...",
          "is_active": true,
          "created_at": "2024-01-01T00:00:00Z",
          "expires_at": "2024-01-02T00:00:00Z"
        }
      }
    ],
    "demo_expires_at": "2024-01-02T00:00:00Z",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

#### **Cleanup Demo Environment**
```http
DELETE /api/v1/admin/demo/cleanup
Authorization: Bearer <admin_api_key>
```
**Response:**
```json
{
  "success": true,
  "cleaned_tenants": 3,
  "expired_keys": 6,
  "message": "Cleaned up 3 tenants and expired 6 demo keys"
}
```

---

## Authentication & Security

### API Key Authentication
All endpoints require authentication via API keys:
- **Header**: `Authorization: Bearer <api_key>`
- **Alternative**: `X-API-Key: <api_key>` (for some endpoints)
- Each tenant has their own API keys for data isolation
- Admin operations require admin-level API keys

### Tenant Isolation
- All data operations are automatically scoped to the authenticated tenant
- Admin endpoints bypass tenant isolation
- Cross-tenant access requires admin privileges

### Security Features
- Input validation and sanitization on all endpoints
- Comprehensive error handling without information leakage
- Rate limiting (configurable per endpoint)
- Audit logging for all operations

---

## Data Models

The API uses comprehensive Pydantic models for:
- **Request/Response validation**
- **Type safety**
- **Automatic documentation generation**
- **Data serialization/deserialization**

### Key Model Categories

#### Setup & Initialization Models
- `SetupCheckResponse` - System initialization status
- `SetupInitializeRequest` - System initialization request
- `SetupInitializeResponse` - System initialization response

#### Admin Operation Models
- `TenantCreateRequest` - Tenant creation request
- `TenantUpdateRequest` - Tenant update request
- `TenantResponse` - Tenant information
- `TenantListResponse` - List of tenants
- `ApiKeyCreateRequest` - API key creation request
- `ApiKeyResponse` - API key information
- `SystemStatusResponse` - System status
- `SystemMetricsResponse` - System metrics

#### Delta Sync Models
- `SyncTriggerRequest` - Sync trigger request
- `SyncResponse` - Sync operation response
- `SyncHistoryResponse` - Sync history
- `SyncConfigRequest` - Sync configuration request
- `SyncConfigResponse` - Sync configuration response

#### Query Processing Models
- `QueryRequest` - RAG query request with metadata filtering
- `QueryResponse` - RAG query response
- `QueryBatchRequest` - Batch query request
- `QueryBatchResponse` - Batch query response
- `SourceCitation` - Source document citation
- `DocumentResponse` - Document information
- `DocumentListResponse` - List of documents

---

## Error Handling

The API implements comprehensive error handling:

### Standard Error Response Format
```json
{
  "error": "Error message",
  "code": "ERROR_CODE",
  "details": {
    "field": "additional_error_details"
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### Error Categories
- **400 Bad Request** - Invalid input data
- **401 Unauthorized** - Missing or invalid API key
- **403 Forbidden** - Insufficient permissions
- **404 Not Found** - Resource not found
- **422 Validation Error** - Request validation failed
- **500 Internal Server Error** - Server-side error

### Error Codes
- `UNAUTHORIZED` - Authentication required
- `INVALID_API_KEY` - Invalid or expired API key
- `VALIDATION_ERROR` - Input validation failed
- `RESOURCE_NOT_FOUND` - Requested resource not found
- `RAG_PIPELINE_ERROR` - RAG processing error
- `SYNC_FAILED` - Document sync error

---

## Performance & Monitoring

### Monitoring Capabilities
- **Request/response logging** with correlation IDs
- **Performance metrics** collection
- **Error tracking** and alerting
- **System health monitoring** with component status
- **Delta sync progress tracking**

### Performance Features
- **Async processing** for long-running operations
- **Batch operations** for efficiency
- **Caching** for frequently accessed data
- **Connection pooling** for database operations

### Metrics Available
- Query processing times
- Sync operation durations
- System resource usage (CPU, memory, disk)
- Error rates and types
- API endpoint usage statistics

---

## Usage Examples

### Delta Sync Workflow
```bash
# 1. Copy files to tenant folder (manual)
cp document.pdf data/tenants/tenant-1/documents/

# 2. Trigger delta sync
curl -X POST "http://localhost:8000/api/v1/syncs" \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"force_full_sync": false}'

# 3. Check sync status
curl -X GET "http://localhost:8000/api/v1/syncs/{sync_id}" \
  -H "Authorization: Bearer your-api-key"
```

### Query with Metadata Filtering
```bash
curl -X POST "http://localhost:8000/api/v1/queries" \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is machine learning?",
    "max_sources": 5,
    "confidence_threshold": 0.7,
    "metadata_filters": {
      "author": "John Doe",
      "date_from": "2023-01-01",
      "date_to": "2023-12-31",
      "tags": ["AI", "research"],
      "document_type": "pdf"
    }
  }'
```

### Document Search
```bash
curl -X GET "http://localhost:8000/api/v1/queries/search?query=machine+learning&author=John+Doe&tags=AI,research" \
  -H "Authorization: Bearer your-api-key"
```

### System Health Check
```bash
curl -X GET "http://localhost:8000/api/v1/health" \
  -H "Authorization: Bearer your-api-key"
```

### Admin Operations
```bash
# List all tenants (admin only)
curl -X GET "http://localhost:8000/api/v1/admin/tenants" \
  -H "Authorization: Bearer admin-api-key"

# Create new tenant (admin only)
curl -X POST "http://localhost:8000/api/v1/admin/tenants" \
  -H "Authorization: Bearer admin-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "New Company",
    "description": "New company tenant",
    "auto_sync": true,
    "sync_interval": 60
  }'
```

---

## File Storage Structure

```
data/
├── tenants/
│   ├── tenant-1/
│   │   ├── documents/          # Tenant's document folder
│   │   │   ├── report.pdf
│   │   │   ├── manual.docx
│   │   │   └── data.csv
│   │   └── uploads/           # Temporary upload area
│   └── tenant-2/
│       ├── documents/
│       └── uploads/
├── cache/
│   ├── transformers/          # Model cache
│   └── embeddings/            # Embedding cache
└── logs/
    ├── application.log        # Application logs
    ├── error.log             # Error logs
    └── audit.log             # Audit logs
```

---

## Qdrant Collections

Each tenant has separate collections in Qdrant:
- `{tenant_id}_documents` - Document chunks and embeddings
- `{tenant_id}_metadata` - Document metadata
- `tenants_metadata` - Global tenant information (shared)

---

## Future Enhancements

Planned API improvements:

### **WebSocket Support**
- Real-time sync updates via WebSocket connections
- Live progress tracking for long-running operations
- Instant notifications for system events

### **GraphQL Endpoint**
- Flexible querying with GraphQL
- Reduced over-fetching and under-fetching
- Complex query support

### **Rate Limiting & Usage Quotas**
- Configurable rate limits per API key
- Usage quotas and billing integration
- Fair usage policies

### **Advanced Filtering & Search**
- Full-text search across documents
- Semantic search capabilities
- Advanced metadata filtering

### **Bulk Operations**
- Batch document processing
- Bulk API key management
- Mass tenant operations

### **Webhook Notifications**
- Event-driven notifications
- Custom webhook endpoints
- Real-time system alerts

### **API Versioning Strategy**
- Semantic versioning for API changes
- Backward compatibility guarantees
- Migration guides for version updates

---

## Testing

The API includes comprehensive testing:

### **Unit Tests**
- Individual component testing
- Model validation tests
- Service layer testing
- Utility function testing

### **Integration Tests**
- API endpoint testing
- Database integration tests
- External service integration
- Authentication flow testing

### **End-to-End Tests**
- Complete workflow testing
- User journey validation
- Cross-component integration
- Performance under load

### **Performance Tests**
- Load testing with realistic scenarios
- Stress testing for system limits
- Benchmark testing for optimizations
- Memory and CPU profiling

### **Security Tests**
- Vulnerability assessment
- Penetration testing
- Authentication bypass testing
- Data isolation validation

---

## Migration from Previous Version

### **Removed Routes**
The following routes have been removed for simplification:
- `/api/v1/documents` - File management handled externally
- `/api/v1/audit` - Auditing consolidated into admin routes
- `/api/v1/embeddings` - Internal service only
- `/api/v1/llm` - Internal service only
- `/api/v1/monitoring` - Consolidated into admin routes

### **Enhanced Features**
- **Delta Sync**: Hash-based change detection for efficient processing
- **Metadata Filtering**: Rich metadata support for queries and search
- **Document Search**: Enhanced search capabilities with metadata
- **Query History**: Improved query tracking and analytics
- **System Monitoring**: Comprehensive health and performance metrics

---

## Support

For API support and questions:
- **Interactive Documentation**: Check `/docs` when server is running
- **OpenAPI Specification**: Review `/api/v1/openapi.json`
- **System Health**: Check `/api/v1/health` for system status
- **Development Team**: Contact for additional support

---

## Additional Endpoints

### **Query Management (Planned/Internal)**
- `GET /query/suggestions` - Get query suggestions based on history
- `POST /query/clear-history` - Clear query history for tenant

### **Embedding Management (Internal Service)**
- `GET /embeddings/info` - Get embedding service information
- `POST /embeddings/generate` - Generate embeddings for single text
- `POST /embeddings/generate-batch` - Generate embeddings for multiple texts
- `POST /embeddings/generate-async` - Submit async embedding job
- `GET /embeddings/stats` - Get embedding statistics

### **LLM Service (Internal Service)**
- `GET /llm/info` - Get LLM service information
- `POST /llm/generate` - Generate text using LLM
- `GET /llm/models` - Get available models
- `GET /llm/stats` - Get LLM statistics

---

## WebSocket Endpoints

### **Real-time Updates (Planned)**
- `WS /ws/sync/{tenant_id}` - Real-time sync status updates
- `WS /ws/monitoring` - Real-time system metrics
- `WS /ws/notifications` - Real-time notifications

---

## File Upload Endpoints

### **Document Upload (Planned)**
- `POST /documents/upload` - Upload single document
- `POST /documents/upload/batch` - Upload multiple documents
- `POST /documents/upload/url` - Upload from URL

### **Supported Formats**
- **Text**: `.txt`, `.md`, `.rst`
- **Office**: `.docx`, `.xlsx`, `.pptx`
- **PDF**: `.pdf`
- **Images**: `.png`, `.jpg`, `.jpeg` (OCR supported)
- **Web**: `.html`, `.htm`

---

## Development & Testing Endpoints

### **Development Endpoints**
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation (ReDoc)
- `GET /openapi.json` - OpenAPI specification

### **Testing Endpoints (Planned)**
- `POST /test/health` - Test health check
- `POST /test/embedding` - Test embedding generation
- `POST /test/llm` - Test LLM generation
- `POST /test/query` - Test RAG query

---

## Rate Limiting

### **Rate Limits by Endpoint Type**
- **Default**: 100 requests per minute per API key
- **Admin endpoints**: 1000 requests per minute
- **Health endpoints**: No rate limiting
- **Monitoring endpoints**: 60 requests per minute
- **Query endpoints**: 200 requests per minute
- **Sync endpoints**: 50 requests per minute

### **Rate Limit Headers**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

---

## Response Formats

### **Standard Success Response**
```json
{
  "data": {...},
  "message": "Success message",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### **Standard Error Response**
```json
{
  "error": "Error message",
  "code": "ERROR_CODE",
  "details": {...},
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### **Pagination Response**
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 10,
    "total_count": 100,
    "total_pages": 10
  }
}
```

---

## Implementation Summary

| Route Category | Status | Endpoints | RESTful Updates |
|----------------|--------|-----------|----------------|
| Health Routes | ✅ Complete | 2 endpoints | ✅ No changes needed |
| Query Routes | ✅ Complete | 11 endpoints | ✅ Updated to `/queries` |
| Sync Routes | ✅ Complete | 9 endpoints | ✅ Updated to `/syncs` |
| Setup Routes | ✅ Complete | 2 endpoints | ✅ No changes needed |
| Admin Routes | ✅ Complete | 19 endpoints | ✅ Updated maintenance endpoints |
| Demo Routes | ✅ Complete | 3 endpoints | ✅ RESTful from start |

### Recent Improvements
1. ✅ **RESTful Restructure**: All endpoints follow REST conventions
2. ✅ **Consistent Naming**: Standardized endpoint patterns
3. ✅ **HTTP Methods**: Proper use of GET, POST, PUT, DELETE
4. ✅ **Documentation**: Updated all examples and references
5. ✅ **Script Updates**: API scripts use centralized configuration

---

## API Documentation

The API automatically generates OpenAPI/Swagger documentation:
- **OpenAPI Spec**: Available at `/api/v1/openapi.json`
- **Interactive Docs**: Available at `/docs` (when running)
- **ReDoc**: Available at `/redoc` (when running)

All endpoints include comprehensive descriptions, request/response examples, and validation rules.

---

## Notes

1. **API Versioning**: All endpoints are versioned under `/api/v1`
2. **Content-Type**: JSON for all requests/responses unless specified
3. **CORS**: Configured for web frontend access
4. **Logging**: All requests are logged for audit purposes
5. **Monitoring**: All endpoints are monitored for performance and errors
6. **Security**: API keys are validated on every request
7. **Scalability**: Designed for horizontal scaling with load balancing

For detailed endpoint specifications, see the interactive API documentation at `/docs` when the server is running. 