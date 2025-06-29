# RAG Platform Scripts Directory

**Streamlined scripts for the Enterprise RAG Platform with PostgreSQL + Qdrant hybrid architecture.**

After comprehensive cleanup, this directory contains **20 focused scripts** that provide essential functionality without redundancy.

## 🚀 Quick Start

### Essential Scripts (Run These First)
```bash
# 1. Initialize database and start services
python scripts/startup.py

# 2. Set up demo environment
python scripts/setup_demo_tenants.py

# 3. Test demo functionality
python scripts/test_demo_tenants.py

# 4. Verify admin setup
python scripts/verify_admin_setup.py
```

## 📁 Script Categories

### ⭐ **Core API Scripts (4)**
Essential scripts for API management and tenant operations:

- **`config.py`** - Centralized configuration management
  - Manages API keys, database connections, environment variables
  - Required dependency for all other API scripts

- **`api-demo.py`** - Demo environment management
  - Creates/manages demo environments via admin API
  - Generates demo_tenant_keys.json for authentication

- **`api-tenant.py`** - Tenant CRUD operations  
  - Create, read, update, delete tenant operations
  - Uses current PostgreSQL + API architecture

- **`startup.py`** - Application initialization
  - Database seeding, service health checks
  - Essential for application startup

### 🏗️ **Setup & Demo Scripts (4)**
Scripts for environment setup and demo management:

- **`setup_demo_tenants.py`** - Demo tenant creation
  - Creates demo tenants with sample company documents
  - PostgreSQL-compatible, current architecture

- **`test_demo_tenants.py`** - Demo functionality testing
  - Tests demo tenant functionality via real API endpoints
  - Validates end-to-end demo workflow

- **`verify_admin_setup.py`** - Comprehensive admin verification
  - Database connectivity, API access validation
  - Complete system health check

- **`verify_admin_setup_simple.py`** - Simple admin verification  
  - File-based verification without database dependencies
  - Good fallback verification method

### 🗄️ **Database & Infrastructure (3)**
Database initialization and maintenance:

- **`init_db.sql`** - PostgreSQL schema initialization
  - Complete database schema for hybrid architecture
  - Run this first for new installations

- **`add_api_keys.sql`** - API key migration
  - Adds API key columns to existing tenant tables
  - Migration script for existing databases

- **`delta-sync.py`** - File synchronization
  - Hybrid PostgreSQL + Qdrant file synchronization
  - Core sync functionality for document processing

### 🔧 **Utilities & Debug (6)**
Development and debugging utilities:

- **`debug-tenants.py`** - Tenant debugging
  - Tenant troubleshooting and API key recovery
  - Current service layer integration

- **`rename-tenants.py`** - Directory renaming
  - Cross-platform tenant directory renaming utility
  - Consolidated from multiple platform-specific scripts

- **`test_api_key.py`** - API key testing
  - API key validation and testing utility
  - Moved from root directory

- **`test_system.py`** - System integration testing
  - Comprehensive system integration tests
  - Moved from root directory

- **`test_tenants.py`** - Tenant testing
  - Tenant-specific testing utilities
  - Moved from root directory

- **`api_rebuild.py`** - Minimal API testing server
  - Lightweight FastAPI server for testing
  - Moved from root directory

### 🏗️ **Build & Platform (3)**
Build and platform-specific scripts:

- **`build-backend.ps1`** - Backend build script (PowerShell)
  - Windows PowerShell build automation
  - Platform-specific but maintained

- **`run_frontend.ps1`** - Frontend launcher (PowerShell)  
  - Windows PowerShell frontend startup
  - Platform-specific but useful for Windows development

## 🧹 **Cleanup Summary**

### **Before Cleanup**: 60+ scripts
### **After Cleanup**: 20 focused scripts  
### **Reduction**: 67% fewer scripts

### **Removed Categories**:
- ❌ **14 archived scripts** (outdated architecture)
- ❌ **20+ deprecated scripts** (old Qdrant-only system)
- ❌ **15+ redundant scripts** (duplicate functionality)
- ❌ **5+ broken scripts** (non-functional endpoints)

### **Consolidated**:
- 🔄 **3 rename scripts** → 1 cross-platform script
- 🔄 **Multiple test scripts** → focused testing utilities
- 🔄 **Platform variations** → kept essential platform-specific tools

## 📋 **Usage Examples**

### **Initial Setup**
```bash
# 1. Initialize database schema
psql -U rag_user -d rag_db -f scripts/init_db.sql

# 2. Start application with health checks
python scripts/startup.py

# 3. Create demo environment
python scripts/setup_demo_tenants.py

# 4. Verify everything works
python scripts/test_demo_tenants.py
```

