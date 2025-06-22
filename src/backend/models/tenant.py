"""
Tenant Data Models for the Enterprise RAG Platform.

This module defines the SQLAlchemy models for the multi-tenant architecture
of the platform. It includes models for:
- `Tenant`: The central model representing a customer or organization. It holds
  configuration details, status, resource limits, and contact information.
- `TenantUsageStats`: Tracks resource consumption and performance metrics for
  each tenant over specific time periods (e.g., daily, monthly).
- `TenantApiKey`: Manages the API keys associated with a tenant, including their
  hashed values, scopes, status, and usage information for authentication.
- `TenantDocument`: A metadata model that links documents to a specific tenant,
  ensuring data isolation and tracking processing status.

These models are essential for enforcing tenant separation, managing resources,
and providing secure, isolated access to the platform's features.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column, String, DateTime, Boolean, Integer, Text, JSON, ForeignKey, 
    Index, UniqueConstraint, func
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.dialects.postgresql import UUID
import uuid
from enum import Enum
from pydantic import BaseModel, Field
from src.backend.db.base import Base
from ..core.tenant_isolation import TenantTier, IsolationLevel

# This will be removed
# Base = declarative_base()


class TenantStatus(str, Enum):
    """Tenant status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"


class Tenant(Base):
    """
    Core tenant model representing an organization or customer
    """
    __tablename__ = "tenants"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)
    
    # Tenant classification
    tier = Column(String(20), nullable=False, default=TenantTier.BASIC.value)
    isolation_level = Column(String(20), nullable=False, default=IsolationLevel.LOGICAL.value)
    
    # Status and lifecycle
    status = Column(String(20), nullable=False, default="active")  # active, suspended, inactive
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    activated_at = Column(DateTime(timezone=True), nullable=True)
    suspended_at = Column(DateTime(timezone=True), nullable=True)
    
    # Resource limits and quotas
    max_documents = Column(Integer, nullable=False, default=1000)
    max_storage_mb = Column(Integer, nullable=False, default=5000)  # 5GB default
    max_api_calls_per_day = Column(Integer, nullable=False, default=10000)
    max_concurrent_queries = Column(Integer, nullable=False, default=10)
    
    # Contact and billing information
    contact_email = Column(String(255), nullable=True)
    contact_name = Column(String(255), nullable=True)
    billing_email = Column(String(255), nullable=True)
    
    # Custom configuration
    custom_config = Column(JSON, nullable=True, default=dict)
    
    # Relationships
    usage_stats = relationship("TenantUsageStats", back_populates="tenant", cascade="all, delete-orphan")
    api_keys = relationship("TenantApiKey", back_populates="tenant", cascade="all, delete-orphan")
    documents = relationship("TenantDocument", back_populates="tenant", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_tenant_status', 'status'),
        Index('idx_tenant_tier', 'tier'),
        Index('idx_tenant_created', 'created_at'),
    )
    
    @validates('tier')
    def validate_tier(self, key, value):
        if value not in [tier.value for tier in TenantTier]:
            raise ValueError(f"Invalid tier: {value}")
        return value
    
    @validates('isolation_level')
    def validate_isolation_level(self, key, value):
        if value not in [level.value for level in IsolationLevel]:
            raise ValueError(f"Invalid isolation level: {value}")
        return value
    
    @validates('status')
    def validate_status(self, key, value):
        valid_statuses = ['active', 'suspended', 'inactive', 'pending']
        if value not in valid_statuses:
            raise ValueError(f"Invalid status: {value}. Must be one of {valid_statuses}")
        return value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tenant to dictionary representation"""
        return {
            'id': str(self.id),
            'tenant_id': self.tenant_id,
            'name': self.name,
            'display_name': self.display_name,
            'tier': self.tier,
            'isolation_level': self.isolation_level,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'max_documents': self.max_documents,
            'max_storage_mb': self.max_storage_mb,
            'max_api_calls_per_day': self.max_api_calls_per_day,
            'max_concurrent_queries': self.max_concurrent_queries,
            'contact_email': self.contact_email,
            'contact_name': self.contact_name,
            'custom_config': self.custom_config
        }


class TenantUsageStats(Base):
    """
    Tenant usage statistics and metrics
    """
    __tablename__ = "tenant_usage_stats"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(64), ForeignKey('tenants.tenant_id'), nullable=False)
    
    # Time period
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    period_type = Column(String(20), nullable=False)  # daily, weekly, monthly
    
    # Usage metrics
    documents_processed = Column(Integer, nullable=False, default=0)
    embeddings_generated = Column(Integer, nullable=False, default=0)
    queries_processed = Column(Integer, nullable=False, default=0)
    api_calls_made = Column(Integer, nullable=False, default=0)
    storage_used_mb = Column(Integer, nullable=False, default=0)
    
    # Performance metrics
    avg_query_time_ms = Column(Integer, nullable=True)
    avg_embedding_time_ms = Column(Integer, nullable=True)
    error_count = Column(Integer, nullable=False, default=0)
    success_rate = Column(Integer, nullable=False, default=100)  # Percentage
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    tenant = relationship("Tenant", back_populates="usage_stats")
    
    # Indexes
    __table_args__ = (
        Index('idx_usage_stats_period', 'tenant_id', 'period_type', 'period_start'),
        UniqueConstraint('tenant_id', 'period_type', 'period_start', name='uq_tenant_usage_period'),
    )


class TenantApiKey(Base):
    """
    API keys for tenant authentication
    """
    __tablename__ = "tenant_api_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(64), ForeignKey('tenants.tenant_id'), nullable=False)
    
    # Key information
    key_name = Column(String(100), nullable=False)
    key_hash = Column(String(256), nullable=False, unique=True)  # Hashed API key
    key_prefix = Column(String(20), nullable=False)  # First few chars for identification
    
    # Permissions and scope
    scopes = Column(JSON, nullable=False, default=list)  # List of permitted operations
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Usage tracking
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    usage_count = Column(Integer, nullable=False, default=0)
    
    # Expiration
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    tenant = relationship("Tenant", back_populates="api_keys")
    
    # Indexes
    __table_args__ = (
        Index('idx_api_key_tenant', 'tenant_id'),
        Index('idx_api_key_hash', 'key_hash'),
        Index('idx_api_key_active', 'is_active'),
    )
    
    def is_expired(self) -> bool:
        """Check if the API key has expired"""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if the API key is valid and active"""
        return self.is_active and not self.is_expired()


class TenantDocument(Base):
    """
    Document metadata for tenant isolation
    """
    __tablename__ = "tenant_documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(64), ForeignKey('tenants.tenant_id'), nullable=False)
    
    # Document identification
    document_id = Column(String(255), nullable=False)
    filename = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_hash = Column(String(64), nullable=True)  # SHA-256 hash
    
    # Document metadata
    file_size_bytes = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=True)
    document_type = Column(String(50), nullable=True)  # pdf, docx, txt, etc.
    
    # Processing status
    status = Column(String(20), nullable=False, default="pending")  # pending, processing, completed, failed
    processed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Embedding information
    embedding_model = Column(String(100), nullable=True)
    chunk_count = Column(Integer, nullable=False, default=0)
    vector_store_id = Column(String(255), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    tenant = relationship("Tenant", back_populates="documents")

    # Indexes
    __table_args__ = (
        Index('idx_tenant_document_id', 'tenant_id', 'document_id'),
        UniqueConstraint('tenant_id', 'document_id', name='uq_tenant_document_id'),
    ) 