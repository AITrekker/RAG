# 🏢 Enterprise RAG Platform

A production-ready, enterprise-grade Retrieval-Augmented Generation (RAG) platform designed for scalable document intelligence with comprehensive multi-tenant support, intelligent delta synchronization, and advanced ML capabilities.

## ✨ Features

### 🏗️ **Enterprise Architecture**
- **🔒 Multi-tenant Isolation**: Complete data separation across database, vector operations, and file system
- **🔄 Intelligent Delta Sync**: Hash-based change detection with atomic transaction processing
- **🗃️ Unified Storage Design**: PostgreSQL with pgvector for both metadata and high-performance vector operations
- **🌐 API-First Architecture**: Comprehensive RESTful API with OpenAPI documentation
- **🚀 Production Ready**: Container orchestration, health checks, monitoring, and graceful degradation

### 📄 **Document Processing**
- **📚 Multi-Format Support**: PDF, DOCX, HTML, TXT, CSV with extensible processor architecture
- **🧩 Smart Chunking**: Sentence-aware text splitting with configurable overlap and size
- **🔍 Content Extraction**: Intelligent text extraction with fallback mechanisms
- **📊 Metadata Enrichment**: Automatic file analysis, word counts, language detection

### 🧠 **AI & Machine Learning**
- **🎯 Advanced RAG Pipeline**: Query processing → Vector retrieval → Context ranking → LLM generation
- **🚀 GPU Optimization**: RTX 5070 tuned with mixed precision and memory management
- **🔀 Model Flexibility**: Configurable embedding models (sentence-transformers) and LLMs
- **⚡ Performance Optimized**: Batch processing, caching, and async operations

### 🔐 **Security & Compliance**
- **🔑 API Key Authentication**: Stateless, secure tenant authentication
- **👥 Role-Based Access**: Granular permissions and file sharing controls
- **📋 Audit Trails**: Comprehensive operation tracking and sync history
- **🛡️ Input Validation**: Robust security with sanitization and rate limiting

## ⚡ Quick Start

Get the entire enterprise platform running locally in under 5 minutes with our streamlined deployment process.

### 📋 Prerequisites
- **Docker** (24.0+) and **Docker Compose** (2.20+)
- **8GB+ RAM** (for ML models and vector operations)
- **2GB+ disk space** (for containers and model cache)

### 🚀 One-Command Deployment

Clone and start the complete platform:

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

Monitor container health and readiness:

```bash
# Check all services are running
docker-compose ps

# View real-time logs
docker-compose logs -f

# Health check script
python scripts/verify_admin_setup.py
```

Expected healthy state:
```
NAME                STATUS              PORTS
rag_backend         Up (healthy)        0.0.0.0:8000->8000/tcp
rag_frontend        Up (healthy)        0.0.0.0:3000->3000/tcp  
rag_postgres        Up (healthy)        0.0.0.0:5432->5432/tcp
rag_init            Exited (0)          # Normal after successful setup
```

### 🌐 Access Your Platform

