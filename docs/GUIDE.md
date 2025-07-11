# 📚 Enterprise RAG Platform - Complete Guide

This comprehensive guide covers everything you need to deploy, configure, and operate the Enterprise RAG Platform with PostgreSQL + pgvector and hybrid LlamaIndex integration.

---

## 🚀 Quick Start

### Prerequisites
- **Docker** (24.0+) and **Docker Compose** (2.20+)
- **8GB+ RAM** (for ML models and vector operations)
- **2GB+ disk space** (for containers and model cache)

### One-Command Deployment
```bash
git clone <repository-url>
cd rag
docker-compose up -d
```

### Services & Ports
| Service | Port | Purpose |
|---------|------|---------|
| **Frontend** | `localhost:3000` | React management interface |
| **Backend API** | `localhost:8000` | FastAPI with Swagger docs |
| **Database** | `localhost:5432` | PostgreSQL with pgvector |

### Initial Setup
```bash
# Setup demo tenants and API keys
python scripts/workflow/setup_demo_tenants.py

# Test the complete system
python scripts/test_system.py

# Try sample queries
python demo_rag_queries.py
```

---

## 🏗️ Architecture Overview

### Unified Storage Architecture
The platform uses a **simplified PostgreSQL + pgvector architecture** for both metadata and vectors:

```
PostgreSQL (Unified Storage)
├── tenants & users          # Authentication & isolation
├── files & metadata         # Document management
├── embedding_chunks         # Text chunks with pgvector embeddings
├── sync_operations         # Change tracking
└── access_control          # Permissions
```

### 🦙 Hybrid LlamaIndex Integration
- **Complex Documents** (PDF, DOCX, HTML): Uses LlamaIndex for superior parsing
- **Simple Documents** (TXT): Uses lightweight internal processors
- **Unified Storage**: All chunks stored in PostgreSQL + pgvector
- **Graceful Fallbacks**: Optional dependencies with automatic fallback

### Service Architecture
- **🔑 Authentication Service**: API key-based tenant isolation
- **📁 File Management**: Upload, CRUD, metadata tracking
- **🔄 Delta Sync Service**: Hash-based change detection
- **📄 Document Processing**: Multi-format extraction with hybrid LlamaIndex
- **🧠 Embedding Service**: Sentence-transformers + pgvector storage
- **🔍 RAG Service**: Query processing, vector search, answer generation

---

## 🔧 Configuration

### Environment Variables
Create `.env` file in project root:
```bash
# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=rag_platform
POSTGRES_USER=rag_user
POSTGRES_PASSWORD=your_secure_password

# RAG Configuration
EMBEDDING_MODEL=all-MiniLM-L6-v2
CHUNK_SIZE=512
CHUNK_OVERLAP=50
MAX_CHUNKS_PER_FILE=100

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO

# Optional: LLM Configuration
OPENAI_API_KEY=your_openai_key  # For enhanced answer generation
```

### Docker Configuration
The `docker-compose.yml` orchestrates three services:
- **postgres**: PostgreSQL 16 with pgvector extension
- **backend**: FastAPI application with ML models
- **frontend**: React development server

### Build Configuration
```bash
# Fast incremental build (recommended)
make backend-build

# Clean rebuild (slow, 6+ minutes)
docker-compose build --no-cache
```

---

## 📄 Document Processing

### Supported Formats
- **PDF**: Advanced parsing with LlamaIndex (when available) or pypdf2 fallback
- **DOCX**: Microsoft Word documents with python-docx
- **HTML/HTM**: Web content with selectolax parser
- **TXT**: Plain text with efficient processing
- **CSV**: Structured data processing

### Processing Pipeline
1. **File Upload**: Via API or direct file copy to tenant directories
2. **Change Detection**: Hash-based delta sync identifies new/modified files
3. **Hybrid Processing**: 
   - Complex documents → LlamaIndex parsing
   - Simple documents → Internal processors
4. **Chunking**: Sentence-aware splitting with configurable overlap
5. **Embedding**: Generate vectors using sentence-transformers
6. **Storage**: Store chunks and vectors in PostgreSQL + pgvector

### File Organization
```
data/uploads/
├── {tenant-id-1}/
│   ├── document1.pdf
│   ├── report.docx
│   └── data.csv
├── {tenant-id-2}/
│   └── manual.txt
```

---

## 🔍 RAG Query Pipeline

