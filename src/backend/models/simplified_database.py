"""
Simplified Database Models - 4 Core Tables Only
Replaces the complex 12-table schema with essential multi-tenant functionality
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, String, Text, BigInteger, Float,
    ForeignKey, CheckConstraint, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID as PostgreUUID, JSONB

# pgvector support
try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    Vector = None

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

Base = declarative_base()


# =============================================
# BASE MODEL CLASS
# =============================================

class BaseModel(Base):
    """Base model with common fields"""
    __abstract__ = True
    
    id: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# =============================================
# CORE TABLE 1: TENANTS
# =============================================

class Tenant(BaseModel):
    """Multi-tenant isolation - the foundation"""
    __tablename__ = "tenants"
    
    # Essential tenant fields
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    
    # API Key Authentication (simple, no users table needed for MVP)
    api_key: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    api_key_hash: Mapped[Optional[str]] = mapped_column(String(64))
    api_key_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Simple settings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_sync: Mapped[bool] = mapped_column(Boolean, default=False)
    storage_limit_gb: Mapped[int] = mapped_column(Integer, default=10)
    
    # Relationships to other core tables
    files: Mapped[List["File"]] = relationship("File", back_populates="tenant")
    sync_operations: Mapped[List["SyncOperation"]] = relationship("SyncOperation", back_populates="tenant")
    
    # Essential indexes only
    __table_args__ = (
        Index('idx_tenants_slug', 'slug'),
        Index('idx_tenants_api_key', 'api_key'),
        Index('idx_tenants_active', 'is_active'),
    )


# =============================================
# CORE TABLE 2: FILES  
# =============================================

class File(BaseModel):
    """File tracking with tenant isolation"""
    __tablename__ = "files"
    
    # Tenant isolation (most important)
    tenant_id: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    
    # Essential file information
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)  # relative to tenant directory
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 for change detection
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Sync status tracking
    sync_status: Mapped[str] = mapped_column(String(20), nullable=False, default='pending')
    sync_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sync_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sync_error: Mapped[Optional[str]] = mapped_column(Text)
    
    # Soft delete
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="files")
    chunks: Mapped[List["EmbeddingChunk"]] = relationship("EmbeddingChunk", back_populates="file")
    
    # Critical indexes for performance
    __table_args__ = (
        UniqueConstraint('tenant_id', 'file_path', name='uq_tenant_file_path'),
        CheckConstraint('file_size > 0', name='check_file_size_positive'),
        CheckConstraint("sync_status IN ('pending', 'processing', 'synced', 'failed', 'deleted')", name='check_sync_status'),
        # Essential indexes for tenant isolation and sync operations
        Index('idx_files_tenant_id', 'tenant_id'),
        Index('idx_files_sync_status', 'sync_status', 'updated_at'),
        Index('idx_files_hash_lookup', 'tenant_id', 'file_hash'),
        Index('idx_files_path_lookup', 'tenant_id', 'file_path'),
    )


# =============================================
# CORE TABLE 3: EMBEDDING_CHUNKS
# =============================================

class EmbeddingChunk(BaseModel):
    """Vector embeddings with tenant isolation"""
    __tablename__ = "embedding_chunks"
    
    # Tenant isolation and file relationship
    file_id: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('files.id', ondelete='CASCADE'), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    
    # Chunk information
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    token_count: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Vector embedding (384 dimensions for all-MiniLM-L6-v2)
    if PGVECTOR_AVAILABLE:
        embedding: Mapped[Optional[Vector]] = mapped_column(Vector(384))
    else:
        # Fallback when pgvector not available
        embedding: Mapped[Optional[list]] = mapped_column(JSONB)
    
    # Processing metadata
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False, default='all-MiniLM-L6-v2')
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    file: Mapped["File"] = relationship("File", back_populates="chunks")
    
    # Indexes for vector similarity search and tenant isolation
    if PGVECTOR_AVAILABLE:
        __table_args__ = (
            UniqueConstraint('file_id', 'chunk_index', name='uq_file_chunk_index'),
            CheckConstraint('chunk_index >= 0', name='check_chunk_index_non_negative'),
            # Critical indexes for multi-tenant vector search
            Index('idx_chunks_tenant_id', 'tenant_id'),
            Index('idx_chunks_file_id', 'file_id', 'chunk_index'),
            Index('idx_chunks_embedding', 'embedding', postgresql_using='ivfflat', postgresql_ops={'embedding': 'vector_cosine_ops'}),
        )
    else:
        __table_args__ = (
            UniqueConstraint('file_id', 'chunk_index', name='uq_file_chunk_index'),
            CheckConstraint('chunk_index >= 0', name='check_chunk_index_non_negative'),
            Index('idx_chunks_tenant_id', 'tenant_id'),
            Index('idx_chunks_file_id', 'file_id', 'chunk_index'),
        )


# =============================================
# CORE TABLE 4: SYNC_OPERATIONS
# =============================================

class SyncOperation(BaseModel):
    """Track sync operations for monitoring and debugging"""
    __tablename__ = "sync_operations"
    
    # Tenant isolation
    tenant_id: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    
    # Operation details
    operation_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'full_sync', 'delta_sync', 'file_sync'
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='running')  # 'running', 'completed', 'failed'
    
    # Timing
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Statistics (simple counters)
    files_processed: Mapped[int] = mapped_column(Integer, default=0)
    files_added: Mapped[int] = mapped_column(Integer, default=0)
    files_updated: Mapped[int] = mapped_column(Integer, default=0)
    files_deleted: Mapped[int] = mapped_column(Integer, default=0)
    
    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    
    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="sync_operations")
    
    # Simple indexes for monitoring
    __table_args__ = (
        CheckConstraint("operation_type IN ('full_sync', 'delta_sync', 'file_sync')", name='check_operation_type'),
        CheckConstraint("status IN ('running', 'completed', 'failed', 'cancelled')", name='check_sync_status'),
        Index('idx_sync_operations_tenant', 'tenant_id', 'started_at'),
        Index('idx_sync_operations_status', 'status', 'started_at'),
    )


# =============================================
# REMOVED TABLES (for reference)
# =============================================

"""
These 8 tables have been removed to simplify the system:

1. users - Use API key auth instead of user accounts for MVP
2. tenant_memberships - No user management needed yet
3. file_access_control - No sharing features needed yet  
4. file_sharing_links - No sharing features needed yet
5. query_logs - No analytics needed yet
6. query_feedback - No feedback system needed yet
7. tenant_metrics - No metrics dashboard needed yet
8. document_access_logs - No access tracking needed yet
9. user_sessions - No session management needed yet

These can be added back when you actually need the features,
but for MVP multi-tenant RAG, you only need the 4 core tables above.
"""


# =============================================
# MIGRATION COMPATIBILITY
# =============================================

def get_core_tables():
    """Get list of core table names for migration scripts"""
    return ['tenants', 'files', 'embedding_chunks', 'sync_operations']


def get_removed_tables():
    """Get list of tables that were removed in simplification"""
    return [
        'users', 'tenant_memberships', 'file_access_control',
        'file_sharing_links', 'query_logs', 'query_feedback',
        'tenant_metrics', 'document_access_logs', 'user_sessions'
    ]