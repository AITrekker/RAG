"""
Main document processing pipeline for Enterprise RAG system.

This module provides the primary document processing pipeline that orchestrates
document loading, text splitting, node parsing, and metadata extraction with
full tenant awareness and folder-based organization.
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Tuple, Iterator
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from llama_index.core import Document
from llama_index.core.schema import BaseNode

from .llama_config import TenantLlamaConfig, get_tenant_config
from .tenant_models import get_model_manager, ResourceAwareModelManager
from .document_loaders import ResourceAwareDocumentLoader, create_document_loader
from .text_splitters import TenantAwareTextSplitterManager, SplittingStrategy
from .node_parsers import TenantAwareNodeParserManager, NodeParsingStrategy
from ..config.settings import get_settings

logger = logging.getLogger(__name__)


class ProcessingStatus(Enum):
    """Processing status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProcessingMetrics:
    """Metrics for document processing operations."""
    tenant_id: str
    folder_path: str
    start_time: float
    end_time: Optional[float] = None
    status: ProcessingStatus = ProcessingStatus.PENDING
    
    # File metrics
    total_files: int = 0
    processed_files: int = 0
    failed_files: int = 0
    skipped_files: int = 0
    
    # Document metrics
    total_documents: int = 0
    total_nodes: int = 0
    
    # Processing metrics
    loading_time: float = 0.0
    splitting_time: float = 0.0
    parsing_time: float = 0.0
    total_processing_time: float = 0.0
    
    # Resource metrics
    peak_memory_usage_gb: float = 0.0
    average_cpu_usage: float = 0.0
    
    # Error tracking
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "tenant_id": self.tenant_id,
            "folder_path": self.folder_path,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status.value,
            "duration": self.end_time - self.start_time if self.end_time else None,
            "file_metrics": {
                "total_files": self.total_files,
                "processed_files": self.processed_files,
                "failed_files": self.failed_files,
                "skipped_files": self.skipped_files,
                "success_rate": (self.processed_files / self.total_files * 100) if self.total_files > 0 else 0
            },
            "document_metrics": {
                "total_documents": self.total_documents,
                "total_nodes": self.total_nodes,
                "avg_nodes_per_document": self.total_nodes / self.total_documents if self.total_documents > 0 else 0
            },
            "performance_metrics": {
                "loading_time": self.loading_time,
                "splitting_time": self.splitting_time,
                "parsing_time": self.parsing_time,
                "total_processing_time": self.total_processing_time,
                "throughput_files_per_second": self.processed_files / self.total_processing_time if self.total_processing_time > 0 else 0
            },
            "resource_metrics": {
                "peak_memory_usage_gb": self.peak_memory_usage_gb,
                "average_cpu_usage": self.average_cpu_usage
            },
            "error_count": len(self.errors),
            "warning_count": len(self.warnings)
        }


@dataclass
class ProcessingPipelineConfig:
    """Configuration for document processing pipeline."""
    tenant_id: str
    folder_path: str
    
    # Processing strategies
    splitting_strategy: SplittingStrategy = SplittingStrategy.RECURSIVE
    parsing_strategy: NodeParsingStrategy = NodeParsingStrategy.SIMPLE
    
    # Batch settings
    batch_size: int = 10
    max_concurrent_batches: int = 2
    
    # Resource limits
    max_memory_usage_gb: float = 4.0
    timeout_seconds: int = 300
    
    # Processing options
    enable_metadata_extraction: bool = True
    enable_folder_hierarchy_tracking: bool = True
    enable_content_validation: bool = True
    
    # Output options
    save_processing_logs: bool = True
    save_metrics: bool = True


