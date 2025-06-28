#!/usr/bin/env python3
"""
Qdrant Database Clear Script

This script completely clears the Qdrant database by:
1. Deleting all collections
2. Removing all data
3. Confirming the database is empty

Usage:
    python scripts/db-clear.py [--force]
"""

import argparse
import sys
import time
from typing import List, Optional

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    from qdrant_client.http.exceptions import UnexpectedResponse
except ImportError:
    print("❌ Error: qdrant-client not installed")
    print("Install with: pip install qdrant-client")
    sys.exit(1)


def connect_to_qdrant(host: str = "localhost", port: int = 6333) -> Optional[QdrantClient]:
    """Connect to Qdrant and return client or None if failed."""
    try:
        client = QdrantClient(host=host, port=port)
        # Test connection
        client.get_collections()
        return client
    except Exception as e:
        print(f"❌ Failed to connect to Qdrant at {host}:{port}")
        print(f"Error: {e}")
        return None


def get_collections(client: QdrantClient) -> List[str]:
    """Get list of all collection names."""
    try:
        collections = client.get_collections()
        return [col.name for col in collections.collections]
    except Exception as e:
        print(f"❌ Failed to get collections: {e}")
        return []


def clear_database(client: QdrantClient, force: bool = False) -> bool:
    """Clear all data from Qdrant database."""
    print("🗑️  Clearing Qdrant Database")
    print("=" * 50)
    
    # Get current collections
    collections = get_collections(client)
    
    if not collections:
        print("✅ Database is already empty")
        return True
    
    print(f"📋 Found {len(collections)} collection(s):")
    for i, col_name in enumerate(collections, 1):
        try:
            info = client.get_collection(col_name)
            points = info.points_count
            print(f"   {i}. {col_name} ({points} points)")
        except Exception:
            print(f"   {i}. {col_name} (error getting info)")
    
    if not force:
        print("\n⚠️  WARNING: This will permanently delete ALL data!")
        response = input("Are you sure you want to continue? (yes/no): ").lower().strip()
        if response not in ['yes', 'y']:
            print("❌ Operation cancelled")
            return False
    
    print("\n🗑️  Deleting collections...")
    
    # Delete each collection
    for col_name in collections:
        try:
            print(f"   Deleting: {col_name}")
            client.delete_collection(col_name)
            print(f"   ✅ Deleted: {col_name}")
        except Exception as e:
            print(f"   ❌ Failed to delete {col_name}: {e}")
            return False
    
    # Verify deletion
    print("\n🔍 Verifying deletion...")
    time.sleep(1)  # Give Qdrant time to process
    
    remaining_collections = get_collections(client)
    if remaining_collections:
        print(f"❌ Failed to delete all collections. Remaining: {remaining_collections}")
        return False
    
    print("✅ Database cleared successfully!")
    return True


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Clear Qdrant database")
    parser.add_argument("--host", default="localhost", help="Qdrant host (default: localhost)")
    parser.add_argument("--port", type=int, default=6333, help="Qdrant port (default: 6333)")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    
    args = parser.parse_args()
    
    print("🗑️  Qdrant Database Clear Tool")
    print("=" * 50)
    print(f"Target: {args.host}:{args.port}")
    print()
    
    # Connect to Qdrant
    client = connect_to_qdrant(args.host, args.port)
    if not client:
        sys.exit(1)
    
    print("✅ Connected to Qdrant")
    
    # Clear database
    success = clear_database(client, args.force)
    
    if success:
        print("\n🎉 Database cleared successfully!")
        print("You can now reinitialize with: python scripts/db-init.py")
    else:
        print("\n❌ Failed to clear database")
        sys.exit(1)


if __name__ == "__main__":
    main() 