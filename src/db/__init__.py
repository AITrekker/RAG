"""
Database module for Enterprise RAG Pipeline.

This module provides database models, connection management, and operations.
"""

from .models import (
    Base,
    TimestampMixin,
    TenantMixin,
    Tenant,
    File,
    FileVersion,
    DocumentChunk,
    Embedding,
    SyncStatus,
    SyncFileStatus,
)

from .engine import (
    get_engine,
    get_session_factory,
    get_db_session,
    get_db,
    get_tenant_session,
    init_database,
    create_tables,
)

from .operations import (
    DatabaseOperationError,
    TenantNotFoundError,
    BaseCRUD,
    TenantAwareCRUD,
    tenant_crud,
    file_crud,
    execute_with_transaction,
    execute_with_tenant_transaction,
)

from .connection_pool import (
    get_pool_monitor,
    get_pool_manager,
    monitored_connection,
    initialize_connection_pool,
    check_pool_health,
    get_pool_status,
)

__all__ = [
    # Base classes
    "Base",
    "TimestampMixin", 
    "TenantMixin",
    
    # Models
    "Tenant",
    "File",
    "FileVersion",
    "DocumentChunk",
    "Embedding", 
    "SyncStatus",
    "SyncFileStatus",
    
    # Engine functions
    "get_engine",
    "get_session_factory",
    "get_db_session",
    "get_db",
    "get_tenant_session",
    "init_database",
    "create_tables",
    
    # Operations
    "DatabaseOperationError",
    "TenantNotFoundError",
    "BaseCRUD",
    "TenantAwareCRUD",
    "tenant_crud",
    "file_crud",
    "execute_with_transaction",
    "execute_with_tenant_transaction",
    
    # Connection pooling
    "get_pool_monitor",
    "get_pool_manager",
    "monitored_connection",
    "initialize_connection_pool",
    "check_pool_health",
    "get_pool_status",
] 