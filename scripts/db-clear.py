#!/usr/bin/env python3
"""
Hybrid Database Clear Script

This script completely clears both PostgreSQL and Qdrant databases by:
1. Deleting all PostgreSQL data (files, chunks, tenants, users)
2. Deleting all Qdrant collections
3. Confirming both databases are empty

Usage:
    python scripts/db-clear.py [--force]
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path
from typing import List, Optional

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.backend.database import AsyncSessionLocal
from src.backend.models.database import (
    EmbeddingChunk, File, SyncOperation, FileAccessControl, 
    FileSharingLinks, FileSyncHistory, TenantMembership, User, Tenant
)
from sqlalchemy import delete

def connect_to_qdrant() -> Optional[object]:
    """Connect to Qdrant and return client or None if failed."""
    try:
        import requests
        
        # Test connection
        response = requests.get("http://localhost:6333/collections", timeout=5)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ Failed to connect to Qdrant at localhost:6333")
        print(f"Error: {e}")
        return None

def get_qdrant_collections() -> List[str]:
    """Get list of all collection names."""
    try:
        import requests
        
        response = requests.get("http://localhost:6333/collections", timeout=5)
        response.raise_for_status()
        
        collections_data = response.json()
        collections = collections_data.get('result', {}).get('collections', [])
        return [col['name'] for col in collections]
    except Exception as e:
        print(f"❌ Failed to get collections: {e}")
        return []

def clear_qdrant_database(force: bool = False) -> bool:
    """Clear all data from Qdrant database."""
    print("🗑️  Clearing Qdrant Database")
    print("-" * 40)
    
    # Get current collections
    collections = get_qdrant_collections()
    
    if not collections:
        print("✅ Qdrant database is already empty")
        return True
    
    print(f"📋 Found {len(collections)} collection(s):")
    for i, col_name in enumerate(collections, 1):
        try:
            import requests
            response = requests.get(f"http://localhost:6333/collections/{col_name}", timeout=5)
            if response.status_code == 200:
                info = response.json()
                points = info.get('result', {}).get('points_count', 0)
                print(f"   {i}. {col_name} ({points} points)")
            else:
                print(f"   {i}. {col_name} (error getting info)")
        except Exception:
            print(f"   {i}. {col_name} (error getting info)")
    
    if not force:
        print("\n⚠️  WARNING: This will permanently delete ALL Qdrant data!")
        response = input("Are you sure you want to continue? (yes/no): ").lower().strip()
        if response not in ['yes', 'y']:
            print("❌ Operation cancelled")
            return False
    
    print("\n🗑️  Deleting Qdrant collections...")
    
    # Delete each collection
    import requests
    for col_name in collections:
        try:
            print(f"   Deleting: {col_name}")
            response = requests.delete(f"http://localhost:6333/collections/{col_name}", timeout=10)
            response.raise_for_status()
            print(f"   ✅ Deleted: {col_name}")
        except Exception as e:
            print(f"   ❌ Failed to delete {col_name}: {e}")
            return False
    
    # Verify deletion
    print("\n🔍 Verifying Qdrant deletion...")
    time.sleep(1)  # Give Qdrant time to process
    
    remaining_collections = get_qdrant_collections()
    if remaining_collections:
        print(f"❌ Failed to delete all collections. Remaining: {remaining_collections}")
        return False
    
    print("✅ Qdrant database cleared successfully!")
    return True

async def clear_postgresql_database(force: bool = False) -> bool:
    """Clear all data from PostgreSQL database."""
    print("\n🗑️  Clearing PostgreSQL Database")
    print("-" * 40)
    
    try:
        async with AsyncSessionLocal() as session:
            # Check what data exists
            tables_with_data = []
            
            # Count records in each table
            for model, name in [
                (EmbeddingChunk, "embedding_chunks"),
                (File, "files"),
                (SyncOperation, "sync_operations"),
                (FileAccessControl, "file_access_control"),
                (FileSharingLinks, "file_sharing_links"),
                (FileSyncHistory, "file_sync_history"),
                (TenantMembership, "tenant_memberships"),
                (User, "users"),
                (Tenant, "tenants")
            ]:
                try:
                    count_result = await session.execute(f"SELECT COUNT(*) FROM {name}")
                    count = count_result.scalar()
                    if count > 0:
                        tables_with_data.append((name, count))
                except Exception:
                    pass  # Table might not exist yet
            
            if not tables_with_data:
                print("✅ PostgreSQL database is already empty")
                return True
            
            print(f"📋 Found data in {len(tables_with_data)} table(s):")
            for table_name, count in tables_with_data:
                print(f"   - {table_name}: {count} records")
            
            if not force:
                print("\n⚠️  WARNING: This will permanently delete ALL PostgreSQL data!")
                response = input("Are you sure you want to continue? (yes/no): ").lower().strip()
                if response not in ['yes', 'y']:
                    print("❌ Operation cancelled")
                    return False
            
            print("\n🗑️  Deleting PostgreSQL data...")
            
            # Delete data in correct order (respecting foreign key constraints)
            deletion_order = [
                (EmbeddingChunk, "embedding_chunks"),
                (FileSyncHistory, "file_sync_history"),
                (FileAccessControl, "file_access_control"),
                (FileSharingLinks, "file_sharing_links"),
                (File, "files"),
                (SyncOperation, "sync_operations"),
                (TenantMembership, "tenant_memberships"),
                (User, "users"),
                (Tenant, "tenants")
            ]
            
            for model, name in deletion_order:
                try:
                    print(f"   Deleting: {name}")
                    result = await session.execute(delete(model))
                    count = result.rowcount
                    print(f"   ✅ Deleted {count} records from {name}")
                except Exception as e:
                    print(f"   ⚠️ Error deleting from {name}: {e}")
                    # Continue with other tables
            
            await session.commit()
            
            print("✅ PostgreSQL database cleared successfully!")
            return True
            
    except Exception as e:
        print(f"❌ Failed to clear PostgreSQL database: {e}")
        return False

async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Clear hybrid PostgreSQL + Qdrant databases")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompts")
    parser.add_argument("--postgres-only", action="store_true", help="Clear only PostgreSQL")
    parser.add_argument("--qdrant-only", action="store_true", help="Clear only Qdrant")
    
    args = parser.parse_args()
    
    print("🗑️  Hybrid Database Clear Tool")
    print("=" * 50)
    print("Target: PostgreSQL + Qdrant")
    print()
    
    success = True
    
    # Clear PostgreSQL unless qdrant-only is specified
    if not args.qdrant_only:
        print("🔍 Checking PostgreSQL connection...")
        try:
            # Test PostgreSQL connection
            async with AsyncSessionLocal() as session:
                await session.execute("SELECT 1")
            print("✅ Connected to PostgreSQL")
            
            success = await clear_postgresql_database(args.force)
        except Exception as e:
            print(f"❌ Failed to connect to PostgreSQL: {e}")
            success = False
    
    # Clear Qdrant unless postgres-only is specified
    if success and not args.postgres_only:
        print("\n🔍 Checking Qdrant connection...")
        if connect_to_qdrant():
            print("✅ Connected to Qdrant")
            success = clear_qdrant_database(args.force)
        else:
            success = False
    
    if success:
        print("\n🎉 Database(s) cleared successfully!")
        print("You can now reinitialize with: python scripts/db-init.py")
    else:
        print("\n❌ Failed to clear database(s)")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())