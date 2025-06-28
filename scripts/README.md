# 🛠️ Scripts Directory

Essential development and setup tools for the RAG platform. This directory contains **12 essential tools** for development, database management, data exploration, and quality assurance.

## 📋 Available Scripts

### 🚀 Development & Deployment
- **`setup_dev.py`** - Complete development environment setup
- **`run_backend.py`** - Start the FastAPI backend server  
- **`run_frontend.ps1`** - Start the React frontend development server

### 🗄️ Database Management
- **`init_qdrant_db.py`** - **NEW**: Initialize Qdrant database with admin tenant
- **`migrate_db.py`** - Run database migrations and updates
- **`direct_setup.py`** - Direct database setup for production
- **`simple_api_key_setup.py`** - Quick API key generation
- **`init_db.sql`** - Initial database schema and data

### 🔍 Data & System Exploration
- **`explore_data.py`** - Explore documents, embeddings, and vector data

### 🏢 Demo Tenant Management
- **`api-demo.py`** - **RECOMMENDED**: Complete demo tenant setup and management
- **`api-tenant.py`** - Individual tenant creation and API key management
- **`db-create-tenant.py`** - Direct database tenant creation

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

# 2. Initialize Qdrant database with admin tenant
python scripts/init_qdrant_db.py

# 3. Run database migrations  
python scripts/migrate_db.py migrate

# 4. Create default tenant and API key
python scripts/direct_setup.py

# 5. Start the backend
python scripts/run_backend.py

# 6. Start the frontend (in new terminal)
.\scripts\run_frontend.ps1
```

## 🪟 **Windows-Specific Frontend Setup**

**If you encounter Rollup native dependency errors on Windows:**
```bash
# The setup scripts now automatically handle this by:
# 1. Trying yarn first (better Windows compatibility)
# 2. Falling back to npm if yarn is not available

# Manual solution if needed:
npm install --global yarn
cd src/frontend
yarn install
yarn dev
```

**Why this happens:**
- Windows-specific npm bug with optional native dependencies (`@rollup/rollup-win32-x64-msvc`)
- Yarn handles optional dependencies differently and doesn't have this issue
- Both `npm run dev` and `yarn dev` work after proper installation

**The setup scripts now automatically:**
- Detect Windows and try yarn first
- Fall back to npm if yarn is not available
- Handle both package managers seamlessly

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

#### **`init_qdrant_db.py`** (NEW - 8.2KB)
**Purpose**: Initialize Qdrant vector database with admin tenant
- Creates system collections (tenants_metadata)
- Creates admin tenant with default API key
- Creates tenant-specific document collections
- Verifies all collections are properly configured
- Provides clear next steps for setup

**Usage**: `python scripts/init_qdrant_db.py`

**Output Example:**
```
🚀 Qdrant Database Initialization
==================================================
Qdrant URL: http://localhost:6333
Embedding Model: sentence-transformers/all-MiniLM-L6-v2
Vector Dimensions: 384

✅ Successfully connected to Qdrant
✅ Created collection: tenants_metadata
✅ Successfully created admin tenant
   Tenant ID: 12345678-1234-1234-1234-123456789abc
   API Key: abc123def456ghi789jkl012mno345pqr678stu901vwx234yz

🎉 QDRANT DATABASE INITIALIZATION COMPLETE
==================================================
Admin Tenant ID: 12345678-1234-1234-1234-123456789abc
Admin Tenant Name: Admin Tenant
Admin API Key: abc123def456ghi789jkl012mno345pqr678stu901vwx234yz

⚠️  IMPORTANT: Save this API key securely!
   You'll need it to access the admin tenant.

Collections Created:
  - tenants_metadata (system)
  - tenant_12345678-1234-1234-1234-123456789abc_documents (admin tenant)

Next Steps:
  1. Use the admin API key in your frontend configuration
  2. Start the backend server: python scripts/run_backend.py
  3. Start the frontend: .\scripts\run_frontend.ps1
  4. Upload documents and start querying!
