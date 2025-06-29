#!/usr/bin/env python3
"""
Hybrid Database Explorer Script

This script provides a comprehensive view of the hybrid PostgreSQL + Qdrant architecture.

Usage:
    python scripts/db-explore.py                    # Full exploration
    python scripts/db-explore.py --collection name  # Explore specific collection
    python scripts/db-explore.py --postgres         # Show only PostgreSQL data
    python scripts/db-explore.py --qdrant           # Show only Qdrant data
    python scripts/db-explore.py --sync             # Show only sync status
"""

import sys
import argparse
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.backend.database import AsyncSessionLocal
from src.backend.services.tenant_service import TenantService
from src.backend.models.database import Tenant, User, File, EmbeddingChunk, SyncOperation
from sqlalchemy import select, func

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def print_banner():
    """Print exploration banner."""
    print("🔍 Hybrid Database Explorer")
    print("=" * 60)
    print("Architecture: PostgreSQL (control plane) + Qdrant (vectors)")
    print()

def explore_qdrant_collections():
    """Explore all collections in Qdrant."""
    print("\n🗂️ QDRANT COLLECTIONS")
    print("-" * 40)
    
    try:
        import requests
        
        # Get collections from Qdrant REST API
        response = requests.get("http://localhost:6333/collections", timeout=5)
        response.raise_for_status()
        
        collections_data = response.json()
        collections = collections_data.get('result', {}).get('collections', [])
        
        if not collections:
            print("❌ No collections found in Qdrant")
            return
        
        print(f"Found {len(collections)} collection(s):")
        
        for i, collection in enumerate(collections, 1):
            try:
                collection_name = collection['name']
                
                # Get detailed collection info
                info_response = requests.get(f"http://localhost:6333/collections/{collection_name}", timeout=5)
                if info_response.status_code == 200:
                    info = info_response.json()
                    result = info.get('result', {})
                    points_count = result.get('points_count', 0)
                    vector_size = result.get('config', {}).get('params', {}).get('vectors', {}).get('size', 'Unknown')
                    distance = result.get('config', {}).get('params', {}).get('vectors', {}).get('distance', 'Unknown')
                    
                    print(f"\n{i}. Collection: {collection_name}")
                    print(f"   Points: {points_count:,}")
                    print(f"   Vector Size: {vector_size}")
                    print(f"   Distance: {distance}")
                    
                    # Extract tenant info from collection name
                    if collection_name.startswith('tenant_') and collection_name.endswith('_documents'):
                        tenant_id = collection_name.replace('tenant_', '').replace('_documents', '')
                        print(f"   Tenant ID: {tenant_id}")
                    
                else:
                    print(f"\n{i}. Collection: {collection_name}")
                    print(f"   Error getting info: HTTP {info_response.status_code}")
                    
            except Exception as e:
                print(f"\n{i}. Collection: {collection.get('name', 'Unknown')}")
                print(f"   Error getting info: {e}")
                
    except Exception as e:
        print(f"❌ Failed to connect to Qdrant: {e}")
        print("   Make sure Qdrant is running: docker-compose up qdrant -d")

