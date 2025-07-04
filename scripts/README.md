# RAG System Scripts

This directory contains operational scripts for the RAG (Retrieval-Augmented Generation) system. All scripts use robust path detection and API validation to prevent brittleness from environment changes and API evolution.

## 🚀 Quick Start

```bash
# Install validation dependencies (recommended)
pip install -r scripts/requirements-validation.txt

# Set up demo environment
python scripts/workflow/setup_demo_tenants.py

# Test the system
python scripts/test_demo_tenants.py

# Validate all scripts
python scripts/validate_all_scripts.py
```

## 📁 Script Categories

### 🚀 **Workflow Scripts** (`workflow/`)
Main operational scripts for system management.

| Script | Purpose | Usage |
|--------|---------|-------|
| `setup_demo_tenants.py` | Create demo tenants and copy sample data | `python scripts/workflow/setup_demo_tenants.py --env test` |
| `cleanup.py` | Clean up containers, databases, files | `python scripts/workflow/cleanup.py --all` |

### 🧪 **Testing Scripts**
Scripts for testing and validation.

| Script | Purpose | Usage |
|--------|---------|-------|
| `test_demo_tenants.py` | Test demo tenant functionality | `python scripts/test_demo_tenants.py` |
| `test_system.py` | Comprehensive system tests | `python scripts/test_system.py` |
| `test_query.py` | Test RAG query functionality | `python scripts/test_query.py` |
| `test_sync.py` | Test file sync operations | `python scripts/test_sync.py` |
| `test_api_key.py` | Test API key functionality | `python scripts/test_api_key.py` |
| `test_hot_reload.py` | Test hot reload capabilities | `python scripts/test_hot_reload.py` |
| `test_tenants.py` | Test tenant operations | `python scripts/test_tenants.py` |

### 🔧 **System Management**
Database and system administration scripts.

| Script | Purpose | Usage |
|--------|---------|-------|
| `delta-sync.py` | Run delta sync for all tenants | `python scripts/delta-sync.py` |
| `setup_environment_databases.py` | Create environment databases | `python scripts/setup_environment_databases.py` |
| `verify_admin_setup.py` | Verify admin tenant setup | `python scripts/verify_admin_setup.py` |
| `verify_admin_setup_simple.py` | Simple admin verification | `python scripts/verify_admin_setup_simple.py` |
| `inspect-db.py` | Database inspection utility | `python scripts/inspect-db.py` |

### 🔍 **Debugging & Analysis**
Diagnostic and debugging utilities.

| Script | Purpose | Usage |
|--------|---------|-------|
| `debug-tenants.py` | Debug tenant configurations | `python scripts/debug-tenants.py` |
| `api_rebuild.py` | Rebuild API components | `python scripts/api_rebuild.py` |
| `config.py` | Configuration management | `python scripts/config.py` |
| `rag_config_manager.py` | RAG configuration manager | `python scripts/rag_config_manager.py` |

### 🛡️ **Security & Validation** (`utils/`, `security/`)
Validation and security tools.

| Script | Purpose | Usage |
|--------|---------|-------|
| `validate_all_scripts.py` | Comprehensive script validation | `python scripts/validate_all_scripts.py` |
| `security/secret_scanner.py` | Scan for exposed secrets | `python scripts/security/secret_scanner.py` |

### 🏗️ **Platform-Specific** 
Platform-specific build and utility scripts.

| Script | Purpose | Usage |
|--------|---------|-------|
| `build-backend.ps1` | Backend build (PowerShell) | `./scripts/build-backend.ps1` |
| `api-demo.py` | Demo API operations | `python scripts/api-demo.py` |
| `api-tenant.py` | Tenant API operations | `python scripts/api-tenant.py` |

## 🔬 Validation System

### **API Validation**
All scripts now include robust API validation to prevent brittleness:

```python
# Example: Using validated API client
from scripts.utils import APIClient

client = APIClient()
response = await client.get("/api/v1/auth/tenants", api_key)
```

