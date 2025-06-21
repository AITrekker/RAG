"""
Tenant-Scoped Database Queries and Vector Store Partitioning

Utilities for ensuring all database queries and vector store operations
are properly scoped to the current tenant context, preventing data leakage.

Author: Enterprise RAG Platform Team
"""

from typing import Dict, List, Optional, Any, Type, TypeVar, Union
from datetime import datetime, timezone
import logging
from contextlib import contextmanager
from sqlalchemy.orm import Query, Session
from sqlalchemy import and_, or_
from sqlalchemy.inspection import inspect
from dataclasses import dataclass
import uuid

from ..models.tenant import (
    Tenant, TenantConfiguration, TenantUsageStats, TenantApiKey, TenantDocument
)
from ..core.tenant_isolation import get_tenant_isolation_strategy, TenantSecurityError
from ..utils.vector_store import ChromaManager

logger = logging.getLogger(__name__)

# Type variable for generic tenant-scoped operations
T = TypeVar('T')


@dataclass
class TenantContext:
    """Tenant context information."""
    tenant_id: str
    tenant_name: str = ""
    settings: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.settings is None:
            self.settings = {}


class TenantScopedQuery:
    """
    Utilities for creating tenant-scoped database queries
    """
    
    TENANT_AWARE_MODELS = {
        TenantConfiguration: 'tenant_id',
        TenantUsageStats: 'tenant_id',
        TenantApiKey: 'tenant_id',
        TenantDocument: 'tenant_id',
    }
    
    @classmethod
    def apply_tenant_filter(cls, query: Query, model_class: Type[T]) -> Query:
        """
        Apply tenant filtering to a query
        
        Args:
            query: SQLAlchemy query object
            model_class: Model class being queried
            
        Returns:
            Query with tenant filter applied
        """
        if TenantContext._bypass_tenant_filter:
            return query
        
        current_tenant = TenantContext.get_current_tenant()
        if not current_tenant:
            raise TenantSecurityError("No tenant context set for database query")
        
        # Check if model is tenant-aware
        if model_class in cls.TENANT_AWARE_MODELS:
            tenant_column = cls.TENANT_AWARE_MODELS[model_class]
            tenant_attr = getattr(model_class, tenant_column)
            return query.filter(tenant_attr == current_tenant)
        
        # For the main Tenant model, filter by tenant_id
        if model_class == Tenant:
            return query.filter(Tenant.tenant_id == current_tenant)
        
        # If model is not tenant-aware, log warning but don't filter
        logger.warning(f"Model {model_class.__name__} is not tenant-aware")
        return query
    
    @classmethod
    def create_scoped_query(cls, session: Session, model_class: Type[T]) -> Query:
        """
        Create a new tenant-scoped query
        
        Args:
            session: Database session
            model_class: Model class to query
            
        Returns:
            Tenant-scoped query
        """
        query = session.query(model_class)
        return cls.apply_tenant_filter(query, model_class)
    
    @classmethod
    def validate_tenant_ownership(cls, session: Session, model_instance: Any) -> bool:
        """
        Validate that a model instance belongs to the current tenant
        
        Args:
            session: Database session
            model_instance: Model instance to validate
            
        Returns:
            True if valid, raises exception if not
        """
        if TenantContext._bypass_tenant_filter:
            return True
        
        current_tenant = TenantContext.get_current_tenant()
        if not current_tenant:
            raise TenantSecurityError("No tenant context set")
        
        model_class = type(model_instance)
        
        if model_class in cls.TENANT_AWARE_MODELS:
            tenant_column = cls.TENANT_AWARE_MODELS[model_class]
            instance_tenant = getattr(model_instance, tenant_column)
            
            if instance_tenant != current_tenant:
                raise TenantSecurityError(
                    f"Access denied: {model_class.__name__} belongs to tenant {instance_tenant}, "
                    f"current context is {current_tenant}"
                )
        elif model_class == Tenant:
            if model_instance.tenant_id != current_tenant:
                raise TenantSecurityError(
                    f"Access denied: Tenant {model_instance.tenant_id} is not accessible "
                    f"from context {current_tenant}"
                )
        
        return True
    
    @classmethod
    def ensure_tenant_assignment(cls, session: Session, model_instance: Any) -> Any:
        """
        Ensure a new model instance is assigned to the current tenant
        
        Args:
            session: Database session
            model_instance: Model instance to assign
            
        Returns:
            Model instance with tenant assignment
        """
        current_tenant = TenantContext.get_current_tenant()
        if not current_tenant:
            raise TenantSecurityError("No tenant context set for model creation")
        
        model_class = type(model_instance)
        
        if model_class in cls.TENANT_AWARE_MODELS:
            tenant_column = cls.TENANT_AWARE_MODELS[model_class]
            setattr(model_instance, tenant_column, current_tenant)
        
        return model_instance


