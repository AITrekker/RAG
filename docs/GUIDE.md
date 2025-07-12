# 📚 Simple RAG Platform Guide

Quick deployment and usage guide for the multi-tenant RAG platform.

## 🚀 Quick Start

### 1. Deploy
```bash
git clone <repository-url>
cd rag
docker-compose up -d
```

### 2. Setup Demo Data
```bash
python scripts/workflow/demo_workflow.py
```

### 3. Test Query
```bash
curl -X POST "http://localhost:8000/api/v1/query/" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: tenant_admin_api_key" \
  -d '{"query": "What is our vacation policy?"}'
```

## 🛠️ Core Operations

### File Upload
```bash
curl -X POST "http://localhost:8000/api/v1/files/upload" \
  -H "X-API-Key: your-api-key" \
  -F "file=@document.pdf"
```

### Trigger Processing
```bash
curl -X POST "http://localhost:8000/api/v1/sync/trigger" \
  -H "X-API-Key: your-api-key"
```

### Search Documents
```bash
curl -X POST "http://localhost:8000/api/v1/query/" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"query": "your search query"}'
```

## 🔧 Configuration

### Environment Variables (.env)
```bash
# Database
DATABASE_URL=postgresql://rag_user:rag_password@postgres:5432/rag_db

# Models
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# API
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
```

### Adding Documents
1. Copy files to `data/uploads/{tenant-id}/`
2. Or upload via API
3. Trigger sync to process

## 🏗️ Architecture

### Stack
- **Frontend**: React (port 3000)
- **Backend**: FastAPI (port 8000)  
- **Database**: PostgreSQL + pgvector (port 5432)

### Data Flow
```
Document → Text Extraction → Chunking → Embedding → pgvector → Search
```

### Key Services
- **DirectRAGService**: Core embedding and search
- **SimpleDocumentProcessor**: Text extraction
- **FileService**: File management
- **SyncService**: Processing pipeline

## 🧠 Embedding Pipeline

### Text Processing
```python
# Extract text from documents
text = extract_text(file_path)

# Split into chunks
chunks = chunk_text(text, size=512, overlap=50)

# Generate embeddings
embeddings = model.encode(chunks)

# Store in pgvector
store_embeddings(embeddings, chunks)
```

### Search Process
```python
# Convert query to embedding
query_embedding = model.encode([query])

# Search similar chunks
results = search_similar(query_embedding, limit=5)

# Generate response
answer = generate_answer(query, results)
```

## 🚀 Development

### Build & Run
```bash
# Rebuild backend
make backend-build

# View logs
docker-compose logs -f backend

# Restart services
docker-compose restart backend
```

### Adding New Models
```python
# In dependencies.py
EMBEDDING_MODEL = "sentence-transformers/all-mpnet-base-v2"
```

### Custom Chunking
```python
# In direct_rag_service.py
def _chunk_text(self, text, strategy="fixed"):
    if strategy == "sliding_window":
        return sliding_window_chunk(text)
    elif strategy == "semantic":
        return semantic_chunk(text)
    else:
        return fixed_chunk(text)
```

## 📊 Monitoring

### Health Checks
```bash
curl http://localhost:8000/api/v1/health/liveness
```

### Database Access
```bash
# Connect to PostgreSQL
docker exec -it rag_postgres psql -U rag_user -d rag_db

# Check embeddings
SELECT COUNT(*) FROM embedding_chunks;
```

### Debug Logs
```bash
# Backend logs
docker-compose logs backend

# All services
docker-compose logs
```

## 🔍 Experimentation Ready

Perfect foundation for:
- **Chunking strategies**: Fixed, sliding window, semantic
- **Embedding models**: sentence-transformers, custom models  
- **Reranking**: Cross-encoders, hybrid scoring
- **Performance testing**: Different similarity metrics

The codebase is now simple and readable - ideal for learning and experimentation!