### **Contract Testing**
Monitor API changes and detect breaking changes:

```bash
# Save current API as baseline
python scripts/utils/contract_tester.py --save-baseline

# Check for breaking changes
python scripts/utils/contract_tester.py --check-compatibility
```

### **Comprehensive Validation**
Validate all scripts against current API:

```bash
# Full validation suite
python scripts/validate_all_scripts.py

# Save API baseline for future comparisons
python scripts/validate_all_scripts.py --save-baseline

# Test live endpoints
python scripts/validate_all_scripts.py --test-endpoints

# Check API compatibility
python scripts/validate_all_scripts.py --check-compat
```

## 🛠️ Utilities (`utils/`)

### **Path Management**
Robust project root detection eliminates path dependency issues:

```python
from scripts.utils import get_paths

paths = get_paths()
PROJECT_ROOT = paths.root
config_dir = paths.config
uploads_dir = paths.uploads
```

### **API Validation**
Prevent script brittleness from API evolution:

```python
from scripts.utils import APIValidator, validated_api_call

# Validate endpoint exists
validator = APIValidator()
await validator.validate_endpoint_exists("GET", "/api/v1/auth/tenants")

# Decorator for automatic validation
@validated_api_call("GET", "/api/v1/auth/tenants")
async def get_tenants():
    pass
```

### **Contract Testing**
Monitor API compatibility over time:

```python
from scripts.utils import APIContractTester

tester = APIContractTester()
changes = await tester.check_compatibility_with_baseline()
```

### **Validated HTTP Client**
Robust API client with automatic validation:

```python
from scripts.utils import APIClient

# Client with request validation
client = APIClient(validate_requests=True)
response = await client.post("/api/v1/query", api_key, {"query": "test"})

# Automatic fallback on validation failure
response = await client.get("/api/v1/files", api_key)
```

## ⚙️ Environment Setup

### **Dependencies**
```bash
# Core dependencies (included in main requirements.txt)
pip install python-dotenv requests asyncio

# Validation dependencies (optional but recommended)
pip install -r scripts/requirements-validation.txt
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

### **Validation Dependencies**
For enhanced script validation (optional):

```bash
# Install additional validation tools
pip install aiohttp>=3.8.0 jsonschema>=4.0.0
```

## 📋 Common Workflows

### **Initial Setup**
```bash
# 1. Start containers
docker-compose up -d

# 2. Set up demo environment
python scripts/workflow/setup_demo_tenants.py --env development

# 3. Test the system
python scripts/test_demo_tenants.py

# 4. Run delta sync to process files
python scripts/delta-sync.py
```

### **Development Workflow**
```bash
# 1. Validate scripts before changes
python scripts/validate_all_scripts.py --save-baseline

# 2. Make your changes...

# 3. Validate after changes
python scripts/validate_all_scripts.py --check-compat

# 4. Test specific functionality
python scripts/test_query.py
```

### **Production Deployment**
```bash
# 1. Validate all scripts
python scripts/validate_all_scripts.py

# 2. Set up production environment
python scripts/workflow/setup_demo_tenants.py --env production

# 3. Verify system health
python scripts/test_system.py
```

### **Cleanup & Reset**
```bash
# Clean everything (interactive)
python scripts/workflow/cleanup.py

# Clean specific environment
python scripts/workflow/cleanup.py --env test

# Force cleanup without prompts
python scripts/workflow/cleanup.py --all --force
```

## 🎯 Best Practices

### **🛡️ Robust Scripts**
- All scripts use project path detection via `scripts.utils.get_paths()`
- API calls use validation when available, graceful fallback when not
- Error handling with informative messages
- Environment-specific configurations

### **🔍 API Validation**
- Validate endpoints before making requests
- Use validated HTTP client for robust API calls
- Monitor for breaking changes with contract testing
- Save API baselines before making changes

### **🧪 Testing**
- Test scripts against live API endpoints
- Validate script endpoints against OpenAPI schema
- Use demo tenants for safe testing
- Check compatibility before deployment

### **🔧 Error Handling**
Scripts provide helpful error messages:

```bash
❌ Missing database credentials in .env file
   Required: POSTGRES_USER, POSTGRES_PASSWORD
   
