# 📚 Documentation Index

Welcome to the Enterprise RAG Platform documentation. This guide helps you navigate the available documentation.

## 📖 Available Documentation

### **🚀 Getting Started**
- **[Main README](../README.md)** - Complete overview, quick start, and architecture
- **[Operations Guide](OPERATIONS_GUIDE.md)** - Deployment, configuration, and maintenance

### **🏗️ Technical Reference**
- **[Architecture Guide](Architecture.md)** - Detailed system architecture and design
- **[API Reference](API_REFERENCE.md)** - Complete API documentation with examples

### **⚙️ Configuration & Tuning**
- **[RAG Tuning Guide](RAG_TUNING.md)** - Configure and optimize the RAG pipeline

## 📋 Quick Navigation

### For New Users
1. Start with **[Main README](../README.md)** for overview and quick setup
2. Follow **[Operations Guide](OPERATIONS_GUIDE.md)** for detailed deployment
3. Use **[API Reference](API_REFERENCE.md)** for integration

### For Developers
1. Review **[Architecture Guide](Architecture.md)** for system design
2. Reference **[API Documentation](API_REFERENCE.md)** for endpoints
3. Configure with **[RAG Tuning Guide](RAG_TUNING.md)** for optimization

### For Operators
1. Use **[Operations Guide](OPERATIONS_GUIDE.md)** for deployment and maintenance
2. Monitor with health checks from **[API Reference](API_REFERENCE.md)**
3. Optimize performance with **[RAG Tuning Guide](RAG_TUNING.md)**

## 🔗 Quick Links

### Essential URLs (when running locally)
- **Frontend UI**: [http://localhost:3000](http://localhost:3000)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

### Key Commands
```bash
# Quick start
docker-compose up -d

# Setup demo
python scripts/workflow/setup_demo_tenants.py

# Test system
python scripts/test_system.py
```

## 📝 Documentation Standards

All documentation follows these principles:
- **Current**: Reflects the simplified PostgreSQL + pgvector architecture
- **Practical**: Includes working examples and commands
- **Complete**: Covers both basic and advanced use cases
- **Tested**: Examples are verified to work with the current system

## 🤝 Contributing to Documentation

To update or improve documentation:
1. Edit the relevant `.md` file
2. Test any code examples
3. Ensure consistency with current architecture
4. Submit a pull request

---

*Last updated: January 2025 - PostgreSQL + pgvector unified architecture*