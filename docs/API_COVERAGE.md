# API Coverage Documentation

This document provides a comprehensive overview of the Enterprise RAG Platform API endpoints and their functionality.

## API Structure Overview

The API is organized into the following route modules:

### 1. Health & Monitoring (`/api/v1/health`)
- **GET** `/health` - Basic health check
- **GET** `/health/detailed` - Detailed system health with component status
- **GET** `/health/ready` - Readiness probe for Kubernetes
- **GET** `/health/live` - Liveness probe for Kubernetes

### 2. Query Processing (`/api/v1/query`)
- **POST** `/ask` - Process RAG queries with metadata filtering
- **POST** `/batch` - Process multiple queries in batch
- **GET** `/documents` - List documents with metadata filtering
- **GET** `/documents/{document_id}` - Get document details with metadata
- **GET** `/search` - Search documents by content and metadata
- **GET** `/history` - Get query history for a tenant
- **POST** `/feedback` - Submit feedback for query responses
- **GET** `/config` - Get query configuration
- **PUT** `/config` - Update query configuration
- **GET** `/stats` - Get query statistics
- **POST** `/validate` - Validate a query without processing

### 3. Delta Sync (`/api/v1/sync`)
- **POST** `/trigger` - Trigger delta sync operation with hash tracking
- **GET** `/status/{sync_id}` - Get sync status and progress
- **GET** `/history` - Get sync history
- **POST** `/cancel/{sync_id}` - Cancel a running sync operation
- **GET** `/config` - Get sync configuration
- **PUT** `/config` - Update sync configuration
- **GET** `/stats` - Get sync statistics
- **POST** `/documents/{file_path}/process` - Process single document manually
- **DELETE** `/documents/{file_path}` - Remove document from Qdrant

### 4. Setup & Initialization (`/api/v1/setup`)
- **GET** `/status` - Check system initialization status
- **POST** `/initialize` - Initialize the system with admin tenant

### 5. Admin Operations (`/api/v1/admin`)
- **POST** `/tenants` - Create new tenant (Admin only)
- **GET** `/tenants` - List all tenants (Admin only)
- **GET** `/tenants/{tenant_id}` - Get tenant details (Admin only)
- **PUT** `/tenants/{tenant_id}` - Update tenant (Admin only)
- **DELETE** `/tenants/{tenant_id}` - Delete tenant (Admin only)
- **POST** `/tenants/{tenant_id}/api-keys` - Create API key (Admin only)
- **GET** `/tenants/{tenant_id}/api-keys` - List API keys (Admin only)
- **DELETE** `/tenants/{tenant_id}/api-keys/{key_id}` - Delete API key (Admin only)
- **GET** `/system/status` - Get system status (Admin only)
- **GET** `/system/metrics` - Get system metrics (Admin only)
- **POST** `/system/clear-embeddings-stats` - Clear embedding statistics (Admin only)
- **POST** `/system/clear-llm-stats` - Clear LLM statistics (Admin only)
- **POST** `/system/clear-llm-cache` - Clear LLM cache (Admin only)
- **POST** `/system/maintenance` - Trigger maintenance mode (Admin only)

## Key Features

### Delta Sync with Hash Tracking
The sync system uses file hashes to efficiently detect changes:
- **File Discovery**: Scans tenant document folders
- **Hash Comparison**: Compares file hashes with stored hashes
- **Change Detection**: Only processes new, modified, or deleted files
- **Metadata Extraction**: Extracts comprehensive document metadata
- **Embedding Generation**: Generates embeddings for document chunks
- **Qdrant Updates**: Updates vector store with new embeddings and metadata

### Metadata Filtering
Rich metadata support for enhanced search and filtering:
- **Document Metadata**: Title, author, date, tags, category, summary
- **Query Filtering**: Filter queries by author, date range, tags, document type
- **Search Capabilities**: Search documents by content and metadata
- **Source Citations**: Include metadata in query responses

