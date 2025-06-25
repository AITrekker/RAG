#!/usr/bin/env python3
"""
Enhanced Qdrant Explorer Script

This script provides a comprehensive view of what's stored in Qdrant.

Usage:
    python scripts/explore_qdrant.py                    # Full exploration
    python scripts/explore_qdrant.py --collection name  # Explore specific collection
    python scripts/explore_qdrant.py --tenants          # Show only tenant info
"""

import sys
import argparse
from pathlib import Path
from typing import Dict, Any, List

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.backend.utils.vector_store import get_vector_store_manager
from src.backend.core.tenant_service import TenantService

def print_banner():
    """Print exploration banner."""
    print("🔍 Qdrant Data Explorer")
    print("=" * 60)

def explore_collections():
    """Explore all collections in Qdrant."""
    print("\n📚 COLLECTIONS OVERVIEW")
    print("-" * 40)
    
    vector_manager = get_vector_store_manager()
    collections = vector_manager.client.get_collections().collections
    
    if not collections:
        print("❌ No collections found in Qdrant")
        return
    
    print(f"Found {len(collections)} collection(s):")
    
    for i, collection in enumerate(collections, 1):
        try:
            # Get collection info
            info = vector_manager.client.get_collection(collection.name)
            count_result = vector_manager.client.count(collection.name, exact=True)
            
            print(f"\n{i}. Collection: {collection.name}")
            print(f"   Points: {count_result.count}")
            print(f"   Vector Size: {info.config.params.vectors.size}")
            print(f"   Distance: {info.config.params.vectors.distance}")
            
        except Exception as e:
            print(f"\n{i}. Collection: {collection.name}")
            print(f"   Error getting info: {e}")

def explore_tenants():
    """Explore tenant data."""
    print("\n👥 TENANTS DATA")
    print("-" * 40)
    
    try:
        tenant_service = TenantService()
        tenants = tenant_service.list_tenants()
        
        if not tenants:
            print("❌ No tenants found")
            return
        
        print(f"Found {len(tenants)} tenant(s):")
        
        for i, tenant in enumerate(tenants, 1):
            print(f"\n{i}. Tenant: {tenant.get('name', 'Unknown')}")
            print(f"   ID: {tenant.get('tenant_id', 'Unknown')}")
            print(f"   Status: {tenant.get('status', 'Unknown')}")
            print(f"   Created: {tenant.get('created_at', 'Unknown')}")
            print(f"   API Keys: {len(tenant.get('api_keys', []))}")
            
            # Show API key prefixes (not the actual keys)
            for j, key in enumerate(tenant.get('api_keys', []), 1):
                print(f"     Key {j}: {key.get('key_prefix', 'Unknown')} ({key.get('name', 'Unknown')})")
                
    except Exception as e:
        print(f"❌ Error exploring tenants: {e}")

def explore_collection_details(collection_name: str):
    """Explore a specific collection in detail."""
    print(f"\n🔍 COLLECTION DETAILS: {collection_name}")
    print("-" * 50)
    
    try:
        vector_manager = get_vector_store_manager()
        
        # Get collection info
        info = vector_manager.client.get_collection(collection_name)
        count_result = vector_manager.client.count(collection_name, exact=True)
        
        print(f"Total Points: {count_result.count}")
        print(f"Vector Size: {info.config.params.vectors.size}")
        print(f"Distance Metric: {info.config.params.vectors.distance}")
        
        if count_result.count > 0:
            # Get sample points
            print(f"\n📄 Sample Points (up to 5):")
            points, _ = vector_manager.client.scroll(
                collection_name=collection_name,
                limit=5,
                with_payload=True,
                with_vectors=False
            )
            
            for i, point in enumerate(points, 1):
                print(f"\n  Point {i}:")
                print(f"    ID: {point.id}")
                print(f"    Payload Keys: {list(point.payload.keys())}")
                
                # Show some payload details
                for key, value in point.payload.items():
                    if key == "text" and isinstance(value, str):
                        # Truncate long text
                        preview = value[:100] + "..." if len(value) > 100 else value
                        print(f"    {key}: {preview}")
                    elif key == "metadata" and isinstance(value, dict):
                        print(f"    {key}: {list(value.keys())}")
                    elif isinstance(value, (str, int, float)) and len(str(value)) < 50:
                        print(f"    {key}: {value}")
                    else:
                        print(f"    {key}: <{type(value).__name__}>")
                        
    except Exception as e:
        print(f"❌ Error exploring collection {collection_name}: {e}")

def explore_system_collections():
    """Explore system collections."""
    print("\n⚙️ SYSTEM COLLECTIONS")
    print("-" * 40)
    
    try:
        vector_manager = get_vector_store_manager()
        
        # Check tenants_metadata collection
        tenants_collection = "tenants_metadata"
        try:
            info = vector_manager.client.get_collection(tenants_collection)
            count_result = vector_manager.client.count(tenants_collection, exact=True)
            
            print(f"✅ {tenants_collection}: {count_result.count} tenant(s)")
            
            if count_result.count > 0:
                # Show tenant IDs
                points, _ = vector_manager.client.scroll(
                    collection_name=tenants_collection,
                    limit=10,
                    with_payload=True,
                    with_vectors=False
                )
                
                print("   Tenant IDs:")
                for point in points:
                    tenant_name = point.payload.get("name", "Unknown")
                    print(f"     - {point.id} ({tenant_name})")
                    
        except Exception as e:
            print(f"❌ {tenants_collection}: {e}")
            
    except Exception as e:
        print(f"❌ Error exploring system collections: {e}")

def show_qdrant_info():
    """Show Qdrant connection and access information."""
    print("\n🌐 QDRANT ACCESS INFO")
    print("-" * 40)
    print("Web Dashboard: http://localhost:6333/dashboard")
    print("REST API: http://localhost:6333")
    print("gRPC Port: 6334")
    print("\nUseful Commands:")
    print("  curl http://localhost:6333/collections")
    print("  curl http://localhost:6333/collections/tenants_metadata/points")
    print("  curl http://localhost:6333/collections/tenants_metadata/points/scroll")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Explore Qdrant data")
    parser.add_argument("--collection", help="Explore specific collection")
    parser.add_argument("--tenants", action="store_true", help="Show only tenant info")
    parser.add_argument("--system", action="store_true", help="Show only system collections")
    
    args = parser.parse_args()
    
    print_banner()
    
    try:
        # Test connection
        vector_manager = get_vector_store_manager()
        collections = vector_manager.client.get_collections()
        print(f"✅ Connected to Qdrant at localhost:6333")
        print(f"   Found {len(collections.collections)} collection(s)")
        
        if args.tenants:
            explore_tenants()
        elif args.system:
            explore_system_collections()
        elif args.collection:
            explore_collection_details(args.collection)
        else:
            # Full exploration
            explore_collections()
            explore_tenants()
            explore_system_collections()
            show_qdrant_info()
            
    except Exception as e:
        print(f"❌ Failed to connect to Qdrant: {e}")
        print("   Make sure Qdrant is running: docker-compose up qdrant -d")
        sys.exit(1)

if __name__ == "__main__":
    main() 