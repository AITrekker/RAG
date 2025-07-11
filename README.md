# 🏢 Enterprise RAG Platform

A production-ready, enterprise-grade Retrieval-Augmented Generation (RAG) platform with PostgreSQL + pgvector for unified storage and intelligent delta synchronization.

## ✨ Features

### 🏗️ **Enterprise Architecture**
- **🔒 Multi-tenant Isolation**: Complete data separation across database and file system
- **🔄 Intelligent Delta Sync**: Hash-based change detection with simplified sequential processing
- **🗃️ Unified Storage**: PostgreSQL with pgvector for both metadata and high-performance vector operations
- **🌐 API-First Architecture**: Comprehensive RESTful API with OpenAPI documentation
- **🚀 Production Ready**: Container orchestration, health checks, and graceful degradation

### 📄 **Document Processing**
- **📚 Multi-Format Support**: PDF, DOCX, HTML, TXT, CSV with extensible processor architecture
- **🧩 Smart Chunking**: Sentence-aware text splitting with configurable overlap and size
- **🔍 Content Extraction**: Intelligent text extraction with fallback mechanisms
- **📊 Metadata Enrichment**: Automatic file analysis, word counts, language detection
- **🦙 Hybrid LlamaIndex Integration**: Optional LlamaIndex for advanced document parsing with pgvector storage

### 🧠 **AI & Machine Learning**
- **🎯 Advanced RAG Pipeline**: Query processing → Vector retrieval → Context ranking → LLM generation
- **🔀 Model Flexibility**: Configurable embedding models (sentence-transformers) and LLMs
- **⚡ Performance Optimized**: Batch processing, caching, and async operations
- **🔄 Hybrid Processing**: LlamaIndex for complex documents, simple processing for basic files

### 🔐 **Security & Compliance**
- **🔑 API Key Authentication**: Stateless, secure tenant authentication
- **📋 Audit Trails**: Comprehensive operation tracking and sync history
- **🛡️ Input Validation**: Robust security with sanitization and rate limiting

## ⚡ Quick Start

### 📋 Prerequisites
- **Docker** (24.0+) and **Docker Compose** (2.20+)
- **8GB+ RAM** (for ML models and vector operations)
- **2GB+ disk space** (for containers and model cache)

### 🚀 One-Command Deployment

```bash
git clone <repository-url>
cd rag
docker-compose up -d
```

This orchestrates all services:
- **🗄️ PostgreSQL**: Multi-tenant database with pgvector for unified storage
- **⚙️ Backend API**: FastAPI with comprehensive endpoints
- **🖥️ Frontend UI**: React-based management interface
- **🔧 Init Container**: Automatic database setup and admin user creation

### ✅ Verify Deployment

```bash
# Check all services are running
docker-compose ps

# View real-time logs
docker-compose logs -f

# Health check script
python scripts/verify_admin_setup.py
```

### 🌐 Access Your Platform