### **Tenant Management**
```bash
# List all tenants
python scripts/api-tenant.py --list

# Create new tenant
python scripts/api-tenant.py --create --name "New Company" --slug "newco"

# Update tenant
python scripts/api-tenant.py --update --id "tenant-uuid" --name "Updated Name"

# Delete tenant
python scripts/api-tenant.py --delete --id "tenant-uuid"
```

### **Demo Management**
```bash
# Setup demo environment
python scripts/api-demo.py --setup

# Reset demo environment  
python scripts/api-demo.py --reset

# Get demo status
python scripts/api-demo.py --status
```

### **Debugging & Maintenance**
```bash
# Debug tenant issues
python scripts/debug-tenants.py --tenant-id "uuid"

# Verify admin setup
python scripts/verify_admin_setup.py

# Test API connectivity
python scripts/test_api_key.py

# Run system integration tests
python scripts/test_system.py
```

### **File Synchronization**
```bash
# Run delta sync for specific tenant
python scripts/delta-sync.py --tenant-id "uuid"

# Full resync
python scripts/delta-sync.py --full-sync

# Monitor sync status
python scripts/delta-sync.py --status
```

## 🔧 **Configuration**

### **Environment Variables**
All scripts use centralized configuration via `config.py`:

```python
# Database connection
DATABASE_URL = "postgresql://rag_user:rag_password@localhost:5432/rag_db"

# API endpoints
API_BASE_URL = "http://localhost:8000"
ADMIN_API_KEY = "your-admin-api-key"

# Qdrant connection
QDRANT_URL = "http://localhost:6333"
```

### **Dependencies**
Scripts require the main application dependencies:
```bash
pip install -r requirements.txt
```

### **Authentication**
Most scripts require admin API key authentication:
- Set `ADMIN_API_KEY` environment variable
- Or configure in `config.py`
- Generate keys via tenant management

## 🎯 **Architecture Alignment**

All remaining scripts are **fully compatible** with the current PostgreSQL + Qdrant hybrid architecture:

✅ **PostgreSQL Integration**: All database operations use PostgreSQL  
✅ **API-First**: Scripts use REST API endpoints, not direct database access  
✅ **Multi-Tenant**: Complete tenant isolation and security  
✅ **Hybrid Vector Store**: Qdrant for vectors, PostgreSQL for metadata  
✅ **Modern Patterns**: Current service interfaces and dependencies  

## 🔒 **Security**

### **API Key Management**
- Admin API keys required for most operations
- Keys stored in environment variables or config
- No hardcoded credentials in scripts

### **Tenant Isolation**
- All operations respect tenant boundaries
- Multi-tenant security enforced
- No cross-tenant data access

### **Safe Operations**
- Scripts use official API endpoints
- No direct database manipulation (except schema initialization)
- Proper error handling and validation

## 🚀 **Development Workflow**

### **New Installation**
1. Run `scripts/init_db.sql` to create schema
2. Run `scripts/startup.py` to initialize services
3. Run `scripts/setup_demo_tenants.py` to create demo data
4. Run `scripts/test_demo_tenants.py` to verify functionality

### **Daily Development**
1. Use `scripts/api-tenant.py` for tenant management
2. Use `scripts/debug-tenants.py` for troubleshooting
3. Use `scripts/delta-sync.py` for file synchronization
4. Use `scripts/verify_admin_setup.py` for health checks

### **Testing & Validation**
1. Use `scripts/test_*.py` for specific component testing
2. Use `scripts/api_rebuild.py` for lightweight API testing
3. Use verification scripts for system health

## 📊 **Script Status**

| Script | Status | Architecture | Purpose |
|--------|--------|--------------|---------|
| `config.py` | ✅ Active | Current | Configuration management |
| `api-demo.py` | ✅ Active | Current | Demo environment |
| `api-tenant.py` | ✅ Active | Current | Tenant operations |
| `startup.py` | ✅ Active | Current | Application initialization |
| `setup_demo_tenants.py` | ✅ Active | Current | Demo setup |
| `test_demo_tenants.py` | ✅ Active | Current | Demo testing |
| `verify_admin_setup.py` | ✅ Active | Current | Admin verification |
| `init_db.sql` | ✅ Active | Current | Database schema |
| `delta-sync.py` | ✅ Active | Current | File synchronization |
| `debug-tenants.py` | ✅ Active | Current | Debugging utility |

All scripts are **production-ready** and aligned with the current PostgreSQL + Qdrant hybrid architecture.

## 🎯 **Next Steps**

The streamlined scripts directory provides all essential functionality for:
- ✅ **Initial setup and configuration**
- ✅ **Tenant and demo management**  
- ✅ **Testing and validation**
- ✅ **Debugging and maintenance**
- ✅ **File synchronization and processing**

**Result**: Clean, focused, and production-ready script collection that supports the full RAG platform lifecycle.