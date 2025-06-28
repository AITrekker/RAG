#!/usr/bin/env python3
"""
Create New Tenant Script

This script creates a new tenant with API key for the RAG platform.

Usage:
    python scripts/create_tenant.py "Tenant Name" "Description"
    python scripts/create_tenant.py "Acme Corp" "Acme Corporation's RAG system"
"""

import sys
import argparse
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.backend.core.tenant_service import TenantService
from src.backend.utils.vector_store import get_vector_store_manager

def create_tenant(name: str, description: str = "") -> dict:
    """Create a new tenant and return the result."""
    try:
        # Initialize services
        tenant_service = TenantService()
        vector_manager = get_vector_store_manager()
        
        print(f"Creating tenant: {name}")
        print(f"Description: {description}")
        print("-" * 50)
        
        # Create the tenant
        result = tenant_service.create_tenant(name=name, description=description)
        
        # Create the tenant's document collection
        tenant_id = result["tenant_id"]
        collection_name = vector_manager.get_collection_name_for_tenant(tenant_id)
        vector_manager.ensure_collection_exists(
            collection_name, 
            vector_size=384  # Default embedding dimensions
        )
        
        print("✅ Tenant created successfully!")
        print(f"Tenant ID: {tenant_id}")
        print(f"API Key: {result['api_key']}")
        print(f"Document Collection: {collection_name}")
        
        return result
        
    except Exception as e:
        print(f"❌ Failed to create tenant: {e}")
        raise

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Create a new tenant for the RAG platform")
    parser.add_argument("name", help="Name of the tenant")
    parser.add_argument("description", nargs="?", default="", help="Description of the tenant")
    
    args = parser.parse_args()
    
    if not args.name.strip():
        print("❌ Tenant name cannot be empty")
        sys.exit(1)
    
    try:
        result = create_tenant(args.name, args.description)
        
        print("\n" + "=" * 50)
        print("🎉 TENANT CREATION COMPLETE")
        print("=" * 50)
        print(f"Tenant Name: {args.name}")
        print(f"Tenant ID: {result['tenant_id']}")
        print(f"API Key: {result['api_key']}")
        print("\n⚠️  IMPORTANT: Save this API key securely!")
        print("   You'll need it to access this tenant.")
        print("\nNext Steps:")
        print("  1. Use this API key in your frontend configuration")
        print("  2. Upload documents to this tenant")
        print("  3. Start querying!")
        print("=" * 50)
        
    except Exception as e:
        print(f"❌ Tenant creation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 