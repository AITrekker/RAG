#!/usr/bin/env python3
"""
Debug Tenants Script

This script provides debugging and recovery tools for tenant management.
It can retrieve tenant API keys and other information from the database.

Usage:
    python debug-tenants.py --tenant-id "tenant_uuid"
    python debug-tenants.py --list-all
    python debug-tenants.py --tenant-slug "tenant_slug"
"""

import argparse
import asyncio
import os
import sys
from typing import Optional
from uuid import UUID

# Add the project root directory to the path so we can import backend modules
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

try:
    from src.backend.database import get_async_db
    from src.backend.services.tenant_service import TenantService
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("💡 Make sure you're running this script from the project root directory")
    print("   Example: python scripts/debug-tenants.py --list-all")
    sys.exit(1)


async def get_tenant_by_id(tenant_id: str) -> Optional[dict]:
    """Get tenant information by ID."""
    try:
        async for db in get_async_db():
            tenant_service = TenantService(db)
            tenant = await tenant_service.get_tenant_by_id(UUID(tenant_id))
            
            if tenant:
                return {
                    "id": str(tenant.id),
                    "name": tenant.name,
                    "slug": tenant.slug,
                    "description": tenant.description,
                    "api_key": tenant.api_key,
                    "api_key_name": tenant.api_key_name,
                    "is_active": tenant.is_active,
                    "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
                    "status": tenant.status
                }
            else:
                return None
    except Exception as e:
        print(f"❌ Error retrieving tenant: {e}")
        return None


async def get_tenant_by_slug(slug: str) -> Optional[dict]:
    """Get tenant information by slug."""
    try:
        async for db in get_async_db():
            tenant_service = TenantService(db)
            tenant = await tenant_service.get_tenant_by_slug(slug)
            
            if tenant:
                return {
                    "id": str(tenant.id),
                    "name": tenant.name,
                    "slug": tenant.slug,
                    "description": tenant.description,
                    "api_key": tenant.api_key,
                    "api_key_name": tenant.api_key_name,
                    "is_active": tenant.is_active,
                    "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
                    "status": tenant.status
                }
            else:
                return None
    except Exception as e:
        print(f"❌ Error retrieving tenant: {e}")
        return None


async def list_all_tenants() -> list:
    """List all tenants with basic information."""
    try:
        async for db in get_async_db():
            tenant_service = TenantService(db)
            tenants = await tenant_service.list_tenants()
            
            tenant_list = []
            for tenant in tenants:
                tenant_list.append({
                    "id": str(tenant.id),
                    "name": tenant.name,
                    "slug": tenant.slug,
                    "description": tenant.description,
                    "api_key": tenant.api_key,
                    "api_key_name": tenant.api_key_name,
                    "is_active": tenant.is_active,
                    "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
                    "status": tenant.status
                })
            
            return tenant_list
    except Exception as e:
        print(f"❌ Error listing tenants: {e}")
        return []


def print_tenant_info(tenant: dict, show_api_key: bool = True):
    """Print tenant information in a formatted way."""
    print("=" * 60)
    print(f"🔍 TENANT INFORMATION")
    print("=" * 60)
    print(f"ID:          {tenant['id']}")
    print(f"Name:        {tenant['name']}")
    print(f"Slug:        {tenant['slug']}")
    print(f"Description: {tenant['description'] or 'N/A'}")
    print(f"Status:      {tenant['status'] or 'active'}")
    print(f"Active:      {tenant['is_active']}")
    print(f"Created:     {tenant['created_at']}")
    print(f"Key Name:    {tenant['api_key_name'] or 'N/A'}")
    
    if show_api_key and tenant['api_key']:
        print(f"API Key:     {tenant['api_key']}")
        print(f"Key Prefix:  {tenant['api_key'][:8]}...{tenant['api_key'][-8:]}")
    elif not tenant['api_key']:
        print("API Key:     ❌ No API key found")
    
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Debug and recover tenant information")
    parser.add_argument("--tenant-id", help="Tenant ID (UUID)")
    parser.add_argument("--tenant-slug", help="Tenant slug")
    parser.add_argument("--list-all", action="store_true", help="List all tenants")
    parser.add_argument("--show-key", action="store_true", help="Show full API key (default: show prefix only)")
    
    args = parser.parse_args()
    
    if not any([args.tenant_id, args.tenant_slug, args.list_all]):
        parser.print_help()
        sys.exit(1)
    
    async def run():
        if args.tenant_id:
            print(f"🔍 Looking up tenant by ID: {args.tenant_id}")
            tenant = await get_tenant_by_id(args.tenant_id)
            
            if tenant:
                print_tenant_info(tenant, show_api_key=args.show_key)
            else:
                print(f"❌ Tenant with ID '{args.tenant_id}' not found")
                sys.exit(1)
        
        elif args.tenant_slug:
            print(f"🔍 Looking up tenant by slug: {args.tenant_slug}")
            tenant = await get_tenant_by_slug(args.tenant_slug)
            
            if tenant:
                print_tenant_info(tenant, show_api_key=args.show_key)
            else:
                print(f"❌ Tenant with slug '{args.tenant_slug}' not found")
                sys.exit(1)
        
        elif args.list_all:
            print("🔍 Listing all tenants...")
            tenants = await list_all_tenants()
            
            if tenants:
                print(f"📋 Found {len(tenants)} tenants:")
                print("=" * 80)
                for i, tenant in enumerate(tenants, 1):
                    print(f"{i:2d}. {tenant['name']} ({tenant['slug']})")
                    print(f"     ID: {tenant['id']}")
                    if tenant['api_key']:
                        print(f"     Key: {tenant['api_key'][:8]}...{tenant['api_key'][-8:]}")
                    else:
                        print(f"     Key: ❌ No API key")
                    print(f"     Status: {tenant['status'] or 'active'}")
                    print()
            else:
                print("❌ No tenants found")
                sys.exit(1)
    
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 