"""
Tenant Management Service for Enterprise RAG Platform

Comprehensive service for managing tenant lifecycle, configuration, and isolation.
Handles tenant creation, updates, deactivation, and resource management.

Author: Enterprise RAG Platform Team
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone, timedelta
import logging
import hashlib
import secrets
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..models.tenant import (
    Tenant, TenantConfiguration, TenantUsageStats, TenantApiKey, TenantDocument,
    create_default_tenant_config
)
from ..core.tenant_isolation import (
    get_tenant_isolation_strategy, TenantTier, IsolationLevel, TenantSecurityError
)
from ..utils.tenant_filesystem import get_tenant_filesystem_manager
from ..utils.vector_store import ChromaManager

logger = logging.getLogger(__name__)


class TenantManager:
    """
    Core service for managing tenant operations and lifecycle
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.isolation_strategy = get_tenant_isolation_strategy()
        self.filesystem_manager = get_tenant_filesystem_manager()
        self.vector_store = ChromaManager()
    
    def create_tenant(
        self,
        tenant_id: str,
        name: str,
        tier: TenantTier = TenantTier.BASIC,
        display_name: Optional[str] = None,
        contact_email: Optional[str] = None,
        contact_name: Optional[str] = None,
        custom_config: Optional[Dict[str, Any]] = None
    ) -> Tenant:
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
            
            # Create default configurations
            default_configs = create_default_tenant_config(tenant_id)
            for config in default_configs:
                self.db.add(config)
            
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
                self.vector_store.create_collection(collection_name)
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
    
    def get_tenant(self, tenant_id: str, include_stats: bool = False) -> Optional[Tenant]:
        """
        Get tenant by ID with optional statistics
        
        Args:
            tenant_id: Unique tenant identifier
            include_stats: Whether to include usage statistics
            
        Returns:
            Tenant instance or None if not found
        """
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
    ) -> List[Tenant]:
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
    ) -> Tenant:
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
    
    def suspend_tenant(self, tenant_id: str, reason: str = "") -> Tenant:
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
        tenant.custom_config['suspended_at'] = tenant.suspended_at.isoformat()
        
        # Deactivate API keys
        api_keys = self.db.query(TenantApiKey).filter(TenantApiKey.tenant_id == tenant_id).all()
        for key in api_keys:
            key.is_active = False
        
        self.db.commit()
        
        logger.warning(f"Suspended tenant {tenant_id}: {reason}")
        return tenant
    
    def reactivate_tenant(self, tenant_id: str) -> Tenant:
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
            raise ValueError(f"Tenant {tenant_id} is not suspended")
        
        tenant.status = "active"
        tenant.suspended_at = None
        tenant.updated_at = datetime.now(timezone.utc)
        
        # Remove suspension info from custom config
        if tenant.custom_config:
            tenant.custom_config.pop('suspension_reason', None)
            tenant.custom_config.pop('suspended_at', None)
        
        # Reactivate API keys (user can disable specific ones if needed)
        api_keys = self.db.query(TenantApiKey).filter(TenantApiKey.tenant_id == tenant_id).all()
        for key in api_keys:
            if not key.is_expired():
                key.is_active = True
        
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
        Delete a tenant and all associated data
        
        Args:
            tenant_id: Unique tenant identifier
            force: Force deletion even if tenant has active resources
            backup: Create backup before deletion
            
        Returns:
            Deletion results
        """
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        deletion_results = {
            'tenant_id': tenant_id,
            'success': False,
            'backup_created': False,
            'backup_path': None,
            'resources_removed': {
                'database_records': 0,
                'filesystem_data': 0,
                'vector_collections': 0,
                'api_keys': 0
            },
            'errors': []
        }
        
        try:
            # Check for active resources
            if not force:
                active_documents = self.db.query(TenantDocument).filter(
                    TenantDocument.tenant_id == tenant_id,
                    TenantDocument.status.in_(['processing', 'pending'])
                ).count()
                
                if active_documents > 0:
                    raise ValueError(f"Tenant has {active_documents} active documents. Use force=True to override.")
            
            # Create backup if requested
            if backup:
                try:
                    backup_result = self.filesystem_manager.archive_tenant_data(tenant_id)
                    if backup_result['success']:
                        deletion_results['backup_created'] = True
                        deletion_results['backup_path'] = backup_result['archive_path']
                except Exception as e:
                    deletion_results['errors'].append(f"Backup failed: {str(e)}")
            
            # Remove database records
            try:
                # Delete related records (cascade should handle most)
                api_keys_count = self.db.query(TenantApiKey).filter(TenantApiKey.tenant_id == tenant_id).count()
                self.db.query(TenantApiKey).filter(TenantApiKey.tenant_id == tenant_id).delete()
                
                configs_count = self.db.query(TenantConfiguration).filter(TenantConfiguration.tenant_id == tenant_id).count()
                self.db.query(TenantConfiguration).filter(TenantConfiguration.tenant_id == tenant_id).delete()
                
                stats_count = self.db.query(TenantUsageStats).filter(TenantUsageStats.tenant_id == tenant_id).count()
                self.db.query(TenantUsageStats).filter(TenantUsageStats.tenant_id == tenant_id).delete()
                
                docs_count = self.db.query(TenantDocument).filter(TenantDocument.tenant_id == tenant_id).count()
                self.db.query(TenantDocument).filter(TenantDocument.tenant_id == tenant_id).delete()
                
                # Delete tenant record
                self.db.delete(tenant)
                self.db.commit()
                
                deletion_results['resources_removed']['database_records'] = (
                    1 + api_keys_count + configs_count + stats_count + docs_count
                )
                
            except Exception as e:
                deletion_results['errors'].append(f"Database cleanup failed: {str(e)}")
                self.db.rollback()
            
            # Remove filesystem data
            try:
                cleanup_result = self.filesystem_manager.cleanup_tenant_structure(tenant_id, force)
                if cleanup_result['success']:
                    deletion_results['resources_removed']['filesystem_data'] = cleanup_result['removed_files']
                else:
                    deletion_results['errors'].extend(cleanup_result['errors'])
            except Exception as e:
                deletion_results['errors'].append(f"Filesystem cleanup failed: {str(e)}")
            
            # Remove vector store collections
            try:
                vector_config = self.isolation_strategy.get_vector_store_strategy(tenant_id)
                if vector_config['type'] == 'separate_instance':
                    # Remove entire instance
                    deletion_results['resources_removed']['vector_collections'] = 1
                else:
                    # Remove collections with tenant prefix
                    collections = self.vector_store.list_collections()
                    prefix = vector_config['collection_prefix']
                    removed_count = 0
                    for collection in collections:
                        if collection.startswith(prefix):
                            try:
                                self.vector_store.delete_collection(collection)
                                removed_count += 1
                            except Exception:
                                pass
                    deletion_results['resources_removed']['vector_collections'] = removed_count
            except Exception as e:
                deletion_results['errors'].append(f"Vector store cleanup failed: {str(e)}")
            
            deletion_results['success'] = len(deletion_results['errors']) == 0
            
            if deletion_results['success']:
                logger.info(f"Successfully deleted tenant {tenant_id}")
            else:
                logger.warning(f"Tenant {tenant_id} deletion completed with errors: {deletion_results['errors']}")
            
        except Exception as e:
            deletion_results['errors'].append(str(e))
            logger.error(f"Failed to delete tenant {tenant_id}: {str(e)}")
        
        return deletion_results
    
    def generate_api_key(
        self,
        tenant_id: str,
        key_name: str,
        scopes: Optional[List[str]] = None,
        expires_in_days: Optional[int] = None
    ) -> Tuple[str, TenantApiKey]:
        """
        Generate a new API key for a tenant
        
        Args:
            tenant_id: Unique tenant identifier
            key_name: Name for the API key
            scopes: List of permitted operations
            expires_in_days: Days until expiration (None for no expiration)
            
        Returns:
            Tuple of (raw_key, api_key_record)
        """
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
    
    def validate_api_key(self, raw_key: str) -> Optional[TenantApiKey]:
        """
        Validate an API key and return the associated record
        
        Args:
            raw_key: Raw API key string
            
        Returns:
            API key record if valid, None otherwise
        """
        if not raw_key.startswith("rag_"):
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
    ) -> List[TenantUsageStats]:
        """
        Get usage statistics for a tenant
        
        Args:
            tenant_id: Unique tenant identifier
            period_type: Type of period (daily, weekly, monthly)
            limit: Maximum number of periods to return
            
        Returns:
            List of usage statistics
        """
        return self.db.query(TenantUsageStats).filter(
            TenantUsageStats.tenant_id == tenant_id,
            TenantUsageStats.period_type == period_type
        ).order_by(TenantUsageStats.period_start.desc()).limit(limit).all()
    
    def update_configuration(
        self,
        tenant_id: str,
        category: str,
        key: str,
        value: str,
        value_type: str = "string"
    ) -> TenantConfiguration:
        """
        Update or create a tenant configuration setting
        
        Args:
            tenant_id: Unique tenant identifier
            category: Configuration category
            key: Configuration key
            value: Configuration value
            value_type: Type of value (string, int, float, bool, json)
            
        Returns:
            Configuration record
        """
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        # Find existing config or create new
        config = self.db.query(TenantConfiguration).filter(
            TenantConfiguration.tenant_id == tenant_id,
            TenantConfiguration.category == category,
            TenantConfiguration.key == key
        ).first()
        
        if config:
            config.value = value
            config.value_type = value_type
            config.updated_at = datetime.now(timezone.utc)
        else:
            config = TenantConfiguration(
                tenant_id=tenant_id,
                category=category,
                key=key,
                value=value,
                value_type=value_type
            )
            self.db.add(config)
        
        self.db.commit()
        
        logger.info(f"Updated configuration {category}.{key} for tenant {tenant_id}")
        return config
    
    def get_tenant_configurations(
        self,
        tenant_id: str,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get tenant configurations as a nested dictionary
        
        Args:
            tenant_id: Unique tenant identifier
            category: Optional category filter
            
        Returns:
            Nested dictionary of configurations
        """
        query = self.db.query(TenantConfiguration).filter(
            TenantConfiguration.tenant_id == tenant_id
        )
        
        if category:
            query = query.filter(TenantConfiguration.category == category)
        
        configs = query.all()
        result = {}
        
        for config in configs:
            if config.category not in result:
                result[config.category] = {}
            result[config.category][config.key] = config.get_typed_value()
        
        return result
    
    def _validate_tenant_id(self, tenant_id: str) -> bool:
        """Validate tenant ID format"""
        import re
        # Allow alphanumeric, hyphens, underscores, 3-64 characters
        pattern = r'^[a-zA-Z0-9_-]{3,64}$'
        return bool(re.match(pattern, tenant_id))
    
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
                collections = self.vector_store.list_collections()
                prefix = vector_config['collection_prefix']
                for collection in collections:
                    if collection.startswith(prefix):
                        try:
                            self.vector_store.delete_collection(collection)
                        except Exception:
                            pass
        except Exception:
            pass


def get_tenant_manager(db_session: Session) -> TenantManager:
    """Get tenant manager instance with database session"""
    return TenantManager(db_session) 