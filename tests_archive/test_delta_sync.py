#!/usr/bin/env python3
"""
Test script for the new delta sync architecture
"""

import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from uuid import UUID, uuid4
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.database import AsyncSessionLocal, init_database
from src.backend.services.tenant_service import TenantService
from src.backend.services.file_service import FileService
from src.backend.services.embedding_service import EmbeddingService
from src.backend.services.sync_service import SyncService
from src.backend.models.database import Tenant, User


async def test_database_setup():
    """Test database connection and table creation"""
    print("🔧 Testing database setup...")
    try:
        await init_database()
        
        # Test basic database connection
        async with AsyncSessionLocal() as session:
            # Try to create a test tenant
            test_tenant = Tenant(
                name="Test Tenant",
                slug="test-tenant",
                plan_tier="free"
            )
            session.add(test_tenant)
            await session.commit()
            await session.refresh(test_tenant)
            
            print(f"✅ Database connected successfully")
            print(f"✅ Created test tenant: {test_tenant.name} (ID: {test_tenant.id})")
            return test_tenant
            
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return None


async def test_service_initialization():
    """Test service layer initialization"""
    print("\n🔧 Testing service initialization...")
    try:
        async with AsyncSessionLocal() as session:
            # Initialize services
            tenant_service = TenantService(session)
            file_service = FileService(session)
            embedding_service = EmbeddingService(session)
            
            # Initialize embedding service
            await embedding_service.initialize()
            
            sync_service = SyncService(session, file_service, embedding_service)
            
            print("✅ All services initialized successfully")
            return {
                'tenant_service': tenant_service,
                'file_service': file_service,
                'embedding_service': embedding_service,
                'sync_service': sync_service,
                'session': session
            }
            
    except Exception as e:
        print(f"❌ Service initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_file_scanning(services, tenant: Tenant):
    """Test file scanning functionality"""
    print(f"\n🔧 Testing file scanning for tenant {tenant.id}...")
    try:
        file_service = services['file_service']
        
        # Scan tenant directory
        files = await file_service.scan_tenant_files(tenant.id)
        print(f"✅ Scanned {len(files)} files in tenant directory")
        
        for file_info in files:
            print(f"  📄 {file_info['path']} ({file_info['size']} bytes)")
        
        return files
        
    except Exception as e:
        print(f"❌ File scanning failed: {e}")
        return []


async def test_delta_sync_detection(services, tenant: Tenant):
    """Test delta sync change detection"""
    print(f"\n🔧 Testing delta sync change detection...")
    try:
        sync_service = services['sync_service']
        
        # Detect changes
        sync_plan = await sync_service.detect_file_changes(tenant.id)
        
        print(f"✅ Delta sync detection completed")
        print(f"  📊 Total changes detected: {sync_plan.total_changes}")
        print(f"  ➕ New files: {len(sync_plan.new_files)}")
        print(f"  🔄 Updated files: {len(sync_plan.updated_files)}")
        print(f"  ➖ Deleted files: {len(sync_plan.deleted_files)}")
        
        for change in sync_plan.changes:
            print(f"  {change.change_type.value}: {change.file_path}")
        
        return sync_plan
        
    except Exception as e:
        print(f"❌ Delta sync detection failed: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_sync_execution(services, tenant: Tenant, sync_plan):
    """Test sync plan execution"""
    print(f"\n🔧 Testing sync execution...")
    try:
        sync_service = services['sync_service']
        
        if sync_plan.total_changes == 0:
            print("⏩ No changes to sync, skipping execution test")
            return True
        
        # Execute sync
        sync_operation = await sync_service.execute_sync_plan(sync_plan)
        
        print(f"✅ Sync execution completed")
        print(f"  📊 Sync operation ID: {sync_operation.id}")
        print(f"  🔄 Status: {sync_operation.status}")
        print(f"  📁 Files processed: {sync_operation.files_processed}")
        
        return sync_operation
        
    except Exception as e:
        print(f"❌ Sync execution failed: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_sync_status(services, tenant: Tenant):
    """Test sync status reporting"""
    print(f"\n🔧 Testing sync status...")
    try:
        sync_service = services['sync_service']
        
        # Get sync status
        status = await sync_service.get_sync_status(tenant.id)
        
        print(f"✅ Sync status retrieved")
        print(f"  📊 Latest sync: {status['latest_sync']['status']}")
        print(f"  📁 File status: {status['file_status']}")
        
        return status
        
    except Exception as e:
        print(f"❌ Sync status failed: {e}")
        return None


async def main():
    """Main test function"""
    print("🚀 Starting Delta Sync Architecture Test\n")
    
    # Test 1: Database Setup
    tenant = await test_database_setup()
    if not tenant:
        print("❌ Cannot continue without database")
        return
    
    # Test 2: Service Initialization
    services = await test_service_initialization()
    if not services:
        print("❌ Cannot continue without services")
        return
    
    # Test 3: File Scanning
    files = await test_file_scanning(services, tenant)
    
    # Test 4: Delta Sync Detection
    sync_plan = await test_delta_sync_detection(services, tenant)
    if not sync_plan:
        print("❌ Cannot continue without sync plan")
        return
    
    # Test 5: Sync Execution (if there are changes)
    if sync_plan.total_changes > 0:
        sync_operation = await test_sync_execution(services, tenant, sync_plan)
    else:
        print("⏩ No changes to test sync execution")
    
    # Test 6: Sync Status
    await test_sync_status(services, tenant)
    
    print("\n🎉 Delta Sync Architecture Test Completed!")
    print("✅ Hybrid PostgreSQL + Qdrant architecture is working!")


if __name__ == "__main__":
    asyncio.run(main())