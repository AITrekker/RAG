import logging
import uuid
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any

from qdrant_client import QdrantClient, models

from ..config.settings import get_settings
from ..utils.vector_store import get_vector_store_manager

logger = logging.getLogger(__name__)
settings = get_settings()

TENANTS_COLLECTION_NAME = "tenants_metadata"

class TenantService:
    """A service for managing tenants and API keys in Qdrant."""

    def __init__(self):
        self.vector_manager = get_vector_store_manager()
        self.client = self.vector_manager.client
        # Ensure the global tenants collection exists. It doesn't need real vectors.
        self.vector_manager.ensure_collection_exists(TENANTS_COLLECTION_NAME, vector_size=1)

    def _generate_api_key(self) -> Tuple[str, str, str]:
        """Generates a new API key, its hash, and its prefix."""
        key_bytes = secrets.token_bytes(32)
        full_key = key_bytes.hex()
        key_prefix = full_key[:8]
        key_hash = hashlib.sha256(full_key.encode()).hexdigest()
        return full_key, key_hash, key_prefix

    def create_tenant(self, name: str, description: Optional[str] = "") -> Dict:
        """Creates a new tenant and a default API key."""
        tenant_id = str(uuid.uuid4())
        api_key, api_key_hash, api_key_prefix = self._generate_api_key()

        tenant_payload = {
            "name": name,
            "description": description,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "api_keys": [
                {
                    "key_hash": api_key_hash,
                    "key_prefix": api_key_prefix,
                    "name": "Default Key",
                    "is_active": True,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "expires_at": None,
                }
            ],
        }

        self.client.upsert(
            collection_name=TENANTS_COLLECTION_NAME,
            points=[models.PointStruct(id=tenant_id, payload=tenant_payload, vector=[0.0])],
            wait=True,
        )
        logger.info(f"Successfully created tenant '{name}' with ID: {tenant_id}")
        return {"tenant_id": tenant_id, "api_key": api_key}

    def get_all_tenants(self) -> List[Dict]:
        """Retrieves a list of all tenants."""
        points, _ = self.client.scroll(
            collection_name=TENANTS_COLLECTION_NAME,
            limit=100,  # Adjust limit as needed
            with_payload=True,
            with_vectors=False,
        )
        
        tenants = []
        for point in points:
            # We don't need to return all the details for the list view
            tenants.append({
                "tenant_id": point.id,
                # In a real app, you might add a 'name' or other fields
                "object_count": self.vector_manager.get_collection_info(point.id).get("points_count", 0)
            })
        return tenants

    def create_api_key(self, tenant_id: str, name: str = "New Key") -> str:
        """Generates and adds a new API key for a specified tenant."""
        tenant_point = self.client.retrieve(collection_name=TENANTS_COLLECTION_NAME, ids=[tenant_id])
        if not tenant_point:
            raise ValueError("Tenant not found")

        tenant_payload = tenant_point[0].payload
        api_key, api_key_hash, api_key_prefix = self._generate_api_key()

        new_key_info = {
            "key_hash": api_key_hash,
            "key_prefix": api_key_prefix,
            "name": name,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": None,
        }
        
        if "api_keys" not in tenant_payload or not tenant_payload["api_keys"]:
            tenant_payload["api_keys"] = []
        
        tenant_payload["api_keys"].append(new_key_info)
        
        self.client.set_payload(
            collection_name=TENANTS_COLLECTION_NAME,
            payload=tenant_payload,
            points=[tenant_id],
            wait=True,
        )
        logger.info(f"Successfully created new API key for tenant {tenant_id}")
        return api_key

    def validate_api_key(self, api_key: str) -> Optional[Dict]:
        """Validates an API key and returns the associated tenant data."""
        if not api_key:
            return None
        
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Scroll through all tenants to find a matching key hash
        # This is not performant for many tenants, but is a start.
        # A real implementation might use a different DB or indexing strategy for this.
        scroll_result, _ = self.client.scroll(
            collection_name=TENANTS_COLLECTION_NAME,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="api_keys.key_hash",  # Note: This requires Qdrant 1.1+ for nested filtering
                        match=models.MatchValue(value=key_hash),
                    )
                ]
            ),
            limit=1,
        )

        if not scroll_result:
            return None

        tenant_point = scroll_result[0]
        tenant_data = tenant_point.payload
        
        # Find the specific key and check its status
        for key_info in tenant_data.get("api_keys", []):
            if key_info.get("key_hash") == key_hash:
                if not key_info.get("is_active"):
                    logger.warning(f"Inactive API key used for tenant {tenant_point.id}")
                    return None
                
                # Check for expiration
                expires_at_str = key_info.get("expires_at")
                if expires_at_str and datetime.fromisoformat(expires_at_str) < datetime.now(timezone.utc):
                    logger.warning(f"Expired API key used for tenant {tenant_point.id}")
                    return None
                
                # Return the full tenant payload if valid
                return {"id": tenant_point.id, **tenant_data}

        return None

    def list_tenants(self) -> List[Dict[str, Any]]:
        """
        Lists all tenants, formatting them for the API response model.
        This method explicitly omits sensitive data like API key hashes.
        """
        try:
            scroll_response, _ = self.client.scroll(
                collection_name=TENANTS_COLLECTION_NAME,
                limit=100,
                with_payload=True,
                with_vectors=False,
            )
            
            tenants_for_api = []
            for point in scroll_response:
                payload = point.payload
                
                # Explicitly construct the API keys list, omitting the hash
                api_keys_for_api = []
                if "api_keys" in payload and payload["api_keys"]:
                    for key_info in payload["api_keys"]:
                        api_keys_for_api.append({
                            "key_prefix": key_info.get("key_prefix"),
                            "name": key_info.get("name"),
                            "is_active": key_info.get("is_active"),
                            "created_at": key_info.get("created_at"),
                            "expires_at": key_info.get("expires_at"),
                        })

                tenants_for_api.append({
                    "tenant_id": point.id,
                    "name": payload.get("name"),
                    "description": payload.get("description"),
                    "status": payload.get("status"),
                    "created_at": payload.get("created_at"),
                    "api_keys": api_keys_for_api,
                })
            return tenants_for_api
            
        except Exception as e:
            logger.error(f"Could not list tenants due to an unexpected error: {e}", exc_info=True)
            return []

    def get_api_key_hash(self, tenant_id: str) -> Optional[str]:
        """
        Retrieves the hashed API key for a given tenant.
        """
        tenant_point = self.client.retrieve(collection_name=TENANTS_COLLECTION_NAME, ids=[tenant_id])
        if not tenant_point:
            return None

        tenant_payload = tenant_point[0].payload
        api_keys = tenant_payload.get("api_keys", [])
        if not api_keys:
            return None

        for key_info in api_keys:
            if key_info.get("is_active"):
                return key_info.get("key_hash")

        return None

def get_tenant_service() -> TenantService:
    """Factory function to get a singleton instance of the TenantService."""
    # In a real app, you might manage the lifecycle differently
    return TenantService() 