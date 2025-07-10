"""
Vector Store Management for the Enterprise RAG Platform using Qdrant.

This module provides a high-level abstraction for interacting with Qdrant,
with environment-separated collections for maximum isolation and safety.
Each environment (production, staging, test, development) has its own
collection, with tenant isolation via payload filtering.
"""

import logging
import os
from typing import Optional, List, Dict, Any
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import Distance, VectorParams, PointStruct, UpdateStatus

from ..config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Environment configuration
CURRENT_ENVIRONMENT = os.getenv("RAG_ENVIRONMENT", "development")
VALID_ENVIRONMENTS = ["production", "staging", "test", "development"]


class VectorStoreManager:
    """
    Manages all interactions with the Qdrant vector database with environment separation.
    """

    def __init__(self, 
                 qdrant_url: str = settings.qdrant_url, 
                 api_key: Optional[str] = settings.qdrant_api_key,
                 environment: str = None):
        """
        Initializes the Qdrant client with environment awareness.
        """
        try:
            self.client = QdrantClient(url=qdrant_url, api_key=api_key)
            self.environment = environment or CURRENT_ENVIRONMENT
            
            if self.environment not in VALID_ENVIRONMENTS:
                raise ValueError(f"Invalid environment: {self.environment}. Valid: {VALID_ENVIRONMENTS}")
                
            logger.info(f"Successfully connected to Qdrant (environment: {self.environment}).")
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            raise

    def get_collection_name(self, environment: str = None) -> str:
        """Get environment-specific collection name."""
        env = environment or self.environment
        return f"documents_{env}"

    def get_collection_for_environment(self, embedding_size: int, environment: str = None) -> models.CollectionInfo:
        """
        Retrieves or creates a Qdrant collection for a specific environment.
        """
        collection_name = self.get_collection_name(environment)
        self.ensure_collection_exists(collection_name, embedding_size)
        return self.client.get_collection(collection_name=collection_name)


    def add_documents(
        self,
        tenant_id: str,
        points: List[PointStruct],
        embedding_size: int,
        environment: str = None
    ):
        """
        Adds documents (as points) to an environment collection with tenant isolation.

        Args:
            tenant_id: The ID of the tenant.
            points: A list of Qdrant PointStructs to add (must include environment in payload).
            embedding_size: The dimension of the vectors, used if collection needs creation.
            environment: Target environment (defaults to current).
        """
        env = environment or self.environment
        collection_name = self.get_collection_name(env)
        
        # Ensure environment and tenant_id are in all point payloads
        for point in points:
            if point.payload is None:
                point.payload = {}
            point.payload["environment"] = env
            point.payload["tenant_id"] = str(tenant_id)
        
        self.ensure_collection_exists(collection_name, embedding_size)
        
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
        filter_metadata: Optional[Dict[str, Any]] = None,
        environment: str = None
    ) -> List[models.ScoredPoint]:
        """
        Performs a similarity search within an environment collection, filtered by tenant.

        Args:
            tenant_id: The ID of the tenant.
            query_embedding: The embedding of the query text.
            top_k: The number of results to return.
            filter_metadata: Additional Qdrant filters to apply to the search.
            environment: Target environment (defaults to current).

        Returns:
            A list of search results.
        """
        env = environment or self.environment
        collection_name = self.get_collection_name(env)
        
        # Build standardized filter for tenant and environment isolation
        tenant_filter = {
            "must": [
                {"key": "tenant_id", "match": {"value": str(tenant_id)}},
                {"key": "environment", "match": {"value": env}}
            ]
        }
        
        # Merge with additional filters if provided
        if filter_metadata:
            if "must" in filter_metadata:
                tenant_filter["must"].extend(filter_metadata["must"])
            if "should" in filter_metadata:
                tenant_filter["should"] = filter_metadata["should"]
            if "must_not" in filter_metadata:
                tenant_filter["must_not"] = filter_metadata["must_not"]
        
        search_results = self.client.search(
            collection_name=collection_name,
            query_vector=query_embedding,
            query_filter=models.Filter(**tenant_filter),
            limit=top_k,
            with_payload=True
        )
        return search_results

    def delete_documents(self, tenant_id: str, point_ids: List[str], environment: str = None):
        """
        Deletes documents from environment collection by their point IDs with tenant filtering.

        Args:
            tenant_id: The ID of the tenant.
            point_ids: A list of point IDs to delete.
            environment: Target environment (defaults to current).
        """
        env = environment or self.environment
        collection_name = self.get_collection_name(env)
        
        self.client.delete(
            collection_name=collection_name,
            points_selector=models.PointIdsList(points=point_ids),
            wait=True,
        )
        logger.info(f"Deleted {len(point_ids)} points from collection '{collection_name}'.")

    def delete_documents_by_path(self, tenant_id: str, file_path: str, environment: str = None):
        """Deletes all points associated with a specific file_path from environment collection."""
        env = environment or self.environment
        collection_name = self.get_collection_name(env)
        logger.info(f"Attempting to delete all points for file '{file_path}' from collection '{collection_name}'.")

        # Use standardized filter with tenant isolation and direct file_path field
        must_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="tenant_id",
                    match=models.MatchValue(value=str(tenant_id))
                ),
                models.FieldCondition(
                    key="environment",
                    match=models.MatchValue(value=env)
                ),
                models.FieldCondition(
                    key="file_path",
                    match=models.MatchValue(value=file_path)
                )
            ]
        )

        self.client.delete(
            collection_name=collection_name,
            points_selector=must_filter,
        )
        logger.info(f"Delete operation completed for file '{file_path}' in collection '{collection_name}'.")

    def ensure_collection_exists(self, collection_name: str, vector_size: int):
        """Creates a collection if it doesn't already exist."""
        try:
            self.client.get_collection(collection_name=collection_name)
        except Exception:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE)
            )
            logger.info(f"Created new collection: {collection_name}")


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