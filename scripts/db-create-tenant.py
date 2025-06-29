#!/usr/bin/env python3
"""
Hybrid Create Tenant Script

This script creates a new tenant with API key for the RAG platform using
the hybrid PostgreSQL + Qdrant architecture.

Usage:
    python scripts/db-create-tenant.py "Tenant Name" "Description"
    python scripts/db-create-tenant.py "Acme Corp" "Acme Corporation's RAG system"
"""

import sys
import argparse
import asyncio
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.backend.database import AsyncSessionLocal
from src.backend.services.tenant_service import TenantService
from src.backend.services.file_service import FileService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def create_tenant(name: str, description: str = "") -> dict:
    """Create a new tenant and return the result."""
    try:
        print(f"🏢 Creating tenant: {name}")
        print(f"📝 Description: {description}")
        print("-" * 50)
        
        async with AsyncSessionLocal() as session:
            # Initialize services
            tenant_service = TenantService(session)
            file_service = FileService(session)
            
            # Create the tenant in PostgreSQL
            result = await tenant_service.create_tenant(
                name=name, 
                description=description,
                auto_sync=True,
                sync_interval=60
            )
            
            tenant_id = result["id"]
            api_key = result["api_key"]
            
            # Create the tenant's upload directory
            upload_dir = Path(f"./data/uploads/{tenant_id}")
            upload_dir.mkdir(parents=True, exist_ok=True)
            
            # Create Qdrant collection for the tenant
            collection_name = f"tenant_{tenant_id}_documents"
            
            try:
                import requests
                
                # Create collection with proper vector configuration
                create_payload = {
                    "vectors": {
                        "size": 384,  # all-MiniLM-L6-v2 dimensions
                        "distance": "Cosine"
                    }
                }
                
                response = requests.put(
                    f"http://localhost:6333/collections/{collection_name}",
                    json=create_payload,
                    timeout=10
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Created Qdrant collection: {collection_name}")
                else:
                    logger.warning(f"⚠️ Qdrant collection creation returned status {response.status_code}")
                    
            except Exception as e:
                logger.error(f"❌ Failed to create Qdrant collection: {e}")
                logger.warning("   Collection will be created automatically on first document upload")
            
            print("✅ Tenant created successfully!")
            print(f"🆔 Tenant ID: {tenant_id}")
            print(f"🔑 API Key: {api_key}")
            print(f"📁 Upload Directory: {upload_dir}")
            print(f"🗂️ Qdrant Collection: {collection_name}")
            
            return {
                "tenant_id": tenant_id,
                "name": name,
                "api_key": api_key,
                "upload_dir": str(upload_dir),
                "collection_name": collection_name
            }
        
    except Exception as e:
        logger.error(f"❌ Failed to create tenant: {e}")
        raise

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Create a new tenant for the hybrid RAG platform")
    parser.add_argument("name", help="Name of the tenant")
    parser.add_argument("description", nargs="?", default="", help="Description of the tenant")
    parser.add_argument("--auto-sync", action="store_true", default=True, help="Enable automatic sync (default: True)")
    parser.add_argument("--sync-interval", type=int, default=60, help="Sync interval in seconds (default: 60)")
    
    args = parser.parse_args()
    
    if not args.name.strip():
        print("❌ Tenant name cannot be empty")
        sys.exit(1)
    
    print("🏢 Hybrid Tenant Creation Tool")
    print("=" * 50)
    print("Architecture: PostgreSQL + Qdrant")
    print()
    
    try:
        result = await create_tenant(args.name, args.description)
        
        print("\n" + "=" * 50)
        print("🎉 TENANT CREATION COMPLETE")
        print("=" * 50)
        print(f"Tenant Name: {args.name}")
        print(f"Tenant ID: {result['tenant_id']}")
        print(f"API Key: {result['api_key']}")
        print(f"Upload Directory: {result['upload_dir']}")
        print(f"Qdrant Collection: {result['collection_name']}")
        print("\n⚠️  IMPORTANT: Save this API key securely!")
        print("   You'll need it to access this tenant.")
        print("\nNext Steps:")
        print("  1. Copy files to the upload directory")
        print("  2. Run delta sync: python scripts/delta-sync.py")
        print("  3. Test with: python scripts/test_existing_tenants.py")
        print("  4. Start querying with the API key!")
        print("=" * 50)
        
    except Exception as e:
        logger.error(f"❌ Tenant creation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 