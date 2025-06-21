"""
Application settings and configuration for the Enterprise RAG Platform.

Handles environment variables, database configuration, and application settings.
"""

import os
from typing import List, Optional
from pydantic import BaseSettings, Field
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
    
    # Database settings
    database_url: str = Field(
        default="sqlite:///./rag_platform.db", 
        env="DATABASE_URL"
    )
    database_pool_size: int = Field(default=10, env="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=20, env="DATABASE_MAX_OVERFLOW")
    
    # Redis settings (for caching and rate limiting)
    redis_url: Optional[str] = Field(default=None, env="REDIS_URL")
    redis_password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    
    # Vector store settings
    vector_store_type: str = Field(default="chroma", env="VECTOR_STORE_TYPE")
    vector_store_path: str = Field(default="./vector_store", env="VECTOR_STORE_PATH")
    vector_store_host: Optional[str] = Field(default=None, env="VECTOR_STORE_HOST")
    vector_store_port: Optional[int] = Field(default=None, env="VECTOR_STORE_PORT")
    
    # Embedding model settings
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2", 
        env="EMBEDDING_MODEL"
    )
    embedding_device: str = Field(default="cpu", env="EMBEDDING_DEVICE")
    embedding_batch_size: int = Field(default=32, env="EMBEDDING_BATCH_SIZE")
    
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
    
    def get_database_url(self) -> str:
        """Get the complete database URL."""
        return self.database_url
    
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
    """Get test-specific settings."""
    settings = get_settings()
    settings.database_url = "sqlite:///:memory:"
    settings.vector_store_path = "./test_vector_store"
    settings.documents_path = "./test_documents"
    settings.mock_llm_responses = True
    return settings 