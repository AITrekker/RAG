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
    auto_sync: Mapped[bool] = mapped_column(Boolean, default=True)
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
    
    # Vector Store Reference
    qdrant_point_id: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), nullable=False)
    collection_name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Processing Metadata
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False, default='all-MiniLM-L6-v2')
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    file: Mapped["File"] = relationship("File", back_populates="chunks")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('file_id', 'chunk_index', name='uq_file_chunk_index'),
        UniqueConstraint('qdrant_point_id', name='uq_qdrant_point_id'),
        CheckConstraint('chunk_index >= 0', name='check_chunk_index_non_negative'),
        CheckConstraint('token_count > 0', name='check_token_count_positive'),
        Index('idx_chunks_tenant_id', 'tenant_id'),
        Index('idx_chunks_file_id', 'file_id', 'chunk_index'),
        Index('idx_qdrant_point_lookup', 'qdrant_point_id')
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
# ANALYTICS & METRICS TRACKING
# =============================================

class QueryLog(BaseModel):
    """Query history and performance tracking"""
    __tablename__ = "query_logs"
    
    tenant_id: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    user_id: Mapped[Optional[UUID]] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))
    
    # Query Content
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # For deduplication
    query_type: Mapped[str] = mapped_column(String(50), default='rag_search')
    
    # Response Details
    response_text: Mapped[Optional[str]] = mapped_column(Text)
    response_type: Mapped[str] = mapped_column(String(50), default='success')  # success, no_answer, error
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)
    sources_count: Mapped[int] = mapped_column(Integer, default=0)
    chunks_retrieved: Mapped[int] = mapped_column(Integer, default=0)
    
    # Performance Metrics
    response_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    search_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    llm_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Model Information
    embedding_model: Mapped[str] = mapped_column(String(100), default='all-MiniLM-L6-v2')
    llm_model: Mapped[str] = mapped_column(String(100), default='gpt-3.5-turbo')
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer)
    cost_usd: Mapped[Optional[float]] = mapped_column(Float)
    
    # Context Information
    session_id: Mapped[Optional[str]] = mapped_column(String(100))
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    
    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    user: Mapped[Optional["User"]] = relationship("User")
    feedback: Mapped[List["QueryFeedback"]] = relationship("QueryFeedback", back_populates="query_log")
    document_access: Mapped[List["DocumentAccessLog"]] = relationship("DocumentAccessLog", back_populates="query_log")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("response_type IN ('success', 'no_answer', 'error', 'filtered')", name='check_response_type'),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name='check_confidence_range'),
        CheckConstraint("response_time_ms > 0", name='check_response_time_positive'),
        Index('idx_query_logs_tenant', 'tenant_id', 'created_at'),
        Index('idx_query_logs_user', 'user_id', 'created_at'),
        Index('idx_query_logs_performance', 'response_time_ms', 'created_at'),
        Index('idx_query_logs_hash', 'query_hash', 'tenant_id'),
        Index('idx_query_logs_type', 'query_type', 'response_type')
    )

class QueryFeedback(BaseModel):
    """User feedback on query responses"""
    __tablename__ = "query_feedback"
    
    query_log_id: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('query_logs.id', ondelete='CASCADE'), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    user_id: Mapped[Optional[UUID]] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))
    
    # Feedback Content
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5 scale
    feedback_type: Mapped[str] = mapped_column(String(50), default='rating')
    feedback_text: Mapped[Optional[str]] = mapped_column(Text)
    helpful: Mapped[Optional[bool]] = mapped_column(Boolean)
    
    # Specific Feedback Categories
    accuracy_rating: Mapped[Optional[int]] = mapped_column(Integer)
    relevance_rating: Mapped[Optional[int]] = mapped_column(Integer)
    completeness_rating: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Relationships
    query_log: Mapped["QueryLog"] = relationship("QueryLog", back_populates="feedback")
    tenant: Mapped["Tenant"] = relationship("Tenant")
    user: Mapped[Optional["User"]] = relationship("User")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name='check_rating_range'),
        CheckConstraint("accuracy_rating >= 1 AND accuracy_rating <= 5", name='check_accuracy_range'),
        CheckConstraint("relevance_rating >= 1 AND relevance_rating <= 5", name='check_relevance_range'),
        CheckConstraint("completeness_rating >= 1 AND completeness_rating <= 5", name='check_completeness_range'),
        CheckConstraint("feedback_type IN ('rating', 'thumbs', 'detailed', 'bug_report')", name='check_feedback_type'),
        Index('idx_query_feedback_query', 'query_log_id'),
        Index('idx_query_feedback_tenant', 'tenant_id', 'created_at'),
        Index('idx_query_feedback_rating', 'rating', 'helpful')
    )

