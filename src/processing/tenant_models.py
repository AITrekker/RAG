"""
Tenant-specific model management for LlamaIndex.

This module provides sophisticated model loading, sharing, and resource management
for multi-tenant environments with GPU/CPU optimization.
"""

import asyncio
import logging
import threading
import time
from typing import Dict, Any, Optional, List, Tuple, Union
from dataclasses import dataclass, field
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import weakref

import torch
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.huggingface import HuggingFaceLLM
from transformers import AutoTokenizer, AutoModel, AutoModelForCausalLM

from .llama_config import TenantLlamaConfig
from ..config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ModelResourceUsage:
    """Track resource usage for a model."""
    model_name: str
    device: str
    memory_mb: float
    last_used: float
    reference_count: int = 0
    tenant_ids: List[str] = field(default_factory=list)


class ResourceAwareModelManager:
    """
    Advanced model manager with resource awareness and sharing capabilities.
    
    Features:
    - Intelligent model sharing across tenants
    - Resource monitoring and limits
    - Lazy loading and automatic unloading
    - GPU memory optimization
    - Batch processing optimization
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the resource-aware model manager."""
        self.config = config or get_settings()
        self.llama_config = self.config.get("llama_index", {})
        
        # Model storage
        self.loaded_models: Dict[str, Any] = {}
        self.model_metadata: Dict[str, ModelResourceUsage] = {}
        self.tenant_model_mapping: Dict[str, Dict[str, str]] = {}
        
        # Resource management
        self.resource_lock = threading.RLock()
        self.max_memory_gb = self.config.get("resources", {}).get("gpu", {}).get("memory_limit_gb", 8.0)
        self.max_concurrent_models = self.llama_config.get("model_management", {}).get("max_concurrent_models", 3)
        self.unload_timeout_minutes = self.llama_config.get("model_management", {}).get("unload_timeout_minutes", 30)
        
        # Performance settings
        self.enable_sharing = self.llama_config.get("tenant_settings", {}).get("shared_models", True)
        self.sharing_strategy = self.llama_config.get("tenant_settings", {}).get("model_sharing_strategy", "memory_efficient")
        self.lazy_loading = self.llama_config.get("model_management", {}).get("lazy_loading", True)
        
        # Background cleanup
        self.cleanup_thread = None
        self.shutdown_event = threading.Event()
        self._start_cleanup_thread()
        
    def _start_cleanup_thread(self):
        """Start background thread for model cleanup."""
        if self.llama_config.get("model_management", {}).get("model_unloading", True):
            self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
            self.cleanup_thread.start()
            logger.info("Started model cleanup background thread")
    
    def _cleanup_worker(self):
        """Background worker for cleaning up unused models."""
        while not self.shutdown_event.is_set():
            try:
                self._cleanup_unused_models()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in model cleanup worker: {e}")
    
    def get_tenant_models(self, tenant_id: str, config: TenantLlamaConfig) -> Dict[str, Any]:
        """
        Get or load models for a specific tenant with resource awareness.
        
        Args:
            tenant_id: Unique identifier for the tenant
            config: Tenant-specific configuration
            
        Returns:
            Dict[str, Any]: Dictionary of loaded models
        """
        with self.resource_lock:
            try:
                # Check if tenant already has models assigned
                if tenant_id in self.tenant_model_mapping:
                    return self._get_existing_tenant_models(tenant_id)
                
                # Load new models for tenant
                return self._load_tenant_models(tenant_id, config)
                
            except Exception as e:
                logger.error(f"Failed to get models for tenant {tenant_id}: {e}")
                raise
    
    def _get_existing_tenant_models(self, tenant_id: str) -> Dict[str, Any]:
        """Get existing models for a tenant."""
        tenant_models = {}
        model_mapping = self.tenant_model_mapping.get(tenant_id, {})
        
        for model_type, model_key in model_mapping.items():
            if model_key in self.loaded_models:
                tenant_models[model_type] = self.loaded_models[model_key]
                # Update last used time
                if model_key in self.model_metadata:
                    self.model_metadata[model_key].last_used = time.time()
        
        return tenant_models
    
    def _load_tenant_models(self, tenant_id: str, config: TenantLlamaConfig) -> Dict[str, Any]:
        """Load models for a new tenant."""
        tenant_models = {}
        
        # Check resource availability
        if not self._check_resource_availability(config):
            raise RuntimeError(f"Insufficient resources to load models for tenant {tenant_id}")
        
        # Load embedding model
        embedding_model = self._get_or_load_embedding_model(tenant_id, config)
        if embedding_model:
            tenant_models["embedding"] = embedding_model
        
        # Load LLM model
        llm_model = self._get_or_load_llm_model(tenant_id, config)
        if llm_model:
            tenant_models["llm"] = llm_model
        
        # Update tenant mapping
        self.tenant_model_mapping[tenant_id] = {
            "embedding": f"embedding_{config.embedding_model}",
            "llm": f"llm_{config.generative_model}"
        }
        
        logger.info(f"Loaded models for tenant {tenant_id}: {list(tenant_models.keys())}")
        return tenant_models
    
    def _get_or_load_embedding_model(self, tenant_id: str, config: TenantLlamaConfig) -> Optional[HuggingFaceEmbedding]:
        """Get or load embedding model with sharing logic."""
        model_key = f"embedding_{config.embedding_model}"
        
        # Check if model can be shared
        if self.enable_sharing and model_key in self.loaded_models:
            self._update_model_usage(model_key, tenant_id)
            logger.info(f"Sharing embedding model {config.embedding_model} with tenant {tenant_id}")
            return self.loaded_models[model_key]
        
        # Load new model
        try:
            embedding_model = HuggingFaceEmbedding(
                model_name=config.embedding_model,
                cache_folder=config.cache_dir,
                device=config.device,
                max_length=self.config.get("models", {}).get("embedding", {}).get("max_length", 512),
                normalize=self.config.get("models", {}).get("embedding", {}).get("normalize_embeddings", True)
            )
            
            # Store model and metadata
            self.loaded_models[model_key] = embedding_model
            self._track_model_resource_usage(model_key, config.embedding_model, config.device, tenant_id)
            
            logger.info(f"Loaded embedding model {config.embedding_model} for tenant {tenant_id}")
            return embedding_model
            
        except Exception as e:
            logger.error(f"Failed to load embedding model {config.embedding_model}: {e}")
            return None
    
    def _get_or_load_llm_model(self, tenant_id: str, config: TenantLlamaConfig) -> Optional[HuggingFaceLLM]:
        """Get or load LLM model with sharing logic."""
        model_key = f"llm_{config.generative_model}"
        
        # Check if model can be shared
        if self.enable_sharing and model_key in self.loaded_models:
            self._update_model_usage(model_key, tenant_id)
            logger.info(f"Sharing LLM model {config.generative_model} with tenant {tenant_id}")
            return self.loaded_models[model_key]
        
        # Load new model
        try:
            generative_config = self.config.get("models", {}).get("generative", {})
            
            llm_model = HuggingFaceLLM(
                model_name=config.generative_model,
                cache_dir=config.cache_dir,
                device_map=config.device if config.device != "auto" else None,
                max_new_tokens=generative_config.get("max_length", 512),
                temperature=generative_config.get("temperature", 0.3),
                do_sample=generative_config.get("do_sample", True)
            )
            
            # Store model and metadata
            self.loaded_models[model_key] = llm_model
            self._track_model_resource_usage(model_key, config.generative_model, config.device, tenant_id)
            
            logger.info(f"Loaded LLM model {config.generative_model} for tenant {tenant_id}")
            return llm_model
            
        except Exception as e:
            logger.error(f"Failed to load LLM model {config.generative_model}: {e}")
            return None
    
    def _track_model_resource_usage(self, model_key: str, model_name: str, device: str, tenant_id: str):
        """Track resource usage for a model."""
        memory_usage = self._estimate_model_memory(model_name, device)
        
        self.model_metadata[model_key] = ModelResourceUsage(
            model_name=model_name,
            device=device,
            memory_mb=memory_usage,
            last_used=time.time(),
            reference_count=1,
            tenant_ids=[tenant_id]
        )
    
    def _update_model_usage(self, model_key: str, tenant_id: str):
        """Update usage tracking for shared model."""
        if model_key in self.model_metadata:
            metadata = self.model_metadata[model_key]
            metadata.last_used = time.time()
            metadata.reference_count += 1
            if tenant_id not in metadata.tenant_ids:
                metadata.tenant_ids.append(tenant_id)
    
    def _estimate_model_memory(self, model_name: str, device: str) -> float:
        """Estimate memory usage for a model in MB."""
        # Simple heuristic based on model name patterns
        memory_estimates = {
            "large": 2000,  # ~2GB
            "base": 1000,   # ~1GB
            "small": 500,   # ~500MB
            "medium": 1500, # ~1.5GB
        }
        
        for size, memory in memory_estimates.items():
            if size in model_name.lower():
                return memory * (2.0 if device.startswith("cuda") else 1.0)  # GPU models use more memory
        
        return 1000  # Default estimate
    
    def _check_resource_availability(self, config: TenantLlamaConfig) -> bool:
        """Check if resources are available for loading new models."""
        current_memory = sum(metadata.memory_mb for metadata in self.model_metadata.values()) / 1024  # GB
        estimated_new_memory = (
            self._estimate_model_memory(config.embedding_model, config.device) +
            self._estimate_model_memory(config.generative_model, config.device)
        ) / 1024  # GB
        
        # Check memory limit
        if current_memory + estimated_new_memory > self.max_memory_gb:
            logger.warning(f"Memory limit exceeded: {current_memory + estimated_new_memory:.2f}GB > {self.max_memory_gb}GB")
            return False
        
        # Check model count limit
        if len(self.loaded_models) >= self.max_concurrent_models * 2:  # 2 models per tenant
            logger.warning(f"Model count limit exceeded: {len(self.loaded_models)} >= {self.max_concurrent_models * 2}")
            return False
        
        return True
    
    def _cleanup_unused_models(self):
        """Clean up unused models based on timeout and reference count."""
        current_time = time.time()
        timeout_seconds = self.unload_timeout_minutes * 60
        
        with self.resource_lock:
            models_to_remove = []
            
            for model_key, metadata in self.model_metadata.items():
                # Check if model is unused and timed out
                if (metadata.reference_count == 0 and 
                    current_time - metadata.last_used > timeout_seconds):
                    models_to_remove.append(model_key)
            
            # Remove unused models
            for model_key in models_to_remove:
                try:
                    if model_key in self.loaded_models:
                        del self.loaded_models[model_key]
                    del self.model_metadata[model_key]
                    logger.info(f"Cleaned up unused model: {model_key}")
                except Exception as e:
                    logger.error(f"Failed to cleanup model {model_key}: {e}")
    
    def release_tenant_models(self, tenant_id: str):
        """Release models for a specific tenant."""
        with self.resource_lock:
            if tenant_id not in self.tenant_model_mapping:
                return
            
            model_mapping = self.tenant_model_mapping[tenant_id]
            
            for model_type, model_key in model_mapping.items():
                if model_key in self.model_metadata:
                    metadata = self.model_metadata[model_key]
                    
                    # Remove tenant from usage
                    if tenant_id in metadata.tenant_ids:
                        metadata.tenant_ids.remove(tenant_id)
                    
                    metadata.reference_count = max(0, metadata.reference_count - 1)
                    
                    # If no more references, mark for cleanup
                    if metadata.reference_count == 0:
                        metadata.last_used = time.time()
            
            # Remove tenant mapping
            del self.tenant_model_mapping[tenant_id]
            logger.info(f"Released models for tenant: {tenant_id}")
    
    def get_resource_status(self) -> Dict[str, Any]:
        """Get current resource usage status."""
        with self.resource_lock:
            total_memory_mb = sum(metadata.memory_mb for metadata in self.model_metadata.values())
            
            return {
                "loaded_models": len(self.loaded_models),
                "total_memory_gb": total_memory_mb / 1024,
                "memory_limit_gb": self.max_memory_gb,
                "memory_utilization": (total_memory_mb / 1024) / self.max_memory_gb * 100,
                "active_tenants": len(self.tenant_model_mapping),
                "model_details": {
                    key: {
                        "model_name": metadata.model_name,
                        "device": metadata.device,
                        "memory_mb": metadata.memory_mb,
                        "reference_count": metadata.reference_count,
                        "tenant_count": len(metadata.tenant_ids),
                        "last_used": metadata.last_used
                    }
                    for key, metadata in self.model_metadata.items()
                }
            }
    
    def shutdown(self):
        """Shutdown the model manager and cleanup resources."""
        logger.info("Shutting down ResourceAwareModelManager")
        
        # Stop cleanup thread
        if self.cleanup_thread:
            self.shutdown_event.set()
            self.cleanup_thread.join(timeout=5)
        
        # Clear all models
        with self.resource_lock:
            self.loaded_models.clear()
            self.model_metadata.clear()
            self.tenant_model_mapping.clear()
        
        logger.info("ResourceAwareModelManager shutdown complete")


# Global model manager instance
_model_manager = None


def get_model_manager() -> ResourceAwareModelManager:
    """Get the global model manager instance."""
    global _model_manager
    if _model_manager is None:
        _model_manager = ResourceAwareModelManager()
    return _model_manager


def get_tenant_models(tenant_id: str, config: TenantLlamaConfig) -> Dict[str, Any]:
    """
    Convenience function to get models for a tenant.
    
    Args:
        tenant_id: Unique identifier for the tenant
        config: Tenant configuration
        
    Returns:
        Dict[str, Any]: Dictionary of tenant models
    """
    manager = get_model_manager()
    return manager.get_tenant_models(tenant_id, config)


def release_tenant_models(tenant_id: str):
    """
    Convenience function to release models for a tenant.
    
    Args:
        tenant_id: Unique identifier for the tenant
    """
    manager = get_model_manager()
    manager.release_tenant_models(tenant_id) 