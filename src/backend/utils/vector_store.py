"""
Vector Store Management for the Enterprise RAG Platform using Qdrant.

This module provides a high-level abstraction for interacting with Qdrant,
the primary vector database. The VectorStoreManager handles all vector-related
operations, including creating tenant-specific collections, adding documents,
and performing similarity searches, ensuring strict data isolation.
"""

import logging
from typing import Optional, List, Dict, Any
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import Distance, VectorParams, PointStruct, UpdateStatus

from ..config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class VectorStoreManager:
    """
    Manages all interactions with the Qdrant vector database.
    """

    def __init__(self, qdrant_url: str = settings.qdrant_url, api_key: Optional[str] = settings.qdrant_api_key):
        """
        Initializes the Qdrant client.
        """
        try:
            self.client = QdrantClient(url=qdrant_url, api_key=api_key)
            logger.info("Successfully connected to Qdrant.")
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            raise

    def get_collection_for_tenant(self, tenant_id: str, embedding_size: int) -> str:
        """
        Ensures a collection exists for the given tenant. If not, it creates one.

        Args:
            tenant_id: The ID of the tenant.
            embedding_size: The dimension of the vectors to be stored.

        Returns:
            The name of the collection for the tenant.
        """
        collection_name = f"tenant_{tenant_id}_documents"
        try:
            self.client.get_collection(collection_name=collection_name)
            logger.debug(f"Collection '{collection_name}' already exists.")
        except Exception:
            logger.info(f"Collection '{collection_name}' not found. Creating new collection.")
            self.client.recreate_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=embedding_size, distance=Distance.COSINE),
            )
            logger.info(f"Successfully created collection '{collection_name}'.")
        return collection_name

    def add_documents(
        self,
        tenant_id: str,
        points: List[PointStruct],
        embedding_size: int,
    ):
        """
        Adds documents (as points) to a tenant's collection.

        Args:
            tenant_id: The ID of the tenant.
            points: A list of Qdrant PointStructs to add.
            embedding_size: The dimension of the vectors, used if collection needs creation.
        """
        collection_name = self.get_collection_for_tenant(tenant_id, embedding_size)
        
        operation_info = self.client.upsert(
            collection_name=collection_name,
            wait=True,
            points=points
        )
        if operation_info.status != UpdateStatus.COMPLETED:
            logger.error(f"Failed to add documents to collection '{collection_name}'.")

    def similarity_search(
        self,
        tenant_id: str,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[models.ScoredPoint]:
        """
        Performs a similarity search within a tenant's collection.

        Args:
            tenant_id: The ID of the tenant.
            query_embedding: The embedding of the query text.
            top_k: The number of results to return.
            filter_metadata: Qdrant filters to apply to the search.

        Returns:
            A list of search results.
        """
        collection_name = f"tenant_{tenant_id}_documents"
        
        search_results = self.client.search(
            collection_name=collection_name,
            query_vector=query_embedding,
            query_filter=models.Filter(**filter_metadata) if filter_metadata else None,
            limit=top_k,
            with_payload=True
        )
        return search_results

    def delete_documents(self, tenant_id: str, point_ids: List[str]):
        """
        Deletes documents from a tenant's collection by their point IDs.

        Args:
            tenant_id: The ID of the tenant.
            point_ids: A list of point IDs to delete.
        """
        collection_name = f"tenant_{tenant_id}_documents"
        
        self.client.delete(
            collection_name=collection_name,
            points_selector=models.PointIdsList(points=point_ids),
            wait=True,
        )

    def delete_tenant_collection(self, tenant_id: str) -> bool:
        """
        Deletes an entire collection for a tenant.

        Args:
            tenant_id: The ID of the tenant whose collection is to be deleted.
        
        Returns:
            True if deletion was successful, False otherwise.
        """
        collection_name = f"tenant_{tenant_id}_documents"
        try:
            result = self.client.delete_collection(collection_name=collection_name)
            if result:
                logger.info(f"Successfully deleted collection '{collection_name}'.")
            return result
        except Exception as e:
            logger.error(f"Error deleting collection '{collection_name}': {e}")
            return False

# Singleton instance of the VectorStoreManager
_vector_store_manager_instance: Optional[VectorStoreManager] = None

def get_vector_store_manager() -> VectorStoreManager:
    """

    Returns a singleton instance of the VectorStoreManager.
    """
    global _vector_store_manager_instance
    if _vector_store_manager_instance is None:
        _vector_store_manager_instance = VectorStoreManager()
    return _vector_store_manager_instance 