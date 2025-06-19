"""
LlamaIndex configuration module with tenant-aware settings.

This module provides configuration classes and utilities for setting up
LlamaIndex with multi-tenant support, resource management, and optimized
settings for the Enterprise RAG pipeline.
"""

import os
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path

import torch
from llama_index.core import Settings
from llama_index.core.node_parser import SimpleNodeParser
from llama_index.core.text_splitter import RecursiveCharacterTextSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.huggingface import HuggingFaceLLM

from ..config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class TenantLlamaConfig:
    """Configuration class for tenant-specific LlamaIndex settings."""
    
    tenant_id: str
    
    # Model configurations
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    generative_model: str = "microsoft/DialoGPT-medium"
    reranker_model: str = "BAAI/bge-reranker-large"
    
    # Resource settings
    device: str = "auto"
    max_memory_gb: float = 4.0
    batch_size: int = 32
    max_workers: int = 2
    
    # Chunking settings
    chunk_size: int = 1000
    chunk_overlap: int = 200
    separators: List[str] = field(default_factory=lambda: ["\n\n", "\n", " ", ""])
    
    # Processing settings
    max_files_per_batch: int = 10
    enable_metadata_extraction: bool = True
    cache_embeddings: bool = True
    
    # Directory paths
    cache_dir: Optional[str] = None
    temp_dir: Optional[str] = None
    
    def __post_init__(self):
        """Initialize tenant-specific paths and validate configuration."""
        if self.cache_dir is None:
            self.cache_dir = f"./models/tenant_{self.tenant_id}"
        
        if self.temp_dir is None:
            self.temp_dir = f"./data/temp/tenant_{self.tenant_id}"
        
        # Create directories if they don't exist
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
        Path(self.temp_dir).mkdir(parents=True, exist_ok=True)
        
        # Validate device settings
        if self.device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        logger.info(f"Initialized LlamaConfig for tenant {self.tenant_id} with device: {self.device}")


