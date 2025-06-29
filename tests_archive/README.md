# Archived Test Scripts

These test scripts were moved here after the PostgreSQL + Qdrant hybrid architecture refactoring.

## Why These Were Archived

These scripts became outdated after the major refactoring that:
- Added PostgreSQL as the control plane database
- Implemented hybrid PostgreSQL + Qdrant architecture  
- Updated service layer interfaces
- Changed tenant management to UUID-based directories
- Replaced manual sync testing with production delta-sync script

## Archived Scripts

### Old Architecture Tests (Qdrant-only era)
- `test_delta_sync.py` - Old delta sync architecture tests
- `test_sync_with_files.py` - File sync tests with manual tenant creation
- `test_sync_final.py` - Final sync tests with hard-coded tenant slugs
- `test_multi_tenant_sync.py` - Multi-tenant sync simulation tests
- `test_complete_workflow.py` - End-to-end workflow with manual file creation
- `test_embedding_simple.py` - Debug script for embedding generation

### Deprecated API Tests
- `test_api_structure.py` - Tests for non-existent api_rebuild.py
- `test_restful_endpoints.py` - Tests for old endpoint patterns
- `test_service_migration.py` - Import tests for completed migration
- `test_api_simple.py` - API tests with outdated hard-coded keys

## Current Test Scripts (Still Active)

### Root Directory
- `test_api_key.py` - PostgreSQL tenant service API key testing
- `test_tenants.py` - Current async database tenant listing  
- `test_system.py` - Comprehensive system health checks

### Scripts Directory
- `scripts/test_demo_tenants.py` - Modern API testing with current endpoints
- `scripts/test_existing_tenants.py` - Comprehensive API tests for real tenant data
- `scripts/test_ml_pipeline.py` - End-to-end ML pipeline testing

### Production Scripts
- `scripts/delta-sync.py` - Production delta sync execution
- `scripts/rename-tenants.py` - Tenant directory management
- `scripts/sync.bat` / `scripts/run-delta-sync.sh` - Easy sync shortcuts

## Date Archived
June 29, 2025 - After successful implementation of hybrid PostgreSQL + Qdrant architecture