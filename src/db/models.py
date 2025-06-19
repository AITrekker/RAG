"""
Database models for Enterprise RAG Pipeline.

This module defines SQLAlchemy models for file tracking, versioning,
embedding management, and sync status with multi-tenant support.
"""

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Float, JSON,
    ForeignKey, Index, UniqueConstraint, CheckConstraint, LargeBinary
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, Dict, Any
import uuid
from enum import Enum

Base = declarative_base()

class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

class TenantMixin:
    """Mixin for tenant support."""
    tenant_id = Column(String(255), nullable=False, index=True)

class SyncTaskStatus(str, Enum):
    """Status of a sync task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    ERROR = "error"

class SyncMetric(Base):
    """Model for storing sync task metrics."""
    __tablename__ = "sync_metrics"
    
    id = Column(Integer, primary_key=True)
    task_id = Column(String(255), nullable=False, index=True)
    tenant_id = Column(String(255), nullable=True, index=True)
    metric_type = Column(String(50), nullable=False)
    value = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class SyncReport(Base):
    """Model for storing sync task reports."""
    __tablename__ = "sync_reports"
    
    id = Column(Integer, primary_key=True)
    task_id = Column(String(255), nullable=False, unique=True, index=True)
    tenant_id = Column(String(255), nullable=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    status = Column(SQLEnum(SyncTaskStatus), nullable=False)
    metrics = Column(JSON, nullable=False)  # Serialized metrics data
    details = Column(JSON, nullable=True)  # Additional report details
    created_at = Column(DateTime, default=datetime.utcnow)

# Tenant Management Tables

class Tenant(Base, TimestampMixin):
    """
    Tenant model for multi-tenant support.
    """
    __tablename__ = "tenants"
    
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Configuration
    config = Column(JSON, default=dict)
    
    # Resource limits
    max_files = Column(Integer, default=10000)
    max_storage_gb = Column(Float, default=50.0)
    max_queries_per_hour = Column(Integer, default=1000)
    
    # Folder mapping
    source_folder_path = Column(String(500), nullable=False)
    processed_folder_path = Column(String(500), nullable=False)
    
    # Relationships
    files = relationship("File", back_populates="tenant", cascade="all, delete-orphan")
    embeddings = relationship("Embedding", back_populates="tenant", cascade="all, delete-orphan")
    sync_status = relationship("SyncStatus", back_populates="tenant", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('name', name='uq_tenant_name'),
        Index('ix_tenant_active', 'is_active'),
    )

# Core File Tracking Tables

class File(Base, TimestampMixin, TenantMixin):
    """
    File model for tracking documents in the system.
    """
    __tablename__ = "files"
    
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # File identification
    file_path = Column(String(1000), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_extension = Column(String(10), nullable=False)
    
    # File metadata
    file_size_bytes = Column(Integer, nullable=False)
    file_hash = Column(String(64), nullable=False)  # SHA-256 hash
    mime_type = Column(String(100))
    
    # File dates
    file_created_at = Column(DateTime)
    file_modified_at = Column(DateTime)
    
    # Processing status
    status = Column(String(50), default="pending", nullable=False)
    processing_started_at = Column(DateTime)
    processing_completed_at = Column(DateTime)
    processing_error = Column(Text)
    
    # Content metadata
    title = Column(String(500))
    author = Column(String(255))
    department = Column(String(255))
    category = Column(String(100))
    keywords = Column(JSON, default=list)
    summary = Column(Text)
    
    # Document structure
    page_count = Column(Integer)
    word_count = Column(Integer)
    character_count = Column(Integer)
    
    # Custom metadata
    custom_metadata = Column(JSON, default=dict)
    
    # Folder context
    folder_path = Column(String(1000), nullable=False)
    relative_path = Column(String(1000), nullable=False)
    
    # Version tracking
    current_version = Column(Integer, default=1)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="files")
    versions = relationship("FileVersion", back_populates="file", cascade="all, delete-orphan")
    chunks = relationship("DocumentChunk", back_populates="file", cascade="all, delete-orphan")
    embeddings = relationship("Embedding", back_populates="file", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('ix_file_tenant_path', 'tenant_id', 'file_path'),
        Index('ix_file_tenant_status', 'tenant_id', 'status'),
        Index('ix_file_hash', 'file_hash'),
        Index('ix_file_modified', 'file_modified_at'),
        Index('ix_file_category', 'tenant_id', 'category'),
        Index('ix_file_department', 'tenant_id', 'department'),
        UniqueConstraint('tenant_id', 'file_path', name='uq_file_tenant_path'),
        CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed', 'deleted')", name='ck_file_status'),
    )

class FileVersion(Base, TimestampMixin, TenantMixin):
    """
    File version tracking for maintaining version history.
    """
    __tablename__ = "file_versions"
    
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String(255), ForeignKey("files.id"), nullable=False)
    
    # Version information
    version_number = Column(Integer, nullable=False)
    file_hash = Column(String(64), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    
    # File dates for this version
    file_modified_at = Column(DateTime, nullable=False)
    
    # Processing status for this version
    status = Column(String(50), default="pending", nullable=False)
    processing_started_at = Column(DateTime)
    processing_completed_at = Column(DateTime)
    processing_error = Column(Text)
    
    # Version metadata
    change_summary = Column(Text)
    is_current = Column(Boolean, default=False)
    
    # Backup information
    backup_path = Column(String(1000))
    backup_created_at = Column(DateTime)
    
    # Relationships
    file = relationship("File", back_populates="versions")
    
    __table_args__ = (
        Index('ix_version_file_number', 'file_id', 'version_number'),
        Index('ix_version_tenant_current', 'tenant_id', 'is_current'),
        Index('ix_version_status', 'status'),
        UniqueConstraint('file_id', 'version_number', name='uq_file_version'),
    )

# Document Processing Tables

class DocumentChunk(Base, TimestampMixin, TenantMixin):
    """
    Document chunks for RAG processing.
    """
    __tablename__ = "document_chunks"
    
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String(255), ForeignKey("files.id"), nullable=False)
    
    # Chunk information
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_size = Column(Integer, nullable=False)
    
    # Chunk context
    start_char = Column(Integer)
    end_char = Column(Integer)
    page_number = Column(Integer)
    section_title = Column(String(500))
    
    # Chunk metadata
    chunk_type = Column(String(50), default="text")  # text, header, footer, table, image_caption
    language = Column(String(10), default="en")
    confidence_score = Column(Float)
    
    # Processing metadata
    preprocessing_applied = Column(JSON, default=list)
    chunk_hash = Column(String(64), nullable=False)
    
    # Relationships
    file = relationship("File", back_populates="chunks")
    embeddings = relationship("Embedding", back_populates="chunk", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('ix_chunk_file_index', 'file_id', 'chunk_index'),
        Index('ix_chunk_tenant_type', 'tenant_id', 'chunk_type'),
        Index('ix_chunk_hash', 'chunk_hash'),
        UniqueConstraint('file_id', 'chunk_index', name='uq_file_chunk_index'),
    )

# Embedding Tables

class Embedding(Base, TimestampMixin, TenantMixin):
    """
    Vector embeddings for semantic search.
    """
    __tablename__ = "embeddings"
    
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String(255), ForeignKey("files.id"), nullable=False)
    chunk_id = Column(String(255), ForeignKey("document_chunks.id"), nullable=True)
    
    # Embedding information
    embedding_model = Column(String(255), nullable=False)
    embedding_version = Column(String(50), nullable=False)
    embedding_dimension = Column(Integer, nullable=False)
    
    # Vector store information
    vector_store_type = Column(String(50), nullable=False)  # chroma, faiss, etc.
    vector_store_id = Column(String(255), nullable=False)
    vector_store_collection = Column(String(255), nullable=False)
    
    # Embedding metadata
    embedding_hash = Column(String(64), nullable=False)
    text_hash = Column(String(64), nullable=False)
    
    # Quality metrics
    embedding_quality_score = Column(Float)
    similarity_threshold = Column(Float, default=0.7)
    
    # Processing information
    processing_time_ms = Column(Integer)
    batch_id = Column(String(255))
    
    # Status
    status = Column(String(50), default="active", nullable=False)  # active, deprecated, failed
    
    # Relationships
    tenant = relationship("Tenant", back_populates="embeddings")
    file = relationship("File", back_populates="embeddings")
    chunk = relationship("DocumentChunk", back_populates="embeddings")
    
    __table_args__ = (
        Index('ix_embedding_file', 'file_id'),
        Index('ix_embedding_chunk', 'chunk_id'),
        Index('ix_embedding_tenant_model', 'tenant_id', 'embedding_model'),
        Index('ix_embedding_vector_store', 'vector_store_type', 'vector_store_id'),
        Index('ix_embedding_status', 'status'),
        Index('ix_embedding_batch', 'batch_id'),
        UniqueConstraint('chunk_id', 'embedding_model', 'embedding_version', name='uq_chunk_embedding'),
    )

# Sync Status Tables

class SyncStatus(Base, TimestampMixin, TenantMixin):
    """
    Sync status tracking for folder monitoring.
    """
    __tablename__ = "sync_status"
    
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Sync information
    sync_type = Column(String(50), nullable=False)  # full, delta, file
    sync_trigger = Column(String(50), nullable=False)  # scheduled, manual, file_change
    
    # Folder information
    source_folder = Column(String(1000), nullable=False)
    target_folder = Column(String(1000), nullable=False)
    
    # Sync status
    status = Column(String(50), default="pending", nullable=False)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Sync statistics
    files_found = Column(Integer, default=0)
    files_processed = Column(Integer, default=0)
    files_failed = Column(Integer, default=0)
    files_skipped = Column(Integer, default=0)
    
    # Data transfer
    bytes_processed = Column(Integer, default=0)
    processing_time_ms = Column(Integer)
    
    # Error information
    error_message = Column(Text)
    error_details = Column(JSON)
    
    # Progress tracking
    progress_percentage = Column(Float, default=0.0)
    current_file = Column(String(500))
    
    # Relationships
    tenant = relationship("Tenant", back_populates="sync_status")
    sync_files = relationship("SyncFileStatus", back_populates="sync_status", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('ix_sync_tenant_status', 'tenant_id', 'status'),
        Index('ix_sync_started', 'started_at'),
        Index('ix_sync_type_trigger', 'sync_type', 'sync_trigger'),
        CheckConstraint("status IN ('pending', 'running', 'completed', 'failed', 'cancelled')", name='ck_sync_status'),
        CheckConstraint("sync_type IN ('full', 'delta', 'file')", name='ck_sync_type'),
        CheckConstraint("sync_trigger IN ('scheduled', 'manual', 'file_change')", name='ck_sync_trigger'),
    )

class SyncFileStatus(Base, TimestampMixin, TenantMixin):
    """
    Individual file sync status within a sync operation.
    """
    __tablename__ = "sync_file_status"
    
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    sync_status_id = Column(String(255), ForeignKey("sync_status.id"), nullable=False)
    file_id = Column(String(255), ForeignKey("files.id"), nullable=True)
    
    # File information
    file_path = Column(String(1000), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size_bytes = Column(Integer)
    file_hash = Column(String(64))
    
    # Sync status
    status = Column(String(50), default="pending", nullable=False)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Sync action
    action = Column(String(50), nullable=False)  # create, update, delete, skip, error
    
    # Error information
    error_message = Column(Text)
    error_code = Column(String(50))
    
    # Processing metrics
    processing_time_ms = Column(Integer)
    retry_count = Column(Integer, default=0)
    
    # Relationships
    sync_status = relationship("SyncStatus", back_populates="sync_files")
    file = relationship("File")
    
    __table_args__ = (
        Index('ix_sync_file_status', 'sync_status_id', 'status'),
        Index('ix_sync_file_action', 'action'),
        Index('ix_sync_file_tenant_status', 'tenant_id', 'status'),
        CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed', 'skipped')", name='ck_sync_file_status'),
        CheckConstraint("action IN ('create', 'update', 'delete', 'skip', 'error')", name='ck_sync_file_action'),
    )

# Export all models
__all__ = [
    "Base",
    "TimestampMixin", 
    "TenantMixin",
    "Tenant",
    "File",
    "FileVersion",
    "DocumentChunk", 
    "Embedding",
    "SyncStatus",
    "SyncFileStatus",
    "SyncTaskStatus",
    "SyncMetric",
    "SyncReport",
]
