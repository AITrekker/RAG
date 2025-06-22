"""
Vector Store Management for the Enterprise RAG Platform.

This module provides an abstraction layer for interacting with the vector
database, which is powered by ChromaDB. It includes the `VectorStoreManager`
class, designed to handle all vector-related operations in a tenant-aware
manner, ensuring data isolation.

Key features:
- A `VectorStoreManager` that acts as a high-level interface to ChromaDB.
- Integration with the `TenantIsolationStrategy` to create and access
  tenant-specific collections using prefixed names (e.g., `tenant_abc_documents`).
- Methods for adding, searching, and deleting documents within a tenant's
  isolated collection.
- Utility functions for managing the lifecycle of collections (create, list, delete)
  and for retrieving database-wide statistics.
- A singleton pattern (`get_vector_store_manager`) to ensure a single,
  consistent connection to the database.
"""

import logging
import chromadb
from typing import Optional, Dict, Any, List
from pathlib import Path

from ..config.settings import settings
from ..core.tenant_isolation import get_tenant_isolation_strategy, TenantSecurityError

logger = logging.getLogger(__name__)


def get_chroma_client() -> chromadb.Client:
    """
    Get or create Chroma database client
    
    Returns:
        ChromaDB client instance
    """
    try:
        # Create persistent directory
        persist_dir = Path(settings.vector_store_path)
        persist_dir.mkdir(parents=True, exist_ok=True)
        
        # Create persistent Chroma client
        client = chromadb.PersistentClient(path=str(persist_dir))
        
        logger.info(f"Connected to Chroma database at: {persist_dir}")
        return client
        
    except Exception as e:
        logger.error(f"Failed to connect to Chroma database: {e}")
        raise


def create_tenant_collection(
    client: chromadb.Client,
    tenant_id: str,
    collection_name: Optional[str] = None
) -> chromadb.Collection:
    """
    Create or get a tenant-specific collection
    
    Args:
        client: Chroma client
        tenant_id: Tenant identifier
        collection_name: Optional custom collection name
        
    Returns:
        Chroma collection instance
    """
    if not collection_name:
        collection_name = f"tenant_{tenant_id}"
    
    try:
        # Get or create collection with tenant metadata
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={
                "tenant_id": tenant_id,
                "created_by": "rag_platform",
                "embedding_model": settings.embedding_model
            }
        )
        
        logger.info(f"Collection '{collection_name}' ready for tenant: {tenant_id}")
        return collection
        
    except Exception as e:
        logger.error(f"Failed to create collection for tenant {tenant_id}: {e}")
        raise


def list_tenant_collections(client: chromadb.Client, tenant_id: str) -> List[Dict[str, Any]]:
    """
    List all collections for a specific tenant
    
    Args:
        client: Chroma client
        tenant_id: Tenant identifier
        
    Returns:
        List of collection information
    """
    try:
        all_collections = client.list_collections()
        tenant_collections = []
        
        for collection in all_collections:
            metadata = collection.metadata or {}
            if metadata.get("tenant_id") == tenant_id:
                tenant_collections.append({
                    "name": collection.name,
                    "metadata": metadata,
                    "count": collection.count()
                })
        
        return tenant_collections
        
    except Exception as e:
        logger.error(f"Failed to list collections for tenant {tenant_id}: {e}")
        raise


def delete_tenant_collection(
    client: chromadb.Client,
    tenant_id: str,
    collection_name: Optional[str] = None
) -> bool:
    """
    Delete a tenant's collection
    
    Args:
        client: Chroma client
        tenant_id: Tenant identifier
        collection_name: Optional specific collection name
        
    Returns:
        True if deleted successfully
    """
    if not collection_name:
        collection_name = f"tenant_{tenant_id}"
    
    try:
        # Verify this collection belongs to the tenant
        collection = client.get_collection(collection_name)
        metadata = collection.metadata or {}
        
        if metadata.get("tenant_id") != tenant_id:
            raise ValueError(f"Collection {collection_name} does not belong to tenant {tenant_id}")
        
        # Delete the collection
        client.delete_collection(collection_name)
        
        logger.info(f"Deleted collection '{collection_name}' for tenant: {tenant_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to delete collection for tenant {tenant_id}: {e}")
        return False