| Service | URL | Purpose |
|---------|-----|---------|
| **🖥️ Frontend Dashboard** | [localhost:3000](http://localhost:3000) | Main user interface |
| **📚 API Documentation** | [localhost:8000/docs](http://localhost:8000/docs) | Interactive API explorer |
| **🗄️ Database** | `localhost:5432` | PostgreSQL with pgvector (external tools) |

### 🎯 Quick Demo Setup

Initialize with demo data:

```bash
# Create demo tenants with sample documents
python scripts/workflow/setup_demo_tenants.py

# Test the complete RAG pipeline
python scripts/test_system.py

# Try sample queries
python demo_rag_queries.py
```

## 🛠️ Development Modes

### 🖥️ **Frontend Development**

The platform supports both **automatic container startup** and **manual debugging**:

#### **Auto-Start Mode (Recommended)**
```bash
# Frontend starts automatically with hot reload
docker-compose up -d
# Frontend available at http://localhost:3000 with live updates
```

#### **Manual Debug Mode** 
```bash
# For debugging frontend issues
make frontend-shell    # Enter container
npm run dev            # Manual yarn/npm dev

# Or directly:
make frontend-yarn     # Run yarn dev in container
```

#### **Production Mode**
```bash
# Build and deploy production frontend (Nginx + optimized build)
make up-prod
```

### 🔄 **Development Workflow**

| Command | Purpose | Use Case |
|---------|---------|----------|
| `make up` | Start all services | Normal development |
| `make frontend-dev` | Start only frontend | Frontend-only work |
| `make frontend-logs` | View frontend logs | Debug frontend issues |
| `make restart-frontend` | Restart frontend container | After config changes |

## 📚 Documentation

For more detailed information, please refer to our comprehensive guides in the `docs` folder.

- **[Architecture](docs/Architecture.md)**: A deep dive into the system's design, components, and data flows.
- **[API Reference](docs/API_REFERENCE.md)**: The complete reference for all API endpoints, including authentication and data models.
- **[Operations Guide](docs/OPERATIONS_GUIDE.md)**: A handbook for setup, deployment, Docker configuration, and managing demo tenants.

## 🧪 Testing

To run the full suite of tests, first set up the demo tenants and then execute the primary test script.

```bash
# 1. Set up demo tenants and API keys
python scripts/workflow/setup_demo_tenants.py

# 2. Run system tests
python scripts/test_system.py
```

For more details on testing, see the `tests/README.md` file.

## 📁 Architecture

### **🏗️ Hybrid PostgreSQL + Qdrant Architecture**

The platform implements a hybrid architecture that separates concerns between metadata management and vector operations:

```
PostgreSQL (Control Plane)          Qdrant (Vector Store)
├── tenants & users                  ├── tenant_{id}_documents
├── files & metadata                 ├── minimal payload 
├── sync operations                  ├── vector embeddings
├── access control                   └── search indices
└── audit trails                     
```

### **🔐 Service Layer Architecture**

The platform is built with a clean service layer pattern:

- **🔑 Authentication Service**: API key authentication with tenant isolation
- **📁 File Management Service**: Upload, CRUD operations, metadata tracking
- **🔄 Delta Sync Service**: Hash-based change detection and sync operations
- **📄 Document Processing Service**: Multi-format extraction (PDF, HTML, TXT, DOCX)
- **🧠 Embedding Service**: Sentence-transformers integration with fallbacks
- **🔍 RAG Service**: Complete query processing, vector search, and answer generation

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
-- PostgreSQL Tables
├── tenants                    # Tenant management & API keys
├── users                      # User accounts (future)
├── files                      # File metadata & sync status
├── embedding_chunks           # Chunk metadata linking to Qdrant
├── sync_operations           # Sync history & tracking
└── file_access_control       # Access permissions (future)

-- Qdrant Collections
└── tenant_{tenant_id}_documents   # Vector embeddings with minimal payload
```

## 🔄 Workflow

1. **🔑 Authentication**: API key-based tenant authentication
2. **📤 File Upload**: Upload files via API or copy to tenant directories
3. **🔄 Delta Sync**: Automatic hash-based change detection and processing
4. **🧠 Processing**: Document chunking and embedding generation
5. **🔍 Query**: RAG queries with metadata filtering and tenant isolation
6. **📊 Results**: Rich answers with source citations and confidence scores

### **✅ Current Implementation Status**

The following core services are **fully implemented and functional**:

- ✅ **Authentication Service**: API key authentication with tenant isolation
- ✅ **File Management Service**: Upload, CRUD operations, hash calculation
- ✅ **Delta Sync Service**: Hash-based change detection and sync tracking
- ✅ **Database Layer**: PostgreSQL schema with full tenant isolation
- ✅ **API Routes**: RESTful endpoints for files, sync, query operations
- ✅ **Service Architecture**: Clean dependency injection and service layer
- ✅ **Document Processing**: Multi-format extraction (PDF, HTML, TXT, DOCX) with factory pattern
- ✅ **Embedding Service**: Full ML pipeline with sentence-transformers + fallbacks
- ✅ **RAG Service**: Complete pipeline - query processing, vector retrieval, context ranking, response generation
- ✅ **Vector Storage**: Qdrant integration with PostgreSQL fallback for keyword search
- ✅ **Testing Infrastructure**: Comprehensive test suites for all components

### **🧪 Testing**

Comprehensive test suites are provided for different scenarios:

```bash
# Setup demo tenants with API keys (run this first!)
python scripts/setup_demo_tenants.py

# Test demo tenant authentication and basic functionality
python scripts/test_demo_tenants.py

# Test service layer and database (requires running backend)
python scripts/test_services.py

# Test HTTP API endpoints and authentication
python scripts/test_api_endpoints.py

# Test complete ML pipeline (embeddings, RAG, vector search) 
python scripts/test_ml_pipeline.py

# Test complete RAG system (query processing, retrieval, ranking)
python scripts/test_rag_system.py

# Test simple RAG with PostgreSQL fallback (when Qdrant unavailable)
python scripts/test_rag_simple.py

# Test with your existing tenant data (legacy test)
python scripts/test_existing_tenants.py
```

**Recommended Testing Workflow:**
1. Start backend: `docker-compose up -d`
2. Setup demo: `python scripts/setup_demo_tenants.py`
3. Test functionality: `python scripts/test_demo_tenants.py`
4. Use API keys from `demo_tenant_keys.json` for manual testing

### **🎯 Production-Ready Features**

The platform now includes complete **production-grade ML capabilities**:

- **📄 Document Processing**: PDF, HTML, TXT, DOCX with extensible factory pattern
- **🧠 ML Models**: sentence-transformers integration with graceful fallbacks
- **🔍 Vector Search**: Qdrant integration with PostgreSQL keyword search fallback
- **💬 RAG Pipeline**: Complete query processing, vector retrieval, context ranking, and answer generation
- **⚡ Performance**: Batch processing, caching, and optimized database queries
- **🛡️ Security**: Tenant isolation at all levels (database, vectors, file system)
- **🔧 Resilience**: Graceful degradation when ML services unavailable

### **🏢 Testing with Your Company Data**

Your project includes **3 pre-configured tenants** with company documents:

```
data/uploads/
├── tenant1/
│   ├── company_mission.txt
│   ├── our_culture.txt
│   ├── vacation_policy.txt
│   └── working_style.txt
├── tenant2/ [same files]
└── tenant3/ [same files]
```

#### **Quick Start Test**

1. **Start the backend**:
   ```bash
   docker-compose up -d
   # OR
   python scripts/run_backend.py
   ```

2. **Setup demo tenants** (Creates 3 demo tenants with API keys):
   ```bash
   python scripts/setup_demo_tenants.py
   ```

   This will:
   - ✅ Create admin tenant with system access
   - ✅ Create 3 demo tenants (tenant1, tenant2, tenant3) with pro plans
   - ✅ Generate API keys and save to `demo_tenant_keys.json`
   - ✅ Save admin API key to `.env` file
   - ✅ Discover company documents in `/data/uploads/` directories

3. **Test demo tenants**:
   ```bash
   python scripts/test_demo_tenants.py
   ```

   This will:
   - ✅ Test authentication for all demo tenants
   - ✅ Verify file API endpoints are working
   - ✅ Test tenant isolation and access control
   - ✅ Provide ready-to-use API keys for manual testing

#### **Manual Testing Commands**

After running the demo setup, use the API keys from `demo_tenant_keys.json`:

```bash
# Example API keys (use the actual keys from your demo_tenant_keys.json):
TENANT1_KEY="tenant_tenant1_xxxxx"
ADMIN_KEY="tenant_admin_xxxxx"

# Test admin access (list all tenants)
curl -H 'X-API-Key: '$ADMIN_KEY'' http://localhost:8000/api/v1/auth/tenants

# Test tenant authentication
curl -H 'X-API-Key: '$TENANT1_KEY'' http://localhost:8000/api/v1/auth/tenant

# List files for a tenant
curl -H 'X-API-Key: '$TENANT1_KEY'' http://localhost:8000/api/v1/files

# Upload a file (if you want to test file upload)
curl -X POST 'http://localhost:8000/api/v1/files/upload' \
  -H 'X-API-Key: '$TENANT1_KEY'' \
  -F 'file=@path/to/your/document.pdf'

# Trigger document sync
curl -X POST 'http://localhost:8000/api/v1/sync/trigger' \
  -H 'X-API-Key: '$TENANT1_KEY''

# Test RAG query (after documents are processed)
curl -X POST 'http://localhost:8000/api/v1/query' \
  -H 'X-API-Key: '$TENANT1_KEY'' \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "What is our company culture?",
    "max_results": 5,
    "min_score": 0.7
  }'
```

#### **Expected Results**

With the demo setup, you should see:
- 🏢 **4 demo tenants** (admin + 3 company tenants) with proper isolation
- 🔑 **API key authentication** working for all tenants  
- 📄 **Company documents** detected in `/data/uploads/tenant[1-3]/`
- 📊 **File API responses** showing empty file lists (until documents are uploaded/synced)
- 🔒 **Access control** ensuring each tenant only sees their own data
- 💾 **Persistent storage** with API keys saved for reuse

**Next Steps After Demo Setup:**
- Upload documents via API or copy files to tenant directories  
- Trigger sync operations to process documents into embeddings
- Test RAG queries with actual content using the comprehensive test scripts
- Use simple RAG test for quick verification without ML dependencies

## 🛠️ API Structure

### **🔑 Authentication**
All API endpoints (except `/health` and `/setup`) require authentication via API key:
```bash
# Header-based authentication
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/files

# Bearer token authentication  
curl -H "Authorization: Bearer your-api-key" http://localhost:8000/api/v1/files
```

### Core Endpoints
- **`/api/v1/health`** - System health checks (no auth required)
- **`/api/v1/files`** - File management with upload and CRUD operations  
- **`/api/v1/sync`** - Delta sync operations and change detection
- **`/api/v1/query`** - Complete RAG query processing with vector search and ranking
- **`/api/v1/auth`** - Tenant and API key management
- **`/api/v1/setup`** - System initialization (no auth required)
- **`/api/v1/admin`** - System administration

### Key Features
- **Complete RAG Pipeline**: Query processing, vector retrieval, context ranking, answer generation
- **Hybrid Search**: Vector similarity search with PostgreSQL keyword fallback
- **Delta Sync**: Only process changed files using hash comparison
- **Multi-Format Processing**: PDF, HTML, TXT, DOCX with extensible factory pattern
- **Tenant Isolation**: Complete data separation at all storage levels
- **Graceful Fallbacks**: System works with or without ML dependencies
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

# Install dependencies (includes ML packages)
pip install -r requirements.txt

# Optional: Install additional ML packages for full functionality
pip install sentence-transformers qdrant-client torch
pip install PyPDF2 python-docx nltk selectolax  # For document processing

# Run setup (creates .env, sets up directories)
python setup.py

# Start services
docker-compose up -d

# Test with your existing tenant data
python scripts/test_existing_tenants.py
```

### **🧠 ML Dependencies**

The platform includes **graceful fallbacks**, so it works with or without ML packages:

**Core Requirements** (always installed):
- FastAPI, SQLAlchemy, PostgreSQL drivers
- Basic text processing and file handling

**ML Enhancement Packages** (optional but recommended):
```bash
# For real embedding generation (vs mock embeddings)
pip install sentence-transformers torch

# For vector search (vs database fallback)  
pip install qdrant-client

# For document processing (vs plain text only)
pip install PyPDF2 python-docx nltk selectolax
```

**Performance Modes**:
- 🚀 **Full ML Mode**: All packages installed, real embeddings + vector search + complete RAG pipeline
- ⚡ **Hybrid Mode**: Some packages, partial ML functionality with fallbacks 
- 🔧 **Fallback Mode**: No ML packages, PostgreSQL keyword search with template responses

The system automatically detects available packages and adapts accordingly!

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
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is machine learning?",
    "max_results": 5,
    "min_score": 0.7,
    "filters": {
      "file_types": ["pdf", "txt"],
      "temporal": "recent"
    }
  }'
