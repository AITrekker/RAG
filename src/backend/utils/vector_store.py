"""
Vector Store Utilities for RAG Platform
Chroma database integration with multi-tenant support
"""

import logging
import chromadb
from typing import Optional, Dict, Any, List
from pathlib import Path

from ..config.settings import settings

logger = logging.getLogger(__name__)


def get_chroma_client() -> chromadb.Client:
    """
    Get or create Chroma database client
    
    Returns:
        ChromaDB client instance
    """
    try:
        # Create persistent directory
        persist_dir = Path(settings.vector_store.chroma_persist_directory)
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
        collection_name = f"{settings.vector_store.collection_name_prefix}_{tenant_id}"
    
    try:
        # Get or create collection with tenant metadata
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={
                "tenant_id": tenant_id,
                "created_by": "rag_platform",
                "embedding_model": settings.embedding.model_name
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
        collection_name = f"{settings.vector_store.collection_name_prefix}_{tenant_id}"
    
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


class ChromaManager:
    """
    High-level manager for Chroma database operations
    """
    
    def __init__(self):
        """Initialize Chroma manager"""
        self.client = get_chroma_client()
        
    def get_collection_for_tenant(
        self,
        tenant_id: str,
        collection_name: Optional[str] = None
    ) -> chromadb.Collection:
        """Get or create collection for tenant"""
        return create_tenant_collection(self.client, tenant_id, collection_name)
    
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
_chroma_manager: Optional[ChromaManager] = None


def get_chroma_manager() -> ChromaManager:
    """
    Get global Chroma manager instance
    
    Returns:
        ChromaManager instance
    """
    global _chroma_manager
    
    if _chroma_manager is None:
        _chroma_manager = ChromaManager()
    
    return _chroma_manager 