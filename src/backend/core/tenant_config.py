"""
Tenant Configuration Management

Centralized configuration management for tenants with validation,
caching, hierarchical configuration, and dynamic updates.

Author: Enterprise RAG Platform Team
"""

from typing import Dict, List, Optional, Any, Union, Callable, Type
from datetime import datetime, timezone, timedelta
import logging
import json
from dataclasses import dataclass, asdict
from enum import Enum
from sqlalchemy.orm import Session
import threading
from collections import defaultdict

from ..models.tenant import TenantConfiguration, Tenant
from ..core.tenant_scoped_db import TenantContext, get_tenant_scoped_session
from ..core.tenant_isolation import get_tenant_isolation_strategy

logger = logging.getLogger(__name__)


class ConfigValueType(Enum):
    """Supported configuration value types"""
    STRING = "string"
    INTEGER = "int"
    FLOAT = "float"
    BOOLEAN = "bool"
    JSON = "json"
    LIST = "list"


@dataclass
class ConfigSchema:
    """Schema definition for configuration values"""
    key: str
    category: str
    value_type: ConfigValueType
    default_value: Any
    description: str
    is_required: bool = False
    is_sensitive: bool = False
    is_editable: bool = True
    validation_rules: Optional[Dict[str, Any]] = None
    allowed_values: Optional[List[Any]] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None