```

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
2. **`init_qdrant_db.py`** - Initialize Qdrant with admin tenant
3. **`migrate_db.py migrate`** - Initialize database schema
4. **`direct_setup.py`** - Create tenant and API key
5. **`run_backend.py`** + **`run_frontend.ps1`** - Start servers

### **Demo Tenant Setup:**
- **`api-demo.py --setup-default`** - **RECOMMENDED**: Create demo tenants (tenant1, tenant2, tenant3) with API keys
- **`api-demo.py --list`** - List all demo tenants
- **`api-demo.py --cleanup`** - Remove demo environment
- See **[/docs/DEMO_TENANT_SETUP.md](../docs/DEMO_TENANT_SETUP.md)** for complete guide

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

## 🔗 API Usage Notes

- All API endpoints are now versioned under `/api/v1/` (e.g., `/api/v1/health`, `/api/v1/admin/audit/events`).
- Tenant CRUD and clear/reset operations are now admin-only.
- Audit logs are accessible only to admins at `/api/v1/admin/audit/events`.
- For a full list of endpoints, see `docs/API_ENDPOINTS_OVERVIEW.md` or the live `/docs` (Swagger UI). 

# API Scripts for Enterprise RAG Platform

This directory contains Python scripts for interacting with the Enterprise RAG Platform admin API endpoints. All scripts require admin API key authentication.

## Prerequisites

1. **Python 3.7+** with `requests` library installed
2. **Admin API Key** - Update the `ADMIN_API_KEY` variable in each script
3. **Backend running** on `http://localhost:8000`

## Installation

```bash
# Install required dependencies
pip install requests

# Make scripts executable (Linux/Mac)
chmod +x api-*.py
```

## Configuration

Before using any script, update the `ADMIN_API_KEY` variable at the top of each script:

```python
# Configuration - Update this with your admin API key
ADMIN_API_KEY = "YOUR_ADMIN_API_KEY_HERE"
```

## Available Scripts

### 1. `api-tenant.py` - Tenant Management

**Operations:**
- List tenants
- Create tenants
- Get tenant details
- Update tenants
- Delete tenants
- Manage API keys per tenant

**Usage Examples:**
```bash
# List all tenants
python api-tenant.py --list

# List tenants with API keys included
python api-tenant.py --list --include-api-keys

# List only demo tenants
python api-tenant.py --list --demo-only

# Create a new tenant
python api-tenant.py --create --name "New Company" --description "New tenant"

# Get tenant details
python api-tenant.py --get --tenant-id "tenant_123"

# Update tenant
python api-tenant.py --update --tenant-id "tenant_123" --name "Updated Name"

# Delete tenant
python api-tenant.py --delete --tenant-id "tenant_123"

# Create API key for tenant
python api-tenant.py --create-key --tenant-id "tenant_123" --key-name "Production Key"

# List API keys for tenant
python api-tenant.py --list-keys --tenant-id "tenant_123"

# Delete API key
python api-tenant.py --delete-key --tenant-id "tenant_123" --key-id "key_456"
```

### 2. `api-audit.py` - Audit Events

**Operations:**
- List audit events with filtering

**Usage Examples:**
```bash
# List all audit events
python api-audit.py --list

# List audit events for specific tenant
python api-audit.py --list --tenant-id "tenant_123"

# List audit events with pagination
python api-audit.py --list --limit 50 --offset 10
```

### 3. `api-demo.py` - Demo Management

**Operations:**
- Setup demo environment
- List demo tenants
- Cleanup demo environment

**Usage Examples:**
```bash
# Setup demo environment
python api-demo.py --setup --demo-tenants "tenant_1,tenant_2" --duration 24

# Setup demo environment without API keys
python api-demo.py --setup --demo-tenants "tenant_1,tenant_2" --no-api-keys

# List demo tenants
python api-demo.py --list

# Cleanup demo environment
python api-demo.py --cleanup
```

### 4. `api-system.py` - System Monitoring & Maintenance