💡 Run scripts/workflow/setup_demo_tenants.py first to set up directories

⚠️ Using fallback path detection (validation utilities not available)
```

## 🔧 Troubleshooting

### **Common Issues**

**Script can't find project root:**
```bash
# The path detection should handle this automatically
# If issues persist, check for marker files:
ls docker-compose.yml Makefile CLAUDE.md .git
```

**API validation not working:**
```bash
# Install validation dependencies
pip install aiohttp jsonschema

# Check backend is running
curl http://localhost:8000/api/v1/health/liveness
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

### **Debug Mode**
Most scripts support verbose output for troubleshooting.

## 📁 File Structure

```
scripts/
├── README.md                           # This file
├── requirements-validation.txt         # Validation dependencies
├── validate_all_scripts.py            # Comprehensive validation
│
├── workflow/                           # Main operational scripts
│   ├── setup_demo_tenants.py          # Demo environment setup
│   └── cleanup.py                     # System cleanup
│
├── utils/                              # Utility modules
│   ├── __init__.py                     # Module exports
│   ├── project_paths.py               # Robust path detection
│   ├── api_validator.py               # OpenAPI validation
│   ├── contract_tester.py             # API compatibility testing
│   └── script_validator.py            # Script validation framework
│
├── security/                           # Security tools
│   ├── secret_scanner.py              # Secret detection
│   ├── setup_security.sh              # Security setup
│   └── pre_commit_security.sh         # Pre-commit hooks
│
└── [individual scripts]                # Testing, management, and utility scripts
```

## 🚀 Key Features

### **Robust Path Detection**
- Automatic project root detection using marker files
- No more hardcoded relative paths
- Works from any directory in the project

### **API Validation System** 
- Validates endpoints against OpenAPI schema
- Detects breaking changes between API versions
- Prevents script brittleness from API evolution

### **Graceful Fallbacks**
- Scripts work even without validation dependencies
- Informative error messages when dependencies missing
- Progressive enhancement pattern

### **Environment Safety**
- Environment-specific configurations
- Safe cleanup operations with confirmations
- Multi-environment support (dev, test, staging, prod)

## 💡 Advanced Usage

### **Custom Validation Rules**
```python
from scripts.utils import APIValidator

validator = APIValidator()

# Custom endpoint validation
@validator.custom_rule
def validate_tenant_access(endpoint, api_key):
    # Your custom validation logic
    pass
```

### **Script Health Monitoring**
```bash
# Monitor script health in CI/CD
python scripts/validate_all_scripts.py --check-compat
if [ $? -ne 0 ]; then
    echo "⚠️ Breaking API changes detected"
    exit 1
fi
```

### **API Evolution Tracking**
```bash
# Track API changes over time
python scripts/utils/contract_tester.py --save-current api_v1.2.0.json
python scripts/utils/contract_tester.py --compare api_v1.1.0.json api_v1.2.0.json
```

## 🎯 Migration from Old Scripts

The new validation system provides backward compatibility while adding robustness:

### **Before (Brittle)**
```python
import requests
response = requests.get("http://localhost:8000/api/v1/auth/tenants")
# Fails silently if endpoint changes
```

### **After (Robust)**
```python
from scripts.utils import APIClient
client = APIClient()
response = await client.get("/api/v1/auth/tenants", api_key)
# Validates endpoint exists, provides helpful errors
```

## 📚 Additional Documentation

- **Validation System**: [`../docs/SCRIPT_VALIDATION.md`](../docs/SCRIPT_VALIDATION.md)
- **API Documentation**: http://localhost:8000/docs (FastAPI Swagger)
- **Architecture**: [`../docs/Architecture.md`](../docs/Architecture.md)

---

**Need help?** Check individual script files for detailed usage information and examples. Most scripts include `--help` options and comprehensive error messages.