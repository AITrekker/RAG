"""
LlamaIndex integration processor for Enterprise RAG system.

This module provides the LlamaIndex-specific processing pipeline that integrates
all document processing components with tenant awareness and advanced features.
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

from llama_index.core import Document, VectorStoreIndex, StorageContext
from llama_index.core.schema import BaseNode
from llama_index.core.service_context import ServiceContext
from llama_index.core.callbacks import CallbackManager

from .llama_config import TenantLlamaConfig, get_tenant_config, configure_tenant_llama
from .tenant_models import get_model_manager, get_tenant_models
from .document_processor import (
    TenantAwareDocumentProcessor, 
    ProcessingPipelineConfig, 
    ProcessingMetrics,
    get_document_processor
)
from .text_splitters import SplittingStrategy
from .node_parsers import NodeParsingStrategy
from ..config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class LlamaProcessingConfig:
    """Configuration for LlamaIndex processing."""
    tenant_id: str
    folder_path: str
    
    # Processing strategies
    splitting_strategy: SplittingStrategy = SplittingStrategy.RECURSIVE
    parsing_strategy: NodeParsingStrategy = NodeParsingStrategy.SIMPLE
    
    # LlamaIndex specific
    create_index: bool = True
    index_type: str = "vector"  # vector, tree, keyword, etc.
    enable_service_context: bool = True
    enable_callbacks: bool = True
    
    # Performance options
    batch_size: int = 10
    max_memory_usage_gb: float = 4.0
    enable_async_processing: bool = False


class TenantAwareLlamaProcessor:
    """
    LlamaIndex integration processor with tenant awareness.
    
    Features:
    - Complete LlamaIndex pipeline integration
    - Tenant-specific model and configuration management
    - Advanced document processing with LlamaIndex
    - Index creation and management
    - Service context optimization
    - Comprehensive monitoring and logging
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the LlamaIndex processor.
        
        Args:
            config: Global configuration dictionary
        """
        self.config = config or get_settings()
        self.document_processor = get_document_processor()
        self.model_manager = get_model_manager()
        
        # LlamaIndex configuration
        self.llama_config = self.config.get("llama_index", {})
        
        # Tenant service contexts
        self.tenant_service_contexts: Dict[str, ServiceContext] = {}
        
        logger.info("Initialized TenantAwareLlamaProcessor")
    
    def create_llama_processing_config(
        self, 
        tenant_id: str, 
        folder_path: str, 
        **kwargs
    ) -> LlamaProcessingConfig:
        """
        Create LlamaIndex processing configuration for a tenant.
        
        Args:
            tenant_id: Unique identifier for the tenant
            folder_path: Path to the folder containing documents
            **kwargs: Additional configuration options
            
        Returns:
            LlamaProcessingConfig: LlamaIndex processing configuration
        """
        tenant_config = get_tenant_config(tenant_id)
        
        return LlamaProcessingConfig(
            tenant_id=tenant_id,
            folder_path=folder_path,
            splitting_strategy=SplittingStrategy(kwargs.get("splitting_strategy", "recursive")),
            parsing_strategy=NodeParsingStrategy(kwargs.get("parsing_strategy", "simple")),
            create_index=kwargs.get("create_index", True),
            index_type=kwargs.get("index_type", "vector"),
            enable_service_context=kwargs.get("enable_service_context", True),
            enable_callbacks=kwargs.get("enable_callbacks", True),
            batch_size=kwargs.get("batch_size", tenant_config.max_files_per_batch),
            max_memory_usage_gb=kwargs.get("max_memory_usage_gb", tenant_config.max_memory_gb),
            enable_async_processing=kwargs.get("enable_async_processing", False)
        )
    
    def process_documents_with_llama(
        self, 
        llama_config: LlamaProcessingConfig
    ) -> Tuple[List[BaseNode], Optional[VectorStoreIndex], ProcessingMetrics]:
        """
        Process documents using the complete LlamaIndex pipeline.
        
        Args:
            llama_config: LlamaIndex processing configuration
            
        Returns:
            Tuple[List[BaseNode], Optional[VectorStoreIndex], ProcessingMetrics]: 
            Processed nodes, created index (if enabled), and processing metrics
        """
        start_time = time.time()
        
        try:
            # Configure LlamaIndex for tenant
            logger.info(f"Configuring LlamaIndex for tenant {llama_config.tenant_id}")
            llama_settings = configure_tenant_llama(llama_config.tenant_id)
            
            # Create processing pipeline configuration
            pipeline_config = ProcessingPipelineConfig(
                tenant_id=llama_config.tenant_id,
                folder_path=llama_config.folder_path,
                splitting_strategy=llama_config.splitting_strategy,
                parsing_strategy=llama_config.parsing_strategy,
                batch_size=llama_config.batch_size,
                max_memory_usage_gb=llama_config.max_memory_usage_gb,
                enable_metadata_extraction=True,
                enable_folder_hierarchy_tracking=True,
                enable_content_validation=True
            )
            
            # Process documents using the main processor
            logger.info(f"Processing documents for tenant {llama_config.tenant_id}")
            nodes, metrics = self.document_processor.process_folder_documents(pipeline_config)
            
            # Create index if enabled
            index = None
            if llama_config.create_index and nodes:
                logger.info(f"Creating {llama_config.index_type} index for tenant {llama_config.tenant_id}")
                index = self._create_tenant_index(llama_config, nodes)
                
                # Update metrics with index creation time
                if index:
                    metrics.warnings.append(f"Created {llama_config.index_type} index with {len(nodes)} nodes")
            
            # Log completion
            processing_time = time.time() - start_time
            logger.info(
                f"Completed LlamaIndex processing for tenant {llama_config.tenant_id}: "
                f"{len(nodes)} nodes, index={'created' if index else 'skipped'}, "
                f"{processing_time:.2f}s"
            )
            
            return nodes, index, metrics
            
        except Exception as e:
            logger.error(f"Failed to process documents with LlamaIndex for tenant {llama_config.tenant_id}: {e}")
            # Create empty metrics with error
            error_metrics = ProcessingMetrics(
                tenant_id=llama_config.tenant_id,
                folder_path=llama_config.folder_path,
                start_time=start_time,
                end_time=time.time()
            )
            error_metrics.errors.append({
                "error": str(e),
                "timestamp": time.time(),
                "stage": "llama_processing"
            })
            return [], None, error_metrics
    
    def _create_tenant_index(
        self, 
        llama_config: LlamaProcessingConfig, 
        nodes: List[BaseNode]
    ) -> Optional[VectorStoreIndex]:
        """Create an index for the tenant using processed nodes."""
        try:
            # Get service context for tenant
            service_context = self._get_tenant_service_context(llama_config.tenant_id)
            
            # Create storage context (can be extended for persistent storage)
            storage_context = StorageContext.from_defaults()
            
            # Create index based on type
            if llama_config.index_type.lower() == "vector":
                index = VectorStoreIndex(
                    nodes=nodes,
                    service_context=service_context,
                    storage_context=storage_context
                )
            else:
                # For now, default to vector index for unsupported types
                logger.warning(f"Index type {llama_config.index_type} not fully implemented, using vector index")
                index = VectorStoreIndex(
                    nodes=nodes,
                    service_context=service_context,
                    storage_context=storage_context
                )
            
            logger.info(f"Created {llama_config.index_type} index with {len(nodes)} nodes for tenant {llama_config.tenant_id}")
            return index
            
        except Exception as e:
            logger.error(f"Failed to create index for tenant {llama_config.tenant_id}: {e}")
            return None
    
    def _get_tenant_service_context(self, tenant_id: str) -> ServiceContext:
        """Get or create service context for a tenant."""
        if tenant_id in self.tenant_service_contexts:
            return self.tenant_service_contexts[tenant_id]
        
        try:
            # Get tenant configuration and models
            tenant_config = get_tenant_config(tenant_id)
            tenant_models = get_tenant_models(tenant_id, tenant_config)
            
            # Create service context with tenant-specific models
            service_context_kwargs = {}
            
            # Add embedding model if available
            if "embedding" in tenant_models:
                service_context_kwargs["embed_model"] = tenant_models["embedding"]
            
            # Add LLM if available
            if "llm" in tenant_models:
                service_context_kwargs["llm"] = tenant_models["llm"]
            
            # Add callback manager if enabled
            if self.llama_config.get("global", {}).get("enable_logging", True):
                callback_manager = CallbackManager()
                service_context_kwargs["callback_manager"] = callback_manager
            
            # Create service context
            if service_context_kwargs:
                service_context = ServiceContext.from_defaults(**service_context_kwargs)
            else:
                service_context = ServiceContext.from_defaults()
            
            # Cache for reuse
            self.tenant_service_contexts[tenant_id] = service_context
            
            logger.info(f"Created service context for tenant {tenant_id}")
            return service_context
            
        except Exception as e:
            logger.error(f"Failed to create service context for tenant {tenant_id}: {e}")
            # Fallback to default service context
            service_context = ServiceContext.from_defaults()
            self.tenant_service_contexts[tenant_id] = service_context
            return service_context
    
    def process_single_document_with_llama(
        self, 
        tenant_id: str, 
        document: Document,
        **kwargs
    ) -> Tuple[List[BaseNode], ProcessingMetrics]:
        """
        Process a single document using LlamaIndex for a specific tenant.
        
        Args:
            tenant_id: Unique identifier for the tenant
            document: Document to process
            **kwargs: Additional processing options
            
        Returns:
            Tuple[List[BaseNode], ProcessingMetrics]: Processed nodes and metrics
        """
        start_time = time.time()
        
        try:
            # Configure LlamaIndex for tenant
            configure_tenant_llama(tenant_id)
            
            # Get tenant configuration
            tenant_config = get_tenant_config(tenant_id)
            
            # Create processing components
            from .text_splitters import create_text_splitter_manager
            from .node_parsers import create_node_parser_manager
            
            splitter_manager = create_text_splitter_manager(tenant_config)
            parser_manager = create_node_parser_manager(tenant_config)
            
            # Parse document into nodes
            parsing_strategy = NodeParsingStrategy(kwargs.get("parsing_strategy", "simple"))
            nodes = parser_manager.parse_documents([document], parsing_strategy)
            
            # Create metrics
            metrics = ProcessingMetrics(
                tenant_id=tenant_id,
                folder_path="single_document",
                start_time=start_time,
                end_time=time.time(),
                total_files=1,
                processed_files=1,
                total_documents=1,
                total_nodes=len(nodes),
                total_processing_time=time.time() - start_time
            )
            
            logger.info(f"Processed single document for tenant {tenant_id}: {len(nodes)} nodes")
            return nodes, metrics
            
        except Exception as e:
            logger.error(f"Failed to process single document for tenant {tenant_id}: {e}")
            error_metrics = ProcessingMetrics(
                tenant_id=tenant_id,
                folder_path="single_document",
                start_time=start_time,
                end_time=time.time(),
                total_files=1,
                failed_files=1
            )
            error_metrics.errors.append({
                "error": str(e),
                "timestamp": time.time(),
                "stage": "single_document_processing"
            })
            return [], error_metrics
    
    def create_query_engine_for_tenant(
        self, 
        tenant_id: str, 
        index: VectorStoreIndex,
        **kwargs
    ):
        """
        Create a query engine for a tenant using their index.
        
        Args:
            tenant_id: Unique identifier for the tenant
            index: VectorStoreIndex to query
            **kwargs: Additional query engine options
            
        Returns:
            Query engine instance
        """
        try:
            # Get service context for tenant
            service_context = self._get_tenant_service_context(tenant_id)
            
            # Create query engine
            query_engine = index.as_query_engine(
                service_context=service_context,
                similarity_top_k=kwargs.get("similarity_top_k", 5),
                response_mode=kwargs.get("response_mode", "compact")
            )
            
            logger.info(f"Created query engine for tenant {tenant_id}")
            return query_engine
            
        except Exception as e:
            logger.error(f"Failed to create query engine for tenant {tenant_id}: {e}")
            return None
    
    def get_tenant_processing_summary(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get processing summary for a specific tenant.
        
        Args:
            tenant_id: Unique identifier for the tenant
            
        Returns:
            Dict[str, Any]: Processing summary
        """
        # Get processing status from document processor
        status = self.document_processor.get_processing_status(tenant_id)
        
        # Add LlamaIndex specific information
        llama_info = {
            "llama_configured": tenant_id in self.tenant_service_contexts,
            "service_context_available": tenant_id in self.tenant_service_contexts,
            "models_loaded": bool(self.model_manager.get_tenant_models(tenant_id))
        }
        
        return {
            "tenant_id": tenant_id,
            "processing_status": status,
            "llama_index_info": llama_info,
            "resource_status": self.model_manager.get_resource_status()
        }
    
    def cleanup_tenant_resources(self, tenant_id: str):
        """
        Clean up all resources for a specific tenant.
        
        Args:
            tenant_id: Unique identifier for the tenant
        """
        try:
            # Clean up service context
            if tenant_id in self.tenant_service_contexts:
                del self.tenant_service_contexts[tenant_id]
            
            # Clean up model manager resources
            self.model_manager.release_tenant_models(tenant_id)
            
            logger.info(f"Cleaned up LlamaIndex resources for tenant {tenant_id}")
            
        except Exception as e:
            logger.error(f"Failed to cleanup resources for tenant {tenant_id}: {e}")
    
    def get_processing_capabilities(self) -> Dict[str, Any]:
        """Get the processing capabilities of this processor."""
        return {
            "supported_splitting_strategies": [strategy.value for strategy in SplittingStrategy],
            "supported_parsing_strategies": [strategy.value for strategy in NodeParsingStrategy],
            "supported_index_types": ["vector"],  # Can be extended
            "features": {
                "tenant_isolation": True,
                "resource_management": True,
                "batch_processing": True,
                "folder_based_processing": True,
                "metadata_extraction": True,
                "hierarchy_tracking": True,
                "content_validation": True,
                "async_processing": False,  # Can be implemented
                "persistent_storage": False,  # Can be implemented
                "custom_callbacks": True
            },
            "resource_limits": {
                "max_concurrent_tenants": self.model_manager.max_concurrent_models,
                "max_memory_gb": self.model_manager.max_memory_gb,
                "supported_file_formats": self.config.get("file_processing", {}).get("supported_formats", [])
            }
        }


# Global processor instance
_llama_processor = None


def get_llama_processor() -> TenantAwareLlamaProcessor:
    """Get the global LlamaIndex processor instance."""
    global _llama_processor
    if _llama_processor is None:
        _llama_processor = TenantAwareLlamaProcessor()
    return _llama_processor


def process_tenant_documents_with_llama(
    tenant_id: str,
    folder_path: str,
    **kwargs
) -> Tuple[List[BaseNode], Optional[VectorStoreIndex], ProcessingMetrics]:
    """
    Convenience function to process tenant documents with LlamaIndex.
    
    Args:
        tenant_id: Unique identifier for the tenant
        folder_path: Path to the folder containing documents
        **kwargs: Additional configuration options
        
    Returns:
        Tuple[List[BaseNode], Optional[VectorStoreIndex], ProcessingMetrics]: 
        Processed nodes, created index, and metrics
    """
    processor = get_llama_processor()
    llama_config = processor.create_llama_processing_config(tenant_id, folder_path, **kwargs)
    return processor.process_documents_with_llama(llama_config) 