class TenantConfigurationManager:
    """
    Manages tenant-specific configuration with validation and caching
    """
    
    def __init__(self, db_session: Session, cache_ttl: int = 300):
        self.db = db_session
        self.cache_ttl = cache_ttl
        self._config_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        self._cache_lock = threading.RLock()
        self._schemas: Dict[str, ConfigSchema] = {}
        self._load_default_schemas()
    
    def _load_default_schemas(self) -> None:
        """Load default configuration schemas"""
        default_schemas = [
            # Embedding configuration
            ConfigSchema(
                key="model_name",
                category="embedding",
                value_type=ConfigValueType.STRING,
                default_value="sentence-transformers/all-MiniLM-L6-v2",
                description="Embedding model name",
                allowed_values=[
                    "sentence-transformers/all-MiniLM-L6-v2",
                    "sentence-transformers/all-mpnet-base-v2",
                    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
                ]
            ),
            ConfigSchema(
                key="batch_size",
                category="embedding",
                value_type=ConfigValueType.INTEGER,
                default_value=32,
                description="Batch size for embedding generation",
                min_value=1,
                max_value=128
            ),
            ConfigSchema(
                key="max_length",
                category="embedding",
                value_type=ConfigValueType.INTEGER,
                default_value=512,
                description="Maximum token length for embeddings",
                min_value=64,
                max_value=2048
            ),
            
            # LLM configuration
            ConfigSchema(
                key="model_name",
                category="llm",
                value_type=ConfigValueType.STRING,
                default_value="microsoft/DialoGPT-medium",
                description="LLM model name",
                allowed_values=[
                    "microsoft/DialoGPT-medium",
                    "microsoft/DialoGPT-large",
                    "facebook/blenderbot-400M-distill"
                ]
            ),
            ConfigSchema(
                key="max_tokens",
                category="llm",
                value_type=ConfigValueType.INTEGER,
                default_value=512,
                description="Maximum tokens for LLM responses",
                min_value=64,
                max_value=2048
            ),
            ConfigSchema(
                key="temperature",
                category="llm",
                value_type=ConfigValueType.FLOAT,
                default_value=0.7,
                description="Temperature for LLM generation",
                min_value=0.0,
                max_value=2.0
            ),
            ConfigSchema(
                key="use_local_model",
                category="llm",
                value_type=ConfigValueType.BOOLEAN,
                default_value=True,
                description="Use local LLM model instead of API"
            ),
            
            # Search configuration
            ConfigSchema(
                key="similarity_threshold",
                category="search",
                value_type=ConfigValueType.FLOAT,
                default_value=0.7,
                description="Minimum similarity threshold for search results",
                min_value=0.0,
                max_value=1.0
            ),
            ConfigSchema(
                key="max_results",
                category="search",
                value_type=ConfigValueType.INTEGER,
                default_value=10,
                description="Maximum number of search results",
                min_value=1,
                max_value=100
            ),
            ConfigSchema(
                key="enable_reranking",
                category="search",
                value_type=ConfigValueType.BOOLEAN,
                default_value=True,
                description="Enable result reranking for better relevance"
            ),
            ConfigSchema(
                key="rerank_top_k",
                category="search",
                value_type=ConfigValueType.INTEGER,
                default_value=20,
                description="Number of results to rerank",
                min_value=5,
                max_value=50
            ),
            
            # Document processing
            ConfigSchema(
                key="chunk_size",
                category="document",
                value_type=ConfigValueType.INTEGER,
                default_value=512,
                description="Document chunk size in tokens",
                min_value=128,
                max_value=2048
            ),
            ConfigSchema(
                key="chunk_overlap",
                category="document",
                value_type=ConfigValueType.INTEGER,
                default_value=64,
                description="Overlap between document chunks",
                min_value=0,
                max_value=512
            ),
            ConfigSchema(
                key="supported_formats",
                category="document",
                value_type=ConfigValueType.LIST,
                default_value=["pdf", "docx", "txt", "md"],
                description="Supported document formats"
            ),
            ConfigSchema(
                key="max_file_size_mb",
                category="document",
                value_type=ConfigValueType.INTEGER,
                default_value=50,
                description="Maximum file size in MB",
                min_value=1,
                max_value=500
            ),
            
            # UI configuration
            ConfigSchema(
                key="theme",
                category="ui",
                value_type=ConfigValueType.STRING,
                default_value="default",
                description="UI theme name",
                allowed_values=["default", "dark", "light", "corporate"]
            ),
            ConfigSchema(
                key="branding_enabled",
                category="ui",
                value_type=ConfigValueType.BOOLEAN,
                default_value=False,
                description="Enable custom branding"
            ),
            ConfigSchema(
                key="logo_url",
                category="ui",
                value_type=ConfigValueType.STRING,
                default_value="",
                description="Custom logo URL"
            ),
            ConfigSchema(
                key="primary_color",
                category="ui",
                value_type=ConfigValueType.STRING,
                default_value="#1f2937",
                description="Primary brand color",
                validation_rules={"pattern": r"^#[0-9a-fA-F]{6}$"}
            ),
            
            # Performance tuning
            ConfigSchema(
                key="enable_gpu",
                category="performance",
                value_type=ConfigValueType.BOOLEAN,
                default_value=True,
                description="Enable GPU acceleration"
            ),
            ConfigSchema(
                key="cache_embeddings",
                category="performance",
                value_type=ConfigValueType.BOOLEAN,
                default_value=True,
                description="Cache generated embeddings"
            ),
            ConfigSchema(
                key="parallel_processing",
                category="performance",
                value_type=ConfigValueType.BOOLEAN,
                default_value=True,
                description="Enable parallel document processing"
            ),
            ConfigSchema(
                key="max_concurrent_requests",
                category="performance",
                value_type=ConfigValueType.INTEGER,
                default_value=10,
                description="Maximum concurrent requests",
                min_value=1,
                max_value=100
            ),
        ]
        
        for schema in default_schemas:
            schema_key = f"{schema.category}.{schema.key}"
            self._schemas[schema_key] = schema
    
    def get_configuration(
        self,
        tenant_id: str,
        category: Optional[str] = None,
        use_cache: bool = True,
        include_defaults: bool = True
    ) -> Dict[str, Any]:
        """
        Get configuration for a tenant
        
        Args:
            tenant_id: Tenant identifier
            category: Optional category filter
            use_cache: Whether to use cached values
            include_defaults: Whether to include default values for missing configs
            
        Returns:
            Configuration dictionary
        """
        # Check cache first
        if use_cache:
            cached_config = self._get_from_cache(tenant_id, category)
            if cached_config is not None:
                return cached_config
        
        # Build configuration from database
        config = self._build_configuration(tenant_id, category, include_defaults)
        
        # Cache the result
        if use_cache:
            self._set_cache(tenant_id, category or "all", config)
        
        return config
    
    def get_config_value(
        self,
        tenant_id: str,
        category: str,
        key: str,
        default: Any = None,
        use_cache: bool = True
    ) -> Any:
        """
        Get a specific configuration value
        
        Args:
            tenant_id: Tenant identifier
            category: Configuration category
            key: Configuration key
            default: Default value if not found
            use_cache: Whether to use cached values
            
        Returns:
            Configuration value
        """
        config = self.get_configuration(tenant_id, category, use_cache)
        return config.get(category, {}).get(key, default)
    
    def set_configuration(
        self,
        tenant_id: str,
        category: str,
        key: str,
        value: Any,
        validate: bool = True
    ) -> TenantConfiguration:
        """
        Set a configuration value for a tenant
        
        Args:
            tenant_id: Tenant identifier
            category: Configuration category
            key: Configuration key
            value: Configuration value
            validate: Whether to validate the value
            
        Returns:
            Configuration record
        """
        schema_key = f"{category}.{key}"
        schema = self._schemas.get(schema_key)
        
        if validate and schema:
            self._validate_value(value, schema)
        
        # Convert value to string for storage
        value_type = schema.value_type.value if schema else "string"
        str_value = self._serialize_value(value, value_type)
        
        # Find existing configuration or create new
        config = self.db.query(TenantConfiguration).filter(
            TenantConfiguration.tenant_id == tenant_id,
            TenantConfiguration.category == category,
            TenantConfiguration.key == key
        ).first()
        
        if config:
            config.value = str_value
            config.value_type = value_type
            config.updated_at = datetime.now(timezone.utc)
        else:
            config = TenantConfiguration(
                tenant_id=tenant_id,
                category=category,
                key=key,
                value=str_value,
                value_type=value_type,
                description=schema.description if schema else "",
                is_sensitive=schema.is_sensitive if schema else False,
                is_editable=schema.is_editable if schema else True
            )
            self.db.add(config)
        
        self.db.commit()
        
        # Invalidate cache
        self._invalidate_cache(tenant_id)
        
        logger.info(f"Updated configuration {category}.{key} for tenant {tenant_id}")
        return config
    
    def bulk_update_configuration(
        self,
        tenant_id: str,
        updates: Dict[str, Dict[str, Any]],
        validate: bool = True
    ) -> List[TenantConfiguration]:
        """
        Bulk update multiple configuration values
        
        Args:
            tenant_id: Tenant identifier
            updates: Nested dict of category -> key -> value
            validate: Whether to validate values
            
        Returns:
            List of updated configuration records
        """
        updated_configs = []
        
        try:
            for category, config_items in updates.items():
                for key, value in config_items.items():
                    config = self.set_configuration(
                        tenant_id, category, key, value, validate
                    )
                    updated_configs.append(config)
            
            self.db.commit()
            logger.info(f"Bulk updated {len(updated_configs)} configurations for tenant {tenant_id}")
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to bulk update configurations for tenant {tenant_id}: {str(e)}")
            raise
        
        return updated_configs
    
    def delete_configuration(
        self,
        tenant_id: str,
        category: str,
        key: str
    ) -> bool:
        """
        Delete a configuration value
        
        Args:
            tenant_id: Tenant identifier
            category: Configuration category
            key: Configuration key
            
        Returns:
            True if deleted, False if not found
        """
        config = self.db.query(TenantConfiguration).filter(
            TenantConfiguration.tenant_id == tenant_id,
            TenantConfiguration.category == category,
            TenantConfiguration.key == key
        ).first()
        
        if config:
            self.db.delete(config)
            self.db.commit()
            self._invalidate_cache(tenant_id)
            logger.info(f"Deleted configuration {category}.{key} for tenant {tenant_id}")
            return True
        
        return False
    
    def validate_configuration(
        self,
        tenant_id: str,
        category: Optional[str] = None
    ) -> Dict[str, List[str]]:
        """
        Validate tenant configuration against schemas
        
        Args:
            tenant_id: Tenant identifier
            category: Optional category filter
            
        Returns:
            Dictionary of validation errors by category
        """
        errors = defaultdict(list)
        config = self.get_configuration(tenant_id, category, use_cache=False, include_defaults=False)
        
        # Validate each schema
        for schema_key, schema in self._schemas.items():
            if category and not schema_key.startswith(f"{category}."):
                continue
            
            cat = schema.category
            key = schema.key
            
            # Check if required value is missing
            if schema.is_required and (cat not in config or key not in config[cat]):
                errors[cat].append(f"Required configuration '{key}' is missing")
                continue
            
            # Validate existing value
            if cat in config and key in config[cat]:
                try:
                    self._validate_value(config[cat][key], schema)
                except ValueError as e:
                    errors[cat].append(f"Invalid value for '{key}': {str(e)}")
        
        return dict(errors)
    
    def get_schema(self, category: str, key: str) -> Optional[ConfigSchema]:
        """
        Get configuration schema
        
        Args:
            category: Configuration category
            key: Configuration key
            
        Returns:
            Configuration schema or None
        """
        schema_key = f"{category}.{key}"
        return self._schemas.get(schema_key)
    
    def list_schemas(self, category: Optional[str] = None) -> List[ConfigSchema]:
        """
        List available configuration schemas
        
        Args:
            category: Optional category filter
            
        Returns:
            List of configuration schemas
        """
        schemas = []
        for schema_key, schema in self._schemas.items():
            if category is None or schema.category == category:
                schemas.append(schema)
        return schemas
    
    def export_configuration(
        self,
        tenant_id: str,
        include_sensitive: bool = False,
        format: str = "json"
    ) -> str:
        """
        Export tenant configuration
        
        Args:
            tenant_id: Tenant identifier
            include_sensitive: Whether to include sensitive values
            format: Export format (json, yaml)
            
        Returns:
            Exported configuration string
        """
        config = self.get_configuration(tenant_id, use_cache=False)
        
        # Filter sensitive values if needed
        if not include_sensitive:
            config = self._filter_sensitive_values(config)
        
        if format.lower() == "json":
            return json.dumps(config, indent=2, default=str)
        elif format.lower() == "yaml":
            import yaml
            return yaml.dump(config, default_flow_style=False)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def import_configuration(
        self,
        tenant_id: str,
        config_data: str,
        format: str = "json",
        validate: bool = True,
        merge: bool = True
    ) -> List[TenantConfiguration]:
        """
        Import tenant configuration
        
        Args:
            tenant_id: Tenant identifier
            config_data: Configuration data string
            format: Import format (json, yaml)
            validate: Whether to validate values
            merge: Whether to merge with existing config
            
        Returns:
            List of imported configuration records
        """
        # Parse configuration data
        if format.lower() == "json":
            config = json.loads(config_data)
        elif format.lower() == "yaml":
            import yaml
            config = yaml.safe_load(config_data)
        else:
            raise ValueError(f"Unsupported import format: {format}")
        
        # Clear existing configuration if not merging
        if not merge:
            self.db.query(TenantConfiguration).filter(
                TenantConfiguration.tenant_id == tenant_id
            ).delete()
        
        # Import configuration
        return self.bulk_update_configuration(tenant_id, config, validate)
    
    def _build_configuration(
        self,
        tenant_id: str,
        category: Optional[str],
        include_defaults: bool
    ) -> Dict[str, Any]:
        """Build configuration dictionary from database and defaults"""
        config = defaultdict(dict)
        
        # Get configurations from database
        query = self.db.query(TenantConfiguration).filter(
            TenantConfiguration.tenant_id == tenant_id
        )
        
        if category:
            query = query.filter(TenantConfiguration.category == category)
        
        db_configs = query.all()
        
        # Add database configurations
        for db_config in db_configs:
            value = self._deserialize_value(db_config.value, db_config.value_type)
            config[db_config.category][db_config.key] = value
        
        # Add default values for missing configurations
        if include_defaults:
            for schema_key, schema in self._schemas.items():
                if category and schema.category != category:
                    continue
                
                if schema.key not in config[schema.category]:
                    config[schema.category][schema.key] = schema.default_value
        
        return dict(config)
    
    def _validate_value(self, value: Any, schema: ConfigSchema) -> None:
        """Validate a value against its schema"""
        # Type validation
        if schema.value_type == ConfigValueType.INTEGER and not isinstance(value, int):
            raise ValueError(f"Expected integer, got {type(value).__name__}")
        elif schema.value_type == ConfigValueType.FLOAT and not isinstance(value, (int, float)):
            raise ValueError(f"Expected float, got {type(value).__name__}")
        elif schema.value_type == ConfigValueType.BOOLEAN and not isinstance(value, bool):
            raise ValueError(f"Expected boolean, got {type(value).__name__}")
        elif schema.value_type == ConfigValueType.STRING and not isinstance(value, str):
            raise ValueError(f"Expected string, got {type(value).__name__}")
        elif schema.value_type == ConfigValueType.LIST and not isinstance(value, list):
            raise ValueError(f"Expected list, got {type(value).__name__}")
        
        # Range validation
        if schema.min_value is not None and value < schema.min_value:
            raise ValueError(f"Value {value} is below minimum {schema.min_value}")
        
        if schema.max_value is not None and value > schema.max_value:
            raise ValueError(f"Value {value} is above maximum {schema.max_value}")
        
        # Allowed values validation
        if schema.allowed_values and value not in schema.allowed_values:
            raise ValueError(f"Value {value} not in allowed values: {schema.allowed_values}")
        
        # Custom validation rules
        if schema.validation_rules:
            for rule_name, rule_value in schema.validation_rules.items():
                if rule_name == "pattern" and isinstance(value, str):
                    import re
                    if not re.match(rule_value, value):
                        raise ValueError(f"Value '{value}' does not match pattern '{rule_value}'")
    
    def _serialize_value(self, value: Any, value_type: str) -> str:
        """Serialize value for database storage"""
        if value_type in ["json", "list"]:
            return json.dumps(value)
        elif value_type == "bool":
            return str(value).lower()
        else:
            return str(value)
    
    def _deserialize_value(self, str_value: str, value_type: str) -> Any:
        """Deserialize value from database"""
        if value_type == "int":
            return int(str_value)
        elif value_type == "float":
            return float(str_value)
        elif value_type == "bool":
            return str_value.lower() in ("true", "1", "yes", "on")
        elif value_type in ["json", "list"]:
            return json.loads(str_value)
        else:
            return str_value
    
    def _get_from_cache(self, tenant_id: str, category: Optional[str]) -> Optional[Dict[str, Any]]:
        """Get configuration from cache"""
        cache_key = f"{tenant_id}:{category or 'all'}"
        
        with self._cache_lock:
            if cache_key in self._config_cache:
                timestamp = self._cache_timestamps.get(cache_key)
                if timestamp and (datetime.now(timezone.utc) - timestamp).seconds < self.cache_ttl:
                    return self._config_cache[cache_key]
                else:
                    # Cache expired
                    del self._config_cache[cache_key]
                    del self._cache_timestamps[cache_key]
        
        return None
    
    def _set_cache(self, tenant_id: str, category: str, config: Dict[str, Any]) -> None:
        """Set configuration in cache"""
        cache_key = f"{tenant_id}:{category}"
        
        with self._cache_lock:
            self._config_cache[cache_key] = config
            self._cache_timestamps[cache_key] = datetime.now(timezone.utc)
    
    def _invalidate_cache(self, tenant_id: str) -> None:
        """Invalidate cache for a tenant"""
        with self._cache_lock:
            keys_to_remove = [key for key in self._config_cache.keys() if key.startswith(f"{tenant_id}:")]
            for key in keys_to_remove:
                del self._config_cache[key]
                if key in self._cache_timestamps:
                    del self._cache_timestamps[key]
    
    def _filter_sensitive_values(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Filter out sensitive configuration values"""
        filtered_config = {}
        
        for category, category_config in config.items():
            filtered_category = {}
            for key, value in category_config.items():
                schema = self.get_schema(category, key)
                if not schema or not schema.is_sensitive:
                    filtered_category[key] = value
            
            if filtered_category:
                filtered_config[category] = filtered_category
        
        return filtered_config


def get_tenant_config_manager(db_session: Session) -> TenantConfigurationManager:
    """Get tenant configuration manager instance"""
    return TenantConfigurationManager(db_session)


# Convenience functions
def get_tenant_config(
    tenant_id: str,
    category: str,
    key: str,
    default: Any = None,
    db_session: Optional[Session] = None
) -> Any:
    """
    Get a single configuration value for a tenant
    
    Args:
        tenant_id: Tenant identifier
        category: Configuration category
        key: Configuration key
        default: Default value if not found
        db_session: Optional database session
        
    Returns:
        Configuration value
    """
    if not db_session:
        # Use tenant context if available
        current_tenant = TenantContext.get_current_tenant()
        if not current_tenant or current_tenant != tenant_id:
            raise ValueError("No valid tenant context for configuration access")
    
    # This would need to be integrated with the actual database session factory
    # For now, this is a placeholder
    return default


def set_tenant_config(
    tenant_id: str,
    category: str,
    key: str,
    value: Any,
    db_session: Optional[Session] = None
) -> bool:
    """
    Set a single configuration value for a tenant
    
    Args:
        tenant_id: Tenant identifier
        category: Configuration category
        key: Configuration key
        value: Configuration value
        db_session: Optional database session
        
    Returns:
        True if successful
    """
    if not db_session:
        # Use tenant context if available
        current_tenant = TenantContext.get_current_tenant()
        if not current_tenant or current_tenant != tenant_id:
            raise ValueError("No valid tenant context for configuration access")
    
    # This would need to be integrated with the actual database session factory
    # For now, this is a placeholder
    return True 