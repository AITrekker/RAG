# 📚 Documentation

Simple, focused documentation for the Enterprise RAG Platform.

## 📖 Documentation Structure

### **📖 [Complete Guide](GUIDE.md)**
The comprehensive guide covering everything you need:
- 🚀 **Quick Start** - Get running in minutes
- 🏗️ **Architecture** - System design and components
- 🔧 **Configuration** - Environment and settings
- 📄 **Document Processing** - File handling and hybrid LlamaIndex
- 🔍 **RAG Pipeline** - Query processing and retrieval
- 🔄 **Sync Operations** - Delta sync and file management
- 🛠️ **API Reference** - All endpoints with examples
- 🧪 **Testing** - Validation and troubleshooting
- 🚨 **Operations** - Deployment and maintenance

### **📋 [Main README](../README.md)**
Project overview, features, and quick start instructions.

## 🔗 Quick Access

### Essential URLs (when running locally)
- **Frontend UI**: [http://localhost:3000](http://localhost:3000)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs) (Interactive Swagger)
- **Health Check**: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

### Key Commands
```bash
# Quick start
docker-compose up -d

# Setup demo tenants and API keys
python scripts/workflow/setup_demo_tenants.py

# Test complete system
python scripts/test_system.py
```

## 🎯 Quick Navigation

**New to the platform?** → Start with [Main README](../README.md), then [Complete Guide](GUIDE.md)

**Need to deploy?** → [Complete Guide - Quick Start section](GUIDE.md#-quick-start)

**API integration?** → [Complete Guide - API Reference section](GUIDE.md#️-api-reference)

**Troubleshooting?** → [Complete Guide - Troubleshooting section](GUIDE.md#-troubleshooting)

---

*Documentation reflects the current PostgreSQL + pgvector unified architecture with hybrid LlamaIndex integration.*