class VectorStoreManager:
    """
    High-level manager for Chroma database operations, now tenant-aware.
    """
    
    def __init__(self):
        """Initialize the manager."""
        self.client = get_chroma_client()
        self.isolation_strategy = get_tenant_isolation_strategy()
        
    def get_collection_for_tenant(
        self,
        tenant_id: str,
        collection_name: Optional[str] = "documents"
    ) -> chromadb.Collection:
        """Get or create a tenant-specific collection."""
        if not tenant_id:
            raise TenantSecurityError("No tenant ID provided for vector store operation.")
        
        try:
            vector_config = self.isolation_strategy.get_vector_store_strategy(tenant_id)
        except ValueError as e:
            if "not registered" in str(e):
                # Auto-register tenant with default settings
                from ..core.tenant_isolation import TenantTier
                logger.info(f"Auto-registering tenant '{tenant_id}' for vector store access")
                self.isolation_strategy.register_tenant(tenant_id, TenantTier.BASIC)
                vector_config = self.isolation_strategy.get_vector_store_strategy(tenant_id)
            else:
                raise
        
        scoped_collection_name = f"{vector_config['collection_prefix']}{collection_name}"
        
        return create_tenant_collection(self.client, tenant_id, scoped_collection_name)

    def add_documents(
        self,
        tenant_id: str,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
        collection_name: str = "documents"
    ):
        """Add documents to a tenant's collection."""
        collection = self.get_collection_for_tenant(tenant_id, collection_name)
        
        # Ensure all metadata includes the tenant_id for verification
        if metadatas:
            for meta in metadatas:
                meta['tenant_id'] = tenant_id
        else:
            metadatas = [{'tenant_id': tenant_id} for _ in documents]
            
        collection.add(documents=documents, metadatas=metadatas, ids=ids)

    def similarity_search(
        self,
        tenant_id: str,
        query_embedding: List[float],
        top_k: int = 5,
        collection_name: str = "documents",
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Perform a similarity search within a tenant's collection."""
        collection = self.get_collection_for_tenant(tenant_id, collection_name)
        
        # Enforce tenant isolation at the filter level
        where_clause = {"tenant_id": tenant_id}
        if filter_metadata:
            where_clause.update(filter_metadata)
            
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_clause
        )
        return results

    def delete_documents(self, tenant_id: str, ids: List[str], collection_name: str = "documents"):
        """Delete documents from a tenant's collection."""
        collection = self.get_collection_for_tenant(tenant_id, collection_name)
        # We might add a check here to ensure the documents belong to the tenant
        # before deletion, but for now, the collection scoping is sufficient.
        collection.delete(ids=ids)

    def list_tenant_data(self, tenant_id: str) -> Dict[str, Any]:
        """Get comprehensive tenant data info"""
        collections = list_tenant_collections(self.client, tenant_id)
        
        total_documents = sum(col["count"] for col in collections)
        
        return {
            "tenant_id": tenant_id,
            "collections": collections,
            "total_collections": len(collections),
            "total_documents": total_documents
        }
    
    def cleanup_tenant_data(self, tenant_id: str) -> Dict[str, Any]:
        """Clean up all data for a tenant"""
        collections = list_tenant_collections(self.client, tenant_id)
        deleted_collections = []
        
        for collection_info in collections:
            if delete_tenant_collection(self.client, tenant_id, collection_info["name"]):
                deleted_collections.append(collection_info["name"])
        
        return {
            "tenant_id": tenant_id,
            "deleted_collections": deleted_collections,
            "total_deleted": len(deleted_collections)  
        }
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get overall database statistics"""
        try:
            all_collections = self.client.list_collections()
            
            stats = {
                "total_collections": len(all_collections),
                "tenants": {},
                "total_documents": 0
            }
            
            for collection in all_collections:
                metadata = collection.metadata or {}
                tenant_id = metadata.get("tenant_id", "unknown")
                count = collection.count()
                
                if tenant_id not in stats["tenants"]:
                    stats["tenants"][tenant_id] = {
                        "collections": 0,
                        "documents": 0
                    }
                
                stats["tenants"][tenant_id]["collections"] += 1
                stats["tenants"][tenant_id]["documents"] += count
                stats["total_documents"] += count
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {"error": str(e)}


# Global manager instance
_vector_store_manager: Optional[VectorStoreManager] = None


def get_vector_store_manager() -> VectorStoreManager:
    """Get the singleton instance of the VectorStoreManager."""
    global _vector_store_manager
    
    if _vector_store_manager is None:
        _vector_store_manager = VectorStoreManager()
    
    return _vector_store_manager 