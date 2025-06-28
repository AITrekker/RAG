"""
High-performance Embedding Generation for the RAG Platform.

This module provides an `EmbeddingManager` that handles the efficient
generation of text embeddings using async patterns. It supports
batching and prioritization to manage high throughput scenarios.
The manager interfaces with an underlying `EmbeddingService` to perform
the actual embedding computation, and it can automatically persist the
generated embeddings into a vector store.
"""

import logging
import time
import asyncio
from typing import List, Dict, Any, Optional, Tuple, Union
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
import numpy as np

# Internal imports
from .embeddings import get_embedding_service, EmbeddingService
from ..config.settings import settings
from ..utils.vector_store import get_vector_store_manager

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingRequest:
    """Request for embedding generation"""
    texts: List[str]
    metadata: Optional[List[Dict[str, Any]]] = None
    doc_ids: Optional[List[str]] = None
    tenant_id: str = "default"
    priority: int = 0  # Higher numbers = higher priority
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


@dataclass
class EmbeddingResult:
    """Result from embedding generation"""
    embeddings: np.ndarray
    texts: List[str]
    metadata: Optional[List[Dict[str, Any]]]
    doc_ids: Optional[List[str]]
    tenant_id: str
    processing_time: float
    timestamp: float
    success: bool = True
    error: Optional[str] = None


