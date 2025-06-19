"""
Version tracking manager for Enterprise RAG system.

This module provides comprehensive version tracking for embeddings including
history management, rollback capabilities, analytics, and comparison tools.
"""

import logging
import time
import threading
import json
import hashlib
from typing import Dict, Any, List, Optional, Set, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import uuid
from datetime import datetime, timedelta
import sqlite3

from sqlalchemy import create_engine, Column, String, Integer, Float, Text, Boolean, DateTime, LargeBinary, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.sqlite import JSON

from .metadata_handler import get_metadata_manager, EmbeddingMetadata
from ..config.settings import get_settings

logger = logging.getLogger(__name__)

Base = declarative_base()


class VersionStatus(Enum):
    """Status of document versions."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"
    ROLLBACK_TARGET = "rollback_target"


class ChangeType(Enum):
    """Type of changes made to documents."""
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    RENAMED = "renamed"
    MOVED = "moved"
    CONTENT_MODIFIED = "content_modified"
    METADATA_MODIFIED = "metadata_modified"


class DocumentVersion(Base):
    """SQLAlchemy model for document versions."""
    __tablename__ = 'document_versions'
    
    version_id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    document_id = Column(String, nullable=False, index=True)
    document_path = Column(String, nullable=False)
    document_hash = Column(String, nullable=False)
    
    # Version tracking
    version_number = Column(Integer, nullable=False)
    parent_version_id = Column(String, ForeignKey('document_versions.version_id'))
    status = Column(String, nullable=False, default=VersionStatus.ACTIVE.value)
    
    # Timestamps
    created_at = Column(Float, nullable=False)
    processed_at = Column(Float)
    archived_at = Column(Float)
    
    # Content tracking
    content_size = Column(Integer, default=0)
    content_type = Column(String)
    content_encoding = Column(String)
    content_checksum = Column(String)
    
    # Processing results
    embedding_count = Column(Integer, default=0)
    node_count = Column(Integer, default=0)
    processing_duration = Column(Float, default=0.0)
    
    # Change tracking
    change_type = Column(String, nullable=False, default=ChangeType.CREATED.value)
    change_description = Column(Text)
    change_metadata = Column(JSON)
    
    # Performance metrics
    processing_metrics = Column(JSON)
    quality_score = Column(Float, default=0.0)
    
    # Relationships
    parent_version = relationship("DocumentVersion", remote_side=[version_id])
    embedding_mappings = relationship("EmbeddingVersionMapping", back_populates="version")


class EmbeddingVersionMapping(Base):
    """SQLAlchemy model for mapping embeddings to versions."""
    __tablename__ = 'embedding_version_mappings'
    
    mapping_id = Column(String, primary_key=True)
    version_id = Column(String, ForeignKey('document_versions.version_id'), nullable=False)
    embedding_id = Column(String, nullable=False, index=True)
    tenant_id = Column(String, nullable=False, index=True)
    
    # Mapping metadata
    created_at = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    node_position = Column(Integer, default=0)
    
    # Quality metrics
    embedding_quality = Column(Float, default=0.0)
    semantic_density = Column(Float, default=0.0)
    
    # Relationships
    version = relationship("DocumentVersion", back_populates="embedding_mappings")


class VersionComparison(Base):
    """SQLAlchemy model for version comparisons."""
    __tablename__ = 'version_comparisons'
    
    comparison_id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    document_id = Column(String, nullable=False, index=True)
    
    source_version_id = Column(String, ForeignKey('document_versions.version_id'), nullable=False)
    target_version_id = Column(String, ForeignKey('document_versions.version_id'), nullable=False)
    
    # Comparison results
    similarity_score = Column(Float, default=0.0)
    content_similarity = Column(Float, default=0.0)
    structural_similarity = Column(Float, default=0.0)
    semantic_similarity = Column(Float, default=0.0)
    
    # Change analysis
    changes_detected = Column(JSON)
    change_summary = Column(Text)
    significant_changes = Column(Boolean, default=False)
    
    # Metadata
    compared_at = Column(Float, nullable=False)
    comparison_duration = Column(Float, default=0.0)
    comparison_method = Column(String, default="automatic")


@dataclass
class VersionMetrics:
    """Metrics for a document version."""
    version_id: str
    processing_time: float
    embedding_count: int
    node_count: int
    content_size: int
    quality_score: float
    change_impact: float


@dataclass
class ComparisonResult:
    """Result of version comparison."""
    comparison_id: str
    source_version_id: str
    target_version_id: str
    similarity_score: float
    content_changes: List[Dict[str, Any]]
    embedding_changes: List[Dict[str, Any]]
    significant_changes: bool
    change_summary: str


class TenantAwareVersionManager:
    """
    Comprehensive version tracking manager.
    
    Features:
    - Complete version history tracking
    - Advanced comparison and analytics
    - Rollback capabilities
    - Performance monitoring
    - Quality tracking
    - Tenant isolation
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the version manager.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or get_settings()
        self.version_config = self.config.get("version_tracking", {})
        
        # Database setup
        db_path = self.version_config.get("database_path", "data/versions.db")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self.engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Core components
        self.metadata_manager = get_metadata_manager()
        
        # Settings
        self.max_versions_per_document = self.version_config.get("max_versions_per_document", 50)
        self.auto_archive_days = self.version_config.get("auto_archive_days", 90)
        self.enable_quality_tracking = self.version_config.get("enable_quality_tracking", True)
        self.enable_auto_comparison = self.version_config.get("enable_auto_comparison", True)
        
        # Caching
        self.version_cache: Dict[str, DocumentVersion] = {}
        self.comparison_cache: Dict[str, ComparisonResult] = {}
        self.cache_lock = threading.RLock()
        
        # Statistics
        self.stats = {
            "total_versions": 0,
            "active_versions": 0,
            "archived_versions": 0,
            "total_comparisons": 0,
            "rollback_operations": 0
        }
        self.stats_lock = threading.RLock()
        
        logger.info("Initialized TenantAwareVersionManager")
    
    def create_version(
        self,
        tenant_id: str,
        document_id: str,
        document_path: str,
        metadata: Optional[Dict[str, Any]] = None,
        parent_version_id: Optional[str] = None
    ) -> str:
        """
        Create a new document version.
        
        Args:
            tenant_id: Unique identifier for the tenant
            document_id: Unique identifier for the document
            document_path: Path to the document
            metadata: Optional metadata
            parent_version_id: Parent version ID for tracking changes
            
        Returns:
            str: Version ID
        """
        version_id = f"ver_{tenant_id}_{uuid.uuid4().hex[:8]}"
        
        # Calculate document hash and size
        document_hash, content_size = self._calculate_document_hash(document_path)
        
        # Determine version number
        version_number = self._get_next_version_number(tenant_id, document_id)
        
        # Determine change type
        change_type = ChangeType.CREATED if version_number == 1 else ChangeType.UPDATED
        
        with self.SessionLocal() as session:
            # Create version record
            version = DocumentVersion(
                version_id=version_id,
                tenant_id=tenant_id,
                document_id=document_id,
                document_path=document_path,
                document_hash=document_hash,
                version_number=version_number,
                parent_version_id=parent_version_id,
                status=VersionStatus.ACTIVE.value,
                created_at=time.time(),
                content_size=content_size,
                content_type=self._detect_content_type(document_path),
                content_checksum=document_hash,
                change_type=change_type.value,
                change_metadata=metadata or {}
            )
            
            session.add(version)
            
            # Archive old versions if needed
            self._archive_old_versions(session, tenant_id, document_id)
            
            session.commit()
        
        # Update cache
        with self.cache_lock:
            self.version_cache[version_id] = version
        
        # Update statistics
        with self.stats_lock:
            self.stats["total_versions"] += 1
            self.stats["active_versions"] += 1
        
        logger.info(f"Created version {version_id} for document {document_id}")
        
        # Auto-comparison with previous version
        if self.enable_auto_comparison and parent_version_id:
            try:
                self.compare_versions(parent_version_id, version_id)
            except Exception as e:
                logger.warning(f"Auto-comparison failed: {e}")
        
        return version_id
    
    def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        """Get version information."""
        # Check cache first
        with self.cache_lock:
            if version_id in self.version_cache:
                return self._version_to_dict(self.version_cache[version_id])
        
        with self.SessionLocal() as session:
            version = session.query(DocumentVersion).filter_by(version_id=version_id).first()
            if version:
                # Update cache
                with self.cache_lock:
                    self.version_cache[version_id] = version
                
                return self._version_to_dict(version)
        
        return None
    
    def get_document_versions(
        self,
        tenant_id: str,
        document_id: str,
        include_archived: bool = False
    ) -> List[Dict[str, Any]]:
        """Get all versions for a document."""
        with self.SessionLocal() as session:
            query = session.query(DocumentVersion).filter_by(
                tenant_id=tenant_id,
                document_id=document_id
            )
            
            if not include_archived:
                query = query.filter(DocumentVersion.status != VersionStatus.ARCHIVED.value)
            
            versions = query.order_by(DocumentVersion.version_number.desc()).all()
            
            return [self._version_to_dict(version) for version in versions]
    
    def get_active_version(self, tenant_id: str, document_id: str) -> Optional[Dict[str, Any]]:
        """Get the active version for a document."""
        with self.SessionLocal() as session:
            version = session.query(DocumentVersion).filter_by(
                tenant_id=tenant_id,
                document_id=document_id,
                status=VersionStatus.ACTIVE.value
            ).order_by(DocumentVersion.version_number.desc()).first()
            
            if version:
                return self._version_to_dict(version)
        
        return None
    
    def link_embeddings_to_version(
        self,
        version_id: str,
        embedding_ids: List[str],
        quality_scores: Optional[List[float]] = None
    ) -> bool:
        """Link embeddings to a version."""
        try:
            with self.SessionLocal() as session:
                # Get version
                version = session.query(DocumentVersion).filter_by(version_id=version_id).first()
                if not version:
                    logger.error(f"Version {version_id} not found")
                    return False
                
                # Create embedding mappings
                for i, embedding_id in enumerate(embedding_ids):
                    mapping_id = f"map_{version_id}_{uuid.uuid4().hex[:8]}"
                    quality_score = quality_scores[i] if quality_scores and i < len(quality_scores) else 0.0
                    
                    mapping = EmbeddingVersionMapping(
                        mapping_id=mapping_id,
                        version_id=version_id,
                        embedding_id=embedding_id,
                        tenant_id=version.tenant_id,
                        created_at=time.time(),
                        is_active=True,
                        node_position=i,
                        embedding_quality=quality_score
                    )
                    
                    session.add(mapping)
                
                # Update version embedding count
                version.embedding_count = len(embedding_ids)
                session.commit()
                
                logger.info(f"Linked {len(embedding_ids)} embeddings to version {version_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to link embeddings to version {version_id}: {e}")
            return False
    
    def compare_versions(
        self,
        source_version_id: str,
        target_version_id: str,
        detailed: bool = True
    ) -> Optional[ComparisonResult]:
        """Compare two versions of a document."""
        comparison_id = f"cmp_{source_version_id}_{target_version_id}_{uuid.uuid4().hex[:8]}"
        
        # Check cache
        cache_key = f"{source_version_id}_{target_version_id}"
        with self.cache_lock:
            if cache_key in self.comparison_cache:
                return self.comparison_cache[cache_key]
        
        start_time = time.time()
        
        try:
            with self.SessionLocal() as session:
                # Get versions
                source_version = session.query(DocumentVersion).filter_by(version_id=source_version_id).first()
                target_version = session.query(DocumentVersion).filter_by(version_id=target_version_id).first()
                
                if not source_version or not target_version:
                    logger.error("One or both versions not found for comparison")
                    return None
                
                # Perform comparison
                comparison_result = self._perform_version_comparison(
                    source_version, target_version, detailed
                )
                
                # Store comparison result
                comparison = VersionComparison(
                    comparison_id=comparison_id,
                    tenant_id=source_version.tenant_id,
                    document_id=source_version.document_id,
                    source_version_id=source_version_id,
                    target_version_id=target_version_id,
                    similarity_score=comparison_result.similarity_score,
                    content_similarity=comparison_result.similarity_score,  # Simplified
                    changes_detected=comparison_result.content_changes,
                    change_summary=comparison_result.change_summary,
                    significant_changes=comparison_result.significant_changes,
                    compared_at=time.time(),
                    comparison_duration=time.time() - start_time,
                    comparison_method="automatic"
                )
                
                session.add(comparison)
                session.commit()
                
                # Update cache
                with self.cache_lock:
                    self.comparison_cache[cache_key] = comparison_result
                
                # Update statistics
                with self.stats_lock:
                    self.stats["total_comparisons"] += 1
                
                return comparison_result
                
        except Exception as e:
            logger.error(f"Failed to compare versions {source_version_id} and {target_version_id}: {e}")
            return None
    
    def rollback_to_version(
        self,
        tenant_id: str,
        document_id: str,
        target_version_id: str
    ) -> bool:
        """Rollback a document to a specific version."""
        try:
            with self.SessionLocal() as session:
                # Get target version
                target_version = session.query(DocumentVersion).filter_by(
                    version_id=target_version_id,
                    tenant_id=tenant_id,
                    document_id=document_id
                ).first()
                
                if not target_version:
                    logger.error(f"Target version {target_version_id} not found")
                    return False
                
                # Get current active version
                current_version = session.query(DocumentVersion).filter_by(
                    tenant_id=tenant_id,
                    document_id=document_id,
                    status=VersionStatus.ACTIVE.value
                ).order_by(DocumentVersion.version_number.desc()).first()
                
                if current_version and current_version.version_id == target_version_id:
                    logger.info(f"Document {document_id} is already at target version")
                    return True
                
                # Archive current version
                if current_version:
                    current_version.status = VersionStatus.ARCHIVED.value
                    current_version.archived_at = time.time()
                
                # Set target version as active
                target_version.status = VersionStatus.ACTIVE.value
                
                # Get target version embeddings
                target_mappings = session.query(EmbeddingVersionMapping).filter_by(
                    version_id=target_version_id,
                    is_active=True
                ).all()
                
                # Update embedding mappings
                for mapping in target_mappings:
                    mapping.is_active = True
                
                session.commit()
                
                # Update statistics
                with self.stats_lock:
                    self.stats["rollback_operations"] += 1
                
                logger.info(f"Successfully rolled back document {document_id} to version {target_version_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to rollback document {document_id} to version {target_version_id}: {e}")
            return False
    
    def delete_version(
        self,
        version_id: str,
        soft_delete: bool = True
    ) -> bool:
        """Delete a version (soft or hard delete)."""
        try:
            with self.SessionLocal() as session:
                version = session.query(DocumentVersion).filter_by(version_id=version_id).first()
                if not version:
                    logger.error(f"Version {version_id} not found")
                    return False
                
                if soft_delete:
                    # Soft delete - mark as deleted
                    version.status = VersionStatus.DELETED.value
                    version.archived_at = time.time()
                    
                    # Deactivate embedding mappings
                    mappings = session.query(EmbeddingVersionMapping).filter_by(version_id=version_id).all()
                    for mapping in mappings:
                        mapping.is_active = False
                else:
                    # Hard delete - remove from database
                    # First delete embedding mappings
                    session.query(EmbeddingVersionMapping).filter_by(version_id=version_id).delete()
                    
                    # Delete comparisons
                    session.query(VersionComparison).filter(
                        (VersionComparison.source_version_id == version_id) |
                        (VersionComparison.target_version_id == version_id)
                    ).delete()
                    
                    # Delete version
                    session.delete(version)
                
                session.commit()
                
                # Update cache
                with self.cache_lock:
                    self.version_cache.pop(version_id, None)
                    # Clear related comparison cache
                    keys_to_remove = [key for key in self.comparison_cache.keys() if version_id in key]
                    for key in keys_to_remove:
                        self.comparison_cache.pop(key, None)
                
                logger.info(f"{'Soft' if soft_delete else 'Hard'} deleted version {version_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete version {version_id}: {e}")
            return False
    
    def get_version_analytics(
        self,
        tenant_id: str,
        document_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get analytics for versions."""
        cutoff_time = time.time() - (days * 24 * 3600)
        
        with self.SessionLocal() as session:
            query = session.query(DocumentVersion).filter(
                DocumentVersion.tenant_id == tenant_id,
                DocumentVersion.created_at >= cutoff_time
            )
            
            if document_id:
                query = query.filter(DocumentVersion.document_id == document_id)
            
            versions = query.all()
            
            # Calculate analytics
            total_versions = len(versions)
            total_size = sum(v.content_size for v in versions if v.content_size)
            avg_quality = sum(v.quality_score for v in versions if v.quality_score) / total_versions if total_versions > 0 else 0
            
            # Change type distribution
            change_types = defaultdict(int)
            for version in versions:
                change_types[version.change_type] += 1
            
            # Version frequency by day
            daily_counts = defaultdict(int)
            for version in versions:
                day = datetime.fromtimestamp(version.created_at).strftime('%Y-%m-%d')
                daily_counts[day] += 1
            
            # Top documents by version count
            doc_counts = defaultdict(int)
            for version in versions:
                doc_counts[version.document_id] += 1
            
            top_documents = sorted(doc_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            
            return {
                "total_versions": total_versions,
                "total_content_size": total_size,
                "average_quality_score": avg_quality,
                "change_type_distribution": dict(change_types),
                "daily_version_counts": dict(daily_counts),
                "top_documents_by_versions": top_documents,
                "period_days": days
            }
    
    def _calculate_document_hash(self, document_path: str) -> Tuple[str, int]:
        """Calculate hash and size of document."""
        try:
            with open(document_path, 'rb') as f:
                content = f.read()
                document_hash = hashlib.sha256(content).hexdigest()
                return document_hash, len(content)
        except Exception as e:
            logger.warning(f"Failed to calculate hash for {document_path}: {e}")
            return "", 0
    
    def _detect_content_type(self, document_path: str) -> str:
        """Detect content type from file extension."""
        extension = Path(document_path).suffix.lower()
        type_mapping = {
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword',
            '.txt': 'text/plain',
            '.md': 'text/markdown',
            '.html': 'text/html',
            '.json': 'application/json',
            '.csv': 'text/csv'
        }
        return type_mapping.get(extension, 'application/octet-stream')
    
    def _get_next_version_number(self, tenant_id: str, document_id: str) -> int:
        """Get the next version number for a document."""
        with self.SessionLocal() as session:
            max_version = session.query(DocumentVersion).filter_by(
                tenant_id=tenant_id,
                document_id=document_id
            ).order_by(DocumentVersion.version_number.desc()).first()
            
            return (max_version.version_number + 1) if max_version else 1
    
    def _archive_old_versions(self, session, tenant_id: str, document_id: str):
        """Archive old versions if limit exceeded."""
        versions = session.query(DocumentVersion).filter_by(
            tenant_id=tenant_id,
            document_id=document_id
        ).order_by(DocumentVersion.version_number.desc()).all()
        
        if len(versions) > self.max_versions_per_document:
            # Archive excess versions
            versions_to_archive = versions[self.max_versions_per_document:]
            for version in versions_to_archive:
                if version.status == VersionStatus.ACTIVE.value:
                    version.status = VersionStatus.ARCHIVED.value
                    version.archived_at = time.time()
    
    def _perform_version_comparison(
        self,
        source_version: DocumentVersion,
        target_version: DocumentVersion,
        detailed: bool
    ) -> ComparisonResult:
        """Perform detailed version comparison."""
        # Basic comparison
        content_similarity = 1.0 if source_version.document_hash == target_version.document_hash else 0.0
        
        # Analyze changes
        content_changes = []
        embedding_changes = []
        
        # Content changes
        if source_version.content_size != target_version.content_size:
            content_changes.append({
                "type": "size_change",
                "old_size": source_version.content_size,
                "new_size": target_version.content_size,
                "size_delta": target_version.content_size - source_version.content_size
            })
        
        if source_version.document_hash != target_version.document_hash:
            content_changes.append({
                "type": "content_modified",
                "old_hash": source_version.document_hash,
                "new_hash": target_version.document_hash
            })
        
        # Embedding changes
        if source_version.embedding_count != target_version.embedding_count:
            embedding_changes.append({
                "type": "embedding_count_change",
                "old_count": source_version.embedding_count,
                "new_count": target_version.embedding_count,
                "count_delta": target_version.embedding_count - source_version.embedding_count
            })
        
        # Calculate overall similarity
        similarity_score = content_similarity
        
        # Determine if changes are significant
        significant_changes = (
            content_similarity < 0.8 or
            abs(target_version.content_size - source_version.content_size) > 1000 or
            abs(target_version.embedding_count - source_version.embedding_count) > 5
        )
        
        # Generate change summary
        change_summary = self._generate_change_summary(content_changes, embedding_changes)
        
        return ComparisonResult(
            comparison_id=f"cmp_{uuid.uuid4().hex[:8]}",
            source_version_id=source_version.version_id,
            target_version_id=target_version.version_id,
            similarity_score=similarity_score,
            content_changes=content_changes,
            embedding_changes=embedding_changes,
            significant_changes=significant_changes,
            change_summary=change_summary
        )
    
    def _generate_change_summary(
        self,
        content_changes: List[Dict[str, Any]],
        embedding_changes: List[Dict[str, Any]]
    ) -> str:
        """Generate human-readable change summary."""
        summary_parts = []
        
        for change in content_changes:
            if change["type"] == "size_change":
                delta = change["size_delta"]
                if delta > 0:
                    summary_parts.append(f"Content increased by {delta} bytes")
                else:
                    summary_parts.append(f"Content decreased by {abs(delta)} bytes")
            elif change["type"] == "content_modified":
                summary_parts.append("Content was modified")
        
        for change in embedding_changes:
            if change["type"] == "embedding_count_change":
                delta = change["count_delta"]
                if delta > 0:
                    summary_parts.append(f"Added {delta} embeddings")
                else:
                    summary_parts.append(f"Removed {abs(delta)} embeddings")
        
        if not summary_parts:
            return "No significant changes detected"
        
        return "; ".join(summary_parts)
    
    def _version_to_dict(self, version: DocumentVersion) -> Dict[str, Any]:
        """Convert version object to dictionary."""
        return {
            "version_id": version.version_id,
            "tenant_id": version.tenant_id,
            "document_id": version.document_id,
            "document_path": version.document_path,
            "document_hash": version.document_hash,
            "version_number": version.version_number,
            "parent_version_id": version.parent_version_id,
            "status": version.status,
            "created_at": version.created_at,
            "processed_at": version.processed_at,
            "archived_at": version.archived_at,
            "content_size": version.content_size,
            "content_type": version.content_type,
            "embedding_count": version.embedding_count,
            "node_count": version.node_count,
            "processing_duration": version.processing_duration,
            "change_type": version.change_type,
            "change_description": version.change_description,
            "change_metadata": version.change_metadata,
            "quality_score": version.quality_score
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get version tracking statistics."""
        with self.stats_lock:
            stats = dict(self.stats)
        
        # Add real-time database stats
        with self.SessionLocal() as session:
            stats["total_versions_db"] = session.query(DocumentVersion).count()
            stats["active_versions_db"] = session.query(DocumentVersion).filter_by(
                status=VersionStatus.ACTIVE.value
            ).count()
            stats["archived_versions_db"] = session.query(DocumentVersion).filter_by(
                status=VersionStatus.ARCHIVED.value
            ).count()
            stats["total_comparisons_db"] = session.query(VersionComparison).count()
        
        with self.cache_lock:
            stats["cached_versions"] = len(self.version_cache)
            stats["cached_comparisons"] = len(self.comparison_cache)
        
        return stats
    
    def cleanup_old_data(self, days: int = 90) -> Dict[str, int]:
        """Clean up old version data."""
        cutoff_time = time.time() - (days * 24 * 3600)
        cleanup_stats = {"versions_deleted": 0, "comparisons_deleted": 0}
        
        try:
            with self.SessionLocal() as session:
                # Delete old comparisons
                old_comparisons = session.query(VersionComparison).filter(
                    VersionComparison.compared_at < cutoff_time
                ).all()
                
                for comparison in old_comparisons:
                    session.delete(comparison)
                    cleanup_stats["comparisons_deleted"] += 1
                
                # Archive very old versions
                old_versions = session.query(DocumentVersion).filter(
                    DocumentVersion.created_at < cutoff_time,
                    DocumentVersion.status == VersionStatus.ACTIVE.value
                ).all()
                
                for version in old_versions:
                    # Don't archive if it's the only version of a document
                    version_count = session.query(DocumentVersion).filter_by(
                        tenant_id=version.tenant_id,
                        document_id=version.document_id
                    ).count()
                    
                    if version_count > 1:
                        version.status = VersionStatus.ARCHIVED.value
                        version.archived_at = time.time()
                        cleanup_stats["versions_deleted"] += 1
                
                session.commit()
                
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
        
        return cleanup_stats


# Global version manager instance
_version_manager = None


def get_version_manager() -> TenantAwareVersionManager:
    """Get the global version manager instance."""
    global _version_manager
    if _version_manager is None:
        _version_manager = TenantAwareVersionManager()
    return _version_manager