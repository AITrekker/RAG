# Enterprise RAG Platform

A production-ready Retrieval-Augmented Generation (RAG) platform designed for enterprise use cases with multi-tenant support, delta sync, and comprehensive metadata management.

## 🚀 Features

- **Multi-tenant Architecture**: Isolated data and processing per tenant
- **Delta Sync**: Efficient document processing with hash-based change detection
- **Rich Metadata**: Comprehensive document metadata extraction and filtering
- **RAG Pipeline**: Advanced query processing with confidence scoring
- **API-First Design**: RESTful API with comprehensive documentation
- **Production Ready**: Health checks, monitoring, and error handling

## 📁 Architecture

### File Storage Structure
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

### Qdrant Collections
```
tenant_{tenant_id}_documents     # Document metadata + file hashes
tenant_{tenant_id}_embeddings    # Document chunks with embeddings
tenant_{tenant_id}_sync_state    # Sync state and file hashes
```

## 🔄 Workflow

1. **File Management**: Manually copy files to tenant document folders
2. **Delta Sync**: API triggers sync to process new/modified files
3. **Query Processing**: RAG queries with metadata filtering
4. **Results**: Rich answers with source citations and metadata

## 🛠️ API Structure

### Core Endpoints
- **`/api/v1/health`** - System health checks
- **`/api/v1/query`** - RAG query processing with metadata filtering
- **`/api/v1/sync`** - Delta sync operations and document processing
- **`/api/v1/setup`** - System initialization
- **`/api/v1/admin`** - System administration

### Key Features
- **Metadata Filtering**: Filter queries by author, date, tags, document type
- **Delta Sync**: Only process changed files using hash comparison
- **Document Search**: Search documents by content and metadata
- **Query History**: Track and analyze query patterns
- **System Monitoring**: Comprehensive health and performance metrics

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.11+
- Docker and Docker Compose
- Git

### 2. Setup (Fresh Clone)
```bash
# Clone the repository
git clone <repository-url>
cd RAG

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Unix/MacOS:
source .venv/bin/activate

# Run setup (installs dependencies, creates .env, sets up directories)
python setup.py

# Start Qdrant
docker-compose up -d qdrant

# Initialize the database
python scripts/db-init.py

# Start the backend
python scripts/run_backend.py
```

### 3. Alternative Setup Options

#### Development Setup (with additional checks)
```bash
python scripts/setup_dev.py
```

#### Docker Setup (Recommended)
```bash
# Start all services with proper orchestration
docker-compose up -d

# The services will start in this order:
# 1. Qdrant (waits for health check)
# 2. Backend (waits for Qdrant, then seeds DB if empty)
# 3. Frontend (waits for Backend health check)
```

#### Docker Setup (Individual Services)
```bash
# Start Qdrant first
docker-compose up -d qdrant

# Wait for Qdrant to be healthy, then start backend
docker-compose up -d backend

# Wait for backend to be healthy, then start frontend
docker-compose up -d frontend
```

#### Docker Setup (backend may have ML library issues)
```bash
# If you encounter ML library compatibility issues with Docker backend:
docker-compose up -d qdrant
python scripts/startup.py  # Run locally to seed DB
python scripts/run_backend.py  # Run backend locally
```

#### Manual Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file
copy .env.example .env

# Create directories
mkdir -p data/tenants logs cache/transformers cache/huggingface
```

### 4. Usage

#### Initialize System
```bash
curl -X POST "http://localhost:8000/api/v1/setup/initialize" \
  -H "Content-Type: application/json" \
  -d '{"admin_tenant_name": "admin", "admin_tenant_description": "System administrator"}'
```

#### Add Documents
```bash
# Copy files to tenant folder
cp document.pdf data/tenants/tenant-1/documents/

# Trigger delta sync
curl -X POST "http://localhost:8000/api/v1/syncs" \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"force_full_sync": false}'
```

#### Query with Metadata Filtering
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
      "tags": ["AI", "research"]
    }
  }'
```

## 📚 API Documentation

### Health Checks
- `GET /api/v1/health` - Basic health check
- `GET /api/v1/health/detailed` - Comprehensive system health