async def explore_postgresql_data():
    """Explore PostgreSQL data."""
    print("\n📊 POSTGRESQL DATA")
    print("-" * 40)
    
    try:
        async with AsyncSessionLocal() as session:
            # Get tenant count and details
            tenant_result = await session.execute(select(func.count(Tenant.id)))
            tenant_count = tenant_result.scalar()
            
            # Get user count
            user_result = await session.execute(select(func.count(User.id)))
            user_count = user_result.scalar()
            
            # Get file count
            file_result = await session.execute(select(func.count(File.id)))
            file_count = file_result.scalar()
            
            # Get chunk count
            chunk_result = await session.execute(select(func.count(EmbeddingChunk.id)))
            chunk_count = chunk_result.scalar()
            
            # Get sync operation count
            sync_result = await session.execute(select(func.count(SyncOperation.id)))
            sync_count = sync_result.scalar()
            
            print(f"Database Overview:")
            print(f"  Tenants: {tenant_count:,}")
            print(f"  Users: {user_count:,}")
            print(f"  Files: {file_count:,}")
            print(f"  Embedding Chunks: {chunk_count:,}")
            print(f"  Sync Operations: {sync_count:,}")
            
            if tenant_count > 0:
                print(f"\nTenant Details:")
                
                # Get tenant details
                tenants_result = await session.execute(
                    select(Tenant.id, Tenant.name, Tenant.slug, Tenant.created_at, Tenant.is_active)
                    .order_by(Tenant.created_at.desc())
                    .limit(10)
                )
                tenants = tenants_result.all()
                
                for i, tenant in enumerate(tenants, 1):
                    print(f"\n  {i}. {tenant.name}")
                    print(f"     ID: {tenant.id}")
                    print(f"     Slug: {tenant.slug}")
                    print(f"     Active: {tenant.is_active}")
                    print(f"     Created: {tenant.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    # Get file count for this tenant
                    tenant_files_result = await session.execute(
                        select(func.count(File.id))
                        .where(File.tenant_id == tenant.id, File.deleted_at.is_(None))
                    )
                    tenant_file_count = tenant_files_result.scalar()
                    print(f"     Files: {tenant_file_count:,}")
                    
                    # Get chunk count for this tenant
                    tenant_chunks_result = await session.execute(
                        select(func.count(EmbeddingChunk.id))
                        .where(EmbeddingChunk.tenant_id == tenant.id)
                    )
                    tenant_chunk_count = tenant_chunks_result.scalar()
                    print(f"     Chunks: {tenant_chunk_count:,}")
                
                if tenant_count > 10:
                    print(f"\n  ... and {tenant_count - 10} more tenant(s)")
            
    except Exception as e:
        logger.error(f"❌ Error exploring PostgreSQL data: {e}")
        import traceback
        traceback.print_exc()

def explore_collection_details(collection_name: str):
    """Explore a specific collection in detail."""
    print(f"\n🔍 COLLECTION DETAILS: {collection_name}")
    print("-" * 50)
    
    try:
        import requests
        
        # Get collection info
        info_response = requests.get(f"http://localhost:6333/collections/{collection_name}", timeout=5)
        info_response.raise_for_status()
        
        info = info_response.json()
        result = info.get('result', {})
        points_count = result.get('points_count', 0)
        vector_config = result.get('config', {}).get('params', {}).get('vectors', {})
        
        print(f"Total Points: {points_count:,}")
        print(f"Vector Size: {vector_config.get('size', 'Unknown')}")
        print(f"Distance Metric: {vector_config.get('distance', 'Unknown')}")
        
        if points_count > 0:
            # Get sample points
            print(f"\n📄 Sample Points (up to 5):")
            
            scroll_payload = {
                "limit": 5,
                "with_payload": True,
                "with_vectors": False
            }
            
            scroll_response = requests.post(
                f"http://localhost:6333/collections/{collection_name}/points/scroll",
                json=scroll_payload,
                timeout=10
            )
            
            if scroll_response.status_code == 200:
                scroll_data = scroll_response.json()
                points = scroll_data.get('result', {}).get('points', [])
                
                for i, point in enumerate(points, 1):
                    print(f"\n  Point {i}:")
                    print(f"    ID: {point.get('id')}")
                    payload = point.get('payload', {})
                    print(f"    Payload Keys: {list(payload.keys())}")
                    
                    # Show payload details
                    for key, value in payload.items():
                        if isinstance(value, str) and len(value) > 100:
                            # Truncate long text
                            preview = value[:100] + "..."
                            print(f"    {key}: {preview}")
                        elif isinstance(value, dict):
                            print(f"    {key}: {list(value.keys())}")
                        elif isinstance(value, (str, int, float)) and len(str(value)) < 50:
                            print(f"    {key}: {value}")
                        else:
                            print(f"    {key}: <{type(value).__name__}>")
            else:
                print(f"   Error getting sample points: HTTP {scroll_response.status_code}")
                        
    except Exception as e:
        print(f"❌ Error exploring collection {collection_name}: {e}")

async def explore_file_sync_status():
    """Explore file synchronization status."""
    print("\n🔄 SYNC STATUS")
    print("-" * 40)
    
    try:
        async with AsyncSessionLocal() as session:
            # Get sync status summary
            sync_status_result = await session.execute(
                select(File.sync_status, func.count(File.id))
                .where(File.deleted_at.is_(None))
                .group_by(File.sync_status)
            )
            sync_status_counts = sync_status_result.all()
            
            if sync_status_counts:
                print("File Sync Status:")
                for status, count in sync_status_counts:
                    print(f"  {status}: {count:,} files")
            else:
                print("No file sync data found")
            
            # Get recent sync operations
            recent_syncs_result = await session.execute(
                select(SyncOperation.operation_type, SyncOperation.status, 
                       SyncOperation.started_at, SyncOperation.files_processed)
                .order_by(SyncOperation.started_at.desc())
                .limit(5)
            )
            recent_syncs = recent_syncs_result.all()
            
            if recent_syncs:
                print("\nRecent Sync Operations:")
                for i, sync_op in enumerate(recent_syncs, 1):
                    print(f"  {i}. {sync_op.operation_type} - {sync_op.status}")
                    print(f"     Started: {sync_op.started_at.strftime('%Y-%m-%d %H:%M:%S') if sync_op.started_at else 'Unknown'}")
                    print(f"     Files: {sync_op.files_processed or 0}")
            
    except Exception as e:
        logger.error(f"❌ Error exploring sync status: {e}")

def show_system_info():
    """Show system connection and access information."""
    print("\n🌐 SYSTEM ACCESS INFO")
    print("-" * 40)
    print("PostgreSQL:")
    print("  Connection: AsyncSessionLocal (via database.py)")
    print("  Tables: tenants, users, files, embedding_chunks, sync_operations")
    print()
    print("Qdrant:")
    print("  Web Dashboard: http://localhost:6333/dashboard")
    print("  REST API: http://localhost:6333")
    print("  gRPC Port: 6334")
    print()
    print("Useful Commands:")
    print("  curl http://localhost:6333/collections")
    print("  curl http://localhost:6333/collections/tenant_<ID>_documents/points")
    print("  python scripts/delta-sync.py")
    print("  python scripts/test_existing_tenants.py")

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Explore hybrid PostgreSQL + Qdrant data")
    parser.add_argument("--collection", help="Explore specific Qdrant collection")
    parser.add_argument("--postgres", action="store_true", help="Show only PostgreSQL data")
    parser.add_argument("--qdrant", action="store_true", help="Show only Qdrant data")
    parser.add_argument("--sync", action="store_true", help="Show only sync status")
    
    args = parser.parse_args()
    
    print_banner()
    
    try:
        # Test PostgreSQL connection
        postgres_ok = True
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(select(1))
            print("✅ Connected to PostgreSQL")
        except Exception as e:
            print(f"❌ Failed to connect to PostgreSQL: {e}")
            postgres_ok = False
        
        # Test Qdrant connection
        qdrant_ok = True
        try:
            import requests
            response = requests.get("http://localhost:6333/collections", timeout=5)
            response.raise_for_status()
            collections_data = response.json()
            collection_count = len(collections_data.get('result', {}).get('collections', []))
            print(f"✅ Connected to Qdrant")
            print(f"   Found {collection_count} collection(s)")
        except Exception as e:
            print(f"❌ Failed to connect to Qdrant: {e}")
            qdrant_ok = False
        
        print()
        
        if args.postgres and postgres_ok:
            await explore_postgresql_data()
        elif args.qdrant and qdrant_ok:
            explore_qdrant_collections()
        elif args.sync and postgres_ok:
            await explore_file_sync_status()
        elif args.collection and qdrant_ok:
            explore_collection_details(args.collection)
        else:
            # Full exploration
            if postgres_ok:
                await explore_postgresql_data()
            if qdrant_ok:
                explore_qdrant_collections()
            if postgres_ok:
                await explore_file_sync_status()
            show_system_info()
            
    except KeyboardInterrupt:
        print("\n🛑 Exploration interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error during exploration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())