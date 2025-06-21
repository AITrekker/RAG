"""
Tenant Isolation Strategy for Enterprise RAG Platform

This module defines the comprehensive tenant isolation strategy across all system components
to ensure complete data separation and security between tenants.

Author: Enterprise RAG Platform Team
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import uuid


class IsolationLevel(Enum):
    """Levels of tenant isolation"""
    LOGICAL = "logical"  # Same database, separate tables/collections
    PHYSICAL = "physical"  # Separate databases/file systems
    HYBRID = "hybrid"  # Combination based on data sensitivity


class TenantTier(Enum):
    """Tenant service tiers affecting isolation strategy"""
    BASIC = "basic"      # Shared resources, logical isolation
    PREMIUM = "premium"  # Enhanced isolation, dedicated resources
    ENTERPRISE = "enterprise"  # Full physical isolation


@dataclass
class TenantIsolationConfig:
    """Configuration for tenant isolation settings"""
    tenant_id: str
    tier: TenantTier
    isolation_level: IsolationLevel
    database_isolation: bool = True
    filesystem_isolation: bool = True
    vector_store_isolation: bool = True
    cache_isolation: bool = True
    logging_isolation: bool = True


class TenantIsolationStrategy:
    """
    Core tenant isolation strategy implementation
    
    This class implements a multi-layered approach to tenant isolation:
    1. Database Layer: Tenant-scoped queries and separate schemas
    2. File System Layer: Tenant-specific directories and access controls
    3. Vector Store Layer: Separate collections with tenant prefixes
    4. Cache Layer: Tenant-scoped cache keys
    5. Logging Layer: Tenant context in all log entries
    """
    
    def __init__(self):
        self.isolation_configs: Dict[str, TenantIsolationConfig] = {}
        
    def register_tenant(self, tenant_id: str, tier: TenantTier = TenantTier.BASIC) -> TenantIsolationConfig:
        """Register a new tenant with appropriate isolation strategy"""
        
        # Determine isolation level based on tier
        isolation_level = {
            TenantTier.BASIC: IsolationLevel.LOGICAL,
            TenantTier.PREMIUM: IsolationLevel.HYBRID,
            TenantTier.ENTERPRISE: IsolationLevel.PHYSICAL
        }[tier]
        
        config = TenantIsolationConfig(
            tenant_id=tenant_id,
            tier=tier,
            isolation_level=isolation_level,
            database_isolation=tier != TenantTier.BASIC,
            filesystem_isolation=True,  # Always isolate file system
            vector_store_isolation=True,  # Always isolate vector store
            cache_isolation=tier != TenantTier.BASIC,
            logging_isolation=True  # Always isolate logging
        )
        
        self.isolation_configs[tenant_id] = config
        return config
    
    def get_database_strategy(self, tenant_id: str) -> Dict[str, Any]:
        """Get database isolation strategy for tenant"""
        config = self.isolation_configs.get(tenant_id)
        if not config:
            raise ValueError(f"Tenant {tenant_id} not registered")
            
        if config.isolation_level == IsolationLevel.PHYSICAL:
            return {
                "type": "separate_database",
                "database_name": f"rag_tenant_{tenant_id}",
                "schema": "public",
                "connection_pool": f"pool_{tenant_id}"
            }
        elif config.isolation_level == IsolationLevel.HYBRID:
            return {
                "type": "separate_schema",
                "database_name": "rag_platform",
                "schema": f"tenant_{tenant_id}",
                "connection_pool": "shared"
            }
        else:  # LOGICAL
            return {
                "type": "tenant_column",
                "database_name": "rag_platform",
                "schema": "public",
                "tenant_column": "tenant_id",
                "connection_pool": "shared"
            }
    
    def get_filesystem_strategy(self, tenant_id: str) -> Dict[str, Any]:
        """Get file system isolation strategy for tenant"""
        config = self.isolation_configs.get(tenant_id)
        if not config:
            raise ValueError(f"Tenant {tenant_id} not registered")
            
        base_path = Path("/data/tenants") if config.isolation_level == IsolationLevel.PHYSICAL else Path("/data/shared")
        
        return {
            "type": "directory_isolation",
            "base_path": str(base_path),
            "tenant_path": str(base_path / tenant_id),
            "documents_path": str(base_path / tenant_id / "documents"),
            "uploads_path": str(base_path / tenant_id / "uploads"),
            "cache_path": str(base_path / tenant_id / "cache"),
            "logs_path": str(base_path / tenant_id / "logs"),
            "permissions": {
                "owner": f"tenant_{tenant_id}",
                "group": "rag_tenants",
                "mode": "0750"
            }
        }
    
    def get_vector_store_strategy(self, tenant_id: str) -> Dict[str, Any]:
        """Get vector store isolation strategy for tenant"""
        config = self.isolation_configs.get(tenant_id)
        if not config:
            raise ValueError(f"Tenant {tenant_id} not registered")
            
        if config.isolation_level == IsolationLevel.PHYSICAL:
            return {
                "type": "separate_instance",
                "instance_name": f"chroma_tenant_{tenant_id}",
                "collection_prefix": "",  # No prefix needed for separate instance
                "persist_directory": f"/data/vector_stores/tenant_{tenant_id}"
            }
        else:
            return {
                "type": "collection_isolation",
                "instance_name": "chroma_shared",
                "collection_prefix": f"tenant_{tenant_id}_",
                "persist_directory": "/data/vector_stores/shared"
            }
    
    def get_cache_strategy(self, tenant_id: str) -> Dict[str, Any]:
        """Get cache isolation strategy for tenant"""
        config = self.isolation_configs.get(tenant_id)
        if not config:
            raise ValueError(f"Tenant {tenant_id} not registered")
            
        if config.cache_isolation:
            return {
                "type": "namespace_isolation",
                "key_prefix": f"tenant:{tenant_id}:",
                "ttl_default": 3600,
                "max_memory": "100MB" if config.tier == TenantTier.BASIC else "500MB"
            }
        else:
            return {
                "type": "shared_cache",
                "key_prefix": "shared:",
                "ttl_default": 1800,
                "max_memory": "50MB"
            }
    
    def get_logging_strategy(self, tenant_id: str) -> Dict[str, Any]:
        """Get logging isolation strategy for tenant"""
        config = self.isolation_configs.get(tenant_id)
        if not config:
            raise ValueError(f"Tenant {tenant_id} not registered")
            
        return {
            "type": "contextual_logging",
            "tenant_context": True,
            "separate_files": config.tier != TenantTier.BASIC,
            "log_file": f"/logs/tenant_{tenant_id}.log" if config.tier != TenantTier.BASIC else "/logs/shared.log",
            "log_level": "INFO",
            "retention_days": 30 if config.tier == TenantTier.BASIC else 90
        }
    
    def validate_tenant_access(self, tenant_id: str, resource_tenant_id: str) -> bool:
        """Validate that a tenant can access a specific resource"""
        if tenant_id != resource_tenant_id:
            return False
        return tenant_id in self.isolation_configs
    
    def get_security_context(self, tenant_id: str) -> Dict[str, Any]:
        """Get security context for tenant operations"""
        config = self.isolation_configs.get(tenant_id)
        if not config:
            raise ValueError(f"Tenant {tenant_id} not registered")
            
        return {
            "tenant_id": tenant_id,
            "tier": config.tier.value,
            "isolation_level": config.isolation_level.value,
            "permissions": {
                "read_own_data": True,
                "write_own_data": True,
                "read_other_data": False,
                "write_other_data": False,
                "admin_operations": config.tier == TenantTier.ENTERPRISE
            }
        }


# Global instance
tenant_isolation = TenantIsolationStrategy()


def get_tenant_isolation_strategy() -> TenantIsolationStrategy:
    """Get the global tenant isolation strategy instance"""
    return tenant_isolation


# Utility functions for common operations
def create_tenant_directory_structure(tenant_id: str) -> None:
    """Create directory structure for a new tenant"""
    strategy = get_tenant_isolation_strategy()
    fs_config = strategy.get_filesystem_strategy(tenant_id)
    
    directories = [
        fs_config["tenant_path"],
        fs_config["documents_path"],
        fs_config["uploads_path"],
        fs_config["cache_path"],
        fs_config["logs_path"]
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)


def get_tenant_scoped_key(tenant_id: str, key: str) -> str:
    """Generate tenant-scoped cache/resource key"""
    strategy = get_tenant_isolation_strategy()
    cache_config = strategy.get_cache_strategy(tenant_id)
    return f"{cache_config['key_prefix']}{key}"


def validate_cross_tenant_access(requesting_tenant: str, target_tenant: str) -> bool:
    """Validate cross-tenant access attempts"""
    strategy = get_tenant_isolation_strategy()
    return strategy.validate_tenant_access(requesting_tenant, target_tenant)


# Security decorators and middleware will use these functions
class TenantSecurityError(Exception):
    """Raised when tenant security violations are detected"""
    pass


def ensure_tenant_isolation(func):
    """Decorator to ensure tenant isolation in function calls"""
    def wrapper(*args, **kwargs):
        # Implementation would check tenant context
        # This is a placeholder for the actual security implementation
        return func(*args, **kwargs)
    return wrapper 