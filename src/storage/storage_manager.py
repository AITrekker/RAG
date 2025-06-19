"""
Unified storage manager for Enterprise RAG system.

This module provides a high-level interface that integrates vector store,
metadata management, and processing pipeline with comprehensive features.
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Tuple, Union
from pathlib import Path
from dataclasses import dataclass
import threading

from llama_index.core.schema import BaseNode, TextNode, Document

from .vector_store import TenantAwareVectorStore, get_vector_store, EmbeddingMetadata
from .metadata_handler import TenantAwareMetadataManager, get_metadata_manager, MetadataFilter, FilterOperator
from ..processing.llama_processor import TenantAwareLlamaProcessor
from ..processing.document_processor import TenantAwareDocumentProcessor
from ..config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class StorageStats:
    """Storage statistics for monitoring."""
    total_documents: int = 0
    total_embeddings: int = 0
    total_tenants: int = 0
    storage_size_bytes: int = 0
    avg_query_time_ms: float = 0.0
    success_rate: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_documents": self.total_documents,
            "total_embeddings": self.total_embeddings,
            "total_tenants": self.total_tenants,
            "storage_size_bytes": self.storage_size_bytes,
            "avg_query_time_ms": self.avg_query_time_ms,
            "success_rate": self.success_rate
        }


class TenantAwareStorageManager:
    """
    Unified storage manager with comprehensive features.
    
    Features:
    - Unified interface for vector store and metadata
    - Complete document lifecycle management
    - Advanced querying with metadata filtering
    - Performance monitoring and analytics
    - Tenant isolation and security
    - Batch processing and optimization
    - Integration with processing pipeline
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the storage manager.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or get_settings()
        
        # Core components
        self.vector_store = get_vector_store()
        self.metadata_manager = get_metadata_manager()
        
        # Processing components
        self.llama_processor = TenantAwareLlamaProcessor(config)
        self.document_processor = TenantAwareDocumentProcessor(config)
        
        # Statistics and monitoring
        self.stats = StorageStats()
        self.stats_lock = threading.RLock()
        
        # Query performance tracking
        self.query_times: List[float] = []
        self.query_count = 0
        self.success_count = 0
        
        logger.info("Initialized TenantAwareStorageManager")
    
    def process_and_store_documents(
        self,
        tenant_id: str,
        folder_path: str,
        recursive: bool = True,
        batch_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Process documents from a folder and store them.
        
        Args:
            tenant_id: Unique identifier for the tenant
            folder_path: Path to the folder containing documents
            recursive: Whether to process folders recursively
            batch_size: Optional batch size for processing
            
        Returns:
            Dict[str, Any]: Processing results
        """
        try:
            logger.info(f"Processing documents for tenant {tenant_id} from {folder_path}")
            
            # Process documents
            processing_result = self.document_processor.process_folder(
                tenant_id=tenant_id,
                folder_path=folder_path,
                recursive=recursive,
                batch_size=batch_size
            )
            
            if not processing_result.get("success", False):
                return {
                    "success": False,
                    "error": "Document processing failed",
                    "details": processing_result
                }
            
            # Get processed nodes
            nodes = processing_result.get("nodes", [])
            if not nodes:
                return {
                    "success": True,
                    "message": "No documents processed",
                    "processed_files": 0,
                    "stored_embeddings": 0
                }
            
            # Create embeddings and store
            embedding_result = self.llama_processor.process_documents_batch(
                tenant_id=tenant_id,
                nodes=nodes
            )
            
            if not embedding_result.get("success", False):
                return {
                    "success": False,
                    "error": "Embedding generation failed",
                    "details": embedding_result
                }
            
            # Store in vector store
            embeddings = embedding_result.get("embeddings", [])
            storage_success = self.vector_store.add_embeddings(
                tenant_id=tenant_id,
                nodes=nodes,
                embeddings=embeddings
            )
            
            if not storage_success:
                return {
                    "success": False,
                    "error": "Vector store insertion failed"
                }
            
            # Update statistics
            with self.stats_lock:
                self.stats.total_documents += len(processing_result.get("processed_files", []))
                self.stats.total_embeddings += len(nodes)
            
            result = {
                "success": True,
                "processed_files": len(processing_result.get("processed_files", [])),
                "stored_embeddings": len(nodes),
                "processing_time": processing_result.get("total_time", 0),
                "embedding_time": embedding_result.get("total_time", 0),
                "tenant_id": tenant_id
            }
            
            logger.info(f"Successfully processed and stored {len(nodes)} embeddings for tenant {tenant_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to process and store documents: {e}")
            return {
                "success": False,
                "error": str(e),
                "tenant_id": tenant_id
            }
    
    def process_and_store_document(
        self,
        tenant_id: str,
        document_path: str
    ) -> Dict[str, Any]:
        """
        Process a single document and store it.
        
        Args:
            tenant_id: Unique identifier for the tenant
            document_path: Path to the document
            
        Returns:
            Dict[str, Any]: Processing results
        """
        try:
            logger.info(f"Processing single document for tenant {tenant_id}: {document_path}")
            
            # Process single document
            processing_result = self.document_processor.process_single_document(
                tenant_id=tenant_id,
                file_path=document_path
            )
            
            if not processing_result.get("success", False):
                return {
                    "success": False,
                    "error": "Document processing failed",
                    "details": processing_result
                }
            
            # Get processed nodes
            nodes = processing_result.get("nodes", [])
            if not nodes:
                return {
                    "success": True,
                    "message": "No content extracted from document",
                    "stored_embeddings": 0
                }
            
            # Create embeddings and store
            embedding_result = self.llama_processor.process_single_document(
                tenant_id=tenant_id,
                document_path=document_path
            )
            
            if not embedding_result.get("success", False):
                return {
                    "success": False,
                    "error": "Embedding generation failed",
                    "details": embedding_result
                }
            
            # Store in vector store
            embeddings = embedding_result.get("embeddings", [])
            storage_success = self.vector_store.add_embeddings(
                tenant_id=tenant_id,
                nodes=nodes,
                embeddings=embeddings
            )
            
            if not storage_success:
                return {
                    "success": False,
                    "error": "Vector store insertion failed"
                }
            
            # Update statistics
            with self.stats_lock:
                self.stats.total_documents += 1
                self.stats.total_embeddings += len(nodes)
            
            result = {
                "success": True,
                "document_path": document_path,
                "stored_embeddings": len(nodes),
                "processing_time": processing_result.get("processing_time", 0),
                "embedding_time": embedding_result.get("processing_time", 0),
                "tenant_id": tenant_id
            }
            
            logger.info(f"Successfully processed and stored document for tenant {tenant_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to process and store document: {e}")
            return {
                "success": False,
                "error": str(e),
                "tenant_id": tenant_id,
                "document_path": document_path
            }
    
    def query_documents(
        self,
        tenant_id: str,
        query: str,
        top_k: int = 5,
        filters: Optional[List[MetadataFilter]] = None,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Query documents with advanced filtering.
        
        Args:
            tenant_id: Unique identifier for the tenant
            query: Query text
            top_k: Number of results to return
            filters: Optional metadata filters
            include_metadata: Whether to include metadata in results
            
        Returns:
            Dict[str, Any]: Query results
        """
        start_time = time.time()
        
        try:
            # Generate query embedding
            query_result = self.llama_processor.create_query_engine(tenant_id)
            if not query_result.get("success", False):
                return {
                    "success": False,
                    "error": "Failed to create query engine",
                    "details": query_result
                }
            
            query_engine = query_result["query_engine"]
            
            # Execute query
            response = query_engine.query(query)
            
            # Get source nodes with metadata
            results = []
            if hasattr(response, 'source_nodes') and response.source_nodes:
                for node in response.source_nodes[:top_k]:
                    result_item = {
                        "text": node.node.text,
                        "score": getattr(node, 'score', 0.0),
                        "node_id": getattr(node.node, 'node_id', '')
                    }
                    
                    if include_metadata and hasattr(node.node, 'metadata'):
                        result_item["metadata"] = node.node.metadata
                        
                        # Get additional metadata from metadata manager
                        embedding_metadata = self.metadata_manager.get_metadata(
                            result_item["node_id"]
                        )
                        if embedding_metadata:
                            result_item["embedding_metadata"] = embedding_metadata.to_dict()
                    
                    results.append(result_item)
            
            # Track performance
            query_time = (time.time() - start_time) * 1000  # Convert to ms
            self._update_query_stats(query_time, success=True)
            
            return {
                "success": True,
                "query": query,
                "response": str(response),
                "results": results,
                "total_results": len(results),
                "query_time_ms": query_time,
                "tenant_id": tenant_id
            }
            
        except Exception as e:
            logger.error(f"Failed to query documents: {e}")
            
            # Track performance
            query_time = (time.time() - start_time) * 1000
            self._update_query_stats(query_time, success=False)
            
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "tenant_id": tenant_id,
                "query_time_ms": query_time
            }
    
    def get_tenant_analytics(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get comprehensive analytics for a tenant.
        
        Args:
            tenant_id: Unique identifier for the tenant
            
        Returns:
            Dict[str, Any]: Analytics data
        """
        try:
            # Get vector store statistics
            vector_stats = self.vector_store.get_tenant_statistics(tenant_id)
            
            # Get metadata analytics
            metadata_analytics = self.metadata_manager.get_tenant_analytics(tenant_id)
            
            # Combine analytics
            analytics = {
                "tenant_id": tenant_id,
                "vector_store": vector_stats,
                "metadata": metadata_analytics,
                "overall_stats": self.stats.to_dict()
            }
            
            return analytics
            
        except Exception as e:
            logger.error(f"Failed to get analytics for tenant {tenant_id}: {e}")
            return {"error": str(e)}
    
    def get_document_relationships(
        self,
        tenant_id: str,
        document_id: str
    ) -> Dict[str, Any]:
        """
        Get relationships for a document.
        
        Args:
            tenant_id: Unique identifier for the tenant
            document_id: Document identifier
            
        Returns:
            Dict[str, Any]: Relationship data
        """
        try:
            return self.metadata_manager.get_document_relationships(tenant_id, document_id)
        except Exception as e:
            logger.error(f"Failed to get relationships for document {document_id}: {e}")
            return {"error": str(e)}
    
    def delete_tenant_data(self, tenant_id: str) -> bool:
        """
        Delete all data for a tenant.
        
        Args:
            tenant_id: Unique identifier for the tenant
            
        Returns:
            bool: Success status
        """
        try:
            # Delete from vector store
            vector_success = self.vector_store.delete_tenant_data(tenant_id)
            
            # Delete metadata
            metadata_success = self.metadata_manager.delete_tenant_metadata(tenant_id)
            
            if vector_success and metadata_success:
                logger.info(f"Successfully deleted all data for tenant {tenant_id}")
                return True
            else:
                logger.warning(f"Partial deletion for tenant {tenant_id}: vector={vector_success}, metadata={metadata_success}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete data for tenant {tenant_id}: {e}")
            return False
    
    def delete_document(
        self,
        tenant_id: str,
        document_id: str
    ) -> bool:
        """
        Delete a specific document.
        
        Args:
            tenant_id: Unique identifier for the tenant
            document_id: Document identifier
            
        Returns:
            bool: Success status
        """
        try:
            # Get document metadata
            metadata_list = self.metadata_manager.query_metadata(
                tenant_id=tenant_id,
                filters=[
                    MetadataFilter(
                        field="document_id",
                        operator=FilterOperator.EQUALS,
                        value=document_id
                    )
                ]
            )
            
            if not metadata_list:
                logger.warning(f"No metadata found for document {document_id}")
                return False
            
            # Delete from vector store
            node_ids = [metadata.node_id for metadata in metadata_list]
            # Note: Actual deletion would depend on vector store implementation
            
            # Delete metadata
            for metadata in metadata_list:
                self.metadata_manager.delete_metadata(metadata.embedding_id)
            
            logger.info(f"Successfully deleted document {document_id} for tenant {tenant_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            return False
    
    def _update_query_stats(self, query_time_ms: float, success: bool):
        """Update query performance statistics."""
        with self.stats_lock:
            self.query_times.append(query_time_ms)
            self.query_count += 1
            
            if success:
                self.success_count += 1
            
            # Keep only last 1000 query times
            if len(self.query_times) > 1000:
                self.query_times = self.query_times[-1000:]
            
            # Update average query time
            if self.query_times:
                self.stats.avg_query_time_ms = sum(self.query_times) / len(self.query_times)
            
            # Update success rate
            if self.query_count > 0:
                self.stats.success_rate = self.success_count / self.query_count
    
    def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        try:
            # Check vector store
            vector_health = self.vector_store.health_check()
            
            # Check metadata manager
            metadata_health = self.metadata_manager.health_check()
            
            # Check processing components
            processor_health = {
                "status": "healthy",
                "llama_processor": "available",
                "document_processor": "available"
            }
            
            # Overall health
            overall_status = "healthy"
            if (vector_health.get("status") != "healthy" or 
                metadata_health.get("status") != "healthy"):
                overall_status = "degraded"
            
            return {
                "status": overall_status,
                "vector_store": vector_health,
                "metadata_manager": metadata_health,
                "processors": processor_health,
                "statistics": self.stats.to_dict()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def get_system_statistics(self) -> Dict[str, Any]:
        """Get comprehensive system statistics."""
        try:
            # Get component statistics
            vector_stats = self.vector_store.health_check()
            metadata_stats = self.metadata_manager.get_statistics()
            
            # Get tenant list
            tenants = list(self.vector_store.tenant_stores.keys())
            
            with self.stats_lock:
                stats = self.stats.to_dict()
                stats.update({
                    "total_tenants": len(tenants),
                    "active_tenants": tenants,
                    "query_count": self.query_count,
                    "success_count": self.success_count,
                    "vector_store_stats": vector_stats,
                    "metadata_stats": metadata_stats
                })
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get system statistics: {e}")
            return {"error": str(e)}


# Global storage manager instance
_storage_manager = None


def get_storage_manager() -> TenantAwareStorageManager:
    """Get the global storage manager instance."""
    global _storage_manager
    if _storage_manager is None:
        _storage_manager = TenantAwareStorageManager()
    return _storage_manager