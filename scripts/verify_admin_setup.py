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
import socket
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup environment BEFORE importing backend modules
def setup_database_url():
    """Setup DATABASE_URL for current environment (Docker vs local)"""
    load_dotenv()
    
    # Get credentials from .env
    postgres_user = os.getenv("POSTGRES_USER", "rag_user")
    postgres_password = os.getenv("POSTGRES_PASSWORD", "rag_password")
    postgres_db = "rag_db"  # This is consistent in docker-compose.yml
    
    # Detect environment
    if is_running_in_docker():
        # Use Docker network hostname
        database_url = f"postgresql://{postgres_user}:{postgres_password}@postgres:5432/{postgres_db}"
        print("🐳 Detected Docker environment")
    else:
        # Use localhost for local execution
        database_url = f"postgresql://{postgres_user}:{postgres_password}@localhost:5432/{postgres_db}"
        print("💻 Detected local environment")
    
    # Set the environment variable for database connections
    os.environ["DATABASE_URL"] = database_url
    print(f"📡 Database URL: {database_url}")

def is_running_in_docker() -> bool:
    """Detect if we're running inside a Docker container"""
    try:
        # Check for Docker-specific files/environments
        if os.path.exists("/.dockerenv"):
            return True
        
        # Check if hostname resolves to postgres (Docker network)
        try:
            socket.gethostbyname("postgres")
            return True
        except socket.gaierror:
            return False
            
    except Exception:
        return False

# Setup database URL BEFORE importing backend modules
setup_database_url()

# Now import backend modules with correct DATABASE_URL
from src.backend.database import get_async_db
from src.backend.services.tenant_service import TenantService


class AdminVerifier:
    def __init__(self):
        self.admin_tenant = None
        self.admin_api_key = None
        self.admin_tenant_id = None
        
        # Load environment variables (already loaded in setup_database_url, but ensure they're available)
        load_dotenv()
        self.env_admin_tenant_id = os.getenv("ADMIN_TENANT_ID")
        self.env_admin_api_key = os.getenv("ADMIN_API_KEY")
        
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
        """Check if admin credentials are stored in .env file"""
        print("\n=== Checking .env File ===")
        
        env_file = Path(".env")
        if not env_file.exists():
            print("❌ .env file not found")
            return False
        
        if not self.env_admin_tenant_id or not self.env_admin_api_key:
            print("❌ Admin credentials not found in .env file")
            print("   Run: python scripts/setup_admin.py")
            return False
        
        print(f"✅ Admin tenant ID found in .env:")
        print(f"   - ID: {self.env_admin_tenant_id}")
        print(f"✅ Admin API key found in .env:")
        print(f"   - Key: {self.env_admin_api_key[:20]}...")
        
        # Verify it matches the database if we have database data
        if self.admin_api_key:
            if self.env_admin_api_key == self.admin_api_key:
                print("✅ API key matches database")
            else:
                print("⚠️  API key in .env doesn't match database")
                print("   This might indicate the database was reset without updating .env")
        
        return True
    
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
        """Test admin API access using .env credentials"""
        print("\n=== Testing Admin API Access ===")
        
        api_key = self.env_admin_api_key or self.admin_api_key
        if not api_key:
            print("❌ No admin API key available for testing")
            return False
        
        try:
            import aiohttp
            
            # Test basic admin endpoint
            url = "http://localhost:8000/api/v1/auth/tenants"
            headers = {"X-API-Key": api_key}
            
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
        
        api_key = self.env_admin_api_key or self.admin_api_key
        
        print("🔍 Manual Verification:")
        print("1. Check database directly:")
        print("   psql -d rag_db -c \"SELECT name, slug, api_key, api_key_name FROM tenants WHERE slug = 'admin';\"")
        
        print("\n2. Test API access:")
        if api_key:
            print(f"   curl -H 'X-API-Key: {api_key}' http://localhost:8000/api/v1/auth/tenants")
        
        print("\n3. Check setup status:")
        print("   curl http://localhost:8000/api/v1/setup/status")
        
        print("\n4. List all tenants (admin only):")
        if api_key:
            print(f"   curl -H 'X-API-Key: {api_key}' http://localhost:8000/api/v1/admin/tenants")
        
        print("\n5. Environment status:")
        print("   Check .env file for ADMIN_TENANT_ID and ADMIN_API_KEY")
    
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
        print(f"   ✅ Admin tenant (DB): {'OK' if self.admin_tenant else 'FAILED'}")
        print(f"   ✅ Admin API key (DB): {'OK' if self.admin_api_key else 'FAILED'}")
        print(f"   ✅ .env credentials: {'OK' if env_ok else 'FAILED'}")
        print(f"   ✅ Demo keys: {'OK' if demo_keys_ok else 'FAILED'}")
        print(f"   ✅ API access: {'OK' if api_ok else 'FAILED'}")
        
        # Check if we have credentials from either source
        has_credentials = (self.admin_tenant and self.admin_api_key) or (self.env_admin_tenant_id and self.env_admin_api_key)
        
        if has_credentials and env_ok:
            print("\n🎉 Admin setup is properly configured!")
            if self.env_admin_tenant_id and self.env_admin_api_key:
                print("   Using credentials from .env file (recommended)")
            return True
        else:
            print("\n⚠️  Some issues found. Check the details above.")
            if not self.env_admin_tenant_id or not self.env_admin_api_key:
                print("   Run: python scripts/setup_admin.py")
            return False


async def main():
    """Main entry point"""
    verifier = AdminVerifier()
    success = await verifier.run_verification()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main()) 