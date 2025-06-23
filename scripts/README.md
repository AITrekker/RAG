# 🛠️ Scripts Directory

Essential development and setup tools for the RAG platform. This directory contains **12 essential tools** for development, database management, data exploration, and quality assurance.

## 📋 Available Scripts

### 🚀 Development & Deployment
- **`setup_dev.py`** - Complete development environment setup
- **`run_backend.py`** - Start the FastAPI backend server  
- **`run_frontend.ps1`** - Start the React frontend development server

### 🗄️ Database Management
- **`migrate_db.py`** - Run database migrations and updates
- **`direct_setup.py`** - Direct database setup for production
- **`simple_api_key_setup.py`** - Quick API key generation
- **`init_db.sql`** - Initial database schema and data

### 🔍 Data & System Exploration
- **`explore_data.py`** - Explore documents, embeddings, and vector data

### 🧪 Quality Assurance & Development Workflow
- **`health_check.py`** - **NEW**: Comprehensive system health validation
- **`dev_workflow.py`** - **NEW**: Enforces safe development practices

### 📖 Documentation
- **`README.md`** - This documentation file

---

## 🛡️ **Making Development Less Brittle**

### **🔥 Before Making ANY Changes:**
```bash
# Validate system is healthy
python scripts/health_check.py

# OR use safe development mode
python scripts/dev_workflow.py safe
```

### **🧪 Testing Workflow:**
```bash
# 1. Pre-change validation
python scripts/dev_workflow.py pre

# 2. Make your changes

# 3. Post-change validation  
python scripts/dev_workflow.py post
```

### **🔍 When Debugging Issues:**
```bash
# Check what data exists
python scripts/explore_data.py

# Test specific functionality
python scripts/explore_data.py "your test query"

# Validate all systems
python scripts/health_check.py
```

---

## 🚀 **Quick Start Guide**

**For first-time setup:**
```bash
# 1. Set up development environment
python scripts/setup_dev.py

# 2. Run database migrations  
python scripts/migrate_db.py migrate

# 3. Create default tenant and API key
python scripts/direct_setup.py

# 4. Start the backend
python scripts/run_backend.py

# 5. Start the frontend (in new terminal)
.\scripts\run_frontend.ps1
```

## 📁 **Core Scripts (8 Essential Tools)**

### **🔧 Development Setup**

#### **`setup_dev.py`** (18KB)
**Purpose**: Complete automated development environment setup
- Validates system requirements (Python, Node.js, Docker, Git)
- Creates project structure and virtual environment
- Installs all dependencies (Python + frontend)
- Creates environment files (.env)
- Runs comprehensive verification tests

**Usage**: `python scripts/setup_dev.py`

### **🚀 Application Runners**

#### **`run_backend.py`** (8.5KB)
**Purpose**: Start the FastAPI backend server for development
- Validates Python environment and dependencies
- Checks CUDA availability for GPU acceleration
- Sets up PostgreSQL environment variables
- Runs uvicorn server with auto-reload

**Usage**: `python scripts/run_backend.py`

#### **`run_frontend.ps1`** (9.1KB)
**Purpose**: Start the React frontend development server (Windows)
- Validates Node.js and npm versions
- Installs frontend dependencies if needed
- Configures Vite development server
- Supports custom host/port options

**Usage**: `.\scripts\run_frontend.ps1`

### **🗄️ Database Management**

#### **`migrate_db.py`** (7.5KB)
**Purpose**: Comprehensive database migration management
- Runs Alembic migrations with backup support
- Creates database backups before migrations
- Handles migration rollbacks and status checks
- Includes cleanup utilities for old backups

**Usage**: 
```bash
python scripts/migrate_db.py migrate        # Run migrations
python scripts/migrate_db.py backup         # Create backup only
python scripts/migrate_db.py status         # Check migration status
```

#### **`init_db.sql`** (2.2KB)
**Purpose**: PostgreSQL database initialization (Docker)
- Creates main and test databases
- Sets up required extensions (uuid-ossp, pgcrypto)
- Defines enum types and schemas
- Grants proper permissions

**Usage**: Automatically executed by Docker Compose

### **🔑 Tenant & API Key Setup**

#### **`direct_setup.py`** (5.3KB) 
**Purpose**: Complete setup - creates default tenant AND API key
- Creates the default tenant in database
- Generates the default API key (`dev-api-key-123`)
- Best for initial setup from scratch

**Usage**: `python scripts/direct_setup.py`

#### **`simple_api_key_setup.py`** (3.5KB)
**Purpose**: API key only - adds API key to existing tenant
- Creates API key for existing default tenant
- Useful if tenant exists but API key is missing
- Handles duplicate key scenarios gracefully

**Usage**: `python scripts/simple_api_key_setup.py`

## 🧪 **Testing Tools**

All testing tools have been moved to the `/tests` folder for better organization:

- **`tests/quick_api_test.py`** - Live API endpoint testing against running server
- **`tests/test_sync.ps1`** - PowerShell sync functionality testing
- **`tests/test_*.py`** - Complete pytest test suite (94+ tests)

See `tests/README.md` for complete testing documentation.



## 🎯 **Development Workflow**

### **New Development Environment:**
1. **`setup_dev.py`** - Sets up entire environment
2. **`migrate_db.py migrate`** - Initialize database schema
3. **`direct_setup.py`** - Create tenant and API key
4. **`run_backend.py`** + **`run_frontend.ps1`** - Start servers

### **Daily Development:**
- **`run_backend.py`** - Start backend 
- **`run_frontend.ps1`** - Start frontend
- **`migrate_db.py migrate`** - After schema changes

### **Database Issues:**
- **`migrate_db.py status`** - Check current state
- **`migrate_db.py backup`** - Create backup
- **`simple_api_key_setup.py`** - Fix missing API key

## 🔧 **System Requirements**

- **Python**: 3.8+ with pip
- **Node.js**: 18+ with npm
- **Docker**: For PostgreSQL database
- **PowerShell**: For frontend script (Windows)
- **Git**: For version control

## 🗑️ **Recently Cleaned Up**

The following redundant/debugging scripts were removed for clarity:
- ~~`create_api_key.sql`~~ - Replaced by Python scripts
- ~~`direct_sql_insert.sql`~~ - Unsafe database hack
- ~~`debug_db.py`~~ - Temporary debugging tool
- ~~`simple_migrate.py`~~ - Redundant with full migration script
- ~~`manual_setup.py`~~ - Redundant with other setup scripts  
- ~~`validate_layer2.py`~~ - Development validation script 