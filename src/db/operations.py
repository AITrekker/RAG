"""
Database operations for HR RAG Pipeline.

This module provides CRUD operations, transaction handling,
and tenant-aware database operations.
"""

from typing import List, Optional, Dict, Any, Union, Type, TypeVar
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import and_, or_, desc, asc, func
from datetime import datetime, timedelta
import logging

from .models import (
    Base, TenantMixin, Tenant, File, FileVersion, DocumentChunk,
    Embedding, SyncStatus, SyncFileStatus
)
from .engine import get_db_session, get_tenant_session, TenantAwareSession

logger = logging.getLogger(__name__)

# Generic type for models
ModelType = TypeVar('ModelType', bound=Base)

class DatabaseOperationError(Exception):
    """Custom exception for database operation errors."""
    pass

class TenantNotFoundError(DatabaseOperationError):
    """Exception raised when tenant is not found."""
    pass

# Base CRUD Operations

class BaseCRUD:
    """Base class for CRUD operations."""
    
    def __init__(self, model: Type[ModelType]):
        self.model = model
    
    def create(self, session: Session, **kwargs) -> ModelType:
        """
        Create a new record.
        
        Args:
            session: Database session
            **kwargs: Field values for the new record
            
        Returns:
            Created model instance
        """
        try:
            instance = self.model(**kwargs)
            session.add(instance)
            session.flush()
            logger.debug(f"Created {self.model.__name__} with ID: {instance.id}")
            return instance
        except IntegrityError as e:
            session.rollback()
            logger.error(f"Integrity error creating {self.model.__name__}: {e}")
            raise DatabaseOperationError(f"Failed to create {self.model.__name__}: {e}")
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error creating {self.model.__name__}: {e}")
            raise DatabaseOperationError(f"Database error: {e}")
    
    def get_by_id(self, session: Session, record_id: str) -> Optional[ModelType]:
        """
        Get record by ID.
        
        Args:
            session: Database session
            record_id: Record ID
            
        Returns:
            Model instance or None
        """
        try:
            return session.query(self.model).filter(self.model.id == record_id).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting {self.model.__name__} by ID {record_id}: {e}")
            raise DatabaseOperationError(f"Database error: {e}")
    
    def get_all(self, session: Session, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """
        Get all records with pagination.
        
        Args:
            session: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of model instances
        """
        try:
            return session.query(self.model).offset(skip).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting all {self.model.__name__}: {e}")
            raise DatabaseOperationError(f"Database error: {e}")
    
    def update(self, session: Session, record_id: str, **kwargs) -> Optional[ModelType]:
        """
        Update record by ID.
        
        Args:
            session: Database session
            record_id: Record ID
            **kwargs: Field values to update
            
        Returns:
            Updated model instance or None
        """
        try:
            instance = self.get_by_id(session, record_id)
            if not instance:
                return None
            
            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            
            session.flush()
            logger.debug(f"Updated {self.model.__name__} with ID: {record_id}")
            return instance
        except IntegrityError as e:
            session.rollback()
            logger.error(f"Integrity error updating {self.model.__name__}: {e}")
            raise DatabaseOperationError(f"Failed to update {self.model.__name__}: {e}")
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error updating {self.model.__name__}: {e}")
            raise DatabaseOperationError(f"Database error: {e}")
    
    def delete(self, session: Session, record_id: str) -> bool:
        """
        Delete record by ID.
        
        Args:
            session: Database session
            record_id: Record ID
            
        Returns:
            True if deleted, False if not found
        """
        try:
            instance = self.get_by_id(session, record_id)
            if not instance:
                return False
            
            session.delete(instance)
            session.flush()
            logger.debug(f"Deleted {self.model.__name__} with ID: {record_id}")
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error deleting {self.model.__name__}: {e}")
            raise DatabaseOperationError(f"Database error: {e}")

class TenantAwareCRUD(BaseCRUD):
    """CRUD operations with tenant awareness."""
    
    def __init__(self, model: Type[ModelType]):
        super().__init__(model)
        if not issubclass(model, TenantMixin):
            raise ValueError(f"Model {model.__name__} must inherit from TenantMixin")
    
    def create_for_tenant(self, session: Session, tenant_id: str, **kwargs) -> ModelType:
        """
        Create record for specific tenant.
        
        Args:
            session: Database session
            tenant_id: Tenant ID
            **kwargs: Field values
            
        Returns:
            Created model instance
        """
        kwargs['tenant_id'] = tenant_id
        return self.create(session, **kwargs)
    
    def get_by_id_for_tenant(self, session: Session, tenant_id: str, record_id: str) -> Optional[ModelType]:
        """
        Get record by ID for specific tenant.
        
        Args:
            session: Database session
            tenant_id: Tenant ID
            record_id: Record ID
            
        Returns:
            Model instance or None
        """
        try:
            return session.query(self.model).filter(
                and_(self.model.id == record_id, self.model.tenant_id == tenant_id)
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting {self.model.__name__} for tenant {tenant_id}: {e}")
            raise DatabaseOperationError(f"Database error: {e}")
    
    def get_all_for_tenant(self, session: Session, tenant_id: str, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """
        Get all records for specific tenant.
        
        Args:
            session: Database session
            tenant_id: Tenant ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of model instances
        """
        try:
            return session.query(self.model).filter(
                self.model.tenant_id == tenant_id
            ).offset(skip).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting all {self.model.__name__} for tenant {tenant_id}: {e}")
            raise DatabaseOperationError(f"Database error: {e}")

# Specific CRUD Classes

class TenantCRUD(BaseCRUD):
    """CRUD operations for Tenant model."""
    
    def __init__(self):
        super().__init__(Tenant)
    
    def get_by_name(self, session: Session, name: str) -> Optional[Tenant]:
        """Get tenant by name."""
        try:
            return session.query(Tenant).filter(Tenant.name == name).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting tenant by name {name}: {e}")
            raise DatabaseOperationError(f"Database error: {e}")
    
    def get_active_tenants(self, session: Session) -> List[Tenant]:
        """Get all active tenants."""
        try:
            return session.query(Tenant).filter(Tenant.is_active == True).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting active tenants: {e}")
            raise DatabaseOperationError(f"Database error: {e}")

class FileCRUD(TenantAwareCRUD):
    """CRUD operations for File model."""
    
    def __init__(self):
        super().__init__(File)
    
    def get_by_path(self, session: Session, tenant_id: str, file_path: str) -> Optional[File]:
        """Get file by path for tenant."""
        try:
            return session.query(File).filter(
                and_(File.tenant_id == tenant_id, File.file_path == file_path)
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting file by path for tenant {tenant_id}: {e}")
            raise DatabaseOperationError(f"Database error: {e}")
    
    def get_by_hash(self, session: Session, tenant_id: str, file_hash: str) -> List[File]:
        """Get files by hash for tenant."""
        try:
            return session.query(File).filter(
                and_(File.tenant_id == tenant_id, File.file_hash == file_hash)
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting files by hash for tenant {tenant_id}: {e}")
            raise DatabaseOperationError(f"Database error: {e}")
    
    def get_by_status(self, session: Session, tenant_id: str, status: str) -> List[File]:
        """Get files by status for tenant."""
        try:
            return session.query(File).filter(
                and_(File.tenant_id == tenant_id, File.status == status)
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting files by status for tenant {tenant_id}: {e}")
            raise DatabaseOperationError(f"Database error: {e}")
    
    def get_pending_files(self, session: Session, tenant_id: str, limit: int = 100) -> List[File]:
        """Get pending files for processing."""
        try:
            return session.query(File).filter(
                and_(File.tenant_id == tenant_id, File.status == "pending")
            ).order_by(File.created_at).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting pending files for tenant {tenant_id}: {e}")
            raise DatabaseOperationError(f"Database error: {e}")
    
    def mark_as_processing(self, session: Session, file_id: str) -> Optional[File]:
        """Mark file as processing."""
        return self.update(session, file_id, 
                         status="processing", 
                         processing_started_at=datetime.utcnow())
    
    def mark_as_completed(self, session: Session, file_id: str) -> Optional[File]:
        """Mark file as completed."""
        return self.update(session, file_id, 
                         status="completed", 
                         processing_completed_at=datetime.utcnow())
    
    def mark_as_failed(self, session: Session, file_id: str, error_message: str) -> Optional[File]:
        """Mark file as failed."""
        return self.update(session, file_id, 
                         status="failed", 
                         processing_error=error_message,
                         processing_completed_at=datetime.utcnow())

# Instantiate CRUD objects
tenant_crud = TenantCRUD()
file_crud = FileCRUD()

# Transaction Management

def execute_with_transaction(operation, *args, **kwargs):
    """
    Execute operation with transaction management.
    
    Args:
        operation: Function to execute
        *args: Arguments to pass to operation
        **kwargs: Keyword arguments to pass to operation
        
    Returns:
        Result of operation
    """
    with get_db_session() as session:
        try:
            result = operation(session, *args, **kwargs)
            session.commit()
            return result
        except Exception as e:
            session.rollback()
            logger.error(f"Transaction failed: {e}")
            raise

def execute_with_tenant_transaction(tenant_id: str, operation, *args, **kwargs):
    """
    Execute operation with tenant-aware transaction management.
    
    Args:
        tenant_id: Tenant ID
        operation: Function to execute
        *args: Arguments to pass to operation
        **kwargs: Keyword arguments to pass to operation
        
    Returns:
        Result of operation
    """
    with get_tenant_session(tenant_id) as session:
        try:
            result = operation(session, *args, **kwargs)
            session.commit()
            return result
        except Exception as e:
            session.rollback()
            logger.error(f"Tenant transaction failed for {tenant_id}: {e}")
            raise

# Export commonly used functions and classes
__all__ = [
    "DatabaseOperationError",
    "TenantNotFoundError",
    "BaseCRUD",
    "TenantAwareCRUD",
    "TenantCRUD",
    "FileCRUD",
    "tenant_crud",
    "file_crud",
    "execute_with_transaction",
    "execute_with_tenant_transaction",
]