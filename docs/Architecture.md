# Enterprise RAG Platform - Architecture Analysis

## Perfect Frontend/Backend Separation ✅

The Enterprise RAG Platform has been designed with complete separation between the frontend and backend layers. This document outlines the architecture and ensures all backend functionality is accessible via well-defined APIs.

## Architecture Overview

```
┌─────────────────┐    HTTP/REST APIs    ┌─────────────────┐
│                 │ ◄─────────────────► │                 │
│   Frontend      │                     │   Backend       │
│   (React/Vite)  │                     │   (FastAPI)     │
│   Port: 5175    │                     │   Port: 8000    │
│                 │                     │                 │
└─────────────────┘                     └─────────────────┘
```

### Frontend Layer
- **Technology**: React 19 + TypeScript + Vite + Tailwind CSS
- **Port**: 5175 (auto-assigned)
- **Communication**: Pure HTTP REST API calls via Axios
- **Authentication**: API key headers (`X-API-Key`)
- **No Direct Backend Dependencies**: Zero imports from backend code

### Backend Layer
- **Technology**: FastAPI + Python 3.11
- **Port**: 8000
- **Database**: SQLAlchemy with PostgreSQL
- **Vector Store**: ChromaDB
- **Authentication**: API key-based with tenant isolation
- **Documentation**: Auto-generated OpenAPI/Swagger docs

## Complete API Catalog

### 1. Health & System APIs

| Endpoint | Method | Description | Authentication |
|----------|--------|-------------|----------------|
| `/api/v1/health` | GET | Basic health check | No |
| `/api/v1/health/detailed` | GET | Detailed component health | No |
| `/api/v1/status` | GET | System status & metrics | No |
| `/api/v1/health/readiness` | GET | Kubernetes readiness probe | No |
| `/api/v1/health/liveness` | GET | Kubernetes liveness probe | No |
| `/api/v1/metrics` | GET | Prometheus metrics | No |

### 2. Query Processing APIs

| Endpoint | Method | Description | Authentication |
|----------|--------|-------------|----------------|
| `/api/v1/query` | POST | Process natural language query | Required |
| `/api/v1/query/history` | GET | Get query history (paginated) | Required |
| `/api/v1/query/{query_id}` | GET | Get specific query result | Required |
| `/api/v1/query/{query_id}` | DELETE | Delete query from history | Required |

### 3. Document Management APIs

| Endpoint | Method | Description | Authentication |
|----------|--------|-------------|----------------|
| `/api/v1/documents/upload` | POST | Upload document for processing | Required |
| `/api/v1/documents/` | GET | List tenant documents (paginated) | Required |
| `/api/v1/documents/{document_id}` | GET | Get document details | Required |
| `/api/v1/documents/{document_id}` | PUT | Update document metadata | Required |
| `/api/v1/documents/{document_id}` | DELETE | Delete document & chunks | Required |
| `/api/v1/documents/{document_id}/download` | GET | Download original file | Required |
| `/api/v1/documents/{document_id}/chunks` | GET | Get document chunks (paginated) | Required |

### 4. Tenant Management APIs

| Endpoint | Method | Description | Authentication |
|----------|--------|-------------|----------------|
| `/api/v1/tenants/` | POST | Create new tenant | Required |
| `/api/v1/tenants/` | GET | List tenants (paginated) | Required |
| `/api/v1/tenants/{tenant_id}` | GET | Get tenant details | Required |
| `/api/v1/tenants/{tenant_id}` | PUT | Update tenant information | Required |
| `/api/v1/tenants/{tenant_id}` | DELETE | Delete tenant | Required |
| `/api/v1/tenants/{tenant_id}/stats` | GET | Get tenant statistics | Required |

### 5. Synchronization APIs

| Endpoint | Method | Description | Authentication |
|----------|--------|-------------|----------------|
| `/api/v1/sync/` | POST | Trigger manual sync | Required |
| `/api/v1/sync/status` | GET | Get current sync status | Required |
| `/api/v1/sync/{sync_id}` | GET | Get specific sync operation | Required |
| `/api/v1/sync/history` | GET | Get sync history (paginated) | Required |
| `/api/v1/sync/{sync_id}` | DELETE | Cancel running sync | Required |
| `/api/v1/sync/schedule` | GET | Get auto-sync schedule | Required |
| `/api/v1/sync/schedule` | PUT | Update auto-sync schedule | Required |

### 6. Audit & Logging APIs

| Endpoint | Method | Description | Authentication |
|----------|--------|-------------|----------------|
| `/api/v1/audit/events` | GET | Get audit events (paginated) | Required |

