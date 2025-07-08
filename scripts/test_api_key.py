#!/usr/bin/env python3
"""
Test script to verify API key lookup
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.backend.database import get_async_db
from src.backend.services.tenant_service import TenantService

async def main():
    """Test API key lookup functionality."""
    api_key = "tenant_system_admin_52cc85c532cbf7c4310500333569d92d"
    
    async for db in get_async_db():
        try:
            tenant_service = TenantService(db)
            
            # Test direct lookup
            tenant = await tenant_service.get_tenant_by_api_key(api_key)
            
            if tenant:
                print(f"✅ Found tenant: {tenant.name} (slug: {tenant.slug})")
                print(f"   API Key: {tenant.api_key}")
                print(f"   API Key Hash: {tenant.api_key_hash}")
                print(f"   Is Active: {tenant.is_active}")
                print(f"   Status: {tenant.status}")
            else:
                print(f"❌ No tenant found for API key: {api_key}")
                
                # List all tenants to debug
                tenants = await tenant_service.list_tenants()
                print(f"\nAll tenants ({len(tenants)}):")
                for t in tenants:
                    print(f"  - {t.name}: {t.api_key}")
                    
        except Exception as e:
            print(f"Error testing API key: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 