class EmbeddingManager:
    """
    High-performance embedding generation manager
    Supports batch processing and async operations
    """
    
    def __init__(
        self,
        max_batch_size: Optional[int] = None,
        auto_persist: bool = True
    ):
        """
        Initialize embedding manager
        
        Args:
            max_batch_size: Maximum batch size for processing
            auto_persist: Automatically persist embeddings to vector store
        """
        self.max_batch_size = max_batch_size or settings.embedding_batch_size
        self.auto_persist = auto_persist
        
        # Initialize components
        self.embedding_service = get_embedding_service()
        self.vector_store_manager = get_vector_store_manager()
        
        # Performance tracking
        self.processed_requests = 0
        self.total_texts_processed = 0
        self.total_processing_time = 0.0
        self.error_count = 0
        
        logger.info(f"Embedding manager initialized:")
        logger.info(f"  Max batch size: {self.max_batch_size}")
        logger.info(f"  Auto persist: {self.auto_persist}")
    
    async def process_async(
        self,
        texts: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None,
        doc_ids: Optional[List[str]] = None,
        tenant_id: str = "default"
    ) -> EmbeddingResult:
        """
        Process request asynchronously
        
        Args:
            texts: List of texts to embed
            metadata: Optional metadata for each text
            doc_ids: Optional document IDs
            tenant_id: Tenant identifier
            
        Returns:
            EmbeddingResult with generated embeddings
        """
        start_time = time.time()
        
        try:
            # Create request
            request = EmbeddingRequest(
                texts=texts,
                metadata=metadata,
                doc_ids=doc_ids,
                tenant_id=tenant_id
            )
            
            # Process the request asynchronously
            result = await self._process_request_async(request)
            
            # Update statistics
            self.processed_requests += 1
            self.total_texts_processed += len(texts)
            self.total_processing_time += result.processing_time
            
            return result
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Error processing embedding request: {e}")
            
            return EmbeddingResult(
                embeddings=np.array([]),
                texts=texts,
                metadata=metadata,
                doc_ids=doc_ids,
                tenant_id=tenant_id,
                processing_time=time.time() - start_time,
                timestamp=time.time(),
                success=False,
                error=str(e)
            )
    
    def process_sync(
        self,
        texts: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None,
        doc_ids: Optional[List[str]] = None,
        tenant_id: str = "default"
    ) -> EmbeddingResult:
        """
        Process request synchronously (for backward compatibility)
        
        Args:
            texts: List of texts to embed
            metadata: Optional metadata for each text
            doc_ids: Optional document IDs
            tenant_id: Tenant identifier
            
        Returns:
            EmbeddingResult with generated embeddings
        """
        # Run async method in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.process_async(texts, metadata, doc_ids, tenant_id)
            )
        finally:
            loop.close()
    
    async def _process_request_async(self, request: EmbeddingRequest) -> EmbeddingResult:
        """Process a single embedding request asynchronously"""
        start_time = time.time()
        
        try:
            # Split into batches if needed
            batches = self._create_batches(request.texts, request.metadata, request.doc_ids)
            
            all_embeddings = []
            
            for batch_texts, batch_metadata, batch_ids in batches:
                # Generate embeddings for batch (run in thread pool for CPU-bound work)
                loop = asyncio.get_event_loop()
                batch_embeddings = await loop.run_in_executor(
                    None,
                    self.embedding_service.encode_texts,
                    batch_texts,
                    True,  # normalize_embeddings
                    False  # show_progress_bar
                )
                all_embeddings.append(batch_embeddings)
            
            # Combine all batches
            if all_embeddings:
                embeddings = np.vstack(all_embeddings)
            else:
                embeddings = np.array([])
            
            processing_time = time.time() - start_time
            
            # Persist embeddings if enabled
            if self.auto_persist and len(embeddings) > 0:
                await self._persist_embeddings_async(request, embeddings)
            
            return EmbeddingResult(
                embeddings=embeddings,
                texts=request.texts,
                metadata=request.metadata,
                doc_ids=request.doc_ids,
                tenant_id=request.tenant_id,
                processing_time=processing_time,
                timestamp=time.time(),
                success=True
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error in _process_request_async: {e}")
            
            return EmbeddingResult(
                embeddings=np.array([]),
                texts=request.texts,
                metadata=request.metadata,
                doc_ids=request.doc_ids,
                tenant_id=request.tenant_id,
                processing_time=processing_time,
                timestamp=time.time(),
                success=False,
                error=str(e)
            )
    
    def _create_batches(
        self, 
        texts: List[str], 
        metadata: Optional[List[Dict[str, Any]]], 
        doc_ids: Optional[List[str]]
    ) -> List[Tuple[List[str], Optional[List[Dict[str, Any]]], Optional[List[str]]]]:
        """Create batches for processing"""
        if len(texts) <= self.max_batch_size:
            return [(texts, metadata, doc_ids)]
        
        batches = []
        for i in range(0, len(texts), self.max_batch_size):
            end_idx = min(i + self.max_batch_size, len(texts))
            batch_texts = texts[i:end_idx]
            
            batch_metadata = None
            if metadata:
                batch_metadata = metadata[i:end_idx]
            
            batch_ids = None
            if doc_ids:
                batch_ids = doc_ids[i:end_idx]
            
            batches.append((batch_texts, batch_metadata, batch_ids))
        
        return batches
    
    async def _persist_embeddings_async(self, request: EmbeddingRequest, embeddings: np.ndarray):
        """Persist embeddings to vector store asynchronously"""
        try:
            # Run vector store operations in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._persist_embeddings_sync,
                request,
                embeddings
            )
        except Exception as e:
            logger.error(f"Error persisting embeddings: {e}")
    
    def _persist_embeddings_sync(self, request: EmbeddingRequest, embeddings: np.ndarray):
        """Synchronously persist embeddings to vector store"""
        try:
            # Prepare payload for vector store
            payload = []
            for i, text in enumerate(request.texts):
                item = {
                    "text": text,
                    "embedding": embeddings[i].tolist(),
                    "tenant_id": request.tenant_id
                }
                
                if request.metadata and i < len(request.metadata):
                    item["metadata"] = request.metadata[i]
                
                if request.doc_ids and i < len(request.doc_ids):
                    item["doc_id"] = request.doc_ids[i]
                
                payload.append(item)
            
            # Store in vector database
            self.vector_store_manager.add_embeddings(
                collection_name=f"embeddings_{request.tenant_id}",
                embeddings=payload
            )
            
            logger.debug(f"Persisted {len(payload)} embeddings for tenant {request.tenant_id}")
            
        except Exception as e:
            logger.error(f"Error in _persist_embeddings_sync: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline performance statistics"""
        avg_processing_time = (
            self.total_processing_time / self.processed_requests 
            if self.processed_requests > 0 else 0
        )
        
        avg_texts_per_request = (
            self.total_texts_processed / self.processed_requests
            if self.processed_requests > 0 else 0
        )
        
        return {
            "processed_requests": self.processed_requests,
            "total_texts_processed": self.total_texts_processed,
            "total_processing_time": self.total_processing_time,
            "error_count": self.error_count,
            "average_processing_time": avg_processing_time,
            "average_texts_per_request": avg_texts_per_request,
            "embedding_service_stats": self.embedding_service.get_performance_stats()
        }
    
    def clear_stats(self):
        """Clear performance statistics"""
        self.processed_requests = 0
        self.total_texts_processed = 0
        self.total_processing_time = 0.0
        self.error_count = 0
        
        # Clear embedding service stats too
        self.embedding_service.embedding_times = []


_embedding_manager_instance: Optional[EmbeddingManager] = None


def get_embedding_manager(force_reload: bool = False, **kwargs) -> EmbeddingManager:
    """
    Get the singleton instance of the EmbeddingManager.
    
    Args:
        force_reload: If True, creates a new instance.
        **kwargs: Arguments for EmbeddingManager constructor if a new
                  instance is created.
                  
    Returns:
        The singleton EmbeddingManager instance.
    """
    global _embedding_manager_instance
    
    if _embedding_manager_instance is None or force_reload:
        logger.info("Creating new EmbeddingManager instance.")
        _embedding_manager_instance = EmbeddingManager(**kwargs)
    
    return _embedding_manager_instance


def embed_texts_sync(
    texts: List[str],
    tenant_id: str = "default",
    metadata: Optional[List[Dict[str, Any]]] = None,
    doc_ids: Optional[List[str]] = None
) -> EmbeddingResult:
    """
    Synchronously embed a list of texts using the global embedding manager.
    
    Args:
        texts: List of texts to embed.
        tenant_id: The tenant ID.
        metadata: List of metadata dictionaries.
        doc_ids: List of document IDs.
        
    Returns:
        An EmbeddingResult object.
    """
    manager = get_embedding_manager()
    return manager.process_sync(
        texts=texts,
        metadata=metadata,
        doc_ids=doc_ids,
        tenant_id=tenant_id
    )


async def embed_texts_async(
    texts: List[str],
    tenant_id: str = "default",
    metadata: Optional[List[Dict[str, Any]]] = None,
    doc_ids: Optional[List[str]] = None
) -> EmbeddingResult:
    """
    Asynchronously embed a list of texts using the global embedding manager.
    
    Args:
        texts: List of texts to embed.
        tenant_id: The tenant ID.
        metadata: List of metadata dictionaries.
        doc_ids: List of document IDs.
        
    Returns:
        An EmbeddingResult object.
    """
    manager = get_embedding_manager()
    return await manager.process_async(
        texts=texts,
        metadata=metadata,
        doc_ids=doc_ids,
        tenant_id=tenant_id
    )


def embed_documents_from_files(
    file_paths: List[str],
    tenant_id: str = "default",
    chunk_size: Optional[int] = None
) -> List[EmbeddingResult]:
    """
    DEPRECATED: This function is complex and couples document processing
    with embedding. It's recommended to use DocumentIngestionPipeline instead.
    
    Processes files, chunks them, and embeds the content.
    """
    raise NotImplementedError(
        "embed_documents_from_files is deprecated. "
        "Please use the DocumentIngestionPipeline for a more robust workflow."
    )


def get_pipeline_stats() -> Dict[str, Any]:
    """
    Get performance statistics from the global embedding manager.
    
    Returns:
        A dictionary of performance stats.
    """
    manager = get_embedding_manager()
    return manager.get_stats() 