**Operations:**
- Get system status
- Get system metrics
- Clear statistics and caches
- Trigger maintenance mode

**Usage Examples:**
```bash
# Get system status
python api-system.py --status

# Get system metrics
python api-system.py --metrics

# Clear embedding statistics
python api-system.py --clear-embeddings-stats

# Clear LLM statistics
python api-system.py --clear-llm-stats

# Clear LLM cache
python api-system.py --clear-llm-cache

# Trigger maintenance mode
python api-system.py --maintenance
```

## Common Parameters

### Pagination Parameters
- `--page`: Page number (default: 1)
- `--page-size`: Number of items per page (default: 20)

### Tenant Parameters
- `--tenant-id`: Tenant identifier
- `--name`: Tenant name
- `--description`: Tenant description
- `--auto-sync`: Enable/disable auto sync
- `--sync-interval`: Sync interval in seconds

### API Key Parameters
- `--key-name`: API key name
- `--key-id`: API key identifier

### Demo Parameters
- `--demo-tenants`: Comma-separated list of demo tenant IDs
- `--duration`: Demo duration in hours (default: 24)
- `--generate-api-keys`: Generate API keys for demo tenants
- `--no-api-keys`: Don't generate API keys

## Error Handling

All scripts include comprehensive error handling:

- **API Key Validation**: Scripts check if the API key has been updated
- **Required Parameters**: Scripts validate required parameters are provided
- **HTTP Errors**: Scripts display detailed error messages for API failures
- **JSON Parsing**: Scripts handle malformed JSON responses gracefully

## Output Format

All scripts output JSON responses in a readable format:

```json
{
  "data": {
    "id": "tenant_123",
    "name": "Example Company",
    "description": "Example tenant"
  },
  "message": "Success",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## Troubleshooting

### Common Issues

1. **"Please update ADMIN_API_KEY"**
   - Update the `ADMIN_API_KEY` variable in the script

2. **"Connection refused"**
   - Ensure the backend is running on `http://localhost:8000`

3. **"401 Unauthorized"**
   - Verify the admin API key is correct
   - Ensure the API key has admin privileges

4. **"404 Not Found"**
   - Check that the endpoint exists in the current API version
   - Verify the tenant ID or resource ID is correct

### Debug Mode

To see detailed request/response information, you can modify the `make_request` function in any script to include debug output:

```python
def make_request(method: str, endpoint: str, data: Optional[dict] = None, params: Optional[dict] = None) -> dict:
    url = f"{BASE_URL}{endpoint}"
    headers = {
        "Authorization": f"Bearer {ADMIN_API_KEY}",
        "Content-Type": "application/json"
    }
    
    print(f"DEBUG: {method} {url}")
    print(f"DEBUG: Headers: {headers}")
    if data:
        print(f"DEBUG: Data: {json.dumps(data, indent=2)}")
    if params:
        print(f"DEBUG: Params: {params}")
    
    # ... rest of function
```

## Security Notes

- **Never commit API keys** to version control
- **Use environment variables** for production deployments
- **Rotate API keys** regularly
- **Limit API key permissions** to minimum required access

## Integration Examples

### Batch Operations

```bash
#!/bin/bash
# Create multiple tenants
python api-tenant.py --create --name "Company A" --description "First company"
python api-tenant.py --create --name "Company B" --description "Second company"
python api-tenant.py --create --name "Company C" --description "Third company"

# List all tenants
python api-tenant.py --list --include-api-keys
```

### Automated Setup

```bash
#!/bin/bash
# Setup demo environment
python api-demo.py --setup --demo-tenants "demo1,demo2,demo3" --duration 48

# Wait for setup to complete
sleep 5

# List demo tenants
python api-demo.py --list

# Get system status
python api-system.py --status
```

## Contributing

When adding new scripts or modifying existing ones:

1. Follow the existing code structure
2. Include comprehensive error handling
3. Add proper documentation and usage examples
4. Test with various parameter combinations
5. Update this README with new functionality 