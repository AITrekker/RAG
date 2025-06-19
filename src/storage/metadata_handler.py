"""
Advanced metadata management for vector stores with comprehensive handling.

This module provides sophisticated metadata operations including indexing,
analytics, filtering, and relationship management with tenant isolation.
"""

import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set, Tuple, Union, Iterator
from pathlib import Path
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, Counter
import pickle
import gzip

import numpy as np
from sqlalchemy import create_engine, Column, String, Integer, Float, Text, Boolean, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func

from .vector_store import EmbeddingMetadata

logger = logging.getLogger(__name__)

Base = declarative_base()


class MetadataEntry(Base):
    """SQLAlchemy model for metadata entries."""
    __tablename__ = 'metadata_entries'
    
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    embedding_id = Column(String, nullable=False, index=True)
    document_id = Column(String, nullable=False, index=True)
    node_id = Column(String, nullable=False, index=True)
    
    # Content fields
    content_hash = Column(String, nullable=False, index=True)
    content_length = Column(Integer, nullable=False)
    
    # Processing fields
    embedding_model = Column(String, nullable=False)
    embedding_version = Column(String, nullable=False)
    processing_timestamp = Column(Float, nullable=False)
    
    # Document fields
    document_path = Column(String, nullable=False)
    document_name = Column(String, nullable=False)
    document_type = Column(String, nullable=False)
    folder_path = Column(String, nullable=False)
    
    # Vector fields
    vector_dimension = Column(Integer, nullable=False)
    embedding_hash = Column(String, nullable=False)
    
    # JSON fields
    custom_metadata = Column(JSON)
    tags = Column(JSON)
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FilterOperator(Enum):
    """Operators for metadata filtering."""
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    GREATER_EQUAL = "ge"
    LESS_EQUAL = "le"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    REGEX = "regex"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"


@dataclass
class MetadataFilter:
    """Filter for metadata queries."""
    field: str
    operator: FilterOperator
    value: Any
    case_sensitive: bool = True


@dataclass
class MetadataIndex:
    """Index definition for metadata fields."""
    field: str
    index_type: str  # "btree", "hash", "gin", "gist"
    unique: bool = False
    partial_condition: Optional[str] = None


