#!/usr/bin/env python3
"""
Demo Tenants Setup Script

Creates 3 demo tenants based on your existing data structure:
- tenant1, tenant2, tenant3 with company documents
- Saves API keys to demo_tenant_keys.json for reuse
- Uses existing admin credentials from .env file

This script works with the new PostgreSQL + service architecture.

Usage:
    python scripts/setup_demo_tenants.py

Prerequisites:
    - Run 'docker-compose up -d' to start the system
    - Init container should have created admin tenant automatically
"""

import asyncio
import json
import os
import socket
import sys
from pathlib import Path
from typing import Dict, Any
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


class DemoTenantSetup:
    def __init__(self):
        self.tenant_configs = [
            {
                "name": "tenant1", 
                "description": "Demo tenant 1 with company documents"
            },
            {
                "name": "tenant2", 
                "description": "Demo tenant 2 with company documents"
            },
            {
                "name": "tenant3",
                "description": "Demo tenant 3 with company documents"
            }
        ]
        self.api_keys = {}
        self.admin_tenant_id = None
        self.admin_api_key = None
        
        # Load environment variables
        load_dotenv()
        self.admin_tenant_id = os.getenv("ADMIN_TENANT_ID")
        self.admin_api_key = os.getenv("ADMIN_API_KEY")
        
    def check_admin_credentials(self) -> bool:
        """Check if admin credentials are available in .env"""
        print("\n=== Checking Admin Credentials ===")
        
        if not self.admin_tenant_id or not self.admin_api_key:
            print("❌ Admin credentials not found in .env file")
            print("   The init container should have created them automatically.")
            print("   Please ensure you've run: docker-compose up -d")
            print("   Or verify setup with: python scripts/verify_admin_setup.py")
            return False
        
        print(f"✅ Admin tenant ID: {self.admin_tenant_id}")
        print(f"✅ Admin API key: {self.admin_api_key[:20]}...")
        return True
    
    async def setup_demo_tenants(self, tenant_service: TenantService) -> Dict[str, str]:
        """Setup demo tenants and return API keys"""
        print("\n=== Setting Up Demo Tenants ===")
        
        api_keys = {}
        
        for config in self.tenant_configs:
            print(f"\n--- Setting up {config['name']} ---")
            
            # Check if tenant exists
            tenant = await tenant_service.get_tenant_by_slug(config["slug"])
            
            if not tenant:
                # Create tenant
                tenant_result = await tenant_service.create_tenant(
                    name=config["name"],
                    description=config["description"],
                    auto_sync=True,
                    sync_interval=60
                )
                tenant = await tenant_service.get_tenant_by_slug(config["slug"])
                print(f"✓ Created tenant: {tenant_result['name']}")
            else:
                print(f"✓ Found existing tenant: {tenant.name}")
            
            # Generate API key
            api_key = await tenant_service.regenerate_api_key(tenant.id)
            api_keys[config["slug"]] = api_key
            
            print(f"  - Tenant ID: {tenant.id}")
            print(f"  - API Key: {api_key[:20]}...")
            
            # Check for data directory
            data_dir = Path(f"./data/uploads/{config['slug']}")
            if data_dir.exists():
                files = list(data_dir.glob("*.txt"))
                print(f"  - Data files: {len(files)} files found")
                for file in files:
                    print(f"    * {file.name}")
            else:
                print(f"  - ⚠️ Data directory not found: {data_dir}")
        
        return api_keys
    
    def save_api_keys(self, api_keys: Dict[str, str]) -> None:
        """Save API keys to JSON file for reuse"""
        keys_file = Path("demo_tenant_keys.json")
        
        # Create a structured format
        tenant_keys = {}
        for slug, api_key in api_keys.items():
            config = next(c for c in self.tenant_configs if c["slug"] == slug)
            tenant_keys[config["name"]] = {
                "api_key": api_key,
                "slug": slug,
                "description": config["description"]
            }
        
        try:
            with open(keys_file, 'w') as f:
                json.dump(tenant_keys, f, indent=2)
            print(f"\n✓ API keys saved to {keys_file}")
        except Exception as e:
            print(f"\n✗ Failed to save API keys: {e}")
    
    
    async def run_setup(self) -> bool:
        """Run the complete demo setup"""
        print("🚀 Demo Tenants Setup")
        print("=" * 50)
        
        # Check admin credentials first
        if not self.check_admin_credentials():
            return False
        
        try:
            async for db in get_async_db():
                tenant_service = TenantService(db)
                
                # Setup demo tenants  
                self.api_keys = await self.setup_demo_tenants(tenant_service)
                
                break  # Only need first session
            
            # Save keys to files
            self.save_api_keys(self.api_keys)
            
            # Summary
            print("\n" + "=" * 50)
            print("🎉 Demo Setup Complete!")
            print(f"✅ Using existing admin tenant")
            print(f"✅ {len(self.api_keys)} demo tenants configured")
            print(f"✅ API keys saved to demo_tenant_keys.json")
            
            print("\n🔑 Quick Reference:")
            print(f"Admin API Key: {self.admin_api_key[:20]}...")
            for slug, api_key in self.api_keys.items():
                config = next(c for c in self.tenant_configs if c["slug"] == slug)
                print(f"{config['name']}: {api_key[:20]}...")
            
            print("\n🧪 Test Commands:")
            print("# Test admin access:")
            print(f"curl -H 'X-API-Key: {self.admin_api_key}' http://localhost:8000/api/v1/auth/tenants")
            print("\n# Test tenant access:")
            first_key = list(self.api_keys.values())[0]
            print(f"curl -H 'X-API-Key: {first_key}' http://localhost:8000/api/v1/files")
            
            print("\n📋 Next Steps:")
            print("1. Run: python scripts/test_demo_tenants.py")
            print("2. Or test manually with the API keys above")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Setup failed: {e}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    """Main entry point"""
    setup = DemoTenantSetup()
    success = await setup.run_setup()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())