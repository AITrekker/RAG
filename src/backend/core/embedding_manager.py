"""
High-performance Embedding Generation for the RAG Platform.

This module provides an `EmbeddingManager` that handles the efficient
generation of text embeddings using a background worker pool. It supports
batching, queuing, and prioritization to manage high throughput scenarios.
The manager interfaces with an underlying `EmbeddingService` (like one based
on SentenceTransformers) to perform the actual embedding computation, and
it can automatically persist the generated embeddings into a vector store.
"""

import logging
import time
import asyncio
from typing import List, Dict, Any, Optional, Tuple, Union
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import threading

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
    Supports batch processing, queuing, and CUDA acceleration
    """
    
    def __init__(
        self,
        max_batch_size: Optional[int] = None,
        max_queue_size: int = 1000,
        worker_threads: int = 2,
        enable_async: bool = True,
        auto_persist: bool = True
    ):
        """
        Initialize embedding manager
        
        Args:
            max_batch_size: Maximum batch size for processing
            max_queue_size: Maximum queue size for pending requests
            worker_threads: Number of worker threads
            enable_async: Enable async processing
            auto_persist: Automatically persist embeddings to vector store
        """
        self.max_batch_size = max_batch_size or settings.embedding.batch_size
        self.max_queue_size = max_queue_size
        self.worker_threads = worker_threads
        self.enable_async = enable_async
        self.auto_persist = auto_persist
        
        # Initialize components
        self.embedding_service = get_embedding_service()
        self.vector_store_manager = get_vector_store_manager()
        
        # Processing queue and workers
        self.request_queue = queue.PriorityQueue(maxsize=max_queue_size)
        self.result_queue = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=worker_threads)
        self.workers_active = False
        
        # Performance tracking
        self.processed_requests = 0
        self.total_texts_processed = 0
        self.total_processing_time = 0.0
        self.error_count = 0
        
        # Thread safety
        self._lock = threading.RLock()
        
        logger.info(f"Embedding manager initialized:")
        logger.info(f"  Max batch size: {self.max_batch_size}")
        logger.info(f"  Worker threads: {self.worker_threads}")
        logger.info(f"  Auto persist: {self.auto_persist}")
    
    def start_workers(self):
        """Start background worker threads"""
        if self.workers_active:
            return
        
        self.workers_active = True
        
        for i in range(self.worker_threads):
            self.executor.submit(self._worker_loop, f"worker-{i}")
        
        logger.info(f"Started {self.worker_threads} embedding workers")
    
    def stop_workers(self):
        """Stop background worker threads"""
        self.workers_active = False
        
        # Add poison pills to stop workers
        for _ in range(self.worker_threads):
            try:
                self.request_queue.put((float('inf'), None), timeout=1)
            except queue.Full:
                pass
        
        self.executor.shutdown(wait=True)
        logger.info("Stopped embedding workers")
    
    def _worker_loop(self, worker_id: str):
        """Worker thread main loop"""
        logger.info(f"Worker {worker_id} started")
        
        while self.workers_active:
            try:
                # Get request from queue (timeout to check if should stop)
                priority, request = self.request_queue.get(timeout=1.0)
                
                if request is None:  # Poison pill
                    break
                
                # Process the request
                result = self._process_request(request)
                
                # Put result in result queue
                self.result_queue.put(result)
                
                # Mark task as done
                self.request_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
        
        logger.info(f"Worker {worker_id} stopped")
    
    def _process_request(self, request: EmbeddingRequest) -> EmbeddingResult:
        """Process a single embedding request"""
        start_time = time.time()
        
        try:
            # Split into batches if needed
            batches = self._create_batches(request.texts, request.metadata, request.doc_ids)
            
            all_embeddings = []
            
            for batch_texts, batch_metadata, batch_ids in batches:
                # Generate embeddings for batch
                batch_embeddings = self.embedding_service.encode_texts(
                    batch_texts,
                    normalize_embeddings=True,
                    show_progress_bar=False
                )
                all_embeddings.append(batch_embeddings)
            
            # Combine all batches
            if all_embeddings:
                embeddings = np.vstack(all_embeddings)
            else:
                embeddings = np.array([])
            
            processing_time = time.time() - start_time
            
            # Update statistics
            with self._lock:
                self.processed_requests += 1
                self.total_texts_processed += len(request.texts)
                self.total_processing_time += processing_time
            
            # Auto-persist if enabled
            if self.auto_persist and len(embeddings) > 0:
                self._persist_embeddings(request, embeddings)
            
            result = EmbeddingResult(
                embeddings=embeddings,
                texts=request.texts,
                metadata=request.metadata,
                doc_ids=request.doc_ids,
                tenant_id=request.tenant_id,
                processing_time=processing_time,
                timestamp=time.time(),
                success=True
            )
            
            logger.info(f"Processed {len(request.texts)} texts in {processing_time:.3f}s")
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            
            with self._lock:
                self.error_count += 1
            
            logger.error(f"Failed to process embedding request: {e}")
            
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
        """Split texts into processing batches"""
        batches = []
        
        for i in range(0, len(texts), self.max_batch_size):
            end_index = i + self.max_batch_size
            
            batch_texts = texts[i:end_index]
            batch_metadata = metadata[i:end_index] if metadata else None
            batch_ids = doc_ids[i:end_index] if doc_ids else None
            
            batches.append((batch_texts, batch_metadata, batch_ids))
        
        return batches
    
    def _persist_embeddings(self, request: EmbeddingRequest, embeddings: np.ndarray):
        """Persist embeddings to the vector store."""
        try:
            collection = self.vector_store_manager.get_collection_for_tenant(request.tenant_id)
            
            # Convert numpy array to list of lists for Chroma
            embeddings_list = embeddings.tolist()
            
            collection.add(
                embeddings=embeddings_list,
                documents=request.texts,
                metadatas=request.metadata,
                ids=request.doc_ids
            )
            
            logger.info(f"Persisted {len(request.texts)} embeddings for tenant {request.tenant_id}")
            
        except Exception as e:
            logger.error(f"Failed to persist embeddings for tenant {request.tenant_id}: {e}", exc_info=True)
    
    def submit_request(
        self,
        texts: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None,
        doc_ids: Optional[List[str]] = None,
        tenant_id: str = "default",
        priority: int = 0
    ) -> bool:
        """
        Submit request for embedding generation
        
        Args:
            texts: List of texts to embed
            metadata: Optional metadata for each text
            doc_ids: Optional document IDs
            tenant_id: Tenant identifier
            priority: Request priority (higher = more important)
            
        Returns:
            True if request was queued successfully
        """
        if not texts:
            return False
        
        request = EmbeddingRequest(
            texts=texts,
            metadata=metadata,
            doc_ids=doc_ids,
            tenant_id=tenant_id,
            priority=priority
        )
        
        try:
            # Higher priority means lower queue priority number (processed first)
            self.request_queue.put((-priority, request), timeout=1.0)
            logger.info(f"Queued request with {len(texts)} texts for tenant {tenant_id}")
            return True
            
        except queue.Full:
            logger.warning("Request queue is full, dropping request")
            return False
    
    def process_sync(
        self,
        texts: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None,
        doc_ids: Optional[List[str]] = None,
        tenant_id: str = "default"
    ) -> EmbeddingResult:
        """
        Process request synchronously (bypass queue)
        
        Args:
            texts: List of texts to embed
            metadata: Optional metadata for each text
            doc_ids: Optional document IDs
            tenant_id: Tenant identifier
            
        Returns:
            EmbeddingResult with generated embeddings
        """
        request = EmbeddingRequest(
            texts=texts,
            metadata=metadata,
            doc_ids=doc_ids,
            tenant_id=tenant_id
        )
        
        return self._process_request(request)
    
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
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.process_sync,
            texts,
            metadata,
            doc_ids,
            tenant_id
        )
    
    def get_results(self, timeout: float = 1.0) -> List[EmbeddingResult]:
        """Get completed results from the result queue"""
        results = []
        
        while True:
            try:
                result = self.result_queue.get(timeout=timeout)
                results.append(result)
                self.result_queue.task_done()
            except queue.Empty:
                break
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline performance statistics"""
        with self._lock:
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
                "queue_size": self.request_queue.qsize(),
                "workers_active": self.workers_active,
                "embedding_service_stats": self.embedding_service.get_performance_stats()
            }
    
    def clear_stats(self):
        """Clear performance statistics"""
        with self._lock:
            self.processed_requests = 0
            self.total_texts_processed = 0
            self.total_processing_time = 0.0
            self.error_count = 0
        
        # Clear embedding service stats too
        self.embedding_service.embedding_times = []
    
    def __enter__(self):
        """Context manager entry"""
        self.start_workers()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop_workers()


_embedding_manager_instance: Optional[EmbeddingManager] = None
_embedding_manager_lock = threading.Lock()


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
        with _embedding_manager_lock:
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