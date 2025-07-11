# Scripts Directory

Operational scripts for the RAG system.

## Quick Start Scripts

```bash
# Set up demo environment with tenant data
python scripts/workflow/setup_demo_tenants.py

# Test complete system functionality  
python scripts/test_system.py

# Run delta sync for file processing
python scripts/delta-sync.py
```

## Key Scripts

### Workflow Management
- **`workflow/setup_demo_tenants.py`** - Create demo tenants and API keys
- **`workflow/test_demo_tenants.py`** - Test demo tenant functionality
- **`workflow/cleanup.py`** - Clean up containers and data

### Testing & Validation
- **`test_system.py`** - Comprehensive system tests
- **`test_query.py`** - Test RAG query functionality
- **`test_sync.py`** - Test file sync operations

### System Operations
- **`delta-sync.py`** - Run delta sync across all tenants
- **`setup_environment_databases.py`** - Initialize databases
- **`inspect-db.py`** - Database inspection utility

## Development Tools
- **`build-backend.ps1`** - PowerShell backend build script
- **`run_frontend.ps1`** - PowerShell frontend development server
- **`config.py`** - Configuration management utilities

See [docs/GUIDE.md](../docs/GUIDE.md) for complete usage documentation.