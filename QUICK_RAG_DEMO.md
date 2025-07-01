# Quick RAG Demo Guide

## 🚀 How to Query and Use RAG with Test Tenants

### Prerequisites
1. Backend running: `docker-compose up -d`
2. Demo tenants set up: `python scripts/workflow/setup_demo_tenants.py`

### Available Test Tenants

| Tenant | API Key | Documents Available |
|--------|---------|-------------------|
| **tenant1** | `tenant_tenant1_a6eafcd4144ad2b42bd404c9069ea3d9` | company_overview.txt, meeting_notes.txt, product_specifications.txt |
| **tenant2** | `tenant_tenant2_d576904945bf1a1f34e0cc080772d1af` | financial_report.txt, marketing_strategy.txt, team_handbook.txt |
| **tenant3** | `tenant_tenant3_a343ca13dee8c2a151bf3f0cb19feb8b` | project_timeline.txt, technical_documentation.txt, user_manual.txt |

---

## 🎯 Method 1: Using the Demo Script (Recommended)

### Basic Usage
```bash
# Run complete workflow demo for tenant1
python demo_rag_queries.py --workflow --tenant tenant1

# Ask a specific question
python demo_rag_queries.py --tenant tenant1 --query "What is the company's mission?"

# Use different tenant
python demo_rag_queries.py --tenant tenant2 --query "What are the financial results?"
```

### Advanced Usage
```bash
# Interactive demo (shows all features)
python demo_rag_queries.py --tenant tenant1

# Demo different tenants to see isolation
python demo_rag_queries.py --tenant tenant2 --workflow
python demo_rag_queries.py --tenant tenant3 --workflow
```

---

## 🔧 Method 2: Using curl Commands

### 1. Trigger Document Sync
```bash
curl -X POST "http://localhost:8000/api/v1/sync/trigger" \
  -H "X-API-Key: tenant_tenant1_a6eafcd4144ad2b42bd404c9069ea3d9" \
  -H "Content-Type: application/json"
```

### 2. Ask a RAG Question
```bash
curl -X POST "http://localhost:8000/api/v1/query/" \
  -H "X-API-Key: tenant_tenant1_a6eafcd4144ad2b42bd404c9069ea3d9" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the company mission?",
    "max_sources": 5,
    "confidence_threshold": 0.3
  }'
```

### 3. Semantic Search
```bash
curl -X POST "http://localhost:8000/api/v1/query/search" \
  -H "X-API-Key: tenant_tenant1_a6eafcd4144ad2b42bd404c9069ea3d9" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "company products",
    "max_results": 10
  }'
```

### 4. Validate Query
```bash
curl -X POST "http://localhost:8000/api/v1/query/validate" \
  -H "X-API-Key: tenant_tenant1_a6eafcd4144ad2b42bd404c9069ea3d9" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the company mission?"}'
```

### 5. Get Query Suggestions
```bash
curl -X GET "http://localhost:8000/api/v1/query/suggestions?partial_query=company&max_suggestions=5" \
  -H "X-API-Key: tenant_tenant1_a6eafcd4144ad2b42bd404c9069ea3d9"
```

---

## 📋 Method 3: Using Python Requests

```python
import requests
import json

# Configuration
BACKEND_URL = "http://localhost:8000"
API_KEY = "tenant_tenant1_a6eafcd4144ad2b42bd404c9069ea3d9"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

# 1. Trigger sync
sync_response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=headers)
print("Sync:", sync_response.json())

# 2. Ask a question
query_payload = {
    "query": "What does the company do?",
    "max_sources": 5
}
query_response = requests.post(f"{BACKEND_URL}/api/v1/query/", headers=headers, json=query_payload)
result = query_response.json()

print("Answer:", result["answer"])
print("Sources:", [s["filename"] for s in result["sources"]])
print("Confidence:", result["confidence"])
```

---

## 🎯 Sample Queries by Tenant

### Tenant1 (Company Documents)
- "What is the company's mission and vision?"
- "What products does the company offer?"
- "Who attended the recent meetings?"
- "What are the product specifications?"

### Tenant2 (Financial/Marketing)
- "What are the financial results?"
- "What is the marketing strategy?"
- "What does the team handbook say about policies?"
- "What are the revenue projections?"

### Tenant3 (Technical/Project)
- "What is the project timeline?"
- "What are the technical requirements?"
- "How do I use the system?"
- "What are the project milestones?"

---

## 🔍 Understanding RAG Responses

### Response Structure
```json
{
  "query": "What is the company mission?",
  "answer": "AI-generated answer based on documents...",
  "sources": [
    {
      "filename": "company_overview.txt",
      "content": "Relevant text snippet...",
      "score": 0.856
    }
  ],
  "confidence": 0.92,
  "processing_time": 1.234,
  "model_used": "distilgpt2",
  "tokens_used": 150
}
```

### Key Fields
- **answer**: AI-generated response based on your documents
- **sources**: Documents used to generate the answer
- **confidence**: How confident the AI is in the answer (0-1)
- **score**: How relevant each source document is (0-1)

---

## 🚨 Troubleshooting

### Backend Not Responding
```bash
# Check if backend is running
curl http://localhost:8000/api/v1/health/

# Start backend if needed
docker-compose up -d
```

### No Documents Found
```bash
# Check if tenant directories exist
ls -la data/uploads/

# Trigger sync to process documents
curl -X POST "http://localhost:8000/api/v1/sync/trigger" \
  -H "X-API-Key: YOUR_API_KEY"
```

### API Key Issues
```bash
# Verify API keys are correct
cat demo_tenant_keys.json

# Re-setup demo tenants if needed
python scripts/workflow/setup_demo_tenants.py
```

---

## 🎉 Try It Now!

**Quick Start:**
```bash
# 1. Start the demo
python demo_rag_queries.py --workflow

# 2. Ask your own question
python demo_rag_queries.py --query "Your question here"

# 3. Try different tenants
python demo_rag_queries.py --tenant tenant2 --query "What are the financial results?"
```

The RAG system will:
1. 🔄 Process your documents into searchable chunks
2. 🔍 Find the most relevant information for your query  
3. 🤖 Generate an AI answer based on your specific documents
4. 📚 Show you exactly which documents were used as sources

**Multi-tenant isolation means each tenant only sees their own documents!**