class TenantAwareMetadataManager:
    """
    Advanced metadata manager with comprehensive features.
    
    Features:
    - SQLite/PostgreSQL backend support
    - Advanced indexing and querying
    - Tenant isolation
    - Analytics and reporting
    - Relationship tracking
    - Caching and optimization
    - Audit logging
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the metadata manager.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.metadata_config = self.config.get("metadata", {})
        
        # Database setup
        self.db_path = self.metadata_config.get("database_path", "./data/metadata.db")
        self.engine = None
        self.Session = None
        
        # Caching
        self.cache_enabled = self.metadata_config.get("enable_cache", True)
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = self.metadata_config.get("cache_ttl", 300)  # 5 minutes
        self.cache_lock = threading.RLock()
        
        # Indexing
        self.custom_indexes: List[MetadataIndex] = []
        self.index_lock = threading.RLock()
        
        # Statistics
        self.stats: Dict[str, Any] = defaultdict(int)
        self.stats_lock = threading.RLock()
        
        # Initialize database
        self._initialize_database()
        
        logger.info("Initialized TenantAwareMetadataManager")
    
    def _initialize_database(self):
        """Initialize database connection and tables."""
        try:
            # Create data directory
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Create engine
            self.engine = create_engine(
                f"sqlite:///{self.db_path}",
                echo=self.metadata_config.get("debug_sql", False),
                pool_pre_ping=True
            )
            
            # Create tables
            Base.metadata.create_all(self.engine)
            
            # Create session factory
            self.Session = sessionmaker(bind=self.engine)
            
            # Create default indexes
            self._create_default_indexes()
            
            logger.info(f"Database initialized at {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def _create_default_indexes(self):
        """Create default indexes for common queries."""
        default_indexes = [
            ("tenant_id", "btree"),
            ("document_id", "btree"),
            ("document_type", "btree"),
            ("folder_path", "btree"),
            ("processing_timestamp", "btree"),
            ("content_hash", "hash"),
            ("embedding_hash", "hash")
        ]
        
        with self.engine.connect() as conn:
            for field, index_type in default_indexes:
                try:
                    index_name = f"idx_{field}"
                    conn.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON metadata_entries ({field})")
                    logger.debug(f"Created index {index_name}")
                except Exception as e:
                    logger.warning(f"Failed to create index for {field}: {e}")
    
    def add_metadata(self, metadata: EmbeddingMetadata) -> bool:
        """
        Add metadata entry.
        
        Args:
            metadata: Metadata to add
            
        Returns:
            bool: Success status
        """
        try:
            with self.Session() as session:
                # Convert to SQLAlchemy model
                entry = MetadataEntry(
                    id=metadata.embedding_id,
                    tenant_id=metadata.tenant_id,
                    embedding_id=metadata.embedding_id,
                    document_id=metadata.document_id,
                    node_id=metadata.node_id,
                    content_hash=metadata.content_hash,
                    content_length=metadata.content_length,
                    embedding_model=metadata.embedding_model,
                    embedding_version=metadata.embedding_version,
                    processing_timestamp=metadata.processing_timestamp,
                    document_path=metadata.document_path,
                    document_name=metadata.document_name,
                    document_type=metadata.document_type,
                    folder_path=metadata.folder_path,
                    vector_dimension=metadata.vector_dimension,
                    embedding_hash=metadata.embedding_hash,
                    custom_metadata=metadata.custom_metadata,
                    tags=metadata.tags
                )
                
                session.add(entry)
                session.commit()
                
                # Update cache
                self._update_cache(metadata.embedding_id, metadata)
                
                # Update statistics
                with self.stats_lock:
                    self.stats[f"tenant_{metadata.tenant_id}_entries"] += 1
                    self.stats["total_entries"] += 1
                
                logger.debug(f"Added metadata entry {metadata.embedding_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to add metadata: {e}")
            return False
    
    def get_metadata(self, embedding_id: str) -> Optional[EmbeddingMetadata]:
        """
        Get metadata by embedding ID.
        
        Args:
            embedding_id: Embedding identifier
            
        Returns:
            EmbeddingMetadata or None
        """
        # Check cache first
        cached = self._get_from_cache(embedding_id)
        if cached:
            return cached
        
        try:
            with self.Session() as session:
                entry = session.query(MetadataEntry).filter(
                    MetadataEntry.embedding_id == embedding_id
                ).first()
                
                if entry:
                    metadata = self._entry_to_metadata(entry)
                    self._update_cache(embedding_id, metadata)
                    return metadata
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to get metadata {embedding_id}: {e}")
            return None
    
    def query_metadata(
        self,
        tenant_id: str,
        filters: Optional[List[MetadataFilter]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by: Optional[str] = None,
        order_desc: bool = False
    ) -> List[EmbeddingMetadata]:
        """
        Query metadata with advanced filtering.
        
        Args:
            tenant_id: Tenant identifier
            filters: List of filters to apply
            limit: Maximum number of results
            offset: Offset for pagination
            order_by: Field to order by
            order_desc: Descending order flag
            
        Returns:
            List of metadata entries
        """
        try:
            with self.Session() as session:
                query = session.query(MetadataEntry).filter(
                    MetadataEntry.tenant_id == tenant_id
                )
                
                # Apply filters
                if filters:
                    for filter_obj in filters:
                        query = self._apply_filter(query, filter_obj)
                
                # Apply ordering
                if order_by:
                    order_field = getattr(MetadataEntry, order_by, None)
                    if order_field:
                        if order_desc:
                            query = query.order_by(order_field.desc())
                        else:
                            query = query.order_by(order_field)
                
                # Apply pagination
                if offset:
                    query = query.offset(offset)
                if limit:
                    query = query.limit(limit)
                
                entries = query.all()
                results = [self._entry_to_metadata(entry) for entry in entries]
                
                logger.debug(f"Query returned {len(results)} metadata entries")
                return results
                
        except Exception as e:
            logger.error(f"Failed to query metadata: {e}")
            return []
    
    def _apply_filter(self, query, filter_obj: MetadataFilter):
        """Apply a filter to a SQLAlchemy query."""
        field = getattr(MetadataEntry, filter_obj.field, None)
        if not field:
            # Handle custom metadata fields
            if filter_obj.field.startswith("custom_"):
                field_name = filter_obj.field[7:]  # Remove "custom_" prefix
                if filter_obj.operator == FilterOperator.EQUALS:
                    return query.filter(MetadataEntry.custom_metadata[field_name].astext == str(filter_obj.value))
                elif filter_obj.operator == FilterOperator.EXISTS:
                    return query.filter(MetadataEntry.custom_metadata.has_key(field_name))
                # Add more custom metadata operators as needed
            return query
        
        # Apply operator
        if filter_obj.operator == FilterOperator.EQUALS:
            return query.filter(field == filter_obj.value)
        elif filter_obj.operator == FilterOperator.NOT_EQUALS:
            return query.filter(field != filter_obj.value)
        elif filter_obj.operator == FilterOperator.GREATER_THAN:
            return query.filter(field > filter_obj.value)
        elif filter_obj.operator == FilterOperator.LESS_THAN:
            return query.filter(field < filter_obj.value)
        elif filter_obj.operator == FilterOperator.GREATER_EQUAL:
            return query.filter(field >= filter_obj.value)
        elif filter_obj.operator == FilterOperator.LESS_EQUAL:
            return query.filter(field <= filter_obj.value)
        elif filter_obj.operator == FilterOperator.IN:
            return query.filter(field.in_(filter_obj.value))
        elif filter_obj.operator == FilterOperator.NOT_IN:
            return query.filter(~field.in_(filter_obj.value))
        elif filter_obj.operator == FilterOperator.CONTAINS:
            if filter_obj.case_sensitive:
                return query.filter(field.contains(filter_obj.value))
            else:
                return query.filter(field.ilike(f"%{filter_obj.value}%"))
        elif filter_obj.operator == FilterOperator.STARTS_WITH:
            if filter_obj.case_sensitive:
                return query.filter(field.startswith(filter_obj.value))
            else:
                return query.filter(field.ilike(f"{filter_obj.value}%"))
        elif filter_obj.operator == FilterOperator.ENDS_WITH:
            if filter_obj.case_sensitive:
                return query.filter(field.endswith(filter_obj.value))
            else:
                return query.filter(field.ilike(f"%{filter_obj.value}"))
        
        return query
    
    def get_tenant_analytics(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get comprehensive analytics for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Dict[str, Any]: Analytics data
        """
        try:
            with self.Session() as session:
                # Basic counts
                total_entries = session.query(MetadataEntry).filter(
                    MetadataEntry.tenant_id == tenant_id
                ).count()
                
                unique_documents = session.query(MetadataEntry.document_id).filter(
                    MetadataEntry.tenant_id == tenant_id
                ).distinct().count()
                
                # Document type distribution
                doc_types = session.query(
                    MetadataEntry.document_type,
                    func.count(MetadataEntry.id)
                ).filter(
                    MetadataEntry.tenant_id == tenant_id
                ).group_by(MetadataEntry.document_type).all()
                
                # Folder distribution
                folders = session.query(
                    MetadataEntry.folder_path,
                    func.count(MetadataEntry.id)
                ).filter(
                    MetadataEntry.tenant_id == tenant_id
                ).group_by(MetadataEntry.folder_path).all()
                
                # Embedding model distribution
                models = session.query(
                    MetadataEntry.embedding_model,
                    func.count(MetadataEntry.id)
                ).filter(
                    MetadataEntry.tenant_id == tenant_id
                ).group_by(MetadataEntry.embedding_model).all()
                
                # Content statistics
                content_stats = session.query(
                    func.avg(MetadataEntry.content_length).label('avg_length'),
                    func.min(MetadataEntry.content_length).label('min_length'),
                    func.max(MetadataEntry.content_length).label('max_length'),
                    func.sum(MetadataEntry.content_length).label('total_length')
                ).filter(
                    MetadataEntry.tenant_id == tenant_id
                ).first()
                
                # Processing timeline (last 30 days)
                thirty_days_ago = datetime.utcnow() - timedelta(days=30)
                timeline = session.query(
                    func.date(func.datetime(MetadataEntry.processing_timestamp, 'unixepoch')).label('date'),
                    func.count(MetadataEntry.id).label('count')
                ).filter(
                    MetadataEntry.tenant_id == tenant_id,
                    MetadataEntry.processing_timestamp >= thirty_days_ago.timestamp()
                ).group_by(
                    func.date(func.datetime(MetadataEntry.processing_timestamp, 'unixepoch'))
                ).all()
                
                analytics = {
                    "tenant_id": tenant_id,
                    "summary": {
                        "total_entries": total_entries,
                        "unique_documents": unique_documents,
                        "avg_content_length": float(content_stats.avg_length or 0),
                        "min_content_length": content_stats.min_length or 0,
                        "max_content_length": content_stats.max_length or 0,
                        "total_content_size": content_stats.total_length or 0
                    },
                    "distributions": {
                        "document_types": {dt: count for dt, count in doc_types},
                        "folders": {folder: count for folder, count in folders},
                        "embedding_models": {model: count for model, count in models}
                    },
                    "timeline": {
                        str(date): count for date, count in timeline
                    }
                }
                
                return analytics
                
        except Exception as e:
            logger.error(f"Failed to get analytics for tenant {tenant_id}: {e}")
            return {"error": str(e)}
    
    def get_document_relationships(self, tenant_id: str, document_id: str) -> Dict[str, Any]:
        """
        Get relationships for a document.
        
        Args:
            tenant_id: Tenant identifier
            document_id: Document identifier
            
        Returns:
            Dict[str, Any]: Relationship data
        """
        try:
            with self.Session() as session:
                # Get all entries for this document
                entries = session.query(MetadataEntry).filter(
                    MetadataEntry.tenant_id == tenant_id,
                    MetadataEntry.document_id == document_id
                ).all()
                
                if not entries:
                    return {"error": "Document not found"}
                
                doc_path = entries[0].document_path
                folder_path = entries[0].folder_path
                
                # Find related documents in same folder
                folder_docs = session.query(MetadataEntry.document_id).filter(
                    MetadataEntry.tenant_id == tenant_id,
                    MetadataEntry.folder_path == folder_path,
                    MetadataEntry.document_id != document_id
                ).distinct().all()
                
                # Find documents with similar content (same content hash)
                content_hashes = {entry.content_hash for entry in entries}
                similar_docs = session.query(MetadataEntry.document_id).filter(
                    MetadataEntry.tenant_id == tenant_id,
                    MetadataEntry.content_hash.in_(content_hashes),
                    MetadataEntry.document_id != document_id
                ).distinct().all()
                
                # Find documents with shared tags
                all_tags = set()
                for entry in entries:
                    if entry.tags:
                        all_tags.update(entry.tags)
                
                tagged_docs = []
                if all_tags:
                    # This is a simplified approach - in practice, you'd use JSON operators
                    all_entries = session.query(MetadataEntry).filter(
                        MetadataEntry.tenant_id == tenant_id,
                        MetadataEntry.document_id != document_id
                    ).all()
                    
                    for entry in all_entries:
                        if entry.tags and any(tag in all_tags for tag in entry.tags):
                            tagged_docs.append(entry.document_id)
                
                relationships = {
                    "document_id": document_id,
                    "document_path": doc_path,
                    "folder_path": folder_path,
                    "chunks_count": len(entries),
                    "related_documents": {
                        "in_same_folder": [doc[0] for doc in folder_docs],
                        "similar_content": [doc[0] for doc in similar_docs],
                        "shared_tags": list(set(tagged_docs)),
                        "tags": list(all_tags)
                    }
                }
                
                return relationships
                
        except Exception as e:
            logger.error(f"Failed to get relationships for document {document_id}: {e}")
            return {"error": str(e)}
    
    def delete_metadata(self, embedding_id: str) -> bool:
        """
        Delete metadata entry.
        
        Args:
            embedding_id: Embedding identifier
            
        Returns:
            bool: Success status
        """
        try:
            with self.Session() as session:
                entry = session.query(MetadataEntry).filter(
                    MetadataEntry.embedding_id == embedding_id
                ).first()
                
                if entry:
                    tenant_id = entry.tenant_id
                    session.delete(entry)
                    session.commit()
                    
                    # Remove from cache
                    self._remove_from_cache(embedding_id)
                    
                    # Update statistics
                    with self.stats_lock:
                        self.stats[f"tenant_{tenant_id}_entries"] -= 1
                        self.stats["total_entries"] -= 1
                    
                    logger.debug(f"Deleted metadata entry {embedding_id}")
                    return True
                
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete metadata {embedding_id}: {e}")
            return False
    
    def delete_tenant_metadata(self, tenant_id: str) -> bool:
        """
        Delete all metadata for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            bool: Success status
        """
        try:
            with self.Session() as session:
                count = session.query(MetadataEntry).filter(
                    MetadataEntry.tenant_id == tenant_id
                ).count()
                
                session.query(MetadataEntry).filter(
                    MetadataEntry.tenant_id == tenant_id
                ).delete()
                
                session.commit()
                
                # Clear cache for tenant
                self._clear_tenant_cache(tenant_id)
                
                # Update statistics
                with self.stats_lock:
                    self.stats[f"tenant_{tenant_id}_entries"] = 0
                    self.stats["total_entries"] -= count
                
                logger.info(f"Deleted {count} metadata entries for tenant {tenant_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete metadata for tenant {tenant_id}: {e}")
            return False
    
    def _entry_to_metadata(self, entry: MetadataEntry) -> EmbeddingMetadata:
        """Convert SQLAlchemy entry to EmbeddingMetadata."""
        return EmbeddingMetadata(
            embedding_id=entry.embedding_id,
            tenant_id=entry.tenant_id,
            document_id=entry.document_id,
            node_id=entry.node_id,
            text_content="",  # Not stored in DB for space reasons
            content_hash=entry.content_hash,
            content_length=entry.content_length,
            embedding_model=entry.embedding_model,
            embedding_version=entry.embedding_version,
            processing_timestamp=entry.processing_timestamp,
            document_path=entry.document_path,
            document_name=entry.document_name,
            document_type=entry.document_type,
            folder_path=entry.folder_path,
            vector_dimension=entry.vector_dimension,
            embedding_hash=entry.embedding_hash,
            custom_metadata=entry.custom_metadata or {},
            tags=entry.tags or []
        )
    
    def _update_cache(self, key: str, metadata: EmbeddingMetadata):
        """Update cache entry."""
        if not self.cache_enabled:
            return
        
        with self.cache_lock:
            self.cache[key] = {
                "metadata": metadata,
                "timestamp": time.time()
            }
    
    def _get_from_cache(self, key: str) -> Optional[EmbeddingMetadata]:
        """Get from cache if valid."""
        if not self.cache_enabled:
            return None
        
        with self.cache_lock:
            entry = self.cache.get(key)
            if entry and (time.time() - entry["timestamp"]) < self.cache_ttl:
                return entry["metadata"]
            elif entry:
                del self.cache[key]
        
        return None
    
    def _remove_from_cache(self, key: str):
        """Remove from cache."""
        with self.cache_lock:
            if key in self.cache:
                del self.cache[key]
    
    def _clear_tenant_cache(self, tenant_id: str):
        """Clear cache for a tenant."""
        with self.cache_lock:
            keys_to_remove = []
            for key, entry in self.cache.items():
                if entry["metadata"].tenant_id == tenant_id:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self.cache[key]
    
    def create_custom_index(self, field: str, index_type: str = "btree") -> bool:
        """
        Create custom index for better query performance.
        
        Args:
            field: Field name to index
            index_type: Type of index
            
        Returns:
            bool: Success status
        """
        try:
            with self.index_lock:
                index_name = f"idx_custom_{field}"
                
                with self.engine.connect() as conn:
                    conn.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON metadata_entries ({field})")
                
                self.custom_indexes.append(MetadataIndex(
                    field=field,
                    index_type=index_type
                ))
                
                logger.info(f"Created custom index {index_name}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to create index for {field}: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get manager statistics."""
        with self.stats_lock:
            stats = dict(self.stats)
        
        # Add cache statistics
        with self.cache_lock:
            stats["cache_size"] = len(self.cache)
            stats["cache_enabled"] = self.cache_enabled
        
        # Add database statistics
        try:
            with self.Session() as session:
                stats["total_db_entries"] = session.query(MetadataEntry).count()
                stats["unique_tenants"] = session.query(MetadataEntry.tenant_id).distinct().count()
        except Exception:
            pass
        
        return stats
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        try:
            with self.Session() as session:
                # Test database connection
                session.execute("SELECT 1")
                
                health = {
                    "status": "healthy",
                    "database_path": str(self.db_path),
                    "cache_enabled": self.cache_enabled,
                    "custom_indexes": len(self.custom_indexes)
                }
                
                return health
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "database_path": str(self.db_path)
            }


# Global metadata manager instance
_metadata_manager = None


def get_metadata_manager() -> TenantAwareMetadataManager:
    """Get the global metadata manager instance."""
    global _metadata_manager
    if _metadata_manager is None:
        _metadata_manager = TenantAwareMetadataManager()
    return _metadata_manager