class TenantScopedVectorStore:
    """
    Tenant-scoped vector store operations
    """
    
    def __init__(self):
        self.vector_store = ChromaManager()
        self.isolation_strategy = get_tenant_isolation_strategy()
    
    def get_tenant_collection_name(self, collection_type: str = "documents") -> str:
        """
        Get the tenant-scoped collection name
        
        Args:
            collection_type: Type of collection (documents, embeddings, etc.)
            
        Returns:
            Tenant-scoped collection name
        """
        current_tenant = TenantContext.get_current_tenant()
        if not current_tenant:
            raise TenantSecurityError("No tenant context set for vector store operation")
        
        vector_config = self.isolation_strategy.get_vector_store_strategy(current_tenant)
        return f"{vector_config['collection_prefix']}{collection_type}"
    
    def create_collection(self, collection_type: str = "documents") -> str:
        """
        Create a tenant-scoped collection
        
        Args:
            collection_type: Type of collection
            
        Returns:
            Collection name
        """
        collection_name = self.get_tenant_collection_name(collection_type)
        self.vector_store.create_collection(collection_name)
        return collection_name
    
    def get_collection(self, collection_type: str = "documents"):
        """
        Get a tenant-scoped collection
        
        Args:
            collection_type: Type of collection
            
        Returns:
            Collection object
        """
        collection_name = self.get_tenant_collection_name(collection_type)
        return self.vector_store.get_collection(collection_name)
    
    def add_documents(
        self,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
        collection_type: str = "documents"
    ) -> None:
        """
        Add documents to tenant-scoped collection
        
        Args:
            documents: List of document texts
            metadatas: Optional metadata for each document
            ids: Optional IDs for each document
            collection_type: Type of collection
        """
        current_tenant = TenantContext.get_current_tenant()
        if not current_tenant:
            raise TenantSecurityError("No tenant context set")
        
        # Ensure metadata includes tenant information
        if metadatas:
            for metadata in metadatas:
                metadata['tenant_id'] = current_tenant
        else:
            metadatas = [{'tenant_id': current_tenant} for _ in documents]
        
        collection_name = self.get_tenant_collection_name(collection_type)
        self.vector_store.add_documents(
            collection_name=collection_name,
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
    
    def similarity_search(
        self,
        query: str,
        n_results: int = 10,
        collection_type: str = "documents",
        additional_filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Perform tenant-scoped similarity search
        
        Args:
            query: Search query
            n_results: Number of results to return
            collection_type: Type of collection
            additional_filters: Additional metadata filters
            
        Returns:
            Search results
        """
        current_tenant = TenantContext.get_current_tenant()
        if not current_tenant:
            raise TenantSecurityError("No tenant context set")
        
        # Add tenant filter to metadata filters
        tenant_filter = {'tenant_id': current_tenant}
        if additional_filters:
            tenant_filter.update(additional_filters)
        
        collection_name = self.get_tenant_collection_name(collection_type)
        return self.vector_store.similarity_search(
            collection_name=collection_name,
            query=query,
            n_results=n_results,
            where=tenant_filter
        )
    
    def delete_documents(
        self,
        ids: List[str],
        collection_type: str = "documents"
    ) -> None:
        """
        Delete documents from tenant-scoped collection
        
        Args:
            ids: Document IDs to delete
            collection_type: Type of collection
        """
        current_tenant = TenantContext.get_current_tenant()
        if not current_tenant:
            raise TenantSecurityError("No tenant context set")
        
        # Verify documents belong to current tenant before deletion
        collection_name = self.get_tenant_collection_name(collection_type)
        
        # Get documents to verify ownership
        try:
            results = self.vector_store.get_documents(
                collection_name=collection_name,
                ids=ids,
                include=['metadatas']
            )
            
            # Verify all documents belong to current tenant
            for metadata in results.get('metadatas', []):
                if metadata.get('tenant_id') != current_tenant:
                    raise TenantSecurityError(
                        f"Cannot delete document: belongs to different tenant"
                    )
            
            # Proceed with deletion
            self.vector_store.delete_documents(collection_name, ids)
            
        except Exception as e:
            logger.error(f"Failed to delete documents for tenant {current_tenant}: {str(e)}")
            raise
    
    def get_collection_stats(self, collection_type: str = "documents") -> Dict[str, Any]:
        """
        Get statistics for tenant-scoped collection
        
        Args:
            collection_type: Type of collection
            
        Returns:
            Collection statistics
        """
        collection_name = self.get_tenant_collection_name(collection_type)
        return self.vector_store.get_collection_stats(collection_name)


# Convenience functions for common operations
def with_tenant_context(tenant_id: str, user_id: Optional[str] = None):
    """
    Decorator to set tenant context for a function
    
    Args:
        tenant_id: Tenant ID to set
        user_id: Optional user ID
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            with TenantContext.scope(tenant_id, user_id):
                return func(*args, **kwargs)
        return wrapper
    return decorator


def get_tenant_scoped_session(session: Session) -> 'TenantScopedSession':
    """
    Get a tenant-scoped database session wrapper
    
    Args:
        session: Original database session
        
    Returns:
        Tenant-scoped session wrapper
    """
    return TenantScopedSession(session)


class TenantScopedSession:
    """
    Database session wrapper that automatically applies tenant filtering
    """
    
    def __init__(self, session: Session):
        self.session = session
        self.scoped_query = TenantScopedQuery()
    
    def query(self, model_class: Type[T]) -> Query:
        """Create a tenant-scoped query"""
        return self.scoped_query.create_scoped_query(self.session, model_class)
    
    def add(self, instance: Any) -> Any:
        """Add an instance with tenant assignment"""
        instance = self.scoped_query.ensure_tenant_assignment(self.session, instance)
        self.session.add(instance)
        return instance
    
    def merge(self, instance: Any) -> Any:
        """Merge an instance after validating tenant ownership"""
        self.scoped_query.validate_tenant_ownership(self.session, instance)
        return self.session.merge(instance)
    
    def delete(self, instance: Any) -> None:
        """Delete an instance after validating tenant ownership"""
        self.scoped_query.validate_tenant_ownership(self.session, instance)
        self.session.delete(instance)
    
    def commit(self) -> None:
        """Commit the session"""
        self.session.commit()
    
    def rollback(self) -> None:
        """Rollback the session"""
        self.session.rollback()
    
    def flush(self) -> None:
        """Flush the session"""
        self.session.flush()
    
    def close(self) -> None:
        """Close the session"""
        self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


# Global instances
tenant_scoped_vector_store = TenantScopedVectorStore()


def get_tenant_scoped_vector_store() -> TenantScopedVectorStore:
    """Get the global tenant-scoped vector store instance"""
    return tenant_scoped_vector_store


# Middleware utilities for API integration
def validate_tenant_context_middleware():
    """
    Middleware to validate tenant context is set
    Can be used with FastAPI or other frameworks
    """
    def middleware(request, call_next):
        # This would be implemented in the API layer
        # to extract tenant info from headers/auth and set context
        pass
    return middleware


def extract_tenant_from_api_key(api_key: str) -> Optional[str]:
    """Extract tenant ID from API key."""
    # Mock implementation - in real app this would decode the API key
    if api_key.startswith("tenant_"):
        return api_key.replace("tenant_", "").split("_")[0]
    return "default"


def get_tenant_database_path(tenant_id: str) -> str:
    """Get tenant-specific database path."""
    return f"./data/tenant_{tenant_id}.db"


def get_tenant_storage_path(tenant_id: str) -> str:
    """Get tenant-specific storage path."""
    return f"./data/tenants/{tenant_id}" 