### Query Processing Flow
1. **Authentication**: Validate API key and tenant isolation
2. **Query Embedding**: Convert user query to vector using same model
3. **Vector Search**: PostgreSQL pgvector similarity search with tenant filtering
4. **Context Ranking**: Score and rank retrieved chunks by relevance
5. **Answer Generation**: 
   - **Hybrid Mode**: Optional LlamaIndex response synthesis
   - **Fallback**: Template-based answer with source citations
6. **Response**: Rich answer with sources, confidence scores, and metadata

### Example Query
```bash
curl -X POST "http://localhost:8000/api/v1/query/" \
  -H "X-API-Key: your-tenant-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is our company vacation policy?",
    "max_sources": 5,
    "confidence_threshold": 0.7
  }'
```

---

## 🔄 Sync Operations

### Delta Sync Process
The platform uses intelligent delta sync for efficient file processing:

1. **File Scanning**: Scan tenant upload directories
2. **Hash Comparison**: Compare SHA-256 hashes to detect changes
3. **Change Classification**: Identify new, updated, or deleted files
4. **Sequential Processing**: Process changes in order for reliability
5. **Database Updates**: Update file metadata and sync status
6. **Vector Updates**: Generate/update embeddings for changed content

### Sync Commands
```bash
# Manual sync trigger
python scripts/delta-sync.py

# Rename tenant directories to match UUIDs
python scripts/rename-tenants.py

# Check sync status via API
curl "http://localhost:8000/api/v1/sync/status" \
  -H "X-API-Key: your-api-key"
```

---

## 🔑 Authentication & Multi-tenancy

### API Key Authentication
All API endpoints require authentication via API key:
```bash
# Header-based (recommended)
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/files

# Bearer token
curl -H "Authorization: Bearer your-api-key" http://localhost:8000/api/v1/files
```

### Tenant Isolation
- **Database Level**: All queries filtered by tenant_id
- **File System**: Separate upload directories per tenant
- **Vector Search**: Automatic tenant filtering in similarity queries
- **Access Control**: API keys tied to specific tenants

### Setup Demo Tenants
```bash
python scripts/workflow/setup_demo_tenants.py
```
Creates demo tenants with API keys stored in `demo_tenant_keys.json`.

---

## 🛠️ API Reference

### Core Endpoints

#### Health & System
- `GET /api/v1/health` - System health and component status
- `GET /api/v1/health/liveness` - Kubernetes liveness probe
- `GET /api/v1/health/readiness` - Kubernetes readiness probe

#### File Management
- `GET /api/v1/files` - List tenant files
- `POST /api/v1/files/upload` - Upload files
- `GET /api/v1/files/{file_id}` - Get file metadata
- `DELETE /api/v1/files/{file_id}` - Delete file

#### Sync Operations
- `POST /api/v1/sync/trigger` - Manual sync trigger
- `GET /api/v1/sync/status` - Current sync status
- `GET /api/v1/sync/history` - Sync operation history

#### Query & RAG
- `POST /api/v1/query/` - Complete RAG query with answer generation
- `POST /api/v1/query/search` - Semantic search without answer generation
- `GET /api/v1/query/suggestions` - Query autocomplete suggestions

#### Analytics & Admin
- `GET /api/v1/analytics/usage` - Usage statistics
- `POST /api/v1/admin/users` - User management (admin only)
- `GET /api/v1/admin/system` - System administration

### Interactive API Documentation
Visit `http://localhost:8000/docs` for complete Swagger documentation with interactive examples.

---

## 🧪 Testing & Validation

### Automated Testing
```bash
# Setup demo tenants first
python scripts/workflow/setup_demo_tenants.py

# Run comprehensive system tests
python scripts/test_rag_system.py

# Test specific components
python tests/test_embedding_service.py
python tests/test_api_health.py
python tests/test_sync_service.py
```

### Manual Testing
```bash
# Test API health
curl http://localhost:8000/api/v1/health

# Test file upload
curl -X POST "http://localhost:8000/api/v1/files/upload" \
  -H "X-API-Key: your-api-key" \
  -F "file=@document.pdf"

# Test RAG query
curl -X POST "http://localhost:8000/api/v1/query/" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"query": "test question", "max_sources": 3}'
```

---

## 🔧 Maintenance & Operations

### Container Management
```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs backend
docker-compose logs postgres

# Stop services
docker-compose down

# Rebuild and restart
make backend-build && docker-compose up -d
```

### Database Operations
```bash
# Connect to PostgreSQL
docker exec -it rag_postgres psql -U rag_user -d rag_platform

# Backup database
docker exec rag_postgres pg_dump -U rag_user rag_platform > backup.sql

# Check pgvector extension
docker exec rag_postgres psql -U rag_user -d rag_platform -c "SELECT * FROM pg_extension WHERE extname='vector';"
```

