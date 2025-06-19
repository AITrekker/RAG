"""
Resource-aware document loaders for LlamaIndex with tenant isolation.

This module provides sophisticated document loading capabilities with
batch processing, resource management, and tenant-specific optimizations.
"""

import asyncio
import logging
import os
from typing import Dict, Any, List, Optional, Iterator, Tuple
from pathlib import Path
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time

from llama_index.core import Document
from llama_index.readers.file import (
    PDFReader, 
    DocxReader, 
    TextFileReader,
    CSVReader,
    MarkdownReader
)
from llama_index.readers.json import JSONReader

from .llama_config import TenantLlamaConfig
from ..config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class LoaderResourceLimits:
    """Resource limits for document loading operations."""
    max_concurrent_files: int = 5
    max_file_size_mb: float = 100.0
    max_batch_size: int = 10
    max_memory_usage_gb: float = 2.0
    timeout_seconds: int = 300


class ResourceAwareDocumentLoader:
    """
    Document loader with resource awareness and batch processing.
    
    Features:
    - Tenant-specific resource limits
    - Batch processing with size control
    - Memory usage monitoring
    - File type detection and validation
    - Progress tracking and error handling
    """
    
    def __init__(self, tenant_config: TenantLlamaConfig, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the resource-aware document loader.
        
        Args:
            tenant_config: Tenant-specific configuration
            config: Global configuration dictionary
        """
        self.tenant_config = tenant_config
        self.config = config or get_settings()
        self.tenant_id = tenant_config.tenant_id
        
        # Resource limits
        self.resource_limits = self._create_resource_limits()
        
        # File processing configuration
        self.supported_formats = self.config.get("file_processing", {}).get("supported_formats", [])
        self.max_file_size = self.config.get("security", {}).get("input_validation", {}).get("max_file_size_mb", 100)
        
        # Initialize readers
        self.readers = self._initialize_readers()
        
        # Threading and batch control
        self.executor = ThreadPoolExecutor(max_workers=self.resource_limits.max_concurrent_files)
        self.batch_lock = threading.Lock()
        self.current_memory_usage = 0.0
        
        logger.info(f"Initialized DocumentLoader for tenant {self.tenant_id} with limits: {self.resource_limits}")
    
    def _create_resource_limits(self) -> LoaderResourceLimits:
        """Create resource limits based on tenant configuration."""
        tenancy_config = self.config.get("tenancy", {})
        resource_limits = tenancy_config.get("resource_limits", {})
        llama_config = self.config.get("llama_index", {})
        
        return LoaderResourceLimits(
            max_concurrent_files=min(
                self.tenant_config.max_workers,
                llama_config.get("performance", {}).get("max_parallel_workers", 4)
            ),
            max_file_size_mb=min(
                self.max_file_size,
                resource_limits.get("max_file_size_mb", 100)
            ),
            max_batch_size=self.tenant_config.max_files_per_batch,
            max_memory_usage_gb=self.tenant_config.max_memory_gb / 2,  # Reserve half for models
            timeout_seconds=self.config.get("production", {}).get("performance", {}).get("request_timeout_seconds", 300)
        )
    
    def _initialize_readers(self) -> Dict[str, Any]:
        """Initialize document readers for supported file types."""
        readers = {
            "pdf": PDFReader(),
            "docx": DocxReader(),
            "doc": DocxReader(),  # DocxReader can handle .doc files too
            "txt": TextFileReader(),
            "md": MarkdownReader(),
            "csv": CSVReader(),
            "json": JSONReader()
        }
        
        logger.info(f"Initialized readers for formats: {list(readers.keys())}")
        return readers
    
    def load_documents_batch(
        self, 
        file_paths: List[str], 
        batch_size: Optional[int] = None
    ) -> Iterator[Tuple[List[Document], Dict[str, Any]]]:
        """
        Load documents in batches with resource control.
        
        Args:
            file_paths: List of file paths to load
            batch_size: Optional batch size override
            
        Yields:
            Tuple[List[Document], Dict[str, Any]]: (documents, batch_stats)
        """
        batch_size = batch_size or self.resource_limits.max_batch_size
        
        # Validate and filter files
        valid_files = self._validate_files(file_paths)
        
        # Process in batches
        for i in range(0, len(valid_files), batch_size):
            batch_files = valid_files[i:i + batch_size]
            
            try:
                # Check resource availability
                if not self._check_resource_availability(batch_files):
                    logger.warning(f"Skipping batch {i//batch_size + 1} due to resource constraints")
                    continue
                
                # Load batch
                documents, stats = self._load_batch(batch_files)
                
                # Update resource tracking
                self._update_resource_usage(stats)
                
                yield documents, stats
                
            except Exception as e:
                logger.error(f"Failed to load batch {i//batch_size + 1}: {e}")
                yield [], {"error": str(e), "batch_files": batch_files}
    
    def load_documents_async(
        self, 
        file_paths: List[str],
        batch_size: Optional[int] = None
    ) -> List[Document]:
        """
        Load documents asynchronously with resource management.
        
        Args:
            file_paths: List of file paths to load
            batch_size: Optional batch size override
            
        Returns:
            List[Document]: Loaded documents
        """
        all_documents = []
        
        for documents, stats in self.load_documents_batch(file_paths, batch_size):
            all_documents.extend(documents)
            
            if "error" in stats:
                logger.error(f"Batch loading error: {stats['error']}")
        
        logger.info(f"Loaded {len(all_documents)} documents for tenant {self.tenant_id}")
        return all_documents
    
    def _validate_files(self, file_paths: List[str]) -> List[str]:
        """Validate files before loading."""
        valid_files = []
        
        for file_path in file_paths:
            try:
                path = Path(file_path)
                
                # Check if file exists
                if not path.exists():
                    logger.warning(f"File does not exist: {file_path}")
                    continue
                
                # Check file size
                file_size_mb = path.stat().st_size / (1024 * 1024)
                if file_size_mb > self.resource_limits.max_file_size_mb:
                    logger.warning(f"File too large ({file_size_mb:.2f}MB): {file_path}")
                    continue
                
                # Check file format
                file_extension = path.suffix.lower().lstrip('.')
                if file_extension not in self.supported_formats:
                    logger.warning(f"Unsupported format ({file_extension}): {file_path}")
                    continue
                
                valid_files.append(file_path)
                
            except Exception as e:
                logger.error(f"Error validating file {file_path}: {e}")
        
        logger.info(f"Validated {len(valid_files)}/{len(file_paths)} files for tenant {self.tenant_id}")
        return valid_files
    
    def _check_resource_availability(self, batch_files: List[str]) -> bool:
        """Check if resources are available for processing batch."""
        # Estimate memory usage for batch
        estimated_memory = self._estimate_batch_memory(batch_files)
        
        with self.batch_lock:
            total_estimated_memory = self.current_memory_usage + estimated_memory
            
            if total_estimated_memory > self.resource_limits.max_memory_usage_gb:
                logger.warning(
                    f"Memory limit would be exceeded: "
                    f"{total_estimated_memory:.2f}GB > {self.resource_limits.max_memory_usage_gb}GB"
                )
                return False
        
        return True
    
    def _estimate_batch_memory(self, batch_files: List[str]) -> float:
        """Estimate memory usage for a batch of files in GB."""
        total_size_mb = 0
        
        for file_path in batch_files:
            try:
                file_size_mb = Path(file_path).stat().st_size / (1024 * 1024)
                total_size_mb += file_size_mb
            except Exception:
                # Assume average file size if stat fails
                total_size_mb += 10  # 10MB average
        
        # Estimate processing overhead (3x file size for text extraction and processing)
        estimated_memory_gb = (total_size_mb * 3) / 1024
        return estimated_memory_gb
    
    def _load_batch(self, batch_files: List[str]) -> Tuple[List[Document], Dict[str, Any]]:
        """Load a batch of files concurrently."""
        start_time = time.time()
        documents = []
        stats = {
            "batch_size": len(batch_files),
            "successful_loads": 0,
            "failed_loads": 0,
            "total_documents": 0,
            "processing_time": 0,
            "files_processed": [],
            "errors": []
        }
        
        # Submit loading tasks
        future_to_file = {}
        with ThreadPoolExecutor(max_workers=self.resource_limits.max_concurrent_files) as executor:
            for file_path in batch_files:
                future = executor.submit(self._load_single_file, file_path)
                future_to_file[future] = file_path
            
            # Collect results
            for future in as_completed(future_to_file, timeout=self.resource_limits.timeout_seconds):
                file_path = future_to_file[future]
                
                try:
                    file_documents = future.result()
                    documents.extend(file_documents)
                    stats["successful_loads"] += 1
                    stats["total_documents"] += len(file_documents)
                    stats["files_processed"].append({
                        "file": file_path,
                        "document_count": len(file_documents),
                        "status": "success"
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to load file {file_path}: {e}")
                    stats["failed_loads"] += 1
                    stats["errors"].append({
                        "file": file_path,
                        "error": str(e)
                    })
        
        stats["processing_time"] = time.time() - start_time
        
        logger.info(
            f"Batch processing complete for tenant {self.tenant_id}: "
            f"{stats['successful_loads']}/{stats['batch_size']} files, "
            f"{stats['total_documents']} documents, "
            f"{stats['processing_time']:.2f}s"
        )
        
        return documents, stats
    
    def _load_single_file(self, file_path: str) -> List[Document]:
        """Load a single file and return documents."""
        try:
            path = Path(file_path)
            file_extension = path.suffix.lower().lstrip('.')
            
            # Get appropriate reader
            reader = self.readers.get(file_extension)
            if not reader:
                raise ValueError(f"No reader available for format: {file_extension}")
            
            # Load documents
            documents = reader.load_data(file=path)
            
            # Add tenant-specific metadata
            for doc in documents:
                doc.metadata.update({
                    "tenant_id": self.tenant_id,
                    "file_path": str(path),
                    "file_name": path.name,
                    "file_extension": file_extension,
                    "file_size_bytes": path.stat().st_size,
                    "load_timestamp": time.time()
                })
            
            logger.debug(f"Loaded {len(documents)} documents from {file_path}")
            return documents
            
        except Exception as e:
            logger.error(f"Error loading file {file_path}: {e}")
            raise
    
    def _update_resource_usage(self, stats: Dict[str, Any]):
        """Update current resource usage tracking."""
        # Estimate memory usage based on documents loaded
        estimated_memory = stats.get("total_documents", 0) * 0.001  # 1MB per document estimate
        
        with self.batch_lock:
            self.current_memory_usage = min(
                self.current_memory_usage + estimated_memory,
                self.resource_limits.max_memory_usage_gb
            )
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported file formats."""
        return list(self.readers.keys())
    
    def get_resource_status(self) -> Dict[str, Any]:
        """Get current resource usage status."""
        with self.batch_lock:
            return {
                "tenant_id": self.tenant_id,
                "current_memory_usage_gb": self.current_memory_usage,
                "memory_limit_gb": self.resource_limits.max_memory_usage_gb,
                "memory_utilization": (self.current_memory_usage / self.resource_limits.max_memory_usage_gb) * 100,
                "max_concurrent_files": self.resource_limits.max_concurrent_files,
                "max_batch_size": self.resource_limits.max_batch_size,
                "max_file_size_mb": self.resource_limits.max_file_size_mb,
                "supported_formats": self.get_supported_formats()
            }
    
    def cleanup(self):
        """Clean up resources and shutdown executor."""
        try:
            self.executor.shutdown(wait=True, timeout=30)
            with self.batch_lock:
                self.current_memory_usage = 0.0
            logger.info(f"DocumentLoader cleanup complete for tenant {self.tenant_id}")
        except Exception as e:
            logger.error(f"Error during DocumentLoader cleanup: {e}")


def create_document_loader(tenant_config: TenantLlamaConfig) -> ResourceAwareDocumentLoader:
    """
    Factory function to create a document loader for a tenant.
    
    Args:
        tenant_config: Tenant-specific configuration
        
    Returns:
        ResourceAwareDocumentLoader: Configured document loader
    """
    return ResourceAwareDocumentLoader(tenant_config)


def load_documents_for_tenant(
    tenant_config: TenantLlamaConfig,
    file_paths: List[str],
    batch_size: Optional[int] = None
) -> List[Document]:
    """
    Convenience function to load documents for a tenant.
    
    Args:
        tenant_config: Tenant-specific configuration
        file_paths: List of file paths to load
        batch_size: Optional batch size override
        
    Returns:
        List[Document]: Loaded documents
    """
    loader = create_document_loader(tenant_config)
    try:
        return loader.load_documents_async(file_paths, batch_size)
    finally:
        loader.cleanup() 