## Authentication & Security

### API Key Authentication
- **Header**: `X-API-Key` or `Authorization: Bearer <key>`
- **Tenant Isolation**: Automatic tenant scoping based on API key
- **Rate Limiting**: Per-tenant rate limits enforced
- **Security Headers**: CORS, CSRF protection, security headers

### Development API Key
```
X-API-Key: dev-api-key-123
```

## Frontend API Client

The frontend uses a centralized API client (`src/frontend/src/services/api.ts`) that:

- ✅ Handles all HTTP communication with the backend
- ✅ Manages authentication headers automatically
- ✅ Provides TypeScript type safety
- ✅ Implements error handling and retry logic
- ✅ Supports request/response interceptors
- ✅ Includes proper timeout handling (30s)

### Example API Usage

```typescript
import { apiClient } from '../services/api';

// Query processing
const response = await apiClient.processQuery({
  query: "What are the main features?",
  max_sources: 5
});

// Document upload
const uploadResult = await apiClient.uploadDocument(file);

// Sync operations
const syncStatus = await apiClient.triggerSync({
  sync_type: 'manual'
});
```

## Data Flow Architecture

```
Frontend Component
       ↓
   API Client
       ↓ (HTTP Request)
   FastAPI Router
       ↓
   Authentication Middleware
       ↓
   Business Logic Service
       ↓
   Database/Vector Store
       ↓
   Response Models
       ↓ (HTTP Response)
   Frontend Component
```

## Environment Configuration

### Frontend Environment Variables
```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_API_KEY=dev-api-key-123
VITE_APP_TITLE=Enterprise RAG Platform
```

### Backend Environment Variables
```bash
DATABASE_URL=postgresql://rag_user:rag_password@localhost:5432/rag_database
CHROMA_PERSIST_DIRECTORY=./data/chroma
UPLOAD_DIRECTORY=./data/uploads
TRANSFORMERS_CACHE=./cache/transformers
LOG_LEVEL=DEBUG
DEBUG=true
CORS_ORIGINS=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5175"]
```

## Deployment Architecture

### Development
- Frontend: `npm run dev` (Vite dev server)
- Backend: `python scripts/run_backend.py` (Uvicorn)

### Production
- Frontend: Static build deployed to CDN/web server
- Backend: Containerized FastAPI with reverse proxy
- Database: PostgreSQL with connection pooling and optimized settings
- Vector Store: ChromaDB cluster
- Authentication: JWT tokens with refresh mechanism

## API Documentation

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`

## Validation & Testing

### API Contract Testing
- All endpoints have Pydantic request/response models
- Automatic OpenAPI schema generation
- Input validation with detailed error messages
- Response serialization with proper types

### Error Handling
- Consistent error response format
- HTTP status codes follow REST standards
- Request IDs for tracing
- Structured logging for debugging

## Multi-Tenancy Support

### Tenant Isolation
- **Database**: Tenant-scoped queries with tenant_id column
- **Vector Store**: Tenant-prefixed collections
- **File System**: Tenant-specific directories
- **API Keys**: Mapped to specific tenants
- **Rate Limiting**: Per-tenant quotas

### Tenant Context
- Automatic tenant detection from API key
- Request-scoped tenant context
- Tenant validation on all operations
- Cross-tenant access prevention

## Performance & Scalability

### Caching Strategy
- Vector embeddings cached per tenant
- Query results cached with TTL
- Static assets cached at CDN level

### Monitoring
- Request/response logging
- Performance metrics collection
- Health check endpoints
- Error rate monitoring

## Security Considerations

### Data Protection
- Tenant data isolation enforced at all layers
- No cross-tenant data leakage possible
- Secure file upload with validation
- Input sanitization on all endpoints

### API Security
- Rate limiting per tenant
- Request size limits
- File upload restrictions
- CORS policy enforcement
- Security headers (HSTS, CSP, etc.)

## Summary

✅ **Perfect Separation Achieved**: Frontend and backend are completely decoupled with communication only via REST APIs

✅ **Complete API Coverage**: All backend functionality is accessible through well-defined API endpoints

✅ **Comprehensive Documentation**: Auto-generated API docs with request/response examples

✅ **Type Safety**: Full TypeScript support with proper type definitions

✅ **Security**: Robust authentication, authorization, and tenant isolation

✅ **Scalability**: Stateless design with proper caching and monitoring

✅ **Developer Experience**: Easy to develop, test, and deploy both layers independently

The architecture ensures that the frontend can be completely replaced or multiple frontend clients can be built without any changes to the backend, and vice versa. 