### Performance Monitoring
```bash
# Container resource usage
docker stats

# Database performance
docker exec rag_postgres psql -U rag_user -d rag_platform -c "
  SELECT schemaname, tablename, n_live_tup, n_dead_tup 
  FROM pg_stat_user_tables 
  ORDER BY n_live_tup DESC;"

# Vector index statistics
docker exec rag_postgres psql -U rag_user -d rag_platform -c "
  SELECT COUNT(*) as total_chunks, 
         AVG(array_length(embedding, 1)) as avg_dimensions
  FROM embedding_chunks;"
```

### Log Analysis
```bash
# Backend application logs
docker-compose logs backend | grep ERROR

# Database logs
docker-compose logs postgres | grep ERROR

# Real-time log monitoring
docker-compose logs -f backend
```

---

## 🚨 Troubleshooting

### Common Issues

#### Container Build Failures
**Problem**: Docker build fails with timeout or memory errors
**Solution**: 
```bash
# Increase Docker build timeout
docker-compose build --progress=plain --no-cache backend
# or use make command with timeout
make backend-build  # Sets 6-minute timeout
```

#### LlamaIndex Import Errors
**Problem**: "No module named 'llama_index.vector_stores'"
**Solution**: This is expected - the hybrid system automatically falls back to simple processing

#### Database Connection Errors
**Problem**: "Connection refused" to PostgreSQL
**Solution**:
```bash
# Check container status
docker-compose ps
# Restart database
docker-compose restart postgres
# Check logs
docker-compose logs postgres
```

#### Memory Issues
**Problem**: System runs out of memory during model loading
**Solution**:
```bash
# Reduce batch sizes in config
CHUNK_SIZE=256  # Reduce from 512
MAX_CHUNKS_PER_FILE=50  # Reduce from 100
```

### Health Checks
```bash
# System health
curl http://localhost:8000/api/v1/health

# Database connectivity
docker exec rag_postgres pg_isready -U rag_user

# Model loading status
docker-compose logs backend | grep "model initialized"
```

---

## 🎯 Performance Tuning

### Vector Search Optimization
```sql
-- Create optimized indexes for pgvector
CREATE INDEX CONCURRENTLY idx_embedding_tenant_cosine 
ON embedding_chunks USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100)
WHERE tenant_id IS NOT NULL;
```

### Chunking Configuration
```python
# Optimal settings for different document types
PDF_CHUNK_SIZE = 512      # For complex layouts
TEXT_CHUNK_SIZE = 256     # For simple text
CHUNK_OVERLAP = 50        # 10% overlap recommended
```

### Batch Processing
```python
# Process files in smaller batches to reduce memory usage
BATCH_SIZE = 10           # Files per batch
EMBEDDING_BATCH_SIZE = 32 # Chunks per embedding batch
```

---

## 🔐 Security Considerations

### API Security
- All endpoints require valid API keys
- Tenant isolation enforced at database level
- Input validation and sanitization
- Rate limiting on query endpoints

### Data Security
- PostgreSQL with encrypted connections
- File system isolation by tenant
- No sensitive data in logs
- Secure API key generation

### Production Deployment
```bash
# Use environment-specific configurations
cp .env.example .env.production
# Set strong passwords
POSTGRES_PASSWORD=$(openssl rand -base64 32)
# Configure SSL/TLS
POSTGRES_SSL_MODE=require
```

---

## 📊 Monitoring & Analytics

### Key Metrics
- Query response times
- Document processing throughput
- Vector search accuracy
- System resource usage
- API endpoint performance

### Monitoring Commands
```bash
# API performance
curl -w "@curl-format.txt" http://localhost:8000/api/v1/health

# Database performance
docker exec rag_postgres psql -U rag_user -d rag_platform -c "
  SELECT query, mean_exec_time, calls 
  FROM pg_stat_statements 
  ORDER BY mean_exec_time DESC LIMIT 10;"
```

---

## 🔄 Backup & Recovery

### Database Backup
```bash
# Full backup
docker exec rag_postgres pg_dump -U rag_user rag_platform > rag_backup_$(date +%Y%m%d).sql

# Restore
docker exec -i rag_postgres psql -U rag_user rag_platform < rag_backup_20250101.sql
```

### File System Backup
```bash
# Backup tenant uploads
tar -czf uploads_backup_$(date +%Y%m%d).tar.gz data/uploads/
```

---

*This guide covers the unified PostgreSQL + pgvector architecture with hybrid LlamaIndex integration. For questions or issues, check the troubleshooting section or review container logs.*