class TenantAwareDocumentProcessor:
    """
    Main document processing pipeline with tenant awareness and folder-based organization.
    
    Features:
    - Complete document processing pipeline
    - Tenant isolation and resource management
    - Folder-based document organization
    - Comprehensive metrics and logging
    - Batch processing with resource control
    - Error handling and recovery
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the document processor.
        
        Args:
            config: Global configuration dictionary
        """
        self.config = config or get_settings()
        
        # Processing state
        self.active_processors: Dict[str, ProcessingMetrics] = {}
        self.processing_lock = threading.RLock()
        
        # Resource managers
        self.model_manager = get_model_manager()
        
        # Processing history
        self.processing_history: List[ProcessingMetrics] = []
        self.max_history_size = 100
        
        logger.info("Initialized TenantAwareDocumentProcessor")
    
    def create_processing_pipeline(self, tenant_id: str, folder_path: str, **kwargs) -> ProcessingPipelineConfig:
        """
        Create a processing pipeline configuration for a tenant and folder.
        
        Args:
            tenant_id: Unique identifier for the tenant
            folder_path: Path to the folder containing documents
            **kwargs: Additional configuration options
            
        Returns:
            ProcessingPipelineConfig: Pipeline configuration
        """
        # Get tenant configuration
        tenant_config = get_tenant_config(tenant_id)
        
        # Create pipeline configuration
        pipeline_config = ProcessingPipelineConfig(
            tenant_id=tenant_id,
            folder_path=folder_path,
            batch_size=kwargs.get("batch_size", tenant_config.max_files_per_batch),
            max_concurrent_batches=kwargs.get("max_concurrent_batches", 2),
            max_memory_usage_gb=kwargs.get("max_memory_usage_gb", tenant_config.max_memory_gb),
            timeout_seconds=kwargs.get("timeout_seconds", 300),
            splitting_strategy=SplittingStrategy(kwargs.get("splitting_strategy", "recursive")),
            parsing_strategy=NodeParsingStrategy(kwargs.get("parsing_strategy", "simple")),
            enable_metadata_extraction=kwargs.get("enable_metadata_extraction", tenant_config.enable_metadata_extraction),
            enable_folder_hierarchy_tracking=kwargs.get("enable_folder_hierarchy_tracking", True),
            enable_content_validation=kwargs.get("enable_content_validation", True)
        )
        
        logger.info(f"Created processing pipeline config for tenant {tenant_id}, folder: {folder_path}")
        return pipeline_config
    
    def process_folder_documents(
        self, 
        pipeline_config: ProcessingPipelineConfig
    ) -> Tuple[List[BaseNode], ProcessingMetrics]:
        """
        Process all documents in a folder for a specific tenant.
        
        Args:
            pipeline_config: Pipeline configuration
            
        Returns:
            Tuple[List[BaseNode], ProcessingMetrics]: Processed nodes and metrics
        """
        # Initialize metrics
        metrics = ProcessingMetrics(
            tenant_id=pipeline_config.tenant_id,
            folder_path=pipeline_config.folder_path,
            start_time=time.time(),
            status=ProcessingStatus.PROCESSING
        )
        
        # Register active processing
        with self.processing_lock:
            self.active_processors[f"{pipeline_config.tenant_id}_{pipeline_config.folder_path}"] = metrics
        
        try:
            # Validate folder access
            self._validate_folder_access(pipeline_config, metrics)
            
            # Discover files
            file_paths = self._discover_folder_files(pipeline_config, metrics)
            metrics.total_files = len(file_paths)
            
            if not file_paths:
                logger.warning(f"No valid files found in folder: {pipeline_config.folder_path}")
                metrics.status = ProcessingStatus.COMPLETED
                metrics.end_time = time.time()
                return [], metrics
            
            # Get tenant configuration and models
            tenant_config = get_tenant_config(pipeline_config.tenant_id)
            
            # Process documents
            all_nodes = self._process_documents_pipeline(pipeline_config, tenant_config, file_paths, metrics)
            
            # Finalize metrics
            metrics.status = ProcessingStatus.COMPLETED
            metrics.end_time = time.time()
            metrics.total_processing_time = metrics.end_time - metrics.start_time
            
            logger.info(f"Completed processing for tenant {pipeline_config.tenant_id}: {len(all_nodes)} nodes from {metrics.processed_files} files")
            
            return all_nodes, metrics
            
        except Exception as e:
            logger.error(f"Failed to process folder documents for tenant {pipeline_config.tenant_id}: {e}")
            metrics.status = ProcessingStatus.FAILED
            metrics.end_time = time.time()
            metrics.errors.append({
                "error": str(e),
                "timestamp": time.time(),
                "stage": "pipeline_execution"
            })
            return [], metrics
        
        finally:
            # Cleanup and store metrics
            with self.processing_lock:
                if f"{pipeline_config.tenant_id}_{pipeline_config.folder_path}" in self.active_processors:
                    del self.active_processors[f"{pipeline_config.tenant_id}_{pipeline_config.folder_path}"]
            
            # Store in history
            self.processing_history.append(metrics)
            if len(self.processing_history) > self.max_history_size:
                self.processing_history.pop(0)
    
    def _validate_folder_access(self, pipeline_config: ProcessingPipelineConfig, metrics: ProcessingMetrics):
        """Validate folder access for tenant."""
        folder_path = Path(pipeline_config.folder_path)
        
        # Check if folder exists
        if not folder_path.exists():
            raise ValueError(f"Folder does not exist: {pipeline_config.folder_path}")
        
        # Check if it's a directory
        if not folder_path.is_dir():
            raise ValueError(f"Path is not a directory: {pipeline_config.folder_path}")
        
        # Validate tenant access (check if folder is in tenant's allowed directories)
        tenant_folders = self.config.get("tenancy", {}).get("tenant_folders", {})
        tenant_base_folder = tenant_folders.get(pipeline_config.tenant_id)
        
        if tenant_base_folder:
            base_path = Path(tenant_base_folder)
            try:
                # Check if folder is within tenant's allowed path
                folder_path.resolve().relative_to(base_path.resolve())
            except ValueError:
                raise PermissionError(f"Folder access denied for tenant {pipeline_config.tenant_id}: {pipeline_config.folder_path}")
        
        # Add folder validation metrics
        metrics.warnings.append(f"Validated folder access: {pipeline_config.folder_path}")
        logger.debug(f"Validated folder access for tenant {pipeline_config.tenant_id}: {pipeline_config.folder_path}")
    
    def _discover_folder_files(self, pipeline_config: ProcessingPipelineConfig, metrics: ProcessingMetrics) -> List[str]:
        """Discover and filter files in the folder."""
        folder_path = Path(pipeline_config.folder_path)
        
        # Get supported formats
        supported_formats = self.config.get("file_processing", {}).get("supported_formats", [])
        
        # Discover files
        discovered_files = []
        
        if pipeline_config.enable_folder_hierarchy_tracking:
            # Recursive discovery
            for file_path in folder_path.rglob("*"):
                if file_path.is_file():
                    file_extension = file_path.suffix.lower().lstrip('.')
                    if file_extension in supported_formats:
                        discovered_files.append(str(file_path))
        else:
            # Non-recursive discovery
            for file_path in folder_path.iterdir():
                if file_path.is_file():
                    file_extension = file_path.suffix.lower().lstrip('.')
                    if file_extension in supported_formats:
                        discovered_files.append(str(file_path))
        
        logger.info(f"Discovered {len(discovered_files)} files for tenant {pipeline_config.tenant_id} in folder: {pipeline_config.folder_path}")
        return discovered_files
    
    def _process_documents_pipeline(
        self, 
        pipeline_config: ProcessingPipelineConfig, 
        tenant_config: TenantLlamaConfig,
        file_paths: List[str], 
        metrics: ProcessingMetrics
    ) -> List[BaseNode]:
        """Execute the complete document processing pipeline."""
        all_nodes = []
        
        # Initialize processing components
        document_loader = create_document_loader(tenant_config)
        text_splitter_manager = TenantAwareTextSplitterManager(tenant_config)
        node_parser_manager = TenantAwareNodeParserManager(tenant_config)
        
        try:
            # Stage 1: Document Loading
            loading_start = time.time()
            documents = self._load_documents_stage(document_loader, file_paths, pipeline_config, metrics)
            metrics.loading_time = time.time() - loading_start
            metrics.total_documents = len(documents)
            
            if not documents:
                logger.warning(f"No documents loaded for tenant {pipeline_config.tenant_id}")
                return all_nodes
            
            # Stage 2: Text Splitting (if needed for specific strategies)
            splitting_start = time.time()
            # Note: Text splitting is handled within node parsing for most strategies
            metrics.splitting_time = time.time() - splitting_start
            
            # Stage 3: Node Parsing
            parsing_start = time.time()
            nodes = self._parse_documents_stage(node_parser_manager, documents, pipeline_config, metrics)
            metrics.parsing_time = time.time() - parsing_start
            metrics.total_nodes = len(nodes)
            
            # Stage 4: Post-processing
            processed_nodes = self._post_process_nodes_stage(nodes, pipeline_config, metrics)
            all_nodes.extend(processed_nodes)
            
            return all_nodes
            
        except Exception as e:
            logger.error(f"Error in document processing pipeline: {e}")
            metrics.errors.append({
                "error": str(e),
                "timestamp": time.time(),
                "stage": "pipeline_execution"
            })
            raise
        
        finally:
            # Cleanup components
            document_loader.cleanup()
    
    def _load_documents_stage(
        self, 
        document_loader: ResourceAwareDocumentLoader, 
        file_paths: List[str], 
        pipeline_config: ProcessingPipelineConfig, 
        metrics: ProcessingMetrics
    ) -> List[Document]:
        """Document loading stage with batch processing."""
        all_documents = []
        
        try:
            # Process in batches
            for documents, batch_stats in document_loader.load_documents_batch(file_paths, pipeline_config.batch_size):
                all_documents.extend(documents)
                
                # Update metrics
                metrics.processed_files += batch_stats.get("successful_loads", 0)
                metrics.failed_files += batch_stats.get("failed_loads", 0)
                
                # Add batch errors to metrics
                if "errors" in batch_stats:
                    for error in batch_stats["errors"]:
                        metrics.errors.append({
                            "error": error.get("error", "Unknown error"),
                            "file": error.get("file", "Unknown file"),
                            "timestamp": time.time(),
                            "stage": "document_loading"
                        })
                
                # Add folder-specific metadata
                for doc in documents:
                    self._add_folder_metadata(doc, pipeline_config)
            
            logger.info(f"Loaded {len(all_documents)} documents for tenant {pipeline_config.tenant_id}")
            return all_documents
            
        except Exception as e:
            logger.error(f"Error in document loading stage: {e}")
            metrics.errors.append({
                "error": str(e),
                "timestamp": time.time(),
                "stage": "document_loading"
            })
            raise
    
    def _parse_documents_stage(
        self, 
        node_parser_manager: TenantAwareNodeParserManager, 
        documents: List[Document], 
        pipeline_config: ProcessingPipelineConfig, 
        metrics: ProcessingMetrics
    ) -> List[BaseNode]:
        """Document parsing stage."""
        try:
            # Parse documents into nodes
            nodes = node_parser_manager.parse_documents(documents, pipeline_config.parsing_strategy)
            
            logger.info(f"Parsed {len(documents)} documents into {len(nodes)} nodes for tenant {pipeline_config.tenant_id}")
            return nodes
            
        except Exception as e:
            logger.error(f"Error in document parsing stage: {e}")
            metrics.errors.append({
                "error": str(e),
                "timestamp": time.time(),
                "stage": "document_parsing"
            })
            raise
    
    def _post_process_nodes_stage(
        self, 
        nodes: List[BaseNode], 
        pipeline_config: ProcessingPipelineConfig, 
        metrics: ProcessingMetrics
    ) -> List[BaseNode]:
        """Post-processing stage for nodes."""
        processed_nodes = []
        
        try:
            for i, node in enumerate(nodes):
                # Ensure node has proper folder metadata
                self._enhance_node_with_folder_metadata(node, pipeline_config, i)
                
                # Validate node content if enabled
                if pipeline_config.enable_content_validation:
                    if self._validate_node_content(node):
                        processed_nodes.append(node)
                    else:
                        metrics.warnings.append(f"Node {i} failed content validation")
                else:
                    processed_nodes.append(node)
            
            logger.info(f"Post-processed {len(processed_nodes)} nodes for tenant {pipeline_config.tenant_id}")
            return processed_nodes
            
        except Exception as e:
            logger.error(f"Error in post-processing stage: {e}")
            metrics.errors.append({
                "error": str(e),
                "timestamp": time.time(),
                "stage": "post_processing"
            })
            raise
    
    def _add_folder_metadata(self, document: Document, pipeline_config: ProcessingPipelineConfig):
        """Add folder-specific metadata to document."""
        if not hasattr(document, 'metadata') or document.metadata is None:
            document.metadata = {}
        
        folder_path = Path(pipeline_config.folder_path)
        file_path = Path(document.metadata.get("file_path", ""))
        
        # Add folder hierarchy information
        if pipeline_config.enable_folder_hierarchy_tracking:
            try:
                relative_path = file_path.relative_to(folder_path)
                folder_hierarchy = list(relative_path.parts[:-1])  # Exclude filename
                
                document.metadata.update({
                    "folder_path": str(folder_path),
                    "relative_path": str(relative_path),
                    "folder_hierarchy": folder_hierarchy,
                    "folder_depth": len(folder_hierarchy),
                    "parent_folder": str(relative_path.parent) if relative_path.parent != Path(".") else ""
                })
            except ValueError:
                # File is not within the folder path
                document.metadata["folder_path"] = str(folder_path)
        
        # Add processing metadata
        document.metadata.update({
            "processing_folder": str(folder_path),
            "processing_timestamp": time.time(),
            "processing_tenant": pipeline_config.tenant_id
        })
    
    def _enhance_node_with_folder_metadata(self, node: BaseNode, pipeline_config: ProcessingPipelineConfig, node_index: int):
        """Enhance node with folder-specific metadata."""
        if not hasattr(node, 'metadata') or node.metadata is None:
            node.metadata = {}
        
        # Add folder processing metadata
        node.metadata.update({
            "processing_folder": pipeline_config.folder_path,
            "processing_tenant": pipeline_config.tenant_id,
            "node_processing_index": node_index,
            "splitting_strategy": pipeline_config.splitting_strategy.value,
            "parsing_strategy": pipeline_config.parsing_strategy.value,
            "folder_processing_timestamp": time.time()
        })
    
    def _validate_node_content(self, node: BaseNode) -> bool:
        """Validate node content."""
        # Basic content validation
        if not hasattr(node, 'text') or not node.text:
            return False
        
        # Check minimum content length
        if len(node.text.strip()) < 10:
            return False
        
        # Check for valid characters (basic check)
        if not any(c.isalnum() for c in node.text):
            return False
        
        return True
    
    def get_processing_status(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get current processing status."""
        with self.processing_lock:
            if tenant_id:
                # Filter by tenant
                active = {k: v for k, v in self.active_processors.items() if v.tenant_id == tenant_id}
                history = [m for m in self.processing_history if m.tenant_id == tenant_id]
            else:
                active = self.active_processors.copy()
                history = self.processing_history.copy()
        
        return {
            "active_processing": {k: v.to_dict() for k, v in active.items()},
            "processing_history": [m.to_dict() for m in history[-10:]],  # Last 10 entries
            "summary": {
                "active_count": len(active),
                "total_processed": len(history),
                "tenants_active": len(set(m.tenant_id for m in active.values())),
                "recent_success_rate": self._calculate_recent_success_rate(history)
            }
        }
    
    def _calculate_recent_success_rate(self, history: List[ProcessingMetrics]) -> float:
        """Calculate recent success rate from processing history."""
        if not history:
            return 0.0
        
        # Get last 10 processing attempts
        recent = history[-10:]
        successful = sum(1 for m in recent if m.status == ProcessingStatus.COMPLETED)
        
        return (successful / len(recent)) * 100
    
    def cancel_processing(self, tenant_id: str, folder_path: str) -> bool:
        """Cancel active processing for a tenant and folder."""
        key = f"{tenant_id}_{folder_path}"
        
        with self.processing_lock:
            if key in self.active_processors:
                metrics = self.active_processors[key]
                metrics.status = ProcessingStatus.CANCELLED
                metrics.end_time = time.time()
                logger.info(f"Cancelled processing for tenant {tenant_id}, folder: {folder_path}")
                return True
        
        return False
    
    def cleanup_processing_history(self, older_than_hours: int = 24):
        """Clean up old processing history entries."""
        cutoff_time = time.time() - (older_than_hours * 3600)
        
        with self.processing_lock:
            self.processing_history = [
                m for m in self.processing_history 
                if m.start_time > cutoff_time
            ]
        
        logger.info(f"Cleaned up processing history older than {older_than_hours} hours")


# Global processor instance
_document_processor = None


def get_document_processor() -> TenantAwareDocumentProcessor:
    """Get the global document processor instance."""
    global _document_processor
    if _document_processor is None:
        _document_processor = TenantAwareDocumentProcessor()
    return _document_processor


def process_tenant_folder(
    tenant_id: str,
    folder_path: str,
    **kwargs
) -> Tuple[List[BaseNode], ProcessingMetrics]:
    """
    Convenience function to process documents for a tenant folder.
    
    Args:
        tenant_id: Unique identifier for the tenant
        folder_path: Path to the folder containing documents
        **kwargs: Additional configuration options
        
    Returns:
        Tuple[List[BaseNode], ProcessingMetrics]: Processed nodes and metrics
    """
    processor = get_document_processor()
    pipeline_config = processor.create_processing_pipeline(tenant_id, folder_path, **kwargs)
    return processor.process_folder_documents(pipeline_config) 