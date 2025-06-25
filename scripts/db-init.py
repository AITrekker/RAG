#!/usr/bin/env python3
"""
Qdrant Database Initialization Script

This script initializes the Qdrant vector database with:
1. Admin tenant with default API key
2. All necessary collections
3. Proper configuration for the RAG platform

Usage:
    python scripts/init_qdrant_db.py
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.backend.config.settings import get_settings
from src.backend.core.tenant_service import TenantService
from src.backend.utils.vector_store import get_vector_store_manager, VectorStoreManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class QdrantInitializer:
    """Handles Qdrant database initialization."""
    
    def __init__(self):
        self.settings = get_settings()
        self.vector_manager = get_vector_store_manager()
        self.tenant_service = TenantService()
        
    def print_banner(self):
        """Print initialization banner."""
        print("🚀 Qdrant Database Initialization")
        print("=" * 50)
        print(f"Qdrant URL: {self.settings.qdrant_url}")
        print(f"Embedding Model: {self.settings.embedding_model}")
        print(f"Vector Dimensions: {self.settings.embedding_model_dimensions}")
        print()
    
    def check_qdrant_connection(self) -> bool:
        """Check if Qdrant is accessible."""
        try:
            logger.info("Checking Qdrant connection...")
            
            # Test basic connection
            collections = self.vector_manager.client.get_collections()
            logger.info(f"✅ Successfully connected to Qdrant")
            logger.info(f"   Found {len(collections.collections)} existing collections")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Qdrant: {e}")
            logger.error("   Please ensure Qdrant is running and accessible")
            return False
    
    def create_admin_tenant(self) -> Dict[str, Any]:
        """Create the admin tenant with default API key."""
        logger.info("Creating admin tenant...")
        
        try:
            # Check if admin tenant already exists
            existing_tenants = self.tenant_service.list_tenants()
            admin_tenant = next((t for t in existing_tenants if t.get("name") == "admin"), None)
            
            if admin_tenant:
                logger.info(f"✅ Admin tenant already exists with ID: {admin_tenant['tenant_id']}")
                return {
                    "tenant_id": admin_tenant["tenant_id"],
                    "name": admin_tenant["name"],
                    "api_key": "EXISTING_KEY"  # We can't retrieve the actual key
                }
            
            # Create new admin tenant
            result = self.tenant_service.create_tenant(
                name="admin",
                description="Default administrative tenant for the RAG platform"
            )
            
            logger.info(f"✅ Successfully created admin tenant")
            logger.info(f"   Tenant ID: {result['tenant_id']}")
            logger.info(f"   API Key: {result['api_key']}")
            
            return {
                "tenant_id": result["tenant_id"],
                "name": "admin",
                "api_key": result["api_key"]
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to create admin tenant: {e}")
            raise
    
    def create_tenant_collections(self, tenant_id: str) -> bool:
        """Create document collection for a tenant."""
        try:
            logger.info(f"Creating document collection for tenant {tenant_id}...")
            
            collection_name = self.vector_manager.get_collection_name_for_tenant(tenant_id)
            self.vector_manager.ensure_collection_exists(
                collection_name, 
                self.settings.embedding_model_dimensions
            )
            
            logger.info(f"✅ Created collection: {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create collection for tenant {tenant_id}: {e}")
            return False
    
    def create_system_collections(self) -> bool:
        """Create system-wide collections."""
        try:
            logger.info("Creating system collections...")
            
            # Tenants metadata collection (already created by TenantService)
            tenants_collection = "tenants_metadata"
            self.vector_manager.ensure_collection_exists(tenants_collection, vector_size=1)
            logger.info(f"✅ System collection: {tenants_collection}")
            
            # Add any other system collections here as needed
            # For example: audit_logs, system_config, etc.
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create system collections: {e}")
            return False
    
    def verify_initialization(self, admin_tenant: Dict[str, Any]) -> bool:
        """Verify that initialization was successful."""
        try:
            logger.info("Verifying initialization...")
            
            # Check admin tenant exists
            tenants = self.tenant_service.list_tenants()
            admin_exists = any(t["tenant_id"] == admin_tenant["tenant_id"] for t in tenants)
            
            if not admin_exists:
                logger.error("❌ Admin tenant not found in verification")
                return False
            
            # Check admin tenant collection exists
            collection_name = self.vector_manager.get_collection_name_for_tenant(admin_tenant["tenant_id"])
            collection_info = self.vector_manager.client.get_collection(collection_name)
            
            if not collection_info:
                logger.error(f"❌ Admin tenant collection not found: {collection_name}")
                return False
            
            # Check system collections
            tenants_collection = self.vector_manager.client.get_collection("tenants_metadata")
            if not tenants_collection:
                logger.error("❌ Tenants metadata collection not found")
                return False
            
            logger.info("✅ All verifications passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Verification failed: {e}")
            return False
    
    def print_summary(self, admin_tenant: Dict[str, Any]):
        """Print initialization summary."""
        print("\n" + "=" * 50)
        print("🎉 QDRANT DATABASE INITIALIZATION COMPLETE")
        print("=" * 50)
        print(f"Admin Tenant ID: {admin_tenant['tenant_id']}")
        print(f"Admin Tenant Name: {admin_tenant['name']}")
        
        if admin_tenant['api_key'] != "EXISTING_KEY":
            print(f"Admin API Key: {admin_tenant['api_key']}")
            print("\n⚠️  IMPORTANT: Save this API key securely!")
            print("   You'll need it to access the admin tenant.")
        
        print("\nCollections Created:")
        print(f"  - tenants_metadata (system)")
        print(f"  - {self.vector_manager.get_collection_name_for_tenant(admin_tenant['tenant_id'])} (admin tenant)")
        
        print("\nNext Steps:")
        print("  1. Use the admin API key in your frontend configuration")
        print("  2. Start the backend server: python scripts/run_backend.py")
        print("  3. Start the frontend: .\\scripts\\run_frontend.ps1")
        print("  4. Upload documents and start querying!")
        print("=" * 50)
    
    def check_and_prompt_reset(self) -> bool:
        """Check if data exists and prompt user to reset if so."""
        collections = self.vector_manager.client.get_collections().collections
        # Exclude system collections (tenants_metadata)
        user_collections = [c for c in collections if c.name != "tenants_metadata"]
        if collections and (len(collections) > 1 or (collections and collections[0].name != "tenants_metadata")):
            print("\n⚠️  Data already exists in Qdrant:")
            for c in collections:
                print(f"  - {c.name}")
            response = input("\nDo you want to DELETE ALL DATA and reset the database? (y/n): ").strip().lower()
            if response == "y":
                print("\nDeleting all collections...")
                for c in collections:
                    self.vector_manager.client.delete_collection(collection_name=c.name)
                    print(f"  Deleted: {c.name}")
                print("All collections deleted. Proceeding with initialization.\n")
                return True
            else:
                print("Aborting initialization. No changes made.")
                return False
        return True
    
    def run(self) -> bool:
        """Run the complete initialization process."""
        self.print_banner()
        
        # Step 0: Check for existing data and prompt for reset
        if not self.check_and_prompt_reset():
            return False
        
        # Step 1: Check connection
        if not self.check_qdrant_connection():
            return False
        
        # Step 2: Create system collections
        if not self.create_system_collections():
            return False
        
        # Step 3: Create admin tenant
        try:
            admin_tenant = self.create_admin_tenant()
        except Exception as e:
            logger.error(f"Failed to create admin tenant: {e}")
            return False
        
        # Step 4: Create tenant collections
        if not self.create_tenant_collections(admin_tenant["tenant_id"]):
            return False
        
        # Step 5: Verify initialization
        if not self.verify_initialization(admin_tenant):
            return False
        
        # Step 6: Print summary
        self.print_summary(admin_tenant)
        
        return True

def main():
    """Main entry point."""
    try:
        initializer = QdrantInitializer()
        success = initializer.run()
        
        if success:
            logger.info("✅ Database initialization completed successfully")
            sys.exit(0)
        else:
            logger.error("❌ Database initialization failed")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("\n🛑 Initialization interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error during initialization: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 