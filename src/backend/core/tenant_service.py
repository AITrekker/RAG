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
        """Creates a new tenant and a default API key, or returns existing if name exists."""
        # Check if tenant with this name already exists
        points, _ = self.client.scroll(
            collection_name=TENANTS_COLLECTION_NAME,
            scroll_filter=models.Filter(
                must=[models.FieldCondition(
                    key="name",
                    match=models.MatchValue(value=name)
                )]
            ),
            limit=1,
            with_payload=True,
            with_vectors=False,
        )
        if points:
            # Tenant exists, return its info and first API key
            tenant_point = points[0]
            tenant_id = tenant_point.id
            payload = tenant_point.payload
            api_keys = payload.get("api_keys", [])
            if api_keys:
                # Return the first active API key
                for key_info in api_keys:
                    if key_info.get("is_active"):
                        # We cannot return the raw API key, only the hash is stored
                        # So, we should generate a new API key for the admin if needed
                        break
                else:
                    # No active key, generate a new one
                    api_key = self.create_api_key(tenant_id, name="Default Key")
                    return {"tenant_id": tenant_id, "api_key": api_key}
                # If we want to always generate a new key, uncomment below
                # api_key = self.create_api_key(tenant_id, name="Default Key")
                # return {"tenant_id": tenant_id, "api_key": api_key}
                # Otherwise, just return the prefix and warn
                return {"tenant_id": tenant_id, "api_key": "EXISTS"}
            else:
                # No API keys, generate one
                api_key = self.create_api_key(tenant_id, name="Default Key")
                return {"tenant_id": tenant_id, "api_key": api_key}
        # If not found, create new tenant
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
                "name": point.payload.get("name", "Unknown"),
                "description": point.payload.get("description", ""),
                "status": point.payload.get("status", "unknown"),
                "created_at": point.payload.get("created_at", ""),
                "api_keys_count": len(point.payload.get("api_keys", []))
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

        # Get all tenants and check their API keys manually
        # This is more reliable than nested filtering
        scroll_result, _ = self.client.scroll(
            collection_name=TENANTS_COLLECTION_NAME,
            limit=100,  # Adjust limit as needed
            with_payload=True,
            with_vectors=False,
        )

        for tenant_point in scroll_result:
            tenant_data = tenant_point.payload
            
            # Check each API key in this tenant
            for key_info in tenant_data.get("api_keys", []):
                if key_info.get("key_hash") == key_hash:
                    # Found matching key, check if it's active
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
                    for i, key_info in enumerate(payload["api_keys"]):
                        api_keys_for_api.append({
                            "id": f"{key_info.get('key_prefix')}_{i}",
                            "name": key_info.get("name"),
                            "key_prefix": key_info.get("key_prefix"),
                            "is_active": key_info.get("is_active"),
                            "created_at": datetime.fromisoformat(key_info.get("created_at")) if key_info.get("created_at") else datetime.now(),
                            "expires_at": datetime.fromisoformat(key_info.get("expires_at")) if key_info.get("expires_at") else None,
                        })

                tenants_for_api.append({
                    "id": point.id,
                    "name": payload.get("name"),
                    "description": payload.get("description"),
                    "status": payload.get("status", "active"),
                    "created_at": datetime.fromisoformat(payload.get("created_at")) if payload.get("created_at") else datetime.now(),
                    "auto_sync": payload.get("auto_sync", True),
                    "sync_interval": payload.get("sync_interval", 60),
                    "api_keys": api_keys_for_api,
                    "document_count": 0,  # TODO: Implement document counting
                    "storage_used_mb": 0.0,  # TODO: Implement storage calculation
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

    def list_api_keys(self, tenant_id: str) -> List[Dict]:
        """
        Lists all API keys for a given tenant.
        """
        tenant_point = self.client.retrieve(collection_name=TENANTS_COLLECTION_NAME, ids=[tenant_id])
        if not tenant_point:
            return []

        tenant_payload = tenant_point[0].payload
        api_keys = tenant_payload.get("api_keys", [])
        
        # Return API keys in the format expected by ApiKeyResponse
        return [
            {
                "id": f"{key_info.get('key_prefix')}_{i}",
                "name": key_info.get("name"),
                "key_prefix": key_info.get("key_prefix"),
                "is_active": key_info.get("is_active"),
                "created_at": datetime.fromisoformat(key_info.get("created_at")) if key_info.get("created_at") else datetime.now(),
                "expires_at": datetime.fromisoformat(key_info.get("expires_at")) if key_info.get("expires_at") else None,
            }
            for i, key_info in enumerate(api_keys)
        ]

    def get_tenant(self, tenant_id: str) -> Optional[Dict]:
        """
        Gets a specific tenant by ID.
        """
        tenant_point = self.client.retrieve(collection_name=TENANTS_COLLECTION_NAME, ids=[tenant_id])
        if not tenant_point:
            return None

        tenant_payload = tenant_point[0].payload
        
        # Format API keys for API response
        api_keys_for_api = []
        if "api_keys" in tenant_payload and tenant_payload["api_keys"]:
            for i, key_info in enumerate(tenant_payload["api_keys"]):
                api_keys_for_api.append({
                    "id": f"{key_info.get('key_prefix')}_{i}",
                    "name": key_info.get("name"),
                    "key_prefix": key_info.get("key_prefix"),
                    "is_active": key_info.get("is_active"),
                    "created_at": datetime.fromisoformat(key_info.get("created_at")) if key_info.get("created_at") else datetime.now(),
                    "expires_at": datetime.fromisoformat(key_info.get("expires_at")) if key_info.get("expires_at") else None,
                })
        
        return {
            "id": tenant_id,
            "name": tenant_payload.get("name"),
            "description": tenant_payload.get("description"),
            "status": tenant_payload.get("status", "active"),
            "created_at": datetime.fromisoformat(tenant_payload.get("created_at")) if tenant_payload.get("created_at") else datetime.now(),
            "auto_sync": tenant_payload.get("auto_sync", True),
            "sync_interval": tenant_payload.get("sync_interval", 60),
            "api_keys": api_keys_for_api,
            "document_count": 0,  # TODO: Implement document counting
            "storage_used_mb": 0.0,  # TODO: Implement storage calculation
        }

    def update_tenant(self, tenant_id: str, name: str = None, description: str = None, 
                     status: str = None, auto_sync: bool = None, sync_interval: int = None) -> Dict:
        """
        Updates a tenant's information.
        """
        tenant_point = self.client.retrieve(collection_name=TENANTS_COLLECTION_NAME, ids=[tenant_id])
        if not tenant_point:
            raise ValueError("Tenant not found")

        tenant_payload = tenant_point[0].payload
        
        # Update only provided fields
        if name is not None:
            tenant_payload["name"] = name
        if description is not None:
            tenant_payload["description"] = description
        if status is not None:
            tenant_payload["status"] = status
        if auto_sync is not None:
            tenant_payload["auto_sync"] = auto_sync
        if sync_interval is not None:
            tenant_payload["sync_interval"] = sync_interval

        self.client.set_payload(
            collection_name=TENANTS_COLLECTION_NAME,
            payload=tenant_payload,
            points=[tenant_id],
            wait=True,
        )
        
        return self.get_tenant(tenant_id)

    def delete_tenant(self, tenant_id: str) -> bool:
        """
        Deletes a tenant.
        """
        tenant_point = self.client.retrieve(collection_name=TENANTS_COLLECTION_NAME, ids=[tenant_id])
        if not tenant_point:
            raise ValueError("Tenant not found")

        self.client.delete(
            collection_name=TENANTS_COLLECTION_NAME,
            points_selector=[tenant_id],
            wait=True,
        )
        
        return True

    def delete_api_key(self, tenant_id: str, key_id: str) -> bool:
        """
        Deletes an API key for a tenant.
        """
        tenant_point = self.client.retrieve(collection_name=TENANTS_COLLECTION_NAME, ids=[tenant_id])
        if not tenant_point:
            raise ValueError("Tenant not found")

        tenant_payload = tenant_point[0].payload
        api_keys = tenant_payload.get("api_keys", [])
        
        # Find and remove the key
        key_prefix = key_id.split("_")[0] if "_" in key_id else key_id
        api_keys = [key for key in api_keys if key.get("key_prefix") != key_prefix]
        
        tenant_payload["api_keys"] = api_keys
        
        self.client.set_payload(
            collection_name=TENANTS_COLLECTION_NAME,
            payload=tenant_payload,
            points=[tenant_id],
            wait=True,
        )
        
        return True

def get_tenant_service() -> TenantService:
    """Factory function to get a singleton instance of the TenantService."""
    # In a real app, you might manage the lifecycle differently
    return TenantService() 