### Query Processing (RESTful)
- `POST /api/v1/queries` - Create single query with metadata filtering
- `POST /api/v1/queries/batch` - Create batch queries
- `POST /api/v1/queries/validate` - Validate query without processing
- `GET /api/v1/queries/documents` - List documents with metadata
- `GET /api/v1/queries/search` - Search documents
- `GET /api/v1/queries/history` - Query history
- `GET /api/v1/queries/config` - Get query configuration
- `PUT /api/v1/queries/config` - Update query configuration
- `GET /api/v1/queries/stats` - Get query statistics

### Delta Sync (RESTful)
- `POST /api/v1/syncs` - Create delta sync operation
- `GET /api/v1/syncs/{sync_id}` - Get sync status
- `DELETE /api/v1/syncs/{sync_id}` - Cancel sync operation
- `GET /api/v1/syncs/history` - Sync history
- `GET /api/v1/syncs/config` - Sync configuration
- `PUT /api/v1/syncs/config` - Update sync configuration
- `GET /api/v1/syncs/stats` - Get sync statistics
- `POST /api/v1/syncs/documents` - Process single document
- `DELETE /api/v1/syncs/documents/{document_id}` - Remove document

### System Administration (RESTful)
#### Tenant Management
- `POST /api/v1/admin/tenants` - Create tenant
- `GET /api/v1/admin/tenants` - List tenants
- `GET /api/v1/admin/tenants/{tenant_id}` - Get tenant details
- `PUT /api/v1/admin/tenants/{tenant_id}` - Update tenant
- `DELETE /api/v1/admin/tenants/{tenant_id}` - Delete tenant

#### API Key Management
- `POST /api/v1/admin/tenants/{tenant_id}/api-keys` - Create API key
- `GET /api/v1/admin/tenants/{tenant_id}/api-keys` - List API keys
- `DELETE /api/v1/admin/tenants/{tenant_id}/api-keys/{key_id}` - Delete API key

#### System Monitoring
- `GET /api/v1/admin/system/status` - System status
- `GET /api/v1/admin/system/metrics` - System metrics

#### System Maintenance (RESTful)
- `DELETE /api/v1/admin/system/embeddings/stats` - Clear embedding stats
- `DELETE /api/v1/admin/system/llm/stats` - Clear LLM stats
- `DELETE /api/v1/admin/system/llm/cache` - Clear LLM cache
- `PUT /api/v1/admin/system/maintenance` - Set maintenance mode

#### Audit & Demo
- `GET /api/v1/admin/audit/events` - Get audit events
- `POST /api/v1/admin/demo/setup` - Setup demo environment
- `GET /api/v1/admin/demo/tenants` - List demo tenants
- `DELETE /api/v1/admin/demo/cleanup` - Clean up demo environment

## 🔧 Configuration

### Environment Variables
```bash
# Database
QDRANT_HOST=localhost
QDRANT_PORT=6333

# API Settings
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO

# Embedding Model
EMBEDDING_MODEL_PATH=/path/to/model
EMBEDDING_DEVICE=cpu

# LLM Settings
LLM_MODEL_PATH=/path/to/llm
LLM_DEVICE=cpu
```

## 🧪 Testing

```bash
# Run unit tests
pytest tests/

# Run integration tests
pytest tests/test_integration_e2e.py

# Quick API test
python tests/quick_api_test.py
```

## 📊 Monitoring

### Health Checks
- System component status
- Vector store connectivity
- Embedding service health
- LLM service health

### Metrics
- Query performance
- Sync operations
- System resource usage
- Error rates

## 🔒 Security

- **API Key Authentication**: Secure tenant isolation
- **Input Validation**: Comprehensive request validation
- **Error Handling**: Secure error responses
- **Rate Limiting**: Configurable rate limits
- **Audit Logging**: Operation tracking (admin only)

## 🚀 Deployment

### Docker Deployment
```bash
# Build and run with Docker Compose
docker-compose up -d

# Or build individual services
docker build -f docker/Dockerfile.backend -t rag-backend .
docker build -f docker/Dockerfile.frontend -t rag-frontend .
```

### Production Considerations
- Use external Qdrant instance
- Configure proper logging
- Set up monitoring and alerting
- Implement backup strategies
- Use HTTPS in production

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Check the documentation
- Review the API documentation at `/docs`
- Open an issue on GitHub
- Contact the development team