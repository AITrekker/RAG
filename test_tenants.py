#!/usr/bin/env python3
"""
Quick test script to check tenants in the database
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
    """Check what tenants exist in the database."""
    async for db in get_async_db():
        try:
            tenant_service = TenantService(db)
            tenants = await tenant_service.list_tenants()
            print(f"Found {len(tenants)} tenants:")
            for tenant in tenants:
                print(f"  - {tenant.name} (slug: {tenant.slug})")
                print(f"    API Key: {tenant.api_key}")
                print(f"    Status: {tenant.status}")
                print()
        except Exception as e:
            print(f"Error listing tenants: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 