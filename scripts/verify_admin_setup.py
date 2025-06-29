#!/usr/bin/env python3
"""
Admin Tenant Verification Script

This script helps verify that the admin tenant is properly created and configured,
and shows where the API key is stored.

Usage:
    python scripts/verify_admin_setup.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backend.database import get_async_db
from src.backend.services.tenant_service import TenantService


class AdminVerifier:
    def __init__(self):
        self.admin_tenant = None
        self.admin_api_key = None
        
    async def verify_admin_tenant(self) -> bool:
        """Verify admin tenant exists and is properly configured"""
        print("\n=== Verifying Admin Tenant ===")
        
        try:
            async for db in get_async_db():
                tenant_service = TenantService(db)
                
                # Check if admin tenant exists
                admin_tenant = await tenant_service.get_tenant_by_slug("admin")
                
                if not admin_tenant:
                    print("❌ Admin tenant not found!")
                    print("   Run: python scripts/setup_demo_tenants.py")
                    return False
                
                self.admin_tenant = admin_tenant
                print(f"✅ Admin tenant found:")
                print(f"   - ID: {admin_tenant.id}")
                print(f"   - Name: {admin_tenant.name}")
                print(f"   - Slug: {admin_tenant.slug}")
                print(f"   - Plan: {admin_tenant.plan_tier}")
                print(f"   - Created: {admin_tenant.created_at}")
                
                # Check API key
                if admin_tenant.api_key:
                    self.admin_api_key = admin_tenant.api_key
                    print(f"✅ Admin API key configured:")
                    print(f"   - Key: {admin_tenant.api_key[:20]}...")
                    print(f"   - Name: {admin_tenant.api_key_name}")
                    print(f"   - Last Used: {admin_tenant.api_key_last_used}")
                    print(f"   - Expires: {admin_tenant.api_key_expires_at}")
                else:
                    print("⚠️  Admin API key not configured!")
                    print("   Run: python scripts/setup_demo_tenants.py")
                    return False
                
                break  # Only need first session
                
        except Exception as e:
            print(f"❌ Error verifying admin tenant: {e}")
            return False
        
        return True
    
    def check_env_file(self) -> bool:
        """Check if admin API key is stored in .env file"""
        print("\n=== Checking .env File ===")
        
        env_file = Path(".env")
        if not env_file.exists():
            print("❌ .env file not found")
            return False
        
        try:
            with open(env_file, 'r') as f:
                content = f.read()
            
            if "ADMIN_API_KEY=" in content:
                # Extract the API key
                for line in content.split('\n'):
                    if line.startswith("ADMIN_API_KEY="):
                        stored_key = line.split('=', 1)[1].strip()
                        print(f"✅ Admin API key found in .env:")
                        print(f"   - Key: {stored_key[:20]}...")
                        
                        # Verify it matches the database
                        if self.admin_api_key and stored_key == self.admin_api_key:
                            print("✅ API key matches database")
                        else:
                            print("⚠️  API key in .env doesn't match database")
                        
                        return True
                
                print("❌ ADMIN_API_KEY not found in .env file")
                return False
                
        except Exception as e:
            print(f"❌ Error reading .env file: {e}")
            return False
    
    def check_demo_keys_file(self) -> bool:
        """Check if demo tenant keys are stored"""
        print("\n=== Checking Demo Keys File ===")
        
        keys_file = Path("demo_tenant_keys.json")
        if not keys_file.exists():
            print("❌ demo_tenant_keys.json not found")
            return False
        
        try:
            with open(keys_file, 'r') as f:
                keys_data = json.load(f)
            
            print(f"✅ Demo keys file found with {len(keys_data)} tenants:")
            for tenant_name, tenant_info in keys_data.items():
                api_key = tenant_info.get('api_key', '')
                slug = tenant_info.get('slug', '')
                print(f"   - {tenant_name} ({slug}): {api_key[:20]}...")
            
            return True
            
        except Exception as e:
            print(f"❌ Error reading demo keys file: {e}")
            return False
    
    async def test_admin_api_access(self) -> bool:
        """Test admin API access"""
        print("\n=== Testing Admin API Access ===")
        
        if not self.admin_api_key:
            print("❌ No admin API key available for testing")
            return False
        
        try:
            import aiohttp
            
            # Test basic admin endpoint
            url = "http://localhost:8000/api/v1/auth/tenants"
            headers = {"X-API-Key": self.admin_api_key}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ Admin API access working!")
                        print(f"   - Found {len(data)} tenants")
                        return True
                    else:
                        print(f"❌ Admin API access failed: {response.status}")
                        return False
                        
        except ImportError:
            print("⚠️  aiohttp not available, skipping API test")
            return False
        except Exception as e:
            print(f"❌ API test error: {e}")
            return False
    
    def show_database_storage_info(self):
        """Show information about where API keys are stored"""
        print("\n=== API Key Storage Information ===")
        
        print("📊 Database Storage:")
        print("   - Table: tenants")
        print("   - Columns:")
        print("     * api_key (VARCHAR(64)) - The actual API key")
        print("     * api_key_name (VARCHAR(100)) - Key name/description")
        print("     * api_key_expires_at (TIMESTAMP) - Expiration date")
        print("     * api_key_last_used (TIMESTAMP) - Last usage timestamp")
        
        print("\n📁 File Storage:")
        print("   - .env file: Contains ADMIN_API_KEY for admin tenant")
        print("   - demo_tenant_keys.json: Contains demo tenant API keys")
        
        print("\n🔐 Security Notes:")
        print("   - API keys are stored in plain text in the database")
        print("   - Consider hashing API keys for production use")
        print("   - .env file should be in .gitignore")
        print("   - demo_tenant_keys.json should not be committed to version control")
    
    def show_verification_commands(self):
        """Show commands to verify the setup"""
        print("\n=== Verification Commands ===")
        
        print("🔍 Manual Verification:")
        print("1. Check database directly:")
        print("   psql -d your_database -c \"SELECT name, slug, api_key, api_key_name FROM tenants WHERE slug = 'admin';\"")
        
        print("\n2. Test API access:")
        if self.admin_api_key:
            print(f"   curl -H 'X-API-Key: {self.admin_api_key}' http://localhost:8000/api/v1/auth/tenants")
        
        print("\n3. Check setup status:")
        print("   curl http://localhost:8000/api/v1/setup/status")
        
        print("\n4. List all tenants (admin only):")
        if self.admin_api_key:
            print(f"   curl -H 'X-API-Key: {self.admin_api_key}' http://localhost:8000/api/v1/admin/tenants")
    
    async def run_verification(self) -> bool:
        """Run complete verification"""
        print("🔍 Admin Tenant Verification")
        print("=" * 50)
        
        # Verify admin tenant
        if not await self.verify_admin_tenant():
            return False
        
        # Check file storage
        env_ok = self.check_env_file()
        demo_keys_ok = self.check_demo_keys_file()
        
        # Test API access
        api_ok = await self.test_admin_api_access()
        
        # Show storage information
        self.show_database_storage_info()
        
        # Show verification commands
        self.show_verification_commands()
        
        # Summary
        print("\n" + "=" * 50)
        print("📋 Verification Summary:")
        print(f"   ✅ Admin tenant: {'OK' if self.admin_tenant else 'FAILED'}")
        print(f"   ✅ API key: {'OK' if self.admin_api_key else 'FAILED'}")
        print(f"   ✅ .env file: {'OK' if env_ok else 'FAILED'}")
        print(f"   ✅ Demo keys: {'OK' if demo_keys_ok else 'FAILED'}")
        print(f"   ✅ API access: {'OK' if api_ok else 'FAILED'}")
        
        if self.admin_tenant and self.admin_api_key and env_ok:
            print("\n🎉 Admin setup is properly configured!")
            return True
        else:
            print("\n⚠️  Some issues found. Check the details above.")
            return False


async def main():
    """Main entry point"""
    verifier = AdminVerifier()
    success = await verifier.run_verification()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main()) 