### Multi-tenant Architecture
Complete data isolation and tenant management:
- **Tenant Isolation**: Separate document folders and Qdrant collections
- **API Key Authentication**: Secure tenant access control
- **Admin Management**: Comprehensive tenant administration
- **System Monitoring**: Tenant-specific metrics and statistics

## Authentication & Security

All API endpoints require authentication via API keys:
- API keys are passed in the `Authorization` header as `Bearer <api_key>`
- Each tenant has their own API keys for data isolation
- Admin operations require admin-level API keys
- Input validation and error handling on all endpoints

## Data Models

The API uses comprehensive Pydantic models for:
- **Request/Response validation**
- **Type safety**
- **Automatic documentation generation**
- **Data serialization/deserialization**

Key model categories:
- Setup & Initialization models
- Admin operation models
- Delta sync models
- Query processing models with metadata filtering
- Document management models with rich metadata
- System monitoring models

## Error Handling

The API implements comprehensive error handling:
- **Standardized error responses** with error codes and details
- **HTTP status codes** for different error types
- **Detailed logging** for debugging
- **Graceful degradation** for service failures

## Performance & Monitoring

The API includes extensive monitoring capabilities:
- **Request/response logging**
- **Performance metrics**
- **Error tracking**
- **System health monitoring**
- **Delta sync progress tracking**

## API Documentation

The API automatically generates OpenAPI/Swagger documentation:
- Available at `/api/v1/openapi.json`
- Interactive documentation at `/docs` (when running)
- Comprehensive endpoint descriptions
- Request/response examples

## Usage Examples

### Delta Sync Workflow
```bash
# 1. Copy files to tenant folder (manual)
cp document.pdf data/tenants/tenant-1/documents/

# 2. Trigger delta sync
curl -X POST "http://localhost:8000/api/v1/sync/trigger" \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"force_full_sync": false}'

# 3. Check sync status
curl -X GET "http://localhost:8000/api/v1/sync/status/{sync_id}" \
  -H "Authorization: Bearer your-api-key"
```

### Query with Metadata Filtering
```bash
curl -X POST "http://localhost:8000/api/v1/query/ask" \
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
curl -X GET "http://localhost:8000/api/v1/query/search?query=machine+learning&author=John+Doe&tags=AI,research" \
  -H "Authorization: Bearer your-api-key"
```

### System Health Check
```bash
curl -X GET "http://localhost:8000/api/v1/health/detailed" \
  -H "Authorization: Bearer your-api-key"
```

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
```

## Qdrant Collections

```
tenant_{tenant_id}_documents     # Document metadata + file hashes
tenant_{tenant_id}_embeddings    # Document chunks with embeddings
tenant_{tenant_id}_sync_state    # Sync state and file hashes
```

## Future Enhancements

Planned API improvements:
- **WebSocket support** for real-time sync updates
- **GraphQL endpoint** for flexible queries
- **Rate limiting** and usage quotas
- **Advanced filtering** and search capabilities
- **Bulk operations** for efficiency
- **Webhook notifications** for events
- **API versioning** strategy

## Testing

The API includes comprehensive testing:
- **Unit tests** for individual components
- **Integration tests** for API endpoints
- **End-to-end tests** for complete workflows
- **Performance tests** for load testing
- **Security tests** for vulnerability assessment

## Migration from Previous Version

### Removed Routes
The following routes have been removed for simplification:
- `/api/v1/documents` - File management handled externally
- `/api/v1/audit` - Auditing consolidated into admin routes
- `/api/v1/embeddings` - Internal service only
- `/api/v1/llm` - Internal service only
- `/api/v1/monitoring` - Consolidated into admin routes

### Enhanced Features
- **Delta Sync**: Hash-based change detection for efficient processing
- **Metadata Filtering**: Rich metadata support for queries and search
- **Document Search**: Enhanced search capabilities with metadata
- **Query History**: Improved query tracking and analytics
- **System Monitoring**: Comprehensive health and performance metrics

## Support

For API support and questions:
- Check the interactive documentation at `/docs`
- Review the OpenAPI specification at `/api/v1/openapi.json`
- Check system health at `/api/v1/health/detailed`
- Contact the development team for additional support 