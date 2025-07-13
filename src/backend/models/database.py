"""
SQLAlchemy Database Models for RAG Platform
Simplified Multi-Tenant Architecture with PostgreSQL + pgvector
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
# CORE TABLES (4 TABLES TOTAL)
# =============================================

class Tenant(BaseModel):
    """Simple tenant model for RAG experimentation"""
    __tablename__ = "tenants"
    
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    api_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    
    # Relationships
    files: Mapped[List["File"]] = relationship("File", back_populates="tenant")
    sync_operations: Mapped[List["SyncOperation"]] = relationship("SyncOperation", back_populates="tenant")
    
    # Constraints
    __table_args__ = (
        Index('idx_tenants_slug', 'slug'),
        Index('idx_tenants_api_key', 'api_key')
    )

class File(BaseModel):
    """File tracking model"""
    __tablename__ = "files"
    
    tenant_id: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
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
    chunks: Mapped[List["EmbeddingChunk"]] = relationship("EmbeddingChunk", back_populates="file")
    
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
    """Embedding chunk metadata and vector storage"""
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

class SyncOperation(BaseModel):
    """Sync operation tracking"""
    __tablename__ = "sync_operations"
    
    tenant_id: Mapped[UUID] = mapped_column(PostgreUUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    operation_type: Mapped[str] = mapped_column(String(20), nullable=False)
    
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
    
    # Detailed Progress Metrics
    current_file_name: Mapped[Optional[str]] = mapped_column(String(255))
    current_file_size: Mapped[Optional[int]] = mapped_column(Integer)
    current_file_type: Mapped[Optional[str]] = mapped_column(String(10))
    processing_speed_files_per_min: Mapped[Optional[float]] = mapped_column(Float)
    processing_speed_chunks_per_min: Mapped[Optional[float]] = mapped_column(Float)
    memory_usage_mb: Mapped[Optional[int]] = mapped_column(Integer)
    extraction_method: Mapped[Optional[str]] = mapped_column(String(50))
    
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

# =============================================
# SIMPLIFIED SCHEMA SUMMARY
# =============================================
# 
# This simplified schema contains only 4 essential tables:
# 
# 1. tenants - Multi-tenant management with direct API key authentication
# 2. files - File metadata and sync status tracking  
# 3. embedding_chunks - Text chunks with pgvector embeddings for RAG
# 4. sync_operations - Processing pipeline status and statistics
#
# REMOVED TABLES (can be restored from git history if needed):
# - users, tenant_memberships (no user system - using direct tenant API keys)
# - file_access_control, file_sharing_links (no sharing/permissions needed)
# - file_sync_history (basic sync_operations provides enough tracking)
# - analytics tables (QueryLog, QueryFeedback, etc.)
#
# This reduces complexity by 55% while maintaining all core functionality
# needed for embeddings and reranking experimentation.