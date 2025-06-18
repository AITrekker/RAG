"""
Configuration management for HR RAG Pipeline.

This module handles loading configuration from YAML files and environment variables,
with support for environment-specific overrides and validation.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, field_validator
from pydantic_settings import BaseSettings
import logging

logger = logging.getLogger(__name__)

class DatabaseSettings(BaseModel):
    """Database configuration settings."""
    type: str = "sqlite"
    
    # SQLite settings
    sqlite_path: str = "./data/db/hr_rag.db"
    sqlite_echo: bool = False
    sqlite_check_same_thread: bool = False
    
    # PostgreSQL settings
    postgresql_host: str = "database"
    postgresql_port: int = 5432
    postgresql_database: str = "hr_rag"
    postgresql_username: str = "hr_rag_user"
    postgresql_password: str = ""
    postgresql_pool_size: int = 5
    postgresql_max_overflow: int = 10
    postgresql_echo: bool = False
    
    @property
    def database_url(self) -> str:
        """Generate database URL based on type."""
        if self.type == "sqlite":
            return f"sqlite:///{self.sqlite_path}"
        elif self.type == "postgresql":
            return (
                f"postgresql://{self.postgresql_username}:{self.postgresql_password}"
                f"@{self.postgresql_host}:{self.postgresql_port}/{self.postgresql_database}"
            )
        else:
            raise ValueError(f"Unsupported database type: {self.type}")

class VectorStoreSettings(BaseModel):
    """Vector store configuration settings."""
    type: str = "chroma"
    
    # ChromaDB settings
    chroma_host: str = "vector-store"
    chroma_port: int = 8000
    chroma_collection_name: str = "hr_documents"
    chroma_persist_directory: str = "./data/vector_store"
    
    # FAISS settings
    faiss_index_type: str = "IndexFlatIP"
    faiss_dimension: int = 1024
    faiss_index_path: str = "./data/indexes/faiss.index"

class ModelSettings(BaseModel):
    """ML model configuration settings."""
    # Embedding model
    embedding_name: str = "BAAI/bge-large-en-v1.5"
    embedding_device: str = "auto"
    embedding_batch_size: int = 32
    embedding_max_length: int = 512
    embedding_normalize: bool = True
    embedding_cache_dir: str = "./models/embeddings"
    
    # Generative model
    generative_name: str = "microsoft/DialoGPT-medium"
    generative_device: str = "auto"
    generative_max_length: int = 1024
    generative_temperature: float = 0.7
    generative_top_p: float = 0.9
    generative_do_sample: bool = True
    generative_cache_dir: str = "./models/generative"
    
    # Reranker model
    reranker_name: str = "BAAI/bge-reranker-large"
    reranker_device: str = "auto"
    reranker_top_k: int = 10
    reranker_cache_dir: str = "./models/reranker"

class FileProcessingSettings(BaseModel):
    """File processing configuration settings."""
    master_folder: str = "./data/master"
    sync_folder: str = "./data/sync"
    supported_formats: List[str] = [
        "pdf", "docx", "doc", "pptx", "ppt", "txt", "md", "xlsx", "xls", "csv"
    ]
    
    # Chunking settings
    chunking_strategy: str = "recursive"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    chunking_separators: List[str] = ["\n\n", "\n", " ", ""]
    
    # Metadata extraction
    extract_title: bool = True
    extract_author: bool = True
    extract_creation_date: bool = True
    extract_modification_date: bool = True
    extract_file_size: bool = True
    extract_keywords: bool = True

class SyncSettings(BaseModel):
    """Sync configuration settings."""
    interval_hours: int = 1
    batch_size: int = 100
    max_file_versions: int = 3
    report_retention_days: int = 30
    enable_delta_sync: bool = True
    conflict_resolution: str = "latest_wins"

class RAGSettings(BaseModel):
    """RAG pipeline configuration settings."""
    # Retrieval settings
    retrieval_top_k: int = 20
    retrieval_similarity_threshold: float = 0.7
    retrieval_include_metadata: bool = True
    retrieval_search_strategy: str = "hybrid"
    
    # Reranking settings
    reranking_enabled: bool = True
    reranking_top_k: int = 5
    reranking_strategy: str = "cross_encoder"
    
    # Generation settings
    generation_max_tokens: int = 512
    generation_temperature: float = 0.3
    generation_top_p: float = 0.9
    generation_presence_penalty: float = 0.1
    generation_frequency_penalty: float = 0.1
    
    # Context settings
    context_max_length: int = 4000
    context_include_source_metadata: bool = True
    context_citation_style: str = "academic"

class SecuritySettings(BaseModel):
    """Security configuration settings."""
    enable_auth: bool = False
    
    # JWT settings
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    
    # Encryption settings
    encryption_enabled: bool = False
    encryption_key: str = ""
    encryption_algorithm: str = "AES-256-GCM"
    
    # Input validation
    max_query_length: int = 500
    max_file_size_mb: int = 100
    allowed_file_types: List[str] = ["pdf", "docx", "txt", "pptx"]
    sanitize_inputs: bool = True

class ResourceSettings(BaseModel):
    """Resource management settings."""
    # GPU settings
    gpu_enabled: bool = True
    gpu_memory_limit_gb: float = 10.0
    gpu_memory_fraction: float = 0.8
    
    # CPU settings
    cpu_max_workers: int = 4
    cpu_max_threads_per_worker: int = 2
    
    # Memory settings
    memory_max_usage_gb: float = 8.0
    memory_cache_size_mb: int = 512
    
    # Rate limiting
    rate_limiting_enabled: bool = True
    rate_requests_per_minute: int = 60
    rate_burst_size: int = 10

class LoggingSettings(BaseModel):
    """Logging configuration settings."""
    level: str = "INFO"
    format: str = "structured"
    output: str = "both"
    
    # File logging
    file_path: str = "./logs/hr_rag.log"
    file_max_size_mb: int = 100
    file_backup_count: int = 5
    file_rotation: str = "time"
    file_rotation_interval: str = "daily"
    
    # Structured logging
    structured_include_timestamp: bool = True
    structured_include_level: bool = True
    structured_include_module: bool = True
    structured_include_function: bool = True
    structured_include_line_number: bool = True
    structured_include_request_id: bool = True
    
    # Console logging
    console_include_color: bool = True
    console_include_time: bool = True

class MonitoringSettings(BaseModel):
    """Monitoring configuration settings."""
    enable_metrics: bool = True
    metrics_port: int = 9090
    metrics_path: str = "/metrics"
    
    # Health checks
    health_check_enabled: bool = True
    health_check_interval_seconds: int = 30
    health_check_timeout_seconds: int = 5
    
    # Performance monitoring
    track_processing_time: bool = True
    track_memory_usage: bool = True
    track_gpu_usage: bool = True
    
    # Alerting
    alert_on_errors: bool = True
    alert_error_threshold: int = 10
    alert_response_time_threshold_ms: int = 5000

class TenantSettings(BaseModel):
    """Multi-tenant configuration settings."""
    default_tenant_id: str = "default"
    enable_tenant_isolation: bool = True
    tenant_data_separation: str = "logical"  # logical, physical
    tenant_resource_limits: bool = True
    
    # Default limits per tenant
    default_max_files: int = 10000
    default_max_storage_gb: int = 50
    default_max_queries_per_hour: int = 1000
    default_max_concurrent_operations: int = 10

class AppSettings(BaseModel):
    """Main application settings."""
    name: str = "HR RAG Pipeline"
    version: str = "1.0.0"
    environment: str = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    
    # API settings
    api_prefix: str = "/api/v1"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"

class Settings(BaseSettings):
    """Main settings class that combines all configuration sections."""
    
    app: AppSettings = AppSettings()
    database: DatabaseSettings = DatabaseSettings()
    vector_store: VectorStoreSettings = VectorStoreSettings()
    models: ModelSettings = ModelSettings()
    file_processing: FileProcessingSettings = FileProcessingSettings()
    sync: SyncSettings = SyncSettings()
    rag: RAGSettings = RAGSettings()
    security: SecuritySettings = SecuritySettings()
    resources: ResourceSettings = ResourceSettings()
    logging: LoggingSettings = LoggingSettings()
    monitoring: MonitoringSettings = MonitoringSettings()
    tenant: TenantSettings = TenantSettings()
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore"
    }

def load_yaml_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to YAML config file. If None, uses default path.
        
    Returns:
        Dictionary containing configuration data.
    """
    if config_path is None:
        config_file_path = Path(__file__).parent / "config.yaml"
    else:
        config_file_path = Path(config_path)
    
    if not config_file_path.exists():
        logger.warning(f"Config file not found: {config_file_path}")
        return {}
    
    try:
        with open(config_file_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        logger.info(f"Loaded configuration from {config_file_path}")
        return config or {}
    except Exception as e:
        logger.error(f"Failed to load config from {config_file_path}: {e}")
        return {}

def expand_environment_variables(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively expand environment variables in configuration values.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Configuration with environment variables expanded
    """
    def _expand_value(value: Any) -> Any:
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            return os.getenv(env_var, value)
        elif isinstance(value, dict):
            return {k: _expand_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [_expand_value(item) for item in value]
        return value
    
    result = _expand_value(config)
    # Ensure we return a dict as promised by the return type
    if isinstance(result, dict):
        return result
    else:
        logger.warning(f"expand_environment_variables expected dict input, got {type(config)}")
        return {}

def create_directories(settings: Settings) -> None:
    """
    Create necessary directories based on configuration.
    
    Args:
        settings: Application settings
    """
    directories = [
        settings.file_processing.master_folder,
        settings.file_processing.sync_folder,
        settings.vector_store.chroma_persist_directory,
        settings.models.embedding_cache_dir,
        settings.models.generative_cache_dir,
        settings.models.reranker_cache_dir,
        Path(settings.logging.file_path).parent,
        Path(settings.database.sqlite_path).parent if settings.database.type == "sqlite" else None,
    ]
    
    for directory in directories:
        if directory:
            Path(directory).mkdir(parents=True, exist_ok=True)

def load_settings(config_path: Optional[str] = None, 
                 environment: Optional[str] = None) -> Settings:
    """
    Load and create application settings.
    
    Args:
        config_path: Path to YAML configuration file
        environment: Environment name (development, staging, production)
        
    Returns:
        Settings instance with loaded configuration
    """
    # Load YAML configuration
    yaml_config = load_yaml_config(config_path)
    
    # Expand environment variables
    yaml_config = expand_environment_variables(yaml_config)
    
    # Override environment if specified
    if environment:
        yaml_config.setdefault("app", {})["environment"] = environment
    
    # Create settings from YAML and environment variables
    settings = Settings()
    
    # Apply YAML configuration
    if yaml_config:
        # Update settings with YAML values
        for section_name, section_config in yaml_config.items():
            if hasattr(settings, section_name) and isinstance(section_config, dict):
                section_obj = getattr(settings, section_name)
                for key, value in section_config.items():
                    if hasattr(section_obj, key):
                        setattr(section_obj, key, value)
    
    # Create necessary directories
    create_directories(settings)
    
    logger.info(f"Settings loaded for environment: {settings.app.environment}")
    return settings

# Global settings instance
settings: Optional[Settings] = None

def get_settings() -> Settings:
    """
    Get global settings instance.
    
    Returns:
        Settings instance
    """
    global settings
    if settings is None:
        settings = load_settings()
    return settings

def reload_settings(config_path: Optional[str] = None, 
                   environment: Optional[str] = None) -> Settings:
    """
    Reload global settings.
    
    Args:
        config_path: Path to YAML configuration file
        environment: Environment name
        
    Returns:
        Reloaded settings instance
    """
    global settings
    settings = load_settings(config_path, environment)
    return settings

# Export commonly used settings
__all__ = [
    "Settings",
    "AppSettings", 
    "DatabaseSettings",
    "VectorStoreSettings",
    "ModelSettings",
    "FileProcessingSettings",
    "SyncSettings",
    "RAGSettings",
    "SecuritySettings",
    "ResourceSettings",
    "LoggingSettings",
    "load_settings",
    "get_settings",
    "reload_settings",
] 