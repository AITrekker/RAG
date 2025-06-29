# 🚀 RAG Platform Demo Instructions

## Your Setup: 3 Company Tenants with Documents

You have 3 tenants with company documents already in place:

```
data/uploads/
├── tenant1/    ← Company documents
├── tenant2/    ← Company documents  
└── tenant3/    ← Company documents
```

Each tenant has: `company_mission.txt`, `our_culture.txt`, `vacation_policy.txt`, `working_style.txt`

## 🎯 Quick Demo (2 minutes)

### 1. Start the Platform
```bash
# Start all services (PostgreSQL + Qdrant + Backend)
docker-compose up -d

# Wait ~30 seconds for services to initialize
# Check logs: docker-compose logs backend
```

### 2. Test Your Tenants
```bash
# This will setup API keys and test everything
python scripts/test_existing_tenants.py
```

**What this does:**
- ✅ Creates API keys for tenant1, tenant2, tenant3
- ✅ Discovers your 12 company documents (4 per tenant)
- ✅ Processes documents with ML pipeline
- ✅ Tests RAG queries like "What is our company culture?"
- ✅ Shows you API keys for manual testing

### 3. Manual Testing (Optional)

After step 2, you'll get API keys. Test manually:

```bash
# Example API key from output: tenant_tenant1_a1b2c3d4e5f6...
export API_KEY="your_api_key_here"

# List files
curl -H "X-API-Key: $API_KEY" http://localhost:8000/api/v1/files

# Ask about company culture
curl -X POST http://localhost:8000/api/v1/query/ \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is our company culture?", "max_sources": 3}'

# Search for vacation policy
curl -X POST http://localhost:8000/api/v1/query/search \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "vacation time", "max_results": 5}'
```

## 🎯 Expected Results

### File Discovery
- **12 total files** discovered across 3 tenants
- **Automatic sync** processes documents into chunks
- **Hash-based tracking** detects changes for delta sync

### RAG Queries
When you ask **"What is our company culture?"**, you should get:
- **Structured answer** combining information from multiple documents
- **Source citations** showing which files the answer came from
- **Confidence scores** for each source
- **Processing time** (typically < 1 second)

### Semantic Search
When you search for **"team collaboration"**, you should get:
- **Ranked results** from all relevant documents
- **Similarity scores** showing relevance
- **Content snippets** with highlighted matches

## 🔧 Troubleshooting

### Backend Won't Start
```bash
# Check logs
docker-compose logs backend

# Common issues:
# 1. PostgreSQL not ready -> Wait 30 seconds
# 2. Port conflicts -> Change ports in docker-compose.yml
# 3. Python errors -> Check requirements installation
```

### No ML Models
The platform works **with or without** ML packages:
- **With ML**: Real embeddings, vector search, smart chunking
- **Without ML**: Mock embeddings, database search, structured responses

Install ML packages for best results:
```bash
pip install sentence-transformers qdrant-client torch
```

### No Documents Found
Check file paths:
```bash
ls -la data/uploads/tenant1/
# Should show: company_mission.txt, our_culture.txt, vacation_policy.txt, working_style.txt
```

## 🏢 Demo Scenarios

### Scenario 1: Employee Onboarding
**Query**: *"What should I know about working here?"*
- **Expected**: Information from culture, working style, and mission docs
- **Sources**: Multiple files combined intelligently

### Scenario 2: HR Questions  
**Query**: *"What's our vacation policy?"*
- **Expected**: Specific content from vacation_policy.txt
- **Sources**: Direct citation with confidence scores

### Scenario 3: Company Values
**Query**: *"What are our core values and mission?"*
- **Expected**: Content from company_mission.txt and our_culture.txt
- **Sources**: Multiple documents synthesized into coherent answer

### Scenario 4: Semantic Search
**Search**: *"work from home"*
- **Expected**: Relevant snippets from working_style.txt
- **Results**: Ranked by semantic similarity, not just keyword matching

## 📊 Performance Monitoring

The test script shows:
- **Processing times** for each query (should be < 2 seconds)
- **Source counts** (typically 2-4 relevant documents per query)
- **Confidence scores** (0.5-1.0, higher = more relevant)
- **File sync status** (pending → processing → synced)

## 🚀 Next Steps

After the demo works:

1. **Add Real Documents**: Replace test files with actual company docs
2. **Install ML Models**: Get `sentence-transformers` for better embeddings
3. **Custom Queries**: Test with your actual business questions
4. **Multiple Tenants**: Use different API keys for tenant isolation
5. **Production Setup**: Configure for your infrastructure

## 🆘 Support

If something doesn't work:

1. **Check logs**: `docker-compose logs backend`
2. **Test health**: `curl http://localhost:8000/api/v1/health`
3. **Run diagnostics**: `python scripts/test_services.py`
4. **Check database**: Ensure PostgreSQL is running
5. **Verify files**: Confirm documents exist in `/data/uploads/`

The platform is designed to be **robust and self-healing** - it should work even if some components fail!