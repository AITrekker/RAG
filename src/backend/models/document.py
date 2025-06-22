"""
Document and chunk data models for the Enterprise RAG Platform.

This module defines SQLAlchemy models for document management including:
- Document metadata tracking with tenant isolation
- Document version history management
- Chunk-level metadata and hierarchy tracking
- Document processing status tracking
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Float, 
    ForeignKey, JSON, Index, UniqueConstraint, CheckConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, validates
from sqlalchemy.dialects.postgresql import UUID
import uuid
from src.backend.db.base import Base


class DocumentStatus(Enum):
    """Document processing status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class DocumentType(Enum):
    """Supported document types."""
    PDF = "pdf"
    WORD = "word"
    TEXT = "text"
    MARKDOWN = "markdown"
    HTML = "html"
    UNKNOWN = "unknown"


class ChunkType(Enum):
    """Chunk type enumeration for hierarchy tracking."""
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE = "table"
    CODE = "code"
    QUOTE = "quote"
    FOOTER = "footer"
    UNKNOWN = "unknown"


class Document(Base):
    """
    Document model for storing document metadata and tracking.
    
    Provides comprehensive document management with tenant isolation,
    version history, and processing status tracking.
    """
    __tablename__ = "documents"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # File information
    filename = Column(String(255), nullable=False)
    original_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)  # Size in bytes
    file_hash = Column(String(64), nullable=False)  # SHA-256 hash
    mime_type = Column(String(100))
    document_type = Column(String(20), nullable=False, default=DocumentType.UNKNOWN.value)
    
    # Processing information
    status = Column(String(20), nullable=False, default=DocumentStatus.PENDING.value)
    processing_started_at = Column(DateTime(timezone=True))
    processing_completed_at = Column(DateTime(timezone=True))
    processing_error = Column(Text)
    processing_metadata = Column(JSON)  # Store processing-specific data
    
    # Content information
    title = Column(String(500))
    content_preview = Column(Text)  # First 500 characters
    language = Column(String(10))  # ISO language code
    word_count = Column(Integer)
    page_count = Column(Integer)
    
    # Versioning
    version = Column(Integer, nullable=False, default=1)
    is_current_version = Column(Boolean, nullable=False, default=True)
    parent_document_id = Column(UUID(as_uuid=True), ForeignKey('documents.id'))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    file_modified_at = Column(DateTime(timezone=True), nullable=False)
    last_accessed_at = Column(DateTime(timezone=True))
    
    # Embedding information
    embedding_model = Column(String(100))
    embedding_created_at = Column(DateTime(timezone=True))
    total_chunks = Column(Integer, default=0)
    
    # Relationships
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    parent_document = relationship("Document", remote_side=[id])
    child_versions = relationship("Document", remote_side=[parent_document_id])
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_documents_tenant_status', 'tenant_id', 'status'),
        Index('idx_documents_tenant_filename', 'tenant_id', 'filename'),
        Index('idx_documents_hash', 'file_hash'),
        Index('idx_documents_updated', 'updated_at'),
        UniqueConstraint('tenant_id', 'filename', 'version', name='uq_tenant_filename_version'),
        CheckConstraint('file_size >= 0', name='check_file_size_positive'),
        CheckConstraint('version >= 1', name='check_version_positive'),
    )
    
    @validates('status')
    def validate_status(self, key, status):
        """Validate document status."""
        if status not in [s.value for s in DocumentStatus]:
            raise ValueError(f"Invalid document status: {status}")
        return status
    
    @validates('document_type')
    def validate_document_type(self, key, doc_type):
        """Validate document type."""
        if doc_type not in [t.value for t in DocumentType]:
            raise ValueError(f"Invalid document type: {doc_type}")
        return doc_type
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert document to dictionary representation."""
        return {
            'id': str(self.id),
            'tenant_id': str(self.tenant_id),
            'filename': self.filename,
            'original_path': self.original_path,
            'file_size': self.file_size,
            'file_hash': self.file_hash,
            'mime_type': self.mime_type,
            'document_type': self.document_type,
            'status': self.status,
            'processing_started_at': self.processing_started_at.isoformat() if self.processing_started_at else None,
            'processing_completed_at': self.processing_completed_at.isoformat() if self.processing_completed_at else None,
            'processing_error': self.processing_error,
            'title': self.title,
            'content_preview': self.content_preview,
            'language': self.language,
            'word_count': self.word_count,
            'page_count': self.page_count,
            'version': self.version,
            'is_current_version': self.is_current_version,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'file_modified_at': self.file_modified_at.isoformat(),
            'last_accessed_at': self.last_accessed_at.isoformat() if self.last_accessed_at else None,
            'embedding_model': self.embedding_model,
            'embedding_created_at': self.embedding_created_at.isoformat() if self.embedding_created_at else None,
            'total_chunks': self.total_chunks,
        }


class DocumentChunk(Base):
    """
    Document chunk model for storing processed document segments.
    
    Provides chunk-level metadata preservation and hierarchy tracking
    for efficient retrieval and context reconstruction.
    """
    __tablename__ = "document_chunks"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.id'), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Chunk content and metadata
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)  # SHA-256 of content
    chunk_index = Column(Integer, nullable=False)  # Order within document
    chunk_type = Column(String(20), nullable=False, default=ChunkType.UNKNOWN.value)
    
    # Hierarchy and positioning
    page_number = Column(Integer)
    section_title = Column(String(500))
    parent_chunk_id = Column(UUID(as_uuid=True), ForeignKey('document_chunks.id'))
    hierarchy_level = Column(Integer, default=0)  # 0 = top level, 1 = subsection, etc.
    
    # Content analysis
    token_count = Column(Integer, nullable=False)
    word_count = Column(Integer, nullable=False)
    character_count = Column(Integer, nullable=False)
    language = Column(String(10))
    
    # Chunking strategy metadata
    chunk_method = Column(String(50))  # e.g., "fixed_size", "semantic", "hierarchical"
    chunk_size = Column(Integer)  # Target chunk size used
    overlap_size = Column(Integer)  # Overlap with adjacent chunks
    
    # Embedding information
    embedding_vector = Column(JSON)  # Store embedding as JSON array
    embedding_model = Column(String(100))
    embedding_created_at = Column(DateTime(timezone=True))
    
    # Quality metrics
    coherence_score = Column(Float)  # Semantic coherence score
    completeness_score = Column(Float)  # Content completeness score
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    document = relationship("Document", back_populates="chunks")
    parent_chunk = relationship("DocumentChunk", remote_side=[id])
    child_chunks = relationship("DocumentChunk", remote_side=[parent_chunk_id])
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_chunks_document_index', 'document_id', 'chunk_index'),
        Index('idx_chunks_tenant_type', 'tenant_id', 'chunk_type'),
        Index('idx_chunks_content_hash', 'content_hash'),
        Index('idx_chunks_embedding_model', 'embedding_model'),
        UniqueConstraint('document_id', 'chunk_index', name='uq_document_chunk_index'),
        CheckConstraint('token_count >= 0', name='check_token_count_positive'),
        CheckConstraint('word_count >= 0', name='check_word_count_positive'),
        CheckConstraint('character_count >= 0', name='check_character_count_positive'),
        CheckConstraint('hierarchy_level >= 0', name='check_hierarchy_level_positive'),
    )
    
    @validates('chunk_type')
    def validate_chunk_type(self, key, chunk_type):
        """Validate chunk type."""
        if chunk_type not in [t.value for t in ChunkType]:
            raise ValueError(f"Invalid chunk type: {chunk_type}")
        return chunk_type
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk to dictionary representation."""
        return {
            'id': str(self.id),
            'document_id': str(self.document_id),
            'tenant_id': str(self.tenant_id),
            'content': self.content,
            'content_hash': self.content_hash,
            'chunk_index': self.chunk_index,
            'chunk_type': self.chunk_type,
            'page_number': self.page_number,
            'section_title': self.section_title,
            'parent_chunk_id': str(self.parent_chunk_id) if self.parent_chunk_id else None,
            'hierarchy_level': self.hierarchy_level,
            'token_count': self.token_count,
            'word_count': self.word_count,
            'character_count': self.character_count,
            'language': self.language,
            'chunk_method': self.chunk_method,
            'chunk_size': self.chunk_size,
            'overlap_size': self.overlap_size,
            'embedding_model': self.embedding_model,
            'embedding_created_at': self.embedding_created_at.isoformat() if self.embedding_created_at else None,
            'coherence_score': self.coherence_score,
            'completeness_score': self.completeness_score,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class DocumentProcessingJob(Base):
    """
    Document processing job tracking for async operations.
    
    Tracks the status and progress of document processing operations
    including ingestion, chunking, and embedding generation.
    """
    __tablename__ = "document_processing_jobs"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.id'), nullable=False)
    
    # Job information
    job_type = Column(String(50), nullable=False)  # e.g., "ingestion", "reprocessing", "embedding"
    status = Column(String(20), nullable=False, default="pending")
    priority = Column(Integer, default=5)  # 1 = highest, 10 = lowest
    
    # Progress tracking
    total_steps = Column(Integer, default=1)
    completed_steps = Column(Integer, default=0)
    current_step = Column(String(100))
    progress_percentage = Column(Float, default=0.0)
    
    # Timing information
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    estimated_completion = Column(DateTime(timezone=True))
    
    # Error handling
    error_message = Column(Text)
    error_details = Column(JSON)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # Job metadata
    job_metadata = Column(JSON)  # Store job-specific configuration
    result_metadata = Column(JSON)  # Store processing results
    
    # Relationships
    document = relationship("Document")
    
    # Indexes
    __table_args__ = (
        Index('idx_processing_jobs_tenant_status', 'tenant_id', 'status'),
        Index('idx_processing_jobs_priority', 'priority', 'created_at'),
        Index('idx_processing_jobs_document', 'document_id'),
        CheckConstraint('priority >= 1 AND priority <= 10', name='check_priority_range'),
        CheckConstraint('completed_steps >= 0', name='check_completed_steps_positive'),
        CheckConstraint('total_steps >= 1', name='check_total_steps_positive'),
        CheckConstraint('progress_percentage >= 0.0 AND progress_percentage <= 100.0', name='check_progress_range'),
        CheckConstraint('retry_count >= 0', name='check_retry_count_positive'),
        CheckConstraint('max_retries >= 0', name='check_max_retries_positive'),
    )
    
    def update_progress(self, completed_steps: int, current_step: str = None):
        """Update job progress."""
        self.completed_steps = completed_steps
        self.progress_percentage = (completed_steps / self.total_steps) * 100.0
        if current_step:
            self.current_step = current_step
        self.updated_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary representation."""
        return {
            'id': str(self.id),
            'tenant_id': str(self.tenant_id),
            'document_id': str(self.document_id),
            'job_type': self.job_type,
            'status': self.status,
            'priority': self.priority,
            'total_steps': self.total_steps,
            'completed_steps': self.completed_steps,
            'current_step': self.current_step,
            'progress_percentage': self.progress_percentage,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'estimated_completion': self.estimated_completion.isoformat() if self.estimated_completion else None,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
        }


# Utility functions for document management
def create_document_from_file(
    tenant_id: str,
    file_path: str,
    filename: str,
    file_size: int,
    file_hash: str,
    mime_type: str = None,
    file_modified_at: datetime = None
) -> Document:
    """Create a new document instance from file information."""
    # Determine document type from file extension
    extension = filename.lower().split('.')[-1] if '.' in filename else ''
    doc_type_mapping = {
        'pdf': DocumentType.PDF,
        'doc': DocumentType.WORD,
        'docx': DocumentType.WORD,
        'txt': DocumentType.TEXT,
        'md': DocumentType.MARKDOWN,
        'html': DocumentType.HTML,
        'htm': DocumentType.HTML,
    }
    document_type = doc_type_mapping.get(extension, DocumentType.UNKNOWN)
    
    return Document(
        tenant_id=uuid.UUID(tenant_id),
        filename=filename,
        original_path=file_path,
        file_size=file_size,
        file_hash=file_hash,
        mime_type=mime_type,
        document_type=document_type.value,
        file_modified_at=file_modified_at or datetime.now(timezone.utc),
        status=DocumentStatus.PENDING.value
    )


def create_document_chunk(
    document_id: str,
    tenant_id: str,
    content: str,
    chunk_index: int,
    chunk_method: str = "fixed_size",
    chunk_size: int = None,
    overlap_size: int = None,
    **kwargs
) -> DocumentChunk:
    """Create a new document chunk instance."""
    import hashlib
    
    # Calculate content metrics
    content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
    word_count = len(content.split())
    character_count = len(content)
    
    # Estimate token count (rough approximation: 1 token ≈ 4 characters)
    token_count = max(1, character_count // 4)
    
    return DocumentChunk(
        document_id=uuid.UUID(document_id),
        tenant_id=uuid.UUID(tenant_id),
        content=content,
        content_hash=content_hash,
        chunk_index=chunk_index,
        token_count=token_count,
        word_count=word_count,
        character_count=character_count,
        chunk_method=chunk_method,
        chunk_size=chunk_size,
        overlap_size=overlap_size,
        **kwargs
    ) 