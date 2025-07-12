"""
SQLAlchemy Database Models for RAG Platform
PostgreSQL + Qdrant Hybrid Architecture
"""

from datetime import datetime, date
from typing import Optional, List
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, String, Text, BigInteger, Float, Date,
    ForeignKey, CheckConstraint, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID as PostgreUUID, JSONB
try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    Vector = None  # Fallback for when pgvector is not available
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
# TENANTS & USERS
# =============================================

class Tenant(BaseModel):
    """Tenant model for multi-tenancy"""
    __tablename__ = "tenants"
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    plan_tier: Mapped[str] = mapped_column(String(50), nullable=False, default='free')
    storage_limit_gb: Mapped[int] = mapped_column(Integer, default=10)
    max_users: Mapped[int] = mapped_column(Integer, default=5)
    settings: Mapped[dict] = mapped_column(JSONB, default={})
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Additional tenant fields
    description: Mapped[Optional[str]] = mapped_column(Text)
    auto_sync: Mapped[bool] = mapped_column(Boolean, default=False)
    sync_interval: Mapped[int] = mapped_column(Integer, default=60)
    status: Mapped[Optional[str]] = mapped_column(String(50), default='active')
    environment: Mapped[str] = mapped_column(String(20), nullable=False, default='production')
    
    # API Key Authentication
    api_key: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    api_key_hash: Mapped[Optional[str]] = mapped_column(String(64))
    api_key_name: Mapped[Optional[str]] = mapped_column(String(100))
    api_key_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    api_key_last_used: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    memberships: Mapped[List["TenantMembership"]] = relationship("TenantMembership", back_populates="tenant")
    files: Mapped[List["File"]] = relationship("File", back_populates="tenant")
    sync_operations: Mapped[List["SyncOperation"]] = relationship("SyncOperation", back_populates="tenant")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("plan_tier IN ('free', 'pro', 'enterprise')", name='check_plan_tier'),
        CheckConstraint("environment IN ('production', 'test', 'development', 'staging')", name='check_environment'),
        Index('idx_tenants_slug', 'slug'),
        Index('idx_tenants_active', 'is_active'),
        Index('idx_tenants_api_key', 'api_key'),
        Index('idx_tenants_environment', 'environment')
    )

class User(BaseModel):
    """User model"""
    __tablename__ = "users"
    
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    tenant_memberships: Mapped[List["TenantMembership"]] = relationship("TenantMembership", back_populates="user")
    uploaded_files: Mapped[List["File"]] = relationship("File", foreign_keys="File.uploaded_by", back_populates="uploader")
    granted_access: Mapped[List["FileAccessControl"]] = relationship("FileAccessControl", foreign_keys="FileAccessControl.granted_by")
    file_access: Mapped[List["FileAccessControl"]] = relationship("FileAccessControl", foreign_keys="FileAccessControl.user_id")
    
    # Constraints  
    __table_args__ = (
        Index('idx_users_email', 'email'),
        Index('idx_users_active', 'is_active')
    )

class TenantMembership(BaseModel):
    """User membership in tenants"""
    __tablename__ = "tenant_memberships"
    
    tenant_id: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default='member')
    permissions: Mapped[dict] = mapped_column(JSONB, default={})
    
    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="memberships")
    user: Mapped["User"] = relationship("User", back_populates="tenant_memberships")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('tenant_id', 'user_id', name='uq_tenant_user'),
        CheckConstraint("role IN ('owner', 'admin', 'member', 'viewer')", name='check_role'),
        Index('idx_memberships_tenant_id', 'tenant_id'),
        Index('idx_memberships_user_id', 'user_id')
    )

# =============================================
# FILE MANAGEMENT & SYNC
# =============================================

