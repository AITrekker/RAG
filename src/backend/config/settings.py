"""
Application settings and configuration for the Enterprise RAG Platform.

Handles environment variables, database configuration, and application settings.
"""

import os
from typing import List, Optional, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application settings
    app_name: str = Field(default="Enterprise RAG Platform", env="APP_NAME")
    debug: bool = Field(default=False, env="DEBUG")
    version: str = Field(default="1.0.0", env="VERSION")
    
    # Server settings
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    
    # Security settings
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"], 
        env="ALLOWED_ORIGINS"
    )
    allowed_hosts: List[str] = Field(
        default=["localhost", "127.0.0.1"], 
        env="ALLOWED_HOSTS"
    )
    
    # Qdrant settings
    qdrant_url: str = Field(default="http://localhost:6333", env="QDRANT_URL")
    qdrant_api_key: Optional[str] = Field(default=None, env="QDRANT_API_KEY")
    
    # Redis settings (for caching and rate limiting)
    redis_url: Optional[str] = Field(default=None, env="REDIS_URL")
    redis_password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    
    # Vector store settings
    vector_store_type: str = Field(default="chroma", env="VECTOR_STORE_TYPE")
    vector_store_path: str = Field(default="./data/chroma_db", env="VECTOR_STORE_PATH")
    vector_store_host: Optional[str] = Field(default=None, env="VECTOR_STORE_HOST")
    vector_store_port: Optional[int] = Field(default=None, env="VECTOR_STORE_PORT")
    
    # Embedding model settings
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2", 
        env="EMBEDDING_MODEL"
    )
    embedding_device: str = Field(default="cpu", env="EMBEDDING_DEVICE")
    embedding_batch_size: int = Field(default=32, env="EMBEDDING_BATCH_SIZE")
    
    # LLM settings
    llm_model: str = Field(
        default="google/flan-t5-base", 
        env="LLM_MODEL"
    )
    llm_max_length: int = Field(default=1024, env="LLM_MAX_LENGTH")
    llm_temperature: float = Field(default=0.6, env="LLM_TEMPERATURE")
    llm_cache_dir: str = Field(default="./cache/transformers", env="LLM_CACHE_DIR")
    llm_enable_quantization: bool = Field(default=True, env="LLM_ENABLE_QUANTIZATION")
    
    # Document processing settings
    max_file_size_mb: int = Field(default=50, env="MAX_FILE_SIZE_MB")
    supported_file_types: List[str] = Field(
        default=[".pdf", ".docx", ".txt", ".md", ".html", ".htm"],
        env="SUPPORTED_FILE_TYPES"
    )
    chunk_size: int = Field(default=512, env="CHUNK_SIZE")
    chunk_overlap: int = Field(default=50, env="CHUNK_OVERLAP")
    
    # Storage settings
    documents_path: str = Field(default="./documents", env="DOCUMENTS_PATH")
    temp_path: str = Field(default="./temp", env="TEMP_PATH")
    
    # API settings
    api_rate_limit_per_minute: int = Field(default=60, env="API_RATE_LIMIT_PER_MINUTE")
    api_rate_limit_per_hour: int = Field(default=1000, env="API_RATE_LIMIT_PER_HOUR")
    api_timeout_seconds: int = Field(default=30, env="API_TIMEOUT_SECONDS")
    
    # Logging settings
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT"
    )
    log_file: Optional[str] = Field(default=None, env="LOG_FILE")
    
    # Monitoring settings
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    metrics_port: int = Field(default=9090, env="METRICS_PORT")
    
    # Feature flags
    enable_file_monitoring: bool = Field(default=True, env="ENABLE_FILE_MONITORING")
    enable_auto_sync: bool = Field(default=True, env="ENABLE_AUTO_SYNC")
    enable_query_history: bool = Field(default=True, env="ENABLE_QUERY_HISTORY")
    
    # Development settings
    reload_on_change: bool = Field(default=False, env="RELOAD_ON_CHANGE")
    mock_llm_responses: bool = Field(default=False, env="MOCK_LLM_RESPONSES")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    def get_vector_store_config(self) -> dict:
        """Get vector store configuration."""
        config = {
            "type": self.vector_store_type,
            "path": self.vector_store_path
        }
        
        if self.vector_store_host:
            config["host"] = self.vector_store_host
        
        if self.vector_store_port:
            config["port"] = self.vector_store_port
            
        return config
    
    def get_embedding_config(self) -> dict:
        """Get embedding model configuration."""
        return {
            "model_name": self.embedding_model,
            "device": self.embedding_device,
            "batch_size": self.embedding_batch_size
        }
    
    def get_llm_config(self) -> dict:
        """Get LLM service configuration."""
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
    
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.debug
    
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return not self.debug
    
    def get_cors_config(self) -> dict:
        """Get CORS configuration."""
        return {
            "allow_origins": self.allowed_origins,
            "allow_credentials": True,
            "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["*"]
        }


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
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