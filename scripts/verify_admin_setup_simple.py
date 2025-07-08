#!/usr/bin/env python3
"""
Simple Admin Tenant Verification Script

This script helps verify that the admin tenant is properly created and configured
by checking files and API endpoints without requiring database access.

Usage:
    python scripts/verify_admin_setup_simple.py
"""

import json
import os
import sys
import requests
from pathlib import Path
from typing import Dict, Any, Optional


class SimpleAdminVerifier:
    def __init__(self):
        self.admin_api_key = None
        self.base_url = "http://localhost:8000"
        
    def check_env_file(self) -> bool:
        """Check if admin API key is stored in .env file"""
        print("\n=== Checking .env File ===")
        
        env_file = Path(".env")
        if not env_file.exists():
            print("❌ .env file not found")
            print("   Expected location: .env")
            return False
        
        try:
            with open(env_file, 'r') as f:
                content = f.read()
            
            if "ADMIN_API_KEY=" in content:
                # Extract the API key
                for line in content.split('\n'):
                    if line.startswith("ADMIN_API_KEY="):
                        stored_key = line.split('=', 1)[1].strip()
                        self.admin_api_key = stored_key
                        print(f"✅ Admin API key found in .env:")
                        print(f"   - Key: {stored_key[:20]}...")
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
            print("   Expected location: demo_tenant_keys.json")
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
    
    def test_api_endpoint(self, endpoint: str, api_key: str = None) -> Dict[str, Any]:
        """Test an API endpoint"""
        url = f"{self.base_url}{endpoint}"
        headers = {"Content-Type": "application/json"}
        
        if api_key:
            headers["X-API-Key"] = api_key
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            return {
                "status": response.status_code,
                "data": response.json() if response.status_code == 200 else None,
                "error": response.text if response.status_code != 200 else None
            }
        except requests.exceptions.ConnectionError:
            return {"status": "error", "error": "Connection failed - is the server running?"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def test_setup_status(self) -> bool:
        """Test setup status endpoint"""
        print("\n=== Testing Setup Status ===")
        
        result = self.test_api_endpoint("/api/v1/setup/status")
        
        if result["status"] == 200:
            data = result["data"]
            print(f"✅ Setup status endpoint working:")
            print(f"   - Initialized: {data.get('initialized', 'Unknown')}")
            print(f"   - Admin tenant exists: {data.get('admin_tenant_exists', 'Unknown')}")
            print(f"   - Total tenants: {data.get('total_tenants', 'Unknown')}")
            print(f"   - Message: {data.get('message', 'No message')}")
            return True
        else:
            print(f"❌ Setup status failed: {result['error']}")
            return False
    
    def test_admin_api_access(self) -> bool:
        """Test admin API access"""
        print("\n=== Testing Admin API Access ===")
        
        if not self.admin_api_key:
            print("❌ No admin API key available for testing")
            return False
        
        # Test admin tenant list endpoint
        result = self.test_api_endpoint("/api/v1/auth/tenants", self.admin_api_key)
        
        if result["status"] == 200:
            data = result["data"]
            print(f"✅ Admin API access working!")
            print(f"   - Found {len(data)} tenants")
            for tenant in data:
                print(f"     * {tenant.get('name', 'Unknown')} ({tenant.get('slug', 'Unknown')})")
            return True
        else:
            print(f"❌ Admin API access failed: {result['error']}")
            return False
    
    def test_health_endpoint(self) -> bool:
        """Test health endpoint"""
        print("\n=== Testing Health Endpoint ===")
        
        result = self.test_api_endpoint("/api/v1/health")
        
        if result["status"] == 200:
            data = result["data"]
            print(f"✅ Health endpoint working:")
            print(f"   - Status: {data.get('status', 'Unknown')}")
            print(f"   - Version: {data.get('version', 'Unknown')}")
            return True
        else:
            print(f"❌ Health endpoint failed: {result['error']}")
            return False
    
    def show_storage_information(self):
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
        
        print("\n5. Check health:")
        print("   curl http://localhost:8000/api/v1/health")
    
    def show_admin_creation_process(self):
        """Show how admin tenant is created"""
        print("\n=== Admin Tenant Creation Process ===")
        
        print("🔄 Creation Methods:")
        print("1. Setup Script (Recommended):")
        print("   python scripts/setup_demo_tenants.py")
        print("   - Creates admin tenant with slug 'admin'")
        print("   - Generates API key automatically")
        print("   - Saves admin key to .env file")
        print("   - Creates demo tenants")
        
        print("\n2. API Endpoint:")
        print("   POST /api/v1/setup/initialize")
        print("   - Creates admin tenant")
        print("   - Returns admin API key")
        print("   - Can write to .env file")
        
        print("\n3. Manual Database:")
        print("   - Insert into tenants table")
        print("   - Generate API key manually")
        print("   - Update .env file")
    
    def run_verification(self) -> bool:
        """Run complete verification"""
        print("🔍 Simple Admin Tenant Verification")
        print("=" * 50)
        
        # Check file storage
        env_ok = self.check_env_file()
        demo_keys_ok = self.check_demo_keys_file()
        
        # Test API endpoints
        health_ok = self.test_health_endpoint()
        setup_ok = self.test_setup_status()
        api_ok = self.test_admin_api_access() if self.admin_api_key else False
        
        # Show information
        self.show_storage_information()
        self.show_admin_creation_process()
        self.show_verification_commands()
        
        # Summary
        print("\n" + "=" * 50)
        print("📋 Verification Summary:")
        print(f"   ✅ .env file: {'OK' if env_ok else 'FAILED'}")
        print(f"   ✅ Demo keys: {'OK' if demo_keys_ok else 'FAILED'}")
        print(f"   ✅ Health endpoint: {'OK' if health_ok else 'FAILED'}")
        print(f"   ✅ Setup status: {'OK' if setup_ok else 'FAILED'}")
        print(f"   ✅ Admin API access: {'OK' if api_ok else 'FAILED'}")
        
        if env_ok and health_ok:
            print("\n🎉 Basic admin setup appears to be working!")
            if api_ok:
                print("✅ Admin API access is fully functional!")
            else:
                print("⚠️  Admin API access needs verification")
            return True
        else:
            print("\n⚠️  Some issues found. Check the details above.")
            if not env_ok:
                print("💡 Try running: python scripts/setup_demo_tenants.py")
            if not health_ok:
                print("💡 Make sure the server is running on http://localhost:8000")
            return False


def main():
    """Main entry point"""
    verifier = SimpleAdminVerifier()
    success = verifier.run_verification()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main() 