class File(BaseModel):
    """File tracking model"""
    __tablename__ = "files"
    
    tenant_id: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    uploaded_by: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64))
    
    # Sync Status
    sync_status: Mapped[str] = mapped_column(String(20), nullable=False, default='pending')
    sync_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sync_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sync_error: Mapped[Optional[str]] = mapped_column(Text)
    sync_retry_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # File Metadata
    word_count: Mapped[Optional[int]] = mapped_column(Integer)
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
    language: Mapped[Optional[str]] = mapped_column(String(10))
    extraction_method: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Lifecycle
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="files")
    uploader: Mapped["User"] = relationship("User", foreign_keys=[uploaded_by], back_populates="uploaded_files")
    chunks: Mapped[List["EmbeddingChunk"]] = relationship("EmbeddingChunk", back_populates="file")
    access_controls: Mapped[List["FileAccessControl"]] = relationship("FileAccessControl", back_populates="file")
    sharing_links: Mapped[List["FileSharingLink"]] = relationship("FileSharingLink", back_populates="file")
    sync_history: Mapped[List["FileSyncHistory"]] = relationship("FileSyncHistory", back_populates="file")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('tenant_id', 'file_path', name='uq_tenant_file_path'),
        CheckConstraint('file_size > 0', name='check_file_size_positive'),
        CheckConstraint("sync_status IN ('pending', 'processing', 'synced', 'failed', 'deleted')", name='check_sync_status'),
        Index('idx_files_tenant_id', 'tenant_id'),
        Index('idx_files_sync_status', 'sync_status', 'updated_at'),
        Index('idx_files_hash_lookup', 'tenant_id', 'file_hash'),
        Index('idx_files_path_lookup', 'tenant_id', 'file_path')
    )

class EmbeddingChunk(BaseModel):
    """Embedding chunk metadata"""
    __tablename__ = "embedding_chunks"
    
    file_id: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('files.id', ondelete='CASCADE'), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    
    # Chunk Information
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    token_count: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Vector Embedding (384 dimensions for all-MiniLM-L6-v2)
    if PGVECTOR_AVAILABLE:
        embedding: Mapped[Optional[Vector]] = mapped_column(Vector(384))
    else:
        # Fallback: store as JSON when pgvector is not available
        embedding: Mapped[Optional[list]] = mapped_column(JSONB)
    
    # Processing Metadata
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False, default='all-MiniLM-L6-v2')
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    file: Mapped["File"] = relationship("File", back_populates="chunks")
    
    # Constraints
    if PGVECTOR_AVAILABLE:
        __table_args__ = (
            UniqueConstraint('file_id', 'chunk_index', name='uq_file_chunk_index'),
            CheckConstraint('chunk_index >= 0', name='check_chunk_index_non_negative'),
            CheckConstraint('token_count > 0', name='check_token_count_positive'),
            Index('idx_chunks_tenant_id', 'tenant_id'),
            Index('idx_chunks_file_id', 'file_id', 'chunk_index'),
            Index('idx_chunks_embedding', 'embedding', postgresql_using='ivfflat', postgresql_ops={'embedding': 'vector_cosine_ops'})
        )
    else:
        __table_args__ = (
            UniqueConstraint('file_id', 'chunk_index', name='uq_file_chunk_index'),
            CheckConstraint('chunk_index >= 0', name='check_chunk_index_non_negative'),
            CheckConstraint('token_count > 0', name='check_token_count_positive'),
            Index('idx_chunks_tenant_id', 'tenant_id'),
            Index('idx_chunks_file_id', 'file_id', 'chunk_index')
        )

# =============================================
# ACCESS CONTROL & SHARING
# =============================================

class FileAccessControl(BaseModel):
    """File access control"""
    __tablename__ = "file_access_control"
    
    file_id: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('files.id', ondelete='CASCADE'), nullable=False)
    user_id: Mapped[Optional[UUID]] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'))
    access_type: Mapped[str] = mapped_column(String(20), nullable=False, default='read')
    granted_by: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    file: Mapped["File"] = relationship("File", back_populates="access_controls")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('file_id', 'user_id', name='uq_file_user_access'),
        CheckConstraint("access_type IN ('read', 'write', 'admin')", name='check_access_type'),
        Index('idx_file_access_user', 'user_id', 'access_type'),
        Index('idx_file_access_file', 'file_id', 'access_type')
    )

