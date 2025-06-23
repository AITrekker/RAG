"""
Tenant Management Service for the Enterprise RAG Platform.

This module provides the `TenantManager` class, which is the core service
for handling all aspects of a tenant's lifecycle. It is responsible for
creating, configuring, updating, and deleting tenants.

The manager integrates with various other components to ensure that when a
tenant is created, all necessary resources are provisioned correctly across
the different layers of the platform. This includes:
- Interacting with the `TenantIsolationStrategy` to apply the correct data
  segregation policies.
- Using the `TenantFilesystemManager` to create the necessary directory
  structures.
- Setting up collections in the vector store via the `ChromaManager`.
- Managing tenant-specific API keys for secure access.
- Suspending, reactivating, and tracking tenant usage statistics.

Author: Enterprise RAG Platform Team
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone, timedelta
import logging
import hashlib
import secrets
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from uuid import uuid4
from fastapi import HTTPException

from src.backend.models.tenant import Tenant, TenantStatus
from src.backend.core.tenant_isolation import get_tenant_isolation_strategy, TenantTier
from src.backend.utils.vector_store import VectorStoreManager
from src.backend.utils.tenant_filesystem import TenantFileSystemManager

logger = logging.getLogger(__name__)


class TenantManager:
    """
    Core service for managing tenant operations and lifecycle
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.isolation_strategy = get_tenant_isolation_strategy()
        self.filesystem_manager = TenantFileSystemManager()
        self.vector_store_manager = VectorStoreManager()
    
    def create_tenant(
        self,
        tenant_id: str,
        name: str,
        tier: TenantTier = TenantTier.BASIC,
        display_name: Optional[str] = None,
        contact_email: Optional[str] = None,
        contact_name: Optional[str] = None,
        custom_config: Optional[Dict[str, Any]] = None
    ) -> "Tenant":
        """
        Create a new tenant with complete setup
        
        Args:
            tenant_id: Unique tenant identifier
            name: Tenant name
            tier: Service tier
            display_name: Optional display name
            contact_email: Contact email
            contact_name: Contact person name
            custom_config: Custom configuration options
            
        Returns:
            Created tenant instance
        """
        from src.backend.models.tenant import Tenant
        try:
            # Validate tenant_id format
            if not self._validate_tenant_id(tenant_id):
                raise ValueError(f"Invalid tenant_id format: {tenant_id}")
            
            # Check if tenant already exists
            existing = self.db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
            if existing:
                raise ValueError(f"Tenant {tenant_id} already exists")
            
            # Register with isolation strategy
            isolation_config = self.isolation_strategy.register_tenant(tenant_id, tier)
            
            # Create tenant record
            tenant = Tenant(
                tenant_id=tenant_id,
                name=name,
                display_name=display_name or name,
                tier=tier.value,
                isolation_level=isolation_config.isolation_level.value,
                contact_email=contact_email,
                contact_name=contact_name,
                custom_config=custom_config or {},
                status="active",
                activated_at=datetime.now(timezone.utc)
            )
            
            self.db.add(tenant)
            self.db.flush()  # Get the ID
            
            # Create filesystem structure
            try:
                directories = self.filesystem_manager.create_tenant_structure(tenant_id)
                logger.info(f"Created filesystem structure for tenant {tenant_id}")
            except Exception as e:
                logger.error(f"Failed to create filesystem for tenant {tenant_id}: {str(e)}")
                raise
            
            # Create vector store collections
            try:
                vector_config = self.isolation_strategy.get_vector_store_strategy(tenant_id)
                collection_name = f"{vector_config['collection_prefix']}documents"
                self.vector_store_manager.create_collection(collection_name)
                logger.info(f"Created vector store collection for tenant {tenant_id}")
            except Exception as e:
                logger.error(f"Failed to create vector store for tenant {tenant_id}: {str(e)}")
                # Don't fail tenant creation for vector store issues
            
            # Generate initial API key
            try:
                api_key = self.generate_api_key(tenant_id, "default")
                logger.info(f"Generated initial API key for tenant {tenant_id}")
            except Exception as e:
                logger.warning(f"Failed to generate API key for tenant {tenant_id}: {str(e)}")
            
            self.db.commit()
            
            logger.info(f"Successfully created tenant {tenant_id} with tier {tier.value}")
            return tenant
            
        except Exception as e:
            self.db.rollback()
            # Cleanup any partial resources
            self._cleanup_failed_tenant_creation(tenant_id)
            logger.error(f"Failed to create tenant {tenant_id}: {str(e)}")
            raise
    
    def get_tenant(self, tenant_id: str, include_stats: bool = False) -> Optional["Tenant"]:
        """
        Get tenant by ID with optional statistics
        
        Args:
            tenant_id: Unique tenant identifier
            include_stats: Whether to include usage statistics
            
        Returns:
            Tenant instance or None if not found
        """
        from src.backend.models.tenant import Tenant
        tenant = self.db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
        
        if tenant and include_stats:
            # Add current usage statistics
            tenant.current_usage = self.get_tenant_usage_stats(tenant_id)
            tenant.storage_stats = self.filesystem_manager.get_tenant_storage_stats(tenant_id)
        
        return tenant
    
    def list_tenants(
        self,
        status: Optional[str] = None,
        tier: Optional[TenantTier] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List["Tenant"]:
        """
        List tenants with optional filtering
        
        Args:
            status: Filter by status
            tier: Filter by service tier
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            List of tenant instances
        """
        from src.backend.models.tenant import Tenant
        query = self.db.query(Tenant)
        
        if status:
            query = query.filter(Tenant.status == status)
        
        if tier:
            query = query.filter(Tenant.tier == tier.value)
        
        return query.offset(offset).limit(limit).all()
    
    def update_tenant(
        self,
        tenant_id: str,
        updates: Dict[str, Any]
    ) -> "Tenant":
        """
        Update tenant properties
        
        Args:
            tenant_id: Unique tenant identifier
            updates: Dictionary of fields to update
            
        Returns:
            Updated tenant instance
        """
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        # Validate and apply updates
        allowed_fields = {
            'name', 'display_name', 'contact_email', 'contact_name',
            'max_documents', 'max_storage_mb', 'max_api_calls_per_day',
            'max_concurrent_queries', 'custom_config'
        }
        
        for field, value in updates.items():
            if field not in allowed_fields:
                raise ValueError(f"Field {field} cannot be updated")
            setattr(tenant, field, value)
        
        tenant.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        
        logger.info(f"Updated tenant {tenant_id} with fields: {list(updates.keys())}")
        return tenant
    
    def suspend_tenant(self, tenant_id: str, reason: str = "") -> "Tenant":
        """
        Suspend a tenant (temporarily disable)
        
        Args:
            tenant_id: Unique tenant identifier
            reason: Reason for suspension
            
        Returns:
            Updated tenant instance
        """
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        if tenant.status == "suspended":
            return tenant
        
        tenant.status = "suspended"
        tenant.suspended_at = datetime.now(timezone.utc)
        tenant.updated_at = datetime.now(timezone.utc)
        
        # Add suspension reason to custom config
        if not tenant.custom_config:
            tenant.custom_config = {}
        tenant.custom_config['suspension_reason'] = reason
        
        self.db.add(tenant)
        self.db.commit()
        
        logger.info(f"Suspended tenant {tenant_id} for reason: {reason}")
        return tenant

    def reactivate_tenant(self, tenant_id: str) -> "Tenant":
        """
        Reactivate a suspended tenant
        
        Args:
            tenant_id: Unique tenant identifier
            
        Returns:
            Updated tenant instance
        """
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        if tenant.status != "suspended":
            return tenant
        
        tenant.status = "active"
        tenant.activated_at = datetime.now(timezone.utc)
        tenant.suspended_at = None
        tenant.updated_at = datetime.now(timezone.utc)
        
        # Remove suspension reason
        if tenant.custom_config and 'suspension_reason' in tenant.custom_config:
            del tenant.custom_config['suspension_reason']
        
        self.db.add(tenant)
        self.db.commit()
        
        logger.info(f"Reactivated tenant {tenant_id}")
        return tenant

    def delete_tenant(
        self,
        tenant_id: str,
        force: bool = False,
        backup: bool = True
    ) -> Dict[str, Any]:
        """
        Permanently delete a tenant and all associated data
        
        Args:
            tenant_id: Unique tenant identifier
            force: Skip checks and force deletion
            backup: Create a backup before deletion
            
        Returns:
            Deletion status report
        """
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        if tenant.status == "active" and not force:
            raise ValueError("Active tenants must be suspended before deletion. Use force=True to override.")
        
        deletion_results = {
            "tenant_id": tenant_id,
            "status": "pending",
            "backup_path": None,
            "deleted_resources": [],
            "errors": []
        }
        
        # 1. Backup tenant data (optional)
        if backup:
            try:
                backup_info = self.filesystem_manager.archive_tenant_data(tenant_id)
                deletion_results["backup_path"] = backup_info.get("archive_path")
                deletion_results["deleted_resources"].append("filesystem_backup")
                logger.info(f"Created backup for tenant {tenant_id} at {backup_info.get('archive_path')}")
            except Exception as e:
                msg = f"Failed to backup tenant {tenant_id}: {str(e)}"
                deletion_results["errors"].append(msg)
                logger.error(msg)
                if not force:
                    raise
        
        # 2. Delete from vector store
        try:
            vector_config = self.isolation_strategy.get_vector_store_strategy(tenant_id)
            if vector_config['type'] == 'collection_isolation':
                collections = self.vector_store_manager.list_collections()
                prefix = vector_config['collection_prefix']
                for collection in collections:
                    if collection.startswith(prefix):
                        try:
                            self.vector_store_manager.delete_collection(collection)
                            deletion_results["deleted_resources"].append(f"vector_collection:{collection}")
                        except Exception as e:
                            deletion_results["errors"].append(f"Failed to delete collection {collection}: {str(e)}")
            
            logger.info(f"Deleted vector store data for tenant {tenant_id}")
        except Exception as e:
            msg = f"Failed to delete vector store data for tenant {tenant_id}: {str(e)}"
            deletion_results["errors"].append(msg)
            logger.error(msg)
            if not force:
                raise
        
        # 3. Delete from filesystem
        try:
            cleanup_info = self.filesystem_manager.cleanup_tenant_structure(tenant_id, force=True)
            if cleanup_info['success']:
                deletion_results["deleted_resources"].append("filesystem_data")
                logger.info(f"Deleted filesystem data for tenant {tenant_id}")
            else:
                deletion_results["errors"].extend(cleanup_info.get('errors', []))
        except Exception as e:
            msg = f"Failed to delete filesystem data for tenant {tenant_id}: {str(e)}"
            deletion_results["errors"].append(msg)
            logger.error(msg)
            if not force:
                raise
        
        # 4. Delete from database
        try:
            # Delete related records first
            self.db.query(TenantApiKey).filter(TenantApiKey.tenant_id == tenant_id).delete()
            self.db.query(TenantUsageStats).filter(TenantUsageStats.tenant_id == tenant_id).delete()
            self.db.query(TenantDocument).filter(TenantDocument.tenant_id == tenant_id).delete()
            
            # Delete the tenant record
            self.db.delete(tenant)
            self.db.commit()
            
            deletion_results["deleted_resources"].append("database_records")
            logger.info(f"Deleted database records for tenant {tenant_id}")
        except Exception as e:
            self.db.rollback()
            msg = f"Failed to delete database records for tenant {tenant_id}: {str(e)}"
            deletion_results["errors"].append(msg)
            logger.error(msg)
            if not force:
                raise
        
        deletion_results["status"] = "completed"
        logger.info(f"Successfully deleted tenant {tenant_id}")
        
        return deletion_results
    
    def generate_api_key(
        self,
        tenant_id: str,
        key_name: str,
        scopes: Optional[List[str]] = None,
        expires_in_days: Optional[int] = None
    ) -> Tuple[str, "TenantApiKey"]:
        """
        Generate a new API key for a tenant
        
        Args:
            tenant_id: Unique tenant identifier
            key_name: Name for the API key
            scopes: List of permitted operations
            expires_in_days: Days until expiration (None for no expiration)
            
        Returns:
            A tuple of (raw_api_key, TenantApiKey_instance)
        """
        from src.backend.models.tenant import TenantApiKey
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        if tenant.status != "active":
            raise ValueError(f"Cannot generate API key for {tenant.status} tenant")
        
        # Generate secure random key
        raw_key = f"rag_{tenant_id}_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_prefix = raw_key[:12]  # First 12 chars for identification
        
        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
            
        # Create API key record
        api_key = TenantApiKey(
            tenant_id=tenant_id,
            key_name=key_name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            scopes=scopes or ["read", "write", "query"],
            expires_at=expires_at
        )
        
        self.db.add(api_key)
        self.db.commit()
        
        logger.info(f"Generated API key '{key_name}' for tenant {tenant_id}")
        return raw_key, api_key
    
    def validate_api_key(self, raw_key: str) -> Optional["TenantApiKey"]:
        """
        Validate an API key and return the associated tenant key object
        
        Args:
            raw_key: Raw API key string
            
        Returns:
            The TenantApiKey instance if valid, else None
        """
        from src.backend.models.tenant import TenantApiKey
        if not raw_key or ":" not in raw_key:
            return None
        
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        api_key = self.db.query(TenantApiKey).filter(TenantApiKey.key_hash == key_hash).first()
        
        if api_key and api_key.is_valid():
            # Update usage statistics
            api_key.last_used_at = datetime.now(timezone.utc)
            api_key.usage_count += 1
            self.db.commit()
            return api_key
        
        return None
    
    def get_tenant_usage_stats(
        self,
        tenant_id: str,
        period_type: str = "daily",
        limit: int = 30
    ) -> List["TenantUsageStats"]:
        """
        Retrieve usage statistics for a tenant
        
        Args:
            tenant_id: Unique tenant identifier
            period_type: 'daily' or 'monthly'
            limit: Number of periods to retrieve
            
        Returns:
            A list of TenantUsageStats instances
        """
        from src.backend.models.tenant import TenantUsageStats
        query = self.db.query(TenantUsageStats).filter_by(tenant_id=tenant_id)
        
        if period_type == "daily":
            query = query.filter(TenantUsageStats.period_type == "daily")
        elif period_type == "monthly":
            query = query.filter(TenantUsageStats.period_type == "monthly")
        
        return query.order_by(TenantUsageStats.period_start.desc()).limit(limit).all()
    
    def get_tenant_configurations(
        self,
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        Get all configurations for a tenant, merging defaults with custom settings.
        """
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return {}
        
        # In a real application, you would merge tenant.custom_config with global defaults
        return tenant.custom_config or {}

    def update_tenant_configuration(
        self,
        tenant_id: str,
        config_updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update a tenant's custom configuration.
        """
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        if not tenant.custom_config:
            tenant.custom_config = {}
        
        tenant.custom_config.update(config_updates)
        self.db.commit()
        
        return tenant.custom_config

    def _validate_tenant_id(self, tenant_id: str) -> bool:
        """Validate tenant ID format."""
        # Must be lowercase, alphanumeric, with dashes
        return all(c.islower() or c.isdigit() or c == '-' for c in tenant_id)
    
    def _cleanup_failed_tenant_creation(self, tenant_id: str) -> None:
        """Clean up resources from failed tenant creation"""
        try:
            # Try to clean up filesystem
            self.filesystem_manager.cleanup_tenant_structure(tenant_id, force=True)
        except Exception:
            pass
        
        try:
            # Try to clean up vector store
            vector_config = self.isolation_strategy.get_vector_store_strategy(tenant_id)
            if vector_config['type'] == 'collection_isolation':
                collections = self.vector_store_manager.list_collections()
                prefix = vector_config['collection_prefix']
                for collection in collections:
                    if collection.startswith(prefix):
                        try:
                            self.vector_store_manager.delete_collection(collection)
                        except Exception:
                            pass
        except Exception:
            pass

    def get_tenant_uuid(self, tenant_id: str) -> Optional[str]:
        """
        Get the UUID for a tenant given its tenant_id string.
        
        Args:
            tenant_id: The tenant_id string (e.g., "default")
            
        Returns:
            The UUID string of the tenant, or None if not found
        """
        try:
            tenant = self.db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
            if tenant:
                return str(tenant.id)
            return None
        except Exception as e:
            logger.error(f"Error getting tenant UUID for {tenant_id}: {e}")
            return None


def get_tenant_manager(db_session: Session) -> TenantManager:
    """Get tenant manager instance with database session"""
    return TenantManager(db_session)

# Wrapper functions for auth compatibility
def get_tenant_by_api_key(api_key: str) -> Optional[Dict[str, Any]]:
    from .database import SessionLocal
    db = SessionLocal()
    manager = TenantManager(db)
    tenant_info = manager.validate_api_key(api_key)
    if tenant_info:
        return {
            "id": tenant_info.tenant.tenant_id,
            "name": tenant_info.tenant.name,
            "permissions": tenant_info.scopes,
            "key_name": tenant_info.key_name
        }
    return None

def record_api_key_usage(api_key: str):
    # This is handled by validate_api_key
    pass

def create_api_key_for_tenant(tenant_id: str, key_name: str, permissions: List[str]) -> Tuple[str, str]:
    from .database import SessionLocal
    db = SessionLocal()
    manager = TenantManager(db)
    raw_key, api_key_obj = manager.generate_api_key(tenant_id, key_name, permissions)
    return raw_key, api_key_obj.key_hash

def get_api_keys_for_tenant(tenant_id: str) -> List[Dict[str, Any]]:
    from .database import SessionLocal
    db = SessionLocal()
    manager = TenantManager(db)
    keys = db.query(TenantApiKey).filter(TenantApiKey.tenant_id == tenant_id).all()
    return [
        {
            "id": key.id,
            "key_hash": key.key_hash,
            "key_name": key.key_name,
            "permissions": key.scopes,
            "created_at": key.created_at,
            "expires_at": key.expires_at,
            "last_used_at": key.last_used_at,
        } for key in keys
    ]

def delete_api_key_for_tenant(api_key_hash: str) -> bool:
    from .database import SessionLocal
    db = SessionLocal()
    key = db.query(TenantApiKey).filter(TenantApiKey.key_hash == api_key_hash).first()
    if key:
        key.is_active = False
        db.commit()
        return True
    return False

# --- New Singleton and Wrapper Functions ---

_tenant_manager_instance: Optional[TenantManager] = None

def get_tenant_manager_singleton(db_session: Optional[Session] = None) -> TenantManager:
    """Get the singleton instance of the TenantManager."""
    global _tenant_manager_instance
    if _tenant_manager_instance is None:
        if db_session is None:
            from ..models.database import SessionLocal
            db_session = SessionLocal()
        _tenant_manager_instance = TenantManager(db_session)
    return _tenant_manager_instance

def get_tenant_by_api_key(api_key: str) -> Optional[Dict[str, Any]]:
    """Get tenant info by raw API key."""
    manager = get_tenant_manager_singleton()
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    api_key_obj = manager.get_api_key(key_hash)
    
    if api_key_obj and api_key_obj.is_active and (api_key_obj.expires_at is None or api_key_obj.expires_at > datetime.now(timezone.utc)):
        tenant = manager.get_tenant(api_key_obj.tenant_id)
        if tenant and tenant.status == "active":
            return {
                "id": tenant.tenant_id,
                "name": tenant.name,
                "permissions": api_key_obj.permissions,
                "key_name": api_key_obj.key_name
            }
    return None

def record_api_key_usage(api_key: str):
    """Record API key usage."""
    manager = get_tenant_manager_singleton()
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    api_key_obj = manager.get_api_key(key_hash)
    if api_key_obj and api_key_obj.is_active:
        api_key_obj.last_used_at = datetime.now(timezone.utc)
        manager.db.commit()

def create_api_key_for_tenant(tenant_id: str, key_name: str, permissions: List[str]) -> Tuple[str, str]:
    """Create an API key for a tenant."""
    manager = get_tenant_manager_singleton()
    raw_key, api_key_obj = manager.generate_api_key(tenant_id, key_name, permissions)
    return raw_key, api_key_obj.key_hash

def get_api_keys_for_tenant(tenant_id: str) -> List[Dict[str, Any]]:
    """Get all API keys for a tenant."""
    manager = get_tenant_manager_singleton()
    return manager.get_api_keys(tenant_id)

def delete_api_key_for_tenant(api_key_hash: str) -> bool:
    """Delete an API key by its hash."""
    manager = get_tenant_manager_singleton()
    return manager.delete_api_key(api_key_hash) 