```

## 📚 API Documentation

### Health Checks
- `GET /api/v1/health` - Basic health check
- `GET /api/v1/health/detailed` - Comprehensive system health

### RAG Query Processing
- `POST /api/v1/query` - Complete RAG query with vector search and answer generation
- `POST /api/v1/query/validate` - Validate query without processing
- `GET /api/v1/query/history` - Query history and analytics
- `GET /api/v1/query/suggestions` - Get query suggestions
- `GET /api/v1/query/stats` - RAG performance statistics

### Delta Sync Operations
- `POST /api/v1/sync/trigger` - Trigger delta sync with hash-based change detection
- `GET /api/v1/sync/status` - Current sync operation status
- `GET /api/v1/sync/history` - Sync operation history and analytics
- `GET /api/v1/sync/stats` - Sync performance statistics

### File Management
- `GET /api/v1/files` - List tenant files with metadata
- `POST /api/v1/files/upload` - Upload files with automatic processing
- `GET /api/v1/files/{file_id}` - Get file details and processing status
- `DELETE /api/v1/files/{file_id}` - Delete file and associated embeddings

### System Administration
#### Tenant Management
- `GET /api/v1/auth/tenant` - Get current tenant info
- `GET /api/v1/auth/tenants` - List all tenants (admin only)
- `POST /api/v1/admin/tenants` - Create new tenant
- `PUT /api/v1/admin/tenants/{tenant_id}` - Update tenant settings

#### System Monitoring
- `GET /api/v1/admin/system/status` - Comprehensive system health
- `GET /api/v1/admin/system/metrics` - Performance metrics and statistics

## 🔧 Configuration

### Environment Variables
```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=rag_db
POSTGRES_USER=rag_user
POSTGRES_PASSWORD=rag_password

# Vector Store
QDRANT_HOST=localhost
QDRANT_PORT=6333

# API Settings
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO

# ML Settings
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
NLTK_DATA=/tmp/nltk_data
```

## 🧪 Testing

```bash
# Setup demo tenants with API keys (run this first!)
python scripts/setup_demo_tenants.py

# Test complete RAG system (all components)
python scripts/test_rag_system.py

# Test simple RAG with PostgreSQL fallback
python scripts/test_rag_simple.py

# Test ML pipeline (embeddings + vector storage)
python scripts/test_ml_pipeline.py

# Test API endpoints and authentication
python scripts/test_api_endpoints.py
```

## 📊 Monitoring

### Health Checks
- PostgreSQL database connectivity
- Qdrant vector store status
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
- Use external PostgreSQL and Qdrant instances
- Configure ML model caching and GPU acceleration
- Set up monitoring for RAG query performance
- Implement backup strategies for both databases
- Use HTTPS and proper authentication in production
- Consider scaling vector collections for large tenants

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