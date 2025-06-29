#!/usr/bin/env python3
"""
Test script for delta sync with actual files
"""

import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from pathlib import Path
from uuid import UUID, uuid4

from src.backend.database import AsyncSessionLocal, init_database
from src.backend.services.tenant_service import TenantService
from src.backend.services.file_service import FileService
from src.backend.services.embedding_service import EmbeddingService
from src.backend.services.sync_service import SyncService
from src.backend.models.database import Tenant


async def create_test_files(tenant_id):
    """Create test files for sync testing"""
    print("📁 Creating test files...")
    
    test_files = [
        ("test_doc1.txt", "This is a test document about artificial intelligence and machine learning."),
        ("test_doc2.txt", "RAG systems combine retrieval and generation for better AI responses."),
        ("test_doc3.txt", "Delta sync ensures only changed files are processed, improving efficiency.")
    ]
    
    tenant_dir = Path(f"data/uploads/{tenant_id}")
    tenant_dir.mkdir(parents=True, exist_ok=True)
    
    for filename, content in test_files:
        file_path = tenant_dir / filename
        file_path.write_text(content)
        print(f"  ✅ Created {file_path}")
    
    return len(test_files)


async def test_sync_with_files():
    """Test sync functionality with actual files"""
    print("🚀 Testing Delta Sync with Files\n")
    
    # Initialize database
    await init_database()
    
    async with AsyncSessionLocal() as session:
        # Get existing tenant1 or create one
        tenant_service = TenantService(session)
        
        # Try to find tenant1
        tenant = None
        try:
            # This would be the actual tenant lookup logic
            print("🔧 Setting up test tenant...")
            tenant = Tenant(
                name="Test Tenant 1",
                slug="tenant1",
                plan_tier="free",
                api_key="test_key_123"
            )
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)
            print(f"✅ Created tenant: {tenant.name} (ID: {tenant.id})")
            
            # Create test files using the tenant ID
            num_files = await create_test_files(tenant.id)
            print(f"📁 Created {num_files} test files")
            
        except Exception as e:
            print(f"❌ Tenant setup failed: {e}")
            return
        
        # Initialize services
        print("\n🔧 Initializing services...")
        file_service = FileService(session)
        embedding_service = EmbeddingService(session)
        await embedding_service.initialize()
        sync_service = SyncService(session, file_service, embedding_service)
        print("✅ Services initialized")
        
        # Test file scanning
        print(f"\n🔧 Scanning files for tenant {tenant.slug}...")
        files = await file_service.scan_tenant_files(tenant.id)
        print(f"✅ Found {len(files)} files:")
        for file_info in files:
            print(f"  📄 {file_info['path']} ({file_info['size']} bytes)")
        
        # Test change detection
        print(f"\n🔧 Detecting changes...")
        sync_plan = await sync_service.detect_file_changes(tenant.id)
        print(f"✅ Changes detected:")
        print(f"  📊 Total: {sync_plan.total_changes}")
        print(f"  ➕ New: {len(sync_plan.new_files)}")
        print(f"  🔄 Updated: {len(sync_plan.updated_files)}")
        print(f"  ➖ Deleted: {len(sync_plan.deleted_files)}")
        
        # Test sync execution
        if sync_plan.total_changes > 0:
            print(f"\n🔧 Executing sync...")
            try:
                sync_operation = await sync_service.execute_sync_plan(sync_plan, None)
                print(f"✅ Sync completed:")
                print(f"  📊 Operation ID: {sync_operation.id}")
                print(f"  🔄 Status: {sync_operation.status}")
                print(f"  📁 Files processed: {sync_operation.files_processed}")
                
                if sync_operation.error_message:
                    print(f"  ⚠️ Error: {sync_operation.error_message}")
                
            except Exception as e:
                print(f"❌ Sync execution failed: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("⏩ No changes to sync")
        
        # Test file listing
        print(f"\n🔧 Listing files in database...")
        db_files = await file_service.list_files(tenant.id)
        print(f"✅ Database contains {len(db_files)} files:")
        for file_record in db_files:
            print(f"  📄 {file_record.filename} - {file_record.sync_status}")


if __name__ == "__main__":
    asyncio.run(test_sync_with_files())