class TenantAwareLlamaManager:
    """
    Manager class for handling tenant-aware LlamaIndex configurations.
    
    This class manages multiple tenant configurations, resource allocation,
    and provides utilities for creating tenant-specific LlamaIndex settings.
    """
    
    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        """
        Initialize the tenant-aware LlamaIndex manager.
        
        Args:
            config_dict: Configuration dictionary from settings
        """
        self.config = config_dict or get_settings()
        self.tenant_configs: Dict[str, TenantLlamaConfig] = {}
        self.shared_models: Dict[str, Any] = {}
        self.resource_locks: Dict[str, bool] = {}
        
        # Initialize global settings from config
        self._initialize_global_settings()
        
    def _initialize_global_settings(self):
        """Initialize global LlamaIndex settings."""
        try:
            # Get configuration sections
            models_config = self.config.get("models", {})
            resources_config = self.config.get("resources", {})
            rag_config = self.config.get("rag", {})
            
            # Set global chunk size and overlap
            chunk_size = self.config.get("file_processing", {}).get("chunking", {}).get("chunk_size", 1000)
            chunk_overlap = self.config.get("file_processing", {}).get("chunking", {}).get("chunk_overlap", 200)
            
            # Configure global settings
            Settings.chunk_size = chunk_size
            Settings.chunk_overlap = chunk_overlap
            
            # Set global context window
            context_window = rag_config.get("context", {}).get("max_context_length", 4000)
            Settings.context_window = context_window
            
            logger.info(f"Initialized global LlamaIndex settings: chunk_size={chunk_size}, context_window={context_window}")
            
        except Exception as e:
            logger.error(f"Failed to initialize global LlamaIndex settings: {e}")
            raise
    
    def get_tenant_config(self, tenant_id: str) -> TenantLlamaConfig:
        """
        Get or create tenant-specific configuration.
        
        Args:
            tenant_id: Unique identifier for the tenant
            
        Returns:
            TenantLlamaConfig: Tenant-specific configuration
        """
        if tenant_id not in self.tenant_configs:
            self.tenant_configs[tenant_id] = self._create_tenant_config(tenant_id)
        
        return self.tenant_configs[tenant_id]
    
    def _create_tenant_config(self, tenant_id: str) -> TenantLlamaConfig:
        """
        Create a new tenant configuration based on global settings.
        
        Args:
            tenant_id: Unique identifier for the tenant
            
        Returns:
            TenantLlamaConfig: New tenant configuration
        """
        try:
            # Get configuration sections
            models_config = self.config.get("models", {})
            resources_config = self.config.get("resources", {})
            file_processing_config = self.config.get("file_processing", {})
            tenancy_config = self.config.get("tenancy", {})
            
            # Get tenant-specific resource limits
            resource_limits = tenancy_config.get("resource_limits", {})
            
            # Create tenant configuration
            tenant_config = TenantLlamaConfig(
                tenant_id=tenant_id,
                embedding_model=models_config.get("embedding", {}).get("name", "BAAI/bge-large-en-v1.5"),
                generative_model=models_config.get("generative", {}).get("name", "microsoft/DialoGPT-medium"),
                reranker_model=models_config.get("reranker", {}).get("name", "BAAI/bge-reranker-large"),
                device=models_config.get("embedding", {}).get("device", "auto"),
                max_memory_gb=resources_config.get("gpu", {}).get("memory_limit_gb", 4.0),
                batch_size=models_config.get("embedding", {}).get("batch_size", 32),
                max_workers=resources_config.get("cpu", {}).get("max_workers", 2),
                chunk_size=file_processing_config.get("chunking", {}).get("chunk_size", 1000),
                chunk_overlap=file_processing_config.get("chunking", {}).get("chunk_overlap", 200),
                separators=file_processing_config.get("chunking", {}).get("separators", ["\n\n", "\n", " ", ""]),
                max_files_per_batch=resource_limits.get("max_files_per_batch", 10),
                cache_dir=f"./models/tenant_{tenant_id}",
                temp_dir=f"./data/temp/tenant_{tenant_id}"
            )
            
            logger.info(f"Created configuration for tenant: {tenant_id}")
            return tenant_config
            
        except Exception as e:
            logger.error(f"Failed to create tenant configuration for {tenant_id}: {e}")
            raise
    
    def configure_tenant_settings(self, tenant_id: str) -> Dict[str, Any]:
        """
        Configure LlamaIndex Settings for a specific tenant.
        
        Args:
            tenant_id: Unique identifier for the tenant
            
        Returns:
            Dict[str, Any]: Configuration summary
        """
        try:
            tenant_config = self.get_tenant_config(tenant_id)
            
            # Set tenant-specific settings
            Settings.chunk_size = tenant_config.chunk_size
            Settings.chunk_overlap = tenant_config.chunk_overlap
            
            # Configure embedding model if not shared
            if not self._is_model_shared(tenant_config.embedding_model):
                embedding_model = self._create_embedding_model(tenant_config)
                Settings.embed_model = embedding_model
                self.shared_models[f"embedding_{tenant_id}"] = embedding_model
            
            # Configure LLM if not shared
            if not self._is_model_shared(tenant_config.generative_model):
                llm_model = self._create_llm_model(tenant_config)
                Settings.llm = llm_model
                self.shared_models[f"llm_{tenant_id}"] = llm_model
            
            # Configure node parser
            node_parser = self._create_node_parser(tenant_config)
            Settings.node_parser = node_parser
            
            config_summary = {
                "tenant_id": tenant_id,
                "chunk_size": tenant_config.chunk_size,
                "chunk_overlap": tenant_config.chunk_overlap,
                "device": tenant_config.device,
                "embedding_model": tenant_config.embedding_model,
                "generative_model": tenant_config.generative_model,
                "batch_size": tenant_config.batch_size,
                "cache_dir": tenant_config.cache_dir
            }
            
            logger.info(f"Configured LlamaIndex settings for tenant: {tenant_id}")
            return config_summary
            
        except Exception as e:
            logger.error(f"Failed to configure LlamaIndex settings for tenant {tenant_id}: {e}")
            raise
    
    def _create_embedding_model(self, config: TenantLlamaConfig) -> HuggingFaceEmbedding:
        """Create HuggingFace embedding model for tenant."""
        return HuggingFaceEmbedding(
            model_name=config.embedding_model,
            cache_folder=config.cache_dir,
            device=config.device,
            max_length=512,
            normalize=True
        )
    
    def _create_llm_model(self, config: TenantLlamaConfig) -> HuggingFaceLLM:
        """Create HuggingFace LLM model for tenant."""
        return HuggingFaceLLM(
            model_name=config.generative_model,
            cache_dir=config.cache_dir,
            device_map=config.device,
            max_new_tokens=512,
            temperature=0.3,
            do_sample=True
        )
    
    def _create_node_parser(self, config: TenantLlamaConfig) -> SimpleNodeParser:
        """Create node parser with tenant-specific settings."""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            separators=config.separators
        )
        
        return SimpleNodeParser(
            text_splitter=text_splitter,
            include_metadata=config.enable_metadata_extraction,
            include_prev_next_rel=True
        )
    
    def _is_model_shared(self, model_name: str) -> bool:
        """Check if a model is already loaded and can be shared."""
        return model_name in [model for key, model in self.shared_models.items()]
    
    def get_tenant_models(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get all models configured for a specific tenant.
        
        Args:
            tenant_id: Unique identifier for the tenant
            
        Returns:
            Dict[str, Any]: Dictionary of tenant models
        """
        tenant_models = {}
        
        for key, model in self.shared_models.items():
            if tenant_id in key:
                model_type = key.split("_")[0]
                tenant_models[model_type] = model
        
        return tenant_models
    
    def cleanup_tenant_resources(self, tenant_id: str):
        """
        Clean up resources for a specific tenant.
        
        Args:
            tenant_id: Unique identifier for the tenant
        """
        try:
            # Remove tenant-specific models from memory
            keys_to_remove = [key for key in self.shared_models.keys() if tenant_id in key]
            for key in keys_to_remove:
                del self.shared_models[key]
            
            # Remove tenant configuration
            if tenant_id in self.tenant_configs:
                del self.tenant_configs[tenant_id]
            
            # Release resource locks
            if tenant_id in self.resource_locks:
                del self.resource_locks[tenant_id]
            
            logger.info(f"Cleaned up resources for tenant: {tenant_id}")
            
        except Exception as e:
            logger.error(f"Failed to cleanup resources for tenant {tenant_id}: {e}")
    
    def get_resource_status(self) -> Dict[str, Any]:
        """
        Get current resource allocation status.
        
        Returns:
            Dict[str, Any]: Resource status information
        """
        return {
            "active_tenants": list(self.tenant_configs.keys()),
            "loaded_models": list(self.shared_models.keys()),
            "resource_locks": self.resource_locks,
            "memory_usage": self._get_memory_usage(),
            "gpu_available": torch.cuda.is_available(),
            "gpu_count": torch.cuda.device_count() if torch.cuda.is_available() else 0
        }
    
    def _get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage statistics."""
        memory_stats = {}
        
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                allocated = torch.cuda.memory_allocated(i) / 1024**3  # GB
                cached = torch.cuda.memory_reserved(i) / 1024**3  # GB
                memory_stats[f"gpu_{i}"] = {
                    "allocated_gb": allocated,
                    "cached_gb": cached
                }
        
        return memory_stats


# Global manager instance
_llama_manager = None


def get_llama_manager() -> TenantAwareLlamaManager:
    """Get the global LlamaIndex manager instance."""
    global _llama_manager
    if _llama_manager is None:
        _llama_manager = TenantAwareLlamaManager()
    return _llama_manager


def configure_tenant_llama(tenant_id: str) -> Dict[str, Any]:
    """
    Convenience function to configure LlamaIndex for a specific tenant.
    
    Args:
        tenant_id: Unique identifier for the tenant
        
    Returns:
        Dict[str, Any]: Configuration summary
    """
    manager = get_llama_manager()
    return manager.configure_tenant_settings(tenant_id)


def get_tenant_config(tenant_id: str) -> TenantLlamaConfig:
    """
    Convenience function to get tenant configuration.
    
    Args:
        tenant_id: Unique identifier for the tenant
        
    Returns:
        TenantLlamaConfig: Tenant configuration
    """
    manager = get_llama_manager()
    return manager.get_tenant_config(tenant_id) 