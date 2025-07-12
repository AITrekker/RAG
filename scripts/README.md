# Scripts Directory

Operational scripts for the simplified RAG system.

## Quick Start Scripts

```bash
# Set up demo environment with tenant data
python scripts/workflow/demo_workflow.py

# Run delta sync with new simplified architecture
python scripts/simplified_delta_sync.py

# Get current processing statistics
python scripts/simplified_delta_sync.py --stats
```

## Key Scripts

### Workflow Management
- **`workflow/demo_workflow.py`** - Complete demo setup and testing workflow
- **`workflow/cleanup.py`** - Clean up containers and data

### System Operations
- **`simplified_delta_sync.py`** - **NEW**: Delta sync using simplified architecture
- **`delta-sync.py`** - Legacy delta sync (still functional)
- **`setup_environment_databases.py`** - Initialize databases
- **`inspect-db.py`** - Database inspection utility

### Testing & Validation
- **`test_system.py`** - Comprehensive system tests
- **`test_query.py`** - Test RAG query functionality
- **`test_sync.py`** - Test file sync operations

### Development Tools
- **`build-backend.ps1`** - PowerShell backend build script
- **`run_frontend.ps1`** - PowerShell frontend development server
- **`config.py`** - Configuration management utilities

## Removed Scripts (Obsolete)
- ~~`debug_vector_performance.py`~~ - Removed (fixed in new architecture)
- ~~`test_embedding_quality.py`~~ - Removed (use pytest instead)
- ~~`verify_embeddings.py`~~ - Consider removing if redundant

## Migration Notes
The new simplified architecture uses:
- `MultiTenantRAGService` - Single RAG service with LlamaIndex
- `UnifiedDocumentProcessor` - LlamaIndex handles all file types
- `SimplifiedEmbeddingService` - Simplified tracking

Use `simplified_delta_sync.py` for new deployments.

See [docs/GUIDE.md](../docs/GUIDE.md) for complete usage documentation.