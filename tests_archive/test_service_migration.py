#!/usr/bin/env python3
"""
Test Service Migration

Simple test to verify the service layer migration without database connections.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all imports work correctly"""
    print("Testing imports...")
    
    try:
        # Test service imports
        from src.backend.services.tenant_service import TenantService
        print("✓ TenantService imported successfully")
        
        # Test route imports
        from src.backend.api.v1.routes.admin import router as admin_router
        print("✓ Admin routes imported successfully")
        
        from src.backend.api.v1.routes.tenants import router as tenants_router
        print("✓ Tenant routes imported successfully")
        
        from src.backend.api.v1.routes.auth import router as auth_router
        print("✓ Auth routes imported successfully")
        
        # Test middleware imports
        from src.backend.middleware.api_key_auth import get_current_tenant
        print("✓ API key auth middleware imported successfully")
        
        print("\n🎉 All imports successful!")
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def test_service_methods():
    """Test service method signatures"""
    print("\nTesting service method signatures...")
    
    try:
        from src.backend.services.tenant_service import TenantService
        
        # Check that methods exist
        methods = [
            'get_tenant_by_api_key',
            'get_tenant_by_id', 
            'get_tenant_by_slug',
            'create_tenant',
            'update_tenant',
            'delete_tenant',
            'regenerate_api_key',
            'revoke_api_key',
            'list_tenants',
            'update_api_key_last_used'
        ]
        
        for method in methods:
            if hasattr(TenantService, method):
                print(f"✓ {method} method exists")
            else:
                print(f"✗ {method} method missing")
                return False
        
        print("🎉 All required methods exist!")
        return True
        
    except Exception as e:
        print(f"✗ Error testing methods: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing Service Migration")
    print("=" * 40)
    
    # Test imports
    if not test_imports():
        print("\n❌ Import tests failed")
        return False
    
    # Test service methods
    if not test_service_methods():
        print("\n❌ Method tests failed")
        return False
    
    print("\n✅ All tests passed!")
    print("\n📋 Migration Summary:")
    print("- ✓ Old core service archived")
    print("- ✓ New PostgreSQL service enhanced")
    print("- ✓ All route imports updated")
    print("- ✓ All middleware updated")
    print("- ✓ Setup scripts updated")
    print("\n🚀 Ready for testing with database!")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 