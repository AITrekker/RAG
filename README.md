# 🔍 Multi-Tenant RAG Platform

A simple, production-ready RAG platform using **PostgreSQL + pgvector** for multi-tenant document embedding and retrieval.

## ✨ Core Features

- **🔒 Multi-tenant**: Complete data isolation per tenant
- **🗃️ Unified Storage**: PostgreSQL + pgvector for everything
- **📄 Document Processing**: PDF, DOCX, TXT, HTML support
- **🧠 Direct Embeddings**: sentence-transformers integration
- **🔍 Vector Search**: Fast similarity search with pgvector
- **🚀 Production Ready**: Docker deployment with health checks

## ⚡ Quick Start

### Prerequisites
- Docker (24.0+) and Docker Compose (2.20+)
- 4GB+ RAM for ML models

### Deploy
```bash
git clone <repository-url>
cd rag
docker-compose up -d
```

### Access
- **Frontend**: [localhost:3000](http://localhost:3000)
- **API Docs**: [localhost:8000/docs](http://localhost:8000/docs) 
- **Database**: `localhost:5432`

### Test
```bash
# Setup demo data
python scripts/workflow/demo_workflow.py

# Test queries
curl -H "X-API-Key: tenant_admin_api_key" \
     -H "Content-Type: application/json" \
     -d '{"query": "What is our vacation policy?"}' \
     http://localhost:8000/api/v1/query/
```

## 🏗️ Architecture

### Simple Stack
```
Frontend (React) → Backend (FastAPI) → PostgreSQL + pgvector
```

### Database Schema
```sql
tenants             # Tenant management
files               # File metadata
embedding_chunks    # Text chunks with pgvector embeddings
sync_operations     # Processing history
```

### File Structure
```
data/uploads/
├── {tenant-id}/
│   ├── document1.pdf
│   └── manual.docx
```

## 🔄 How It Works

1. **Upload** files via API or file system
2. **Process** documents into text chunks
3. **Embed** chunks using sentence-transformers
4. **Store** in PostgreSQL + pgvector
5. **Query** with vector similarity search
6. **Return** relevant chunks with confidence scores

## 🛠️ API Endpoints

```bash
# Authentication (all endpoints require API key)
-H "X-API-Key: your-tenant-api-key"

# Core endpoints
GET    /api/v1/health       # System health
POST   /api/v1/files/upload # Upload documents  
POST   /api/v1/sync/trigger # Process documents
POST   /api/v1/query/       # RAG queries
GET    /api/v1/files        # List documents
```

## 🧠 Embedding Pipeline

```python
# Document → Chunks → Embeddings → pgvector
text = extract_text(document)
chunks = chunk_text(text, size=512, overlap=50)
embeddings = sentence_transformer.encode(chunks)
store_in_pgvector(embeddings)
```

## 🔧 Configuration

Key environment variables in `.env`:
```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/rag_db

# Models
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# API
API_HOST=0.0.0.0
API_PORT=8000
```

## 🚀 Development

```bash
# Build backend only
make backend-build

# View logs
docker-compose logs -f backend

# Run tests
python -m pytest tests/
```

## 📊 Current Status

✅ **Working**: Multi-tenant document processing and vector search  
✅ **Simple**: ~800 lines of core code vs 2000+ before  
✅ **Fast**: Direct pgvector queries, no abstractions  
✅ **Ready**: Perfect for embedding/reranking experiments  

---

**Goal**: Learn embedding strategies and reranking techniques through direct experimentation.