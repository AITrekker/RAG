# Scripts Directory

This directory contains essential scripts for developing and running the RAG Platform.

## 📁 **Current Scripts**

### **🔧 Development Setup**

#### **`setup_dev.py`** (18KB)
**Purpose**: Automated development environment setup
- Checks system requirements (Python, Node.js, npm, Docker, Git)
- Creates project directory structure
- Sets up Python virtual environment and dependencies
- Installs frontend dependencies
- Creates environment files
- Runs verification tests
- Provides comprehensive development environment setup

**Usage**:
```bash
python scripts/setup_dev.py
```

### **🚀 Application Runners**

#### **`run_backend.py`** (8.4KB)
**Purpose**: Direct backend execution for development (without Docker)
- Validates Python version and virtual environment
- Checks dependencies and CUDA availability
- Sets up environment variables for PostgreSQL
- Runs FastAPI server with uvicorn
- Supports debug mode and custom host/port

**Usage**:
```bash
python scripts/run_backend.py
```

#### **`run_frontend.ps1`** (9.1KB)
**Purpose**: Frontend development server (PowerShell for Windows)
- Validates Node.js and npm versions
- Checks and installs frontend dependencies
- Sets up environment variables for Vite
- Runs React development server
- Supports custom host/port configuration

**Usage**:
```powershell
.\scripts\run_frontend.ps1
# or with options:
.\scripts\run_frontend.ps1 -Port 4000 -HostAddress "0.0.0.0"
```

### **🗄️ Database**

#### **`init_db.sql`** (2.2KB)
**Purpose**: PostgreSQL database initialization for Docker
- Creates main and test databases
- Sets up extensions (uuid-ossp, pgcrypto)
- Creates tenant_data schema
- Defines enum types for sync and document status
- Grants proper permissions to rag_user
- Sets default privileges for future objects

**Usage**: Automatically executed by Docker Compose during PostgreSQL container startup

## 🗑️ **Removed Scripts**

The following scripts were removed during cleanup as they were obsolete or incompatible:

- ~~`generate_test_docs.py`~~ - Used old directory structure, incompatible with tenant-based storage
- ~~`verify_cuda.py`~~ - Overly specialized for RTX 5070, functionality exists in other scripts
- ~~`test_docker_setup.sh`~~ - Referenced services not in current setup, incompatible with PostgreSQL-focused architecture
- ~~`run_frontend.sh`~~ - Bash version redundant on Windows, PowerShell version preferred

## 🎯 **Quick Start**

1. **First-time setup**: `python scripts/setup_dev.py`
2. **Start backend**: `python scripts/run_backend.py`
3. **Start frontend**: `.\scripts\run_frontend.ps1`
4. **Database setup**: Handled automatically by Docker Compose with `init_db.sql`

## 🔧 **Environment Requirements**

- **Python**: 3.8+
- **Node.js**: 18+
- **npm**: Latest
- **Docker**: For PostgreSQL database
- **PowerShell**: For frontend script (Windows) 