| Service | URL | Purpose |
|---------|-----|------------|
| **🖥️ Frontend Dashboard** | [localhost:3000](http://localhost:3000) | Main user interface |
| **📚 API Documentation** | [localhost:8000/docs](http://localhost:8000/docs) | Interactive API explorer |
| **🗄️ Database** | `localhost:5432` | PostgreSQL with pgvector (external tools) |

### 🎯 Quick Demo Setup

```bash
# Create demo tenants with sample documents
python scripts/workflow/setup_demo_tenants.py

# Test the complete RAG pipeline
python scripts/test_system.py

# Try sample queries
python demo_rag_queries.py
```

## 📚 Architecture

### **🏗️ PostgreSQL + pgvector Architecture**

The platform uses a unified PostgreSQL + pgvector architecture for simplicity and performance:

```
PostgreSQL (Unified Storage)
├── tenants & users
├── files & metadata  
├── embedding_chunks (with pgvector embeddings)
├── sync operations
├── access control
└── audit trails
```

### **🔐 Service Layer Architecture**

Clean service layer pattern with simplified sync operations:

- **🔑 Authentication Service**: API key authentication with tenant isolation
- **📁 File Management Service**: Upload, CRUD operations, metadata tracking
- **🔄 Delta Sync Service**: Hash-based change detection with sequential processing
- **📄 Document Processing Service**: Multi-format extraction (PDF, HTML, TXT, DOCX) with hybrid LlamaIndex integration
- **🧠 Embedding Service**: Sentence-transformers integration with pgvector storage
- **🔍 RAG Service**: Complete query processing, vector search, and answer generation with optional LlamaIndex synthesis

### File Storage Structure
```
data/
├── uploads/
│   ├── {tenant-id}/
│   │   ├── document1.pdf
│   │   ├── report.docx
│   │   └── data.csv
│   └── {tenant-id-2}/
│       ├── manual.pdf
│       └── notes.txt
```

### Database Schema
```sql
-- PostgreSQL Tables (Unified Storage)
├── tenants                    # Tenant management & API keys
├── users                      # User accounts
├── files                      # File metadata & sync status
├── embedding_chunks           # Text chunks with pgvector embeddings
├── sync_operations           # Sync history & tracking
└── file_access_control       # Access permissions
```

## 🦙 Hybrid LlamaIndex Integration

The platform features intelligent hybrid processing that combines the best of both worlds:

### **🎯 Smart Document Processing**
- **Complex Documents** (PDF, DOCX, HTML): Uses LlamaIndex for superior parsing and chunking
- **Simple Documents** (TXT): Uses lightweight internal processors for efficiency
- **Unified Storage**: All chunks stored in PostgreSQL + pgvector regardless of processing method

### **🔧 Graceful Fallbacks**
- LlamaIndex dependencies are **optional** - system works without them
- Automatic fallback to simple processing if LlamaIndex unavailable
- No architectural disruption when switching between modes

### **⚡ Performance Benefits**
- LlamaIndex only used where it adds value (complex document parsing)
- Maintains simplified pgvector architecture for storage and retrieval
- Best-in-class document processing with streamlined vector operations

## 🔄 Workflow

1. **🔑 Authentication**: API key-based tenant authentication
2. **📤 File Upload**: Upload files via API or copy to tenant directories
3. **🔄 Delta Sync**: Sequential hash-based change detection and processing
4. **🧠 Hybrid Processing**: LlamaIndex for complex docs, simple processing for basic files
5. **🗃️ Unified Storage**: All chunks stored in PostgreSQL + pgvector
6. **🔍 Query**: RAG queries with optional LlamaIndex response synthesis
7. **📊 Results**: Rich answers with source citations and confidence scores

## 🛠️ API Structure

### **🔑 Authentication**
All API endpoints require authentication via API key:
```bash
# Header-based authentication
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/files

# Bearer token authentication  
curl -H "Authorization: Bearer your-api-key" http://localhost:8000/api/v1/files
```

### Core Endpoints
- **`/api/v1/health`** - System health checks
- **`/api/v1/files`** - File management with upload and CRUD operations  
- **`/api/v1/sync`** - Delta sync operations and change detection
- **`/api/v1/query`** - Complete RAG query processing with vector search
- **`/api/v1/auth`** - Tenant and API key management
- **`/api/v1/setup`** - System initialization
- **`/api/v1/admin`** - System administration

## 🧪 Testing

```bash
# Setup demo tenants with API keys (run this first!)
python scripts/workflow/setup_demo_tenants.py

# Test complete RAG system (all components)
python scripts/test_rag_system.py

# Test simple RAG with PostgreSQL fallback
python scripts/test_rag_simple.py

# Test ML pipeline (embeddings + vector storage)
python scripts/test_ml_pipeline.py

# Test API endpoints and authentication
python scripts/test_api_endpoints.py
```

## 🔧 Configuration

### Environment Variables
```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=rag_db
POSTGRES_USER=rag_user
POSTGRES_PASSWORD=rag_password

# API Settings
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO

# ML Settings
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
NLTK_DATA=/tmp/nltk_data
```

## 📊 Monitoring

### Health Checks
- PostgreSQL database connectivity
- Document processing pipeline health
- RAG service component status

### Metrics
- RAG query performance and accuracy
- Document processing and sync operations
- Vector search response times
- System resource usage and error rates

## 🔒 Security

- **API Key Authentication**: Secure tenant isolation
- **Input Validation**: Comprehensive request validation
- **Error Handling**: Secure error responses
- **Rate Limiting**: Configurable rate limits
- **Audit Logging**: Operation tracking

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
- Use external PostgreSQL with pgvector extension
- Configure ML model caching and GPU acceleration
- Set up monitoring for RAG query performance
- Implement backup strategies for the database
- Use HTTPS and proper authentication in production
- Consider scaling for large tenants

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
- Check the API documentation at `/docs`
- Open an issue on GitHub
- Contact the development team

---

## 📖 Additional Documentation

### Key Commands (from CLAUDE.md)
- **Build**: `make backend-build` (fast container rebuild - ~6 minutes)
- **Full Rebuild**: `docker-compose build --no-cache` (with 6min timeout)
- **Container Management**: `docker-compose up -d`, `docker-compose down`

### Development Notes
- Backend builds take ~6 minutes due to HuggingFace/PyTorch cache copying
- ML model caches persist in Docker volumes for faster restarts
- Delta sync system uses PostgreSQL for control plane + pgvector for vectors
- Simplified sequential processing for reliability over performance optimization

### Current Architecture Status: ✅ WORKING
The PostgreSQL + pgvector delta sync architecture is fully implemented and tested with simplified, reliable sync operations.