class TenantMetrics(BaseModel):
    """Daily aggregated metrics per tenant"""
    __tablename__ = "tenant_metrics"
    
    tenant_id: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Query Metrics
    total_queries: Mapped[int] = mapped_column(Integer, default=0)
    successful_queries: Mapped[int] = mapped_column(Integer, default=0)
    no_answer_queries: Mapped[int] = mapped_column(Integer, default=0)
    error_queries: Mapped[int] = mapped_column(Integer, default=0)
    
    # User Activity
    unique_users: Mapped[int] = mapped_column(Integer, default=0)
    new_users: Mapped[int] = mapped_column(Integer, default=0)
    active_sessions: Mapped[int] = mapped_column(Integer, default=0)
    
    # Performance Metrics
    avg_response_time: Mapped[Optional[float]] = mapped_column(Float)
    avg_confidence_score: Mapped[Optional[float]] = mapped_column(Float)
    p95_response_time: Mapped[Optional[float]] = mapped_column(Float)
    
    # Document Metrics
    total_documents: Mapped[int] = mapped_column(Integer, default=0)
    documents_added: Mapped[int] = mapped_column(Integer, default=0)
    documents_updated: Mapped[int] = mapped_column(Integer, default=0)
    documents_deleted: Mapped[int] = mapped_column(Integer, default=0)
    total_chunks: Mapped[int] = mapped_column(Integer, default=0)
    
    # Storage Metrics
    storage_used_mb: Mapped[float] = mapped_column(Float, default=0.0)
    storage_delta_mb: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Cost Metrics
    total_cost_usd: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    
    # Quality Metrics
    avg_user_rating: Mapped[Optional[float]] = mapped_column(Float)
    feedback_count: Mapped[int] = mapped_column(Integer, default=0)
    thumbs_up_count: Mapped[int] = mapped_column(Integer, default=0)
    thumbs_down_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('tenant_id', 'metric_date', name='uq_tenant_metrics_date'),
        CheckConstraint("avg_confidence_score >= 0 AND avg_confidence_score <= 1", name='check_avg_confidence_range'),
        CheckConstraint("avg_user_rating >= 1 AND avg_user_rating <= 5", name='check_avg_rating_range'),
        CheckConstraint("storage_used_mb >= 0", name='check_storage_positive'),
        Index('idx_tenant_metrics_tenant', 'tenant_id', 'metric_date'),
        Index('idx_tenant_metrics_date', 'metric_date'),
        Index('idx_tenant_metrics_performance', 'avg_response_time', 'metric_date')
    )

class DocumentAccessLog(BaseModel):
    """Track which documents are accessed/referenced in queries"""
    __tablename__ = "document_access_logs"
    
    query_log_id: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('query_logs.id', ondelete='CASCADE'), nullable=False)
    file_id: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('files.id', ondelete='CASCADE'), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    
    # Access Details
    chunks_used: Mapped[int] = mapped_column(Integer, default=1)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False)
    rank_position: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-based ranking
    included_in_response: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    query_log: Mapped["QueryLog"] = relationship("QueryLog", back_populates="document_access")
    file: Mapped["File"] = relationship("File")
    tenant: Mapped["Tenant"] = relationship("Tenant")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("relevance_score >= 0 AND relevance_score <= 1", name='check_relevance_score_range'),
        CheckConstraint("rank_position > 0", name='check_rank_positive'),
        CheckConstraint("chunks_used > 0", name='check_chunks_used_positive'),
        Index('idx_document_access_query', 'query_log_id', 'rank_position'),
        Index('idx_document_access_file', 'file_id', 'created_at'),
        Index('idx_document_access_tenant', 'tenant_id', 'created_at'),
        Index('idx_document_access_relevance', 'relevance_score', 'rank_position')
    )

class UserSession(BaseModel):
    """Track user sessions for analytics"""
    __tablename__ = "user_sessions"
    
    tenant_id: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    user_id: Mapped[Optional[UUID]] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))
    
    # Session Details
    session_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    
    # Session Metrics
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    query_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    user: Mapped[Optional["User"]] = relationship("User")
    
    # Constraints
    __table_args__ = (
        Index('idx_user_sessions_tenant', 'tenant_id', 'started_at'),
        Index('idx_user_sessions_user', 'user_id', 'started_at'),
        Index('idx_user_sessions_session_id', 'session_id'),
        Index('idx_user_sessions_activity', 'last_activity_at')
    )