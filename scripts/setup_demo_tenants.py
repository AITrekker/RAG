#!/usr/bin/env python3
"""
Demo Tenants Setup Script

Creates 3 demo tenants based on your existing data structure:
- tenant1, tenant2, tenant3 with company documents
- Saves API keys to demo_tenant_keys.json for reuse
- Creates admin tenant and saves admin API key to .env

This script works with the new PostgreSQL + service architecture.

Usage:
    python scripts/setup_demo_tenants.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backend.database import get_async_db
from src.backend.services.tenant_service import TenantService


class DemoTenantSetup:
    def __init__(self):
        self.tenant_configs = [
            {
                "name": "Company Demo 1", 
                "slug": "tenant1",
                "description": "Demo tenant 1 with company documents"
            },
            {
                "name": "Company Demo 2", 
                "slug": "tenant2", 
                "description": "Demo tenant 2 with company documents"
            },
            {
                "name": "Company Demo 3", 
                "slug": "tenant3",
                "description": "Demo tenant 3 with company documents"
            }
        ]
        self.api_keys = {}
        self.admin_key = None
        
    async def setup_admin_tenant(self, tenant_service: TenantService) -> str:
        """Setup admin tenant and return API key"""
        print("\n=== Setting Up Admin Tenant ===")
        
        # Check if admin tenant exists
        admin_tenant = await tenant_service.get_tenant_by_slug("admin")
        
        if not admin_tenant:
            # Create admin tenant
            admin_result = await tenant_service.create_tenant(
                name="System Admin",
                description="System administrator tenant",
                auto_sync=True,
                sync_interval=60
            )
            admin_tenant = await tenant_service.get_tenant_by_slug("admin")
            print(f"✓ Created admin tenant: {admin_result['name']}")
        else:
            print(f"✓ Found existing admin tenant: {admin_tenant.name}")
        
        # Generate/regenerate API key
        api_key = await tenant_service.regenerate_api_key(admin_tenant.id)
        print(f"✓ Admin API key: {api_key[:20]}...")
        
        return api_key
    
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
    
    def save_admin_key(self, admin_key: str) -> None:
        """Save admin API key to .env file"""
        env_file = Path(".env")
        
        try:
            # Read existing content
            existing_content = ""
            if env_file.exists():
                with open(env_file, 'r') as f:
                    existing_content = f.read()
            
            # Check if admin key already exists
            admin_key_line = f"ADMIN_API_KEY={admin_key}"
            
            if "ADMIN_API_KEY=" in existing_content:
                # Replace existing key
                lines = existing_content.split('\n')
                new_lines = []
                for line in lines:
                    if line.startswith("ADMIN_API_KEY="):
                        new_lines.append(admin_key_line)
                    else:
                        new_lines.append(line)
                
                with open(env_file, 'w') as f:
                    f.write('\n'.join(new_lines))
                print(f"✓ Updated admin API key in {env_file}")
            else:
                # Add new key
                with open(env_file, 'a') as f:
                    if existing_content and not existing_content.endswith('\n'):
                        f.write('\n')
                    f.write(f"\n# Admin API Key (auto-generated)\n")
                    f.write(f"{admin_key_line}\n")
                print(f"✓ Added admin API key to {env_file}")
                
        except Exception as e:
            print(f"✗ Failed to save admin key to .env: {e}")
    
    async def run_setup(self) -> bool:
        """Run the complete demo setup"""
        print("🚀 Demo Tenants Setup")
        print("=" * 50)
        
        try:
            async for db in get_async_db():
                tenant_service = TenantService(db)
                
                # Setup admin tenant
                self.admin_key = await self.setup_admin_tenant(tenant_service)
                
                # Setup demo tenants  
                self.api_keys = await self.setup_demo_tenants(tenant_service)
                
                break  # Only need first session
            
            # Save keys to files
            self.save_admin_key(self.admin_key)
            self.save_api_keys(self.api_keys)
            
            # Summary
            print("\n" + "=" * 50)
            print("🎉 Demo Setup Complete!")
            print(f"✓ Admin tenant configured")
            print(f"✓ {len(self.api_keys)} demo tenants configured")
            print(f"✓ API keys saved to demo_tenant_keys.json")
            print(f"✓ Admin key saved to .env file")
            
            print("\n🔑 Quick Reference:")
            print(f"Admin API Key: {self.admin_key[:20]}...")
            for slug, api_key in self.api_keys.items():
                config = next(c for c in self.tenant_configs if c["slug"] == slug)
                print(f"{config['name']}: {api_key[:20]}...")
            
            print("\n🧪 Test Commands:")
            print("# Test admin access:")
            print(f"curl -H 'X-API-Key: {self.admin_key}' http://localhost:8000/api/v1/auth/tenants")
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