class FileSharingLink(BaseModel):
    """File sharing links"""
    __tablename__ = "file_sharing_links"
    
    file_id: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('files.id', ondelete='CASCADE'), nullable=False)
    share_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    access_type: Mapped[str] = mapped_column(String(20), nullable=False, default='read')
    created_by: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    max_uses: Mapped[Optional[int]] = mapped_column(Integer)
    current_uses: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    file: Mapped["File"] = relationship("File", back_populates="sharing_links")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("access_type IN ('read', 'write', 'admin')", name='check_share_access_type'),
        Index('idx_sharing_token', 'share_token'),
        Index('idx_sharing_active', 'is_active', 'expires_at')
    )

# =============================================
# SYNC TRACKING & AUDIT
# =============================================

class SyncOperation(BaseModel):
    """Sync operation tracking"""
    __tablename__ = "sync_operations"
    
    tenant_id: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    operation_type: Mapped[str] = mapped_column(String(20), nullable=False)
    triggered_by: Mapped[Optional[UUID]] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('users.id'))
    
    # Operation Status
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='running')
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Heartbeat and Progress Tracking
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    expected_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    progress_stage: Mapped[Optional[str]] = mapped_column(String(50))
    progress_percentage: Mapped[Optional[float]] = mapped_column(Float)
    total_files_to_process: Mapped[Optional[int]] = mapped_column(Integer)
    current_file_index: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Statistics
    files_processed: Mapped[int] = mapped_column(Integer, default=0)
    files_added: Mapped[int] = mapped_column(Integer, default=0)
    files_updated: Mapped[int] = mapped_column(Integer, default=0)
    files_deleted: Mapped[int] = mapped_column(Integer, default=0)
    chunks_created: Mapped[int] = mapped_column(Integer, default=0)
    chunks_updated: Mapped[int] = mapped_column(Integer, default=0)
    chunks_deleted: Mapped[int] = mapped_column(Integer, default=0)
    
    # Error Tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    error_details: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="sync_operations")
    sync_history: Mapped[List["FileSyncHistory"]] = relationship("FileSyncHistory", back_populates="sync_operation")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("operation_type IN ('full_sync', 'delta_sync', 'file_sync')", name='check_operation_type'),
        CheckConstraint("status IN ('running', 'completed', 'failed', 'cancelled')", name='check_sync_status'),
        CheckConstraint("progress_percentage >= 0 AND progress_percentage <= 100", name='check_progress_range'),
        CheckConstraint("current_file_index >= 0", name='check_current_file_index'),
        CheckConstraint("total_files_to_process >= 0", name='check_total_files'),
        Index('idx_sync_operations_tenant', 'tenant_id', 'started_at'),
        Index('idx_sync_operations_status', 'status', 'started_at'),
        Index('idx_sync_operations_heartbeat', 'status', 'heartbeat_at'),
        Index('idx_sync_operations_progress', 'tenant_id', 'status', 'progress_stage')
    )

class FileSyncHistory(BaseModel):
    """File sync history"""
    __tablename__ = "file_sync_history"
    
    file_id: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('files.id', ondelete='CASCADE'), nullable=False)
    sync_operation_id: Mapped[Optional[UUID]] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('sync_operations.id', ondelete='SET NULL'))
    
    # Change Detection
    previous_hash: Mapped[Optional[str]] = mapped_column(String(64))
    new_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    change_type: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Processing Results
    chunks_before: Mapped[int] = mapped_column(Integer, default=0)
    chunks_after: Mapped[int] = mapped_column(Integer, default=0)
    processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    file: Mapped["File"] = relationship("File", back_populates="sync_history")
    sync_operation: Mapped[Optional["SyncOperation"]] = relationship("SyncOperation", back_populates="sync_history")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("change_type IN ('created', 'updated', 'deleted', 'renamed')", name='check_change_type'),
        Index('idx_sync_history_file', 'file_id', 'synced_at'),
        Index('idx_sync_history_operation', 'sync_operation_id', 'synced_at')
    )

# =============================================
# ANALYTICS & METRICS TRACKING - REMOVED
# =============================================
# Analytics tables (QueryLog, QueryFeedback, TenantMetrics, DocumentAccessLog, UserSession)
# have been completely removed to simplify the system for embeddings and reranking experimentation.
# They can be re-added from git history if analytics functionality is needed later.