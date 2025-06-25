# Enterprise RAG Platform API Endpoints Overview

This document provides a comprehensive overview of all available API endpoints in the Enterprise RAG Platform, organized by functional category.

## Base URL
All endpoints are prefixed with `/api/v1`

## Authentication
Most endpoints require authentication via API key in the `X-API-Key` header.

---

## 1. Setup & Initialization

### System Setup
- `GET /setup/check` - Check system initialization status
- `POST /setup/initialize` - Initialize the system with admin tenant
- `GET /setup/status` - Get detailed setup status

---

## 2. Health & Monitoring

### Health Checks
- `GET /health` - Comprehensive health check (all components)
- `GET /health/liveness` - Basic liveness check

### System Monitoring
- `GET /monitoring/metrics/system` - Detailed system metrics (CPU, memory, disk, GPU)
- `GET /monitoring/metrics/performance` - Performance metrics (queries, sync operations)

### Error Tracking
- `GET /monitoring/errors` - Get error logs with filtering
- `GET /monitoring/errors/stats` - Error statistics and trends
- `POST /monitoring/alerts/test` - Test alert system

### Logs & Debugging
- `GET /monitoring/logs/recent` - Get recent application logs
- `POST /monitoring/monitoring/start` - Start system monitoring
- `POST /monitoring/monitoring/stop` - Stop system monitoring

---

## 3. Admin Operations (Admin Only)

### Tenant Management
- `GET /admin/tenants` - List all tenants
- `POST /admin/tenants` - Create new tenant
- `GET /admin/tenants/{tenant_id}` - Get tenant details
- `PUT /admin/tenants/{tenant_id}` - Update tenant
- `DELETE /admin/tenants/{tenant_id}` - Delete tenant
- `POST /admin/tenants/{tenant_id}/suspend` - Suspend tenant
- `POST /admin/tenants/{tenant_id}/activate` - Activate tenant

### API Key Management
- `GET /admin/tenants/{tenant_id}/api-keys` - List tenant API keys
- `POST /admin/tenants/{tenant_id}/api-keys` - Create new API key
- `DELETE /admin/tenants/{tenant_id}/api-keys/{key_id}` - Delete API key

### System Management
- `GET /admin/system/status` - System status overview
- `GET /admin/system/metrics` - System performance metrics
- `POST /admin/system/maintenance` - Trigger maintenance mode
- `POST /admin/system/clear-embeddings-stats` - Clear embedding statistics
- `POST /admin/system/clear-llm-stats` - Clear LLM statistics
- `POST /admin/system/clear-llm-cache` - Clear LLM cache

### Audit Logs
- `GET /admin/audit/events` - Get audit events (admin only, optional tenant filter)

---

## 4. Document Management

### Document Operations
- `GET /documents` - List documents
- `POST /documents/upload` - Upload new document
- `GET /documents/{document_id}` - Get document details
- `DELETE /documents/{document_id}` - Delete document
- `GET /documents/{document_id}/content` - Get document content
- `GET /documents/search` - Search documents

### Document Processing
- `POST /documents/{document_id}/reprocess` - Reprocess document
- `GET /documents/{document_id}/chunks` - Get document chunks
- `GET /documents/{document_id}/status` - Get processing status

---

## 5. Document Synchronization

### Sync Operations
- `POST /sync/trigger` - Trigger document sync
- `GET /sync/status` - Get sync status
- `GET /sync/history` - Get sync history
- `POST /sync/cancel` - Cancel running sync

### Sync Configuration
- `GET /sync/config` - Get sync configuration
- `PUT /sync/config` - Update sync configuration
- `POST /sync/test` - Test sync configuration

---

## 6. Query Processing

### RAG Queries
- `POST /query` - Submit RAG query
- `POST /query/batch` - Submit batch queries
- `GET /query/history` - Get query history
- `POST /query/feedback` - Submit query feedback

### Query Management
- `GET /query/stats` - Get query statistics
- `GET /query/suggestions` - Get query suggestions
- `POST /query/clear-history` - Clear query history

---

## 7. Embedding Management

### Embedding Generation
- `GET /embeddings/info` - Get embedding service information
- `POST /embeddings/generate` - Generate embeddings for single text
- `POST /embeddings/generate-batch` - Generate embeddings for multiple texts
- `POST /embeddings/generate-async` - Submit async embedding job

### Embedding Management
- `GET /embeddings/stats` - Get embedding statistics

---

## 8. LLM Service

### Text Generation
- `GET /llm/info` - Get LLM service information
- `POST /llm/generate` - Generate text using LLM

### LLM Management
- `GET /llm/models` - Get available models
- `GET /llm/stats` - Get LLM statistics

---

## Response Formats

### Standard Success Response
```json
{
  "data": {...},
  "message": "Success message",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### Standard Error Response
```json
{
  "error": "Error message",
  "code": "ERROR_CODE",
  "details": {...},
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### Pagination Response
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

## Authentication & Authorization

### API Key Authentication
- Include `X-API-Key: your-api-key` in request headers
- API keys are tenant-specific
- Admin API keys have access to all endpoints

### Tenant Isolation
- All data operations are automatically scoped to the tenant
- Admin endpoints bypass tenant isolation
- Cross-tenant access requires admin privileges

---

## Rate Limiting

- Default: 100 requests per minute per API key
- Admin endpoints: 1000 requests per minute
- Health endpoints: No rate limiting
- Monitoring endpoints: 60 requests per minute

---

## Error Codes

- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized (invalid/missing API key)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found (resource doesn't exist)
- `429` - Too Many Requests (rate limit exceeded)
- `500` - Internal Server Error
- `503` - Service Unavailable (maintenance mode)

---

## WebSocket Endpoints

### Real-time Updates
- `WS /ws/sync/{tenant_id}` - Real-time sync status updates
- `WS /ws/monitoring` - Real-time system metrics
- `WS /ws/notifications` - Real-time notifications

---

## File Upload Endpoints

### Document Upload
- `POST /documents/upload` - Upload single document
- `POST /documents/upload/batch` - Upload multiple documents
- `POST /documents/upload/url` - Upload from URL

### Supported Formats
- Text: `.txt`, `.md`, `.rst`
- Office: `.docx`, `.xlsx`, `.pptx`
- PDF: `.pdf`
- Images: `.png`, `.jpg`, `.jpeg` (OCR supported)
- Web: `.html`, `.htm`

---

## Development & Testing

### Development Endpoints
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation (ReDoc)
- `GET /openapi.json` - OpenAPI specification

### Testing Endpoints
- `POST /test/health` - Test health check
- `POST /test/embedding` - Test embedding generation
- `POST /test/llm` - Test LLM generation
- `POST /test/query` - Test RAG query

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