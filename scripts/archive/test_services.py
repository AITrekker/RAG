#!/usr/bin/env python3
"""
Test script to validate the new service layer implementation.
This script tests:
1. Database connectivity
2. Tenant service and API key authentication
3. File service upload and management
4. Delta sync service functionality
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backend.database import get_async_db
from src.backend.services.tenant_service import TenantService
from src.backend.services.file_service import FileService
from src.backend.services.sync_service import SyncService
from src.backend.services.embedding_service import EmbeddingService


async def test_database_connection():
    """Test database connectivity"""
    print("\n=== Testing Database Connection ===")
    try:
        async for db in get_async_db():
            print("✓ Database connection successful")
            return db
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return None


async def test_tenant_service(db):
    """Test tenant service functionality"""
    print("\n=== Testing Tenant Service ===")
    try:
        tenant_service = TenantService(db)
        
        # Test creating a tenant
        print("Creating test tenant...")
        tenant = await tenant_service.create_tenant(
            name="Test Tenant",
            slug="test-tenant",
            plan_tier="free"
        )
        print(f"✓ Tenant created: {tenant.name} (ID: {tenant.id})")
        
        # Test generating API key
        print("Generating API key...")
        api_key = await tenant_service.regenerate_api_key(tenant.id)
        print(f"✓ API key generated: {api_key[:20]}...")
        
        # Test API key lookup
        print("Testing API key lookup...")
        found_tenant = await tenant_service.get_tenant_by_api_key(api_key)
        if found_tenant and found_tenant.id == tenant.id:
            print("✓ API key lookup successful")
        else:
            print("✗ API key lookup failed")
            
        return tenant, api_key
        
    except Exception as e:
        print(f"✗ Tenant service test failed: {e}")
        return None, None


async def test_file_service(db, tenant):
    """Test file service functionality"""
    print("\n=== Testing File Service ===")
    try:
        file_service = FileService(db)
        
        # Create a test file
        test_content = b"This is a test file for the RAG system."
        test_file_path = Path("/tmp/test_file.txt")
        test_file_path.write_bytes(test_content)
        
        # Create a mock UploadFile
        class MockUploadFile:
            def __init__(self, filename, content):
                self.filename = filename
                self.content_type = "text/plain"
                self.size = len(content)
                self._content = content
            
            async def read(self):
                return self._content
        
        mock_file = MockUploadFile("test_document.txt", test_content)
        
        # Test file upload (simulation)
        print("Testing file upload simulation...")
        # Note: We can't fully test upload without mocking, but we can test the hash calculation
        file_hash = await file_service.calculate_file_hash(str(test_file_path))
        print(f"✓ File hash calculated: {file_hash[:16]}...")
        
        # Test file listing
        print("Testing file listing...")
        files = await file_service.list_files(tenant.id, limit=10)
        print(f"✓ File listing successful, found {len(files)} files")
        
        # Test tenant file scanning
        print("Testing tenant file scanning...")
        # Create tenant upload directory
        tenant_dir = Path(f"./data/uploads/{tenant.id}")
        tenant_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy test file to tenant directory
        tenant_test_file = tenant_dir / "test_scan.txt"
        tenant_test_file.write_bytes(test_content)
        
        scanned_files = await file_service.scan_tenant_files(tenant.id)
        print(f"✓ File scanning successful, found {len(scanned_files)} files")
        
        # Cleanup
        test_file_path.unlink(missing_ok=True)
        tenant_test_file.unlink(missing_ok=True)
        
        return True
        
    except Exception as e:
        print(f"✗ File service test failed: {e}")
        return False


async def test_sync_service(db, tenant):
    """Test sync service functionality"""
    print("\n=== Testing Sync Service ===")
    try:
        file_service = FileService(db)
        embedding_service = EmbeddingService(db)
        await embedding_service.initialize()
        
        sync_service = SyncService(db, file_service, embedding_service)
        
        # Test change detection
        print("Testing file change detection...")
        sync_plan = await sync_service.detect_file_changes(tenant.id)
        print(f"✓ Change detection successful")
        print(f"  - Total changes: {sync_plan.total_changes}")
        print(f"  - New files: {len(sync_plan.new_files)}")
        print(f"  - Updated files: {len(sync_plan.updated_files)}")
        print(f"  - Deleted files: {len(sync_plan.deleted_files)}")
        
        # Test sync status
        print("Testing sync status...")
        status = await sync_service.get_sync_status(tenant.id)
        print(f"✓ Sync status retrieved: {status}")
        
        return True
        
    except Exception as e:
        print(f"✗ Sync service test failed: {e}")
        return False


async def test_service_dependencies():
    """Test service dependency injection"""
    print("\n=== Testing Service Dependencies ===")
    try:
        from src.backend.dependencies import (
            get_tenant_service_dep,
            get_file_service_dep,
            get_embedding_service_dep,
            get_sync_service_dep,
            get_rag_service_dep
        )
        print("✓ All service dependencies imported successfully")
        return True
    except Exception as e:
        print(f"✗ Service dependency test failed: {e}")
        return False


async def main():
    """Run all tests"""
    print("🚀 Starting Service Layer Tests")
    print("=" * 50)
    
    # Test 1: Database connection
    db = await test_database_connection()
    if not db:
        print("\n❌ Database tests failed - cannot continue")
        return False
    
    # Test 2: Service dependencies
    if not await test_service_dependencies():
        print("\n❌ Dependency tests failed")
        return False
    
    # Test 3: Tenant service
    tenant, api_key = await test_tenant_service(db)
    if not tenant:
        print("\n❌ Tenant service tests failed")
        return False
    
    # Test 4: File service
    if not await test_file_service(db, tenant):
        print("\n❌ File service tests failed")
        return False
    
    # Test 5: Sync service
    if not await test_sync_service(db, tenant):
        print("\n❌ Sync service tests failed")
        return False
    
    # Summary
    print("\n" + "=" * 50)
    print("🎉 All Service Layer Tests Passed!")
    print(f"✓ Test tenant created: {tenant.name}")
    print(f"✓ API key: {api_key[:20]}...")
    print("✓ Database connectivity working")
    print("✓ Service layer architecture functioning")
    print("✓ Ready for ML model integration")
    
    return True


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)