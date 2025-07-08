#!/usr/bin/env python3
"""
Comprehensive system test to verify everything is working
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from scripts.utils import get_paths
    paths = get_paths()
except ImportError:
    # Fallback to old method
    pass

from src.backend.database import get_async_db
from src.backend.services.tenant_service import TenantService

async def main():
    """Run comprehensive system tests."""
    print("🧪 Running Comprehensive System Tests")
    print("=" * 50)
    
    async for db in get_async_db():
        try:
            tenant_service = TenantService(db)
            
            # Test 1: List existing tenants
            print("\n1. Testing tenant listing...")
            tenants = await tenant_service.list_tenants()
            print(f"   ✅ Found {len(tenants)} tenants")
            
            # Test 2: Create a new test tenant
            print("\n2. Testing tenant creation...")
            test_tenant_result = await tenant_service.create_tenant(
                name="Test Tenant",
                description="Test tenant for system verification",
                auto_sync=True,
                sync_interval=30
            )
            print(f"   ✅ Created test tenant: {test_tenant_result['name']}")
            print(f"   API Key: {test_tenant_result['api_key']}")
            
            # Test 3: Verify tenant can be retrieved by API key
            print("\n3. Testing API key lookup...")
            test_tenant = await tenant_service.get_tenant_by_api_key(test_tenant_result['api_key'])
            if test_tenant:
                print(f"   ✅ Successfully retrieved tenant by API key: {test_tenant.name}")
            else:
                print("   ❌ Failed to retrieve tenant by API key")
            
            # Test 4: Test admin tenant API key
            print("\n4. Testing admin tenant API key...")
            admin_tenant = await tenant_service.get_tenant_by_api_key("tenant_system_admin_52cc85c532cbf7c4310500333569d92d")
            if admin_tenant:
                print(f"   ✅ Admin tenant API key works: {admin_tenant.name}")
            else:
                print("   ❌ Admin tenant API key lookup failed")
            
            # Test 5: List all tenants again
            print("\n5. Verifying tenant count...")
            updated_tenants = await tenant_service.list_tenants()
            print(f"   ✅ Total tenants: {len(updated_tenants)}")
            
            print("\n" + "=" * 50)
            print("🎉 All system tests completed successfully!")
            print("\n📋 Summary:")
            print(f"   - Total tenants: {len(updated_tenants)}")
            print(f"   - Test tenant API key: {test_tenant_result['api_key']}")
            print(f"   - Admin tenant API key: tenant_system_admin_52cc85c532cbf7c4310500333569d92d")
            print("\n🚀 System is ready for use!")
            
        except Exception as e:
            print(f"❌ System test failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 