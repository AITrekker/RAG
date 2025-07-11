"""
Application settings and configuration for the Enterprise RAG Platform.

Handles environment variables, database configuration, and application settings.
"""

import os
from typing import List, Optional, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from pathlib import Path

# Define the project's base directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
CACHE_DIR = BASE_DIR / "cache"

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application settings
    app_name: str = Field(default="Enterprise RAG Platform", env="APP_NAME")
    project_name: str = Field(default="Enterprise RAG Platform", env="PROJECT_NAME")
    debug: bool = Field(default=False, env="DEBUG")
    version: str = Field(default="1.0.0", env="VERSION")
    
    # Server settings
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    
    # Security settings - will be dynamically overridden in debug mode
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000"], 
        env="ALLOWED_ORIGINS"
    )
    
    # Database settings
    database_url: str = Field(default="postgresql://rag_user:rag_password@localhost:5432/rag_db", env="DATABASE_URL")
    db_pool_size: int = Field(default=20, env="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=30, env="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, env="DB_POOL_TIMEOUT")
    db_pool_recycle: int = Field(default=3600, env="DB_POOL_RECYCLE")
    
    # PostgreSQL with pgvector settings
    pgvector_enabled: bool = Field(default=True, env="PGVECTOR_ENABLED")
    vector_dimensions: int = Field(default=384, env="VECTOR_DIMENSIONS")
    vector_index_type: str = Field(default="ivfflat", env="VECTOR_INDEX_TYPE")
    vector_distance_metric: str = Field(default="cosine", env="VECTOR_DISTANCE_METRIC")
    
    # Embedding model settings
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2", 
        env="EMBEDDING_MODEL"
    )
    embedding_model_dimensions: int = Field(default=384, env="EMBEDDING_MODEL_DIMENSIONS")
    embedding_device: str = Field(default="cpu", env="EMBEDDING_DEVICE")
    embedding_batch_size: int = Field(default=32, env="EMBEDDING_BATCH_SIZE")
    
    # RAG/LLM settings - Comprehensive configuration for iterative tuning
    rag_llm_model: str = Field(
        default="gpt2-medium", 
        env="RAG_LLM_MODEL",
        description="LLM model for answer generation. Options: gpt2-medium, gpt2-large, microsoft/DialoGPT-medium"
    )
    rag_max_length: int = Field(default=512, env="RAG_MAX_LENGTH")
    rag_max_new_tokens: int = Field(default=200, env="RAG_MAX_NEW_TOKENS")
    rag_temperature: float = Field(default=0.3, env="RAG_TEMPERATURE", description="Lower = more focused, higher = more creative")
    rag_top_p: float = Field(default=0.85, env="RAG_TOP_P", description="Nucleus sampling parameter")
    rag_top_k: int = Field(default=40, env="RAG_TOP_K", description="Limit vocabulary for coherence")
    rag_repetition_penalty: float = Field(default=1.3, env="RAG_REPETITION_PENALTY")
    rag_early_stopping: bool = Field(default=True, env="RAG_EARLY_STOPPING")
    rag_do_sample: bool = Field(default=True, env="RAG_DO_SAMPLE")
    rag_enable_quantization: bool = Field(default=True, env="RAG_ENABLE_QUANTIZATION")
    rag_cache_dir: str = Field(default=str(CACHE_DIR / "transformers"), env="RAG_CACHE_DIR")
    
    # RAG Retrieval settings
    rag_max_sources: int = Field(default=5, env="RAG_MAX_SOURCES", description="Max source documents to retrieve")
    rag_confidence_threshold: float = Field(default=0.3, env="RAG_CONFIDENCE_THRESHOLD")
    rag_max_context_length: int = Field(default=2000, env="RAG_MAX_CONTEXT_LENGTH", description="Max characters in context")
    rag_source_preview_length: int = Field(default=200, env="RAG_SOURCE_PREVIEW_LENGTH")
    
    # RAG Response quality settings
    rag_max_sentences: int = Field(default=4, env="RAG_MAX_SENTENCES", description="Max sentences in response")
    rag_min_sentence_length: int = Field(default=10, env="RAG_MIN_SENTENCE_LENGTH")
    rag_remove_prompt_artifacts: bool = Field(default=True, env="RAG_REMOVE_PROMPT_ARTIFACTS")
    rag_ensure_punctuation: bool = Field(default=True, env="RAG_ENSURE_PUNCTUATION")
    
    # Legacy LLM settings (for backwards compatibility)
    llm_model: str = Field(
        default="google/flan-t5-base", 
        env="LLM_MODEL"
    )
    llm_max_length: int = Field(default=1024, env="LLM_MAX_LENGTH")
    llm_temperature: float = Field(default=0.6, env="LLM_TEMPERATURE")
    llm_enable_quantization: bool = Field(default=True, env="LLM_ENABLE_QUANTIZATION")
    llm_cache_dir: str = Field(default=str(CACHE_DIR / "transformers"), env="LLM_CACHE_DIR")
    
    # Document processing settings
    chunk_size: int = Field(default=512, env="CHUNK_SIZE")
    chunk_overlap: int = Field(default=50, env="CHUNK_OVERLAP")
    
    # Storage settings - Now relative to BASE_DIR
    documents_path: str = Field(default=str(BASE_DIR / "data" / "uploads"), env="DOCUMENTS_PATH")
    
    # API settings
    api_v1_str: str = Field(default="/api/v1", env="API_V1_STR")
    
    # Logging settings
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT"
    )
    log_file: Optional[str] = Field(default=None, env="LOG_FILE")
    
    # Development settings
    reload_on_change: bool = Field(default=False, env="RELOAD_ON_CHANGE")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "allow"  # Allow extra environment variables

    def get_embedding_config(self) -> dict:
        """Get embedding model configuration."""
        return {
            "model_name": self.embedding_model,
            "device": self.embedding_device,
            "batch_size": self.embedding_batch_size
        }
    
    def get_rag_llm_config(self) -> dict:
        """Get RAG LLM configuration for answer generation."""
        return {
            "model_name": self.rag_llm_model,
            "max_length": self.rag_max_length,
            "max_new_tokens": self.rag_max_new_tokens,
            "temperature": self.rag_temperature,
            "top_p": self.rag_top_p,
            "top_k": self.rag_top_k,
            "repetition_penalty": self.rag_repetition_penalty,
            "early_stopping": self.rag_early_stopping,
            "do_sample": self.rag_do_sample,
            "enable_quantization": self.rag_enable_quantization,
            "cache_dir": self.rag_cache_dir
        }
    
    def get_rag_retrieval_config(self) -> dict:
        """Get RAG retrieval configuration."""
        return {
            "max_sources": self.rag_max_sources,
            "confidence_threshold": self.rag_confidence_threshold,
            "max_context_length": self.rag_max_context_length,
            "source_preview_length": self.rag_source_preview_length
        }
    
    def get_rag_response_config(self) -> dict:
        """Get RAG response quality configuration."""
        return {
            "max_sentences": self.rag_max_sentences,
            "min_sentence_length": self.rag_min_sentence_length,
            "remove_prompt_artifacts": self.rag_remove_prompt_artifacts,
            "ensure_punctuation": self.rag_ensure_punctuation
        }
    
    def get_llm_config(self) -> dict:
        """Get legacy LLM service configuration."""
        return {
            "model_name": self.llm_model,
            "max_length": self.llm_max_length,
            "temperature": self.llm_temperature,
            "enable_quantization": self.llm_enable_quantization,
            "cache_dir": self.llm_cache_dir
        }
    
    def get_chunking_config(self) -> dict:
        """Get document chunking configuration."""
        return {
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap
        }
        
    def get_cors_config(self) -> dict:
        """Get CORS configuration."""
        origins = self.allowed_origins
        if self.debug:
            origins = ["*"]
            
        return {
            "allow_origins": origins,
            "allow_credentials": True,
            "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["*"]
        }

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance. This will now be the single entry point."""
    # Pydantic-settings automatically loads from .env and environment variables
    return Settings()


# Global settings instance
settings = get_settings()


def get_embedding_model_config() -> Dict[str, Any]:
    """Get embedding model configuration."""
    return {
        "model_name": settings.embedding_model,
        "device": settings.embedding_device,
        "batch_size": settings.embedding_batch_size,
        "max_seq_length": 512,
        "cache_dir": "./cache/transformers",
        "enable_mixed_precision": True,
        "target_performance": 16.3
    }


def validate_rtx_5070_compatibility() -> Dict[str, Any]:
    """Validate RTX 5070 compatibility and return recommendations."""
    import torch
    
    result = {
        "cuda_available": torch.cuda.is_available(),
        "rtx_5070_detected": False,
        "gpu_name": None,
        "recommendations": []
    }
    
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        result["gpu_name"] = gpu_name
        
        if "RTX 5070" in gpu_name:
            result["rtx_5070_detected"] = True
            result["recommendations"] = [
                "Using mixed precision (FP16) for optimal performance",
                "Batch size optimized for RTX 5070 memory",
                "CUDA acceleration enabled"
            ]
        else:
            result["recommendations"] = [
                "GPU detected but not RTX 5070",
                "Performance may vary based on GPU capabilities"
            ]
    else:
        result["recommendations"] = [
            "CUDA not available - using CPU",
            "Consider installing CUDA for better performance"
        ]
    
    return result


# Environment-specific configurations
def get_development_settings() -> Settings:
    """Get development-specific settings."""
    settings = get_settings()
    settings.debug = True
    settings.log_level = "DEBUG"
    settings.reload_on_change = True
    settings.mock_llm_responses = True
    return settings


def get_production_settings() -> Settings:
    """Get production-specific settings."""
    settings = get_settings()
    settings.debug = False
    settings.log_level = "INFO"
    settings.reload_on_change = False
    settings.mock_llm_responses = False
    return settings


def get_test_settings() -> Settings:
    """Get test-specific settings with test database."""
    settings = get_settings()
    # Override for testing - use a separate test database
    settings.qdrant_url = "http://localhost:6333"
    settings.vector_store_path = "./test_chroma_db"
    settings.documents_path = "./test_documents"
    settings.mock_llm_responses = True
    settings.debug = True
    settings.log_level = "DEBUG"
    return settings 