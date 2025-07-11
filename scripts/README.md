# RAG System Scripts

This directory contains operational scripts for the RAG (Retrieval-Augmented Generation) system, streamlined for the simplified PostgreSQL + pgvector architecture.

## 🚀 Quick Start

```bash
# Set up demo environment
python scripts/workflow/setup_demo_tenants.py

# Test the system
python scripts/test_system.py

# Run delta sync
python scripts/delta-sync.py
```

## 📁 Script Categories

### 🚀 **Workflow Scripts** (`workflow/`)
Main operational scripts for system management.

| Script | Purpose | Usage |
|--------|---------|-------|
| `setup_demo_tenants.py` | Create demo tenants and sample data | `python scripts/workflow/setup_demo_tenants.py` |
| `test_demo_tenants.py` | Test demo tenant functionality | `python scripts/workflow/test_demo_tenants.py` |
| `cleanup.py` | Clean up containers, databases, files | `python scripts/workflow/cleanup.py --all` |

### 🧪 **Testing Scripts**
Scripts for testing and validation.

| Script | Purpose | Usage |
|--------|---------|-------|
| `test_system.py` | Comprehensive system tests | `python scripts/test_system.py` |
| `test_query.py` | Test RAG query functionality | `python scripts/test_query.py` |
| `test_sync.py` | Test file sync operations | `python scripts/test_sync.py` |

### 🔧 **System Management**
Database and system administration scripts.

| Script | Purpose | Usage |
|--------|---------|-------|
| `delta-sync.py` | Run delta sync for all tenants | `python scripts/delta-sync.py` |
| `setup_environment_databases.py` | Initialize databases | `python scripts/setup_environment_databases.py` |
| `inspect-db.py` | Database inspection utility | `python scripts/inspect-db.py` |

### 🔍 **Configuration & Utilities**
Configuration and utility scripts.

| Script | Purpose | Usage |
|--------|---------|-------|
| `config.py` | Configuration management | `python scripts/config.py` |
| `rag_config_manager.py` | RAG configuration manager | `python scripts/rag_config_manager.py` |

### 🏗️ **Platform-Specific** 
Platform-specific build and utility scripts.

| Script | Purpose | Usage |
|--------|---------|-------|
| `build-backend.ps1` | Backend build (PowerShell) | `.\scripts\build-backend.ps1` |
| `run_frontend.ps1` | Frontend dev server (PowerShell) | `.\scripts\run_frontend.ps1` |

## 🛠️ Utilities (`utils/`)

### **Path Management**
Robust project root detection:

```python
from scripts.utils import get_paths

paths = get_paths()
PROJECT_ROOT = paths.root
config_dir = paths.config
uploads_dir = paths.uploads
```

## ⚙️ Environment Setup

### **Dependencies**
```bash
# Core dependencies (included in main requirements.txt)
pip install python-dotenv requests asyncio
```

### **Environment Variables**
Scripts automatically load from `.env` file:

```bash
# Database credentials
POSTGRES_USER=rag_user
POSTGRES_PASSWORD=your_password

# Admin credentials (auto-generated)
ADMIN_TENANT_ID=auto-generated-uuid
ADMIN_API_KEY=auto-generated-key

# Backend URL (optional)
BACKEND_URL=http://localhost:8000
```

## 📋 Common Workflows

### **Initial Setup**
```bash
# 1. Start containers
docker-compose up -d

# 2. Set up demo environment
python scripts/workflow/setup_demo_tenants.py

# 3. Test the system
python scripts/test_system.py

# 4. Run delta sync to process files
python scripts/delta-sync.py
```

### **Development Workflow**
```bash
# 1. Test specific functionality
python scripts/test_query.py

# 2. Run sync operations
python scripts/test_sync.py

# 3. Check database state
python scripts/inspect-db.py
```

### **Cleanup & Reset**
```bash
# Clean everything (interactive)
python scripts/workflow/cleanup.py

# Force cleanup without prompts
python scripts/workflow/cleanup.py --all --force
```

## 🎯 Best Practices

### **🛡️ Robust Scripts**
- All scripts use project path detection via `scripts.utils.get_paths()`
- Error handling with informative messages
- Environment-specific configurations

### **🧪 Testing**
- Test scripts against live API endpoints
- Use demo tenants for safe testing
- Comprehensive system validation

### **🔧 Error Handling**
Scripts provide helpful error messages:

```bash
❌ Missing database credentials in .env file
   Required: POSTGRES_USER, POSTGRES_PASSWORD
   
💡 Run scripts/workflow/setup_demo_tenants.py first to set up directories
```

## 🔧 Troubleshooting

### **Common Issues**

**Script can't find project root:**
```bash
# The path detection should handle this automatically
# If issues persist, check for marker files:
ls docker-compose.yml CLAUDE.md .git
```

**Missing API keys:**
```bash
# Generate demo tenant keys
python scripts/workflow/setup_demo_tenants.py

# Check admin keys in .env
grep ADMIN_API_KEY .env
```

**Database connection issues:**
```bash
# Start containers
docker-compose up -d

# Check container status
docker ps

# Initialize databases
python scripts/setup_environment_databases.py
```

## 📁 Current File Structure

```
scripts/
├── README.md                           # This file
│
├── workflow/                           # Main operational scripts
│   ├── setup_demo_tenants.py          # Demo environment setup
│   ├── test_demo_tenants.py           # Demo testing
│   └── cleanup.py                     # System cleanup
│
├── utils/                              # Utility modules
│   ├── __init__.py                     # Module exports
│   └── project_paths.py               # Robust path detection
│
├── test_system.py                      # System testing
├── test_query.py                       # Query testing
├── test_sync.py                        # Sync testing
├── delta-sync.py                       # Delta sync execution
├── setup_environment_databases.py     # Database setup
├── inspect-db.py                       # Database inspection
├── config.py                           # Configuration management
├── rag_config_manager.py              # RAG configuration
├── build-backend.ps1                  # Backend build (PowerShell)
└── run_frontend.ps1                   # Frontend dev (PowerShell)
```

## 🚀 Key Features

### **Simplified Architecture**
- Focused on PostgreSQL + pgvector architecture
- Streamlined operations and testing
- Removed complex validation overhead

### **Robust Path Detection**
- Automatic project root detection using marker files
- No hardcoded relative paths
- Works from any directory in the project

### **Environment Safety**
- Environment-specific configurations
- Safe cleanup operations with confirmations
- Clear error messages and help

## 📚 Additional Documentation

- **API Documentation**: http://localhost:8000/docs (FastAPI Swagger)
- **Architecture**: [`../docs/Architecture.md`](../docs/Architecture.md)
- **Operations Guide**: [`../docs/OPERATIONS_GUIDE.md`](../docs/OPERATIONS_GUIDE.md)

---

**Need help?** Check individual script files for detailed usage information and examples. Most scripts include `--help` options and comprehensive error messages.