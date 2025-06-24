import os
import sys
from pathlib import Path
import logging

# Add project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from src.backend.core.tenant_service import get_tenant_service, TenantService
from src.backend.utils.vector_store import get_vector_store_manager, VectorStoreManager
from src.backend.config.settings import get_settings

def main():
    """
    Seeds the Qdrant instance with initial data. It ensures a default tenant
    exists and has a document collection ready. This script is idempotent.
    """
    print("🚀 Starting data seeding script...")

    try:
        settings = get_settings()
        tenant_service = get_tenant_service()
        vector_manager = get_vector_store_manager()
        
        tenant_name = "Default Tenant"
        target_tenant_id = None
        
        # --- Check for existing tenant ---
        print(f"Checking for existing tenant: '{tenant_name}'...")
        existing_tenants = tenant_service.list_tenants()
        found_tenant = next((t for t in existing_tenants if t.get("name") == tenant_name), None)

        if found_tenant:
            target_tenant_id = found_tenant["tenant_id"]
            print(f"✅ Tenant '{tenant_name}' already exists with ID: {target_tenant_id}.")
            print("🔑 API key was set on creation. If you've lost it, you'll need to create a new one.")

        else:
            print(f"🔧 Tenant '{tenant_name}' not found. Creating now...")
            result = tenant_service.create_tenant(name=tenant_name)
            target_tenant_id = result["tenant_id"]
            api_key = result["api_key"]
            print("✅ Successfully created new tenant.")
            print("="*50)
            print(f"  Tenant ID: {target_tenant_id}")
            print(f"  API Key:   {api_key}")
            print("="*50)
            print("⬆️  Please use this API key in the frontend UI. ⬆️")

        # --- Ensure a document collection exists for the tenant ---
        if target_tenant_id:
            print(f"\nEnsuring document collection exists for tenant {target_tenant_id}...")
            # Use the correct, high-level method to create the collection.
            # This method handles naming conventions and creation logic internally.
            collection_info = vector_manager.get_collection_for_tenant(
                tenant_id=target_tenant_id,
                embedding_size=settings.embedding_model_dimensions  # Get size from settings
            )
            collection_name = vector_manager.get_collection_name_for_tenant(target_tenant_id)
            print(f"✅ Document collection '{collection_name}' is ready.")
        else:
            logger.error("Could not determine a tenant ID. Skipping collection creation.")


    except Exception as e:
        print(f"❌ An error occurred during seeding: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n✅ Data seeding complete.")

if __name__ == "__main__":
    main() 