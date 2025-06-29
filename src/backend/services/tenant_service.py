"""
Tenant service for managing tenant operations and authentication
"""

import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from src.backend.models.database import Tenant
from src.backend.database import get_async_db


class TenantService:
    """Service for tenant operations"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    def _generate_api_key(self) -> str:
        """Generate a new API key with tenant prefix."""
        # Generate a random hex string
        key_bytes = secrets.token_bytes(16)
        return key_bytes.hex()
    
    def _generate_api_key_hash(self, api_key: str) -> str:
        """Generate hash for API key storage."""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    async def get_tenant_by_api_key(self, api_key: str) -> Optional[Tenant]:
        """Get tenant by API key (supports both direct and hash validation)."""
        if not api_key:
            return None
        
        # First try direct comparison (current approach)
        result = await self.db.execute(
            select(Tenant).where(
                Tenant.api_key == api_key,
                Tenant.is_active == True
            )
        )
        tenant = result.scalar_one_or_none()
        
        if tenant:
            return tenant
        
        # If not found, try hash validation (for migrated keys)
        api_key_hash = self._generate_api_key_hash(api_key)
        result = await self.db.execute(
            select(Tenant).where(
                Tenant.api_key_hash == api_key_hash,
                Tenant.is_active == True
            )
        )
        return result.scalar_one_or_none()
    
    async def get_tenant_by_id(self, tenant_id: UUID) -> Optional[Tenant]:
        """Get tenant by ID."""
        result = await self.db.execute(
            select(Tenant).where(
                Tenant.id == tenant_id,
                Tenant.is_active == True
            )
        )
        return result.scalar_one_or_none()
    
    async def get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        """Get tenant by slug."""
        result = await self.db.execute(
            select(Tenant).where(
                Tenant.slug == slug,
                Tenant.is_active == True
            )
        )
        return result.scalar_one_or_none()
    
    async def update_api_key_last_used(self, tenant_id: UUID) -> None:
        """Update the last used timestamp for the API key."""
        await self.db.execute(
            update(Tenant)
            .where(Tenant.id == tenant_id)
            .values(api_key_last_used=func.now())
        )
        await self.db.commit()
    
    async def list_tenants(self) -> List[Tenant]:
        """List all active tenants."""
        result = await self.db.execute(
            select(Tenant).where(Tenant.is_active == True)
        )
        return result.scalars().all()
    
    async def create_tenant(
        self, 
        name: str, 
        description: str = "",
        auto_sync: bool = True,
        sync_interval: int = 60
    ) -> Dict[str, Any]:
        """Create a new tenant with API key."""
        # Generate slug from name
        slug = name.lower().replace(" ", "_").replace("-", "_")
        
        # Generate API key
        api_key = f"tenant_{slug}_{secrets.token_hex(16)}"
        api_key_hash = self._generate_api_key_hash(api_key)
        
        # Create tenant
        tenant = Tenant(
            name=name,
            slug=slug,
            description=description,
            auto_sync=auto_sync,
            sync_interval=sync_interval,
            api_key=api_key,
            api_key_hash=api_key_hash,
            api_key_name="Default Key",
            is_active=True
        )
        
        self.db.add(tenant)
        await self.db.commit()
        await self.db.refresh(tenant)
        
        return {
            "id": str(tenant.id),
            "name": tenant.name,
            "slug": tenant.slug,
            "description": tenant.description,
            "api_key": api_key,
            "auto_sync": tenant.auto_sync,
            "sync_interval": tenant.sync_interval,
            "created_at": tenant.created_at.isoformat() if tenant.created_at else None
        }
    
    async def update_tenant(
        self,
        tenant_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        auto_sync: Optional[bool] = None,
        sync_interval: Optional[int] = None,
        status: Optional[str] = None
    ) -> Optional[Tenant]:
        """Update tenant details."""
        tenant = await self.get_tenant_by_id(tenant_id)
        if not tenant:
            return None
        
        # Update fields if provided
        if name is not None:
            tenant.name = name
        if description is not None:
            tenant.description = description
        if auto_sync is not None:
            tenant.auto_sync = auto_sync
        if sync_interval is not None:
            tenant.sync_interval = sync_interval
        if status is not None:
            tenant.status = status
        
        await self.db.commit()
        await self.db.refresh(tenant)
        return tenant
    
    async def delete_tenant(self, tenant_id: UUID) -> bool:
        """Soft delete a tenant."""
        tenant = await self.get_tenant_by_id(tenant_id)
        if not tenant:
            return False
        
        tenant.is_active = False
        tenant.deleted_at = datetime.utcnow()
        await self.db.commit()
        return True
    
    async def update_tenant_api_key(
        self, 
        tenant_id: UUID, 
        api_key: str, 
        api_key_name: str = "Development Key"
    ) -> None:
        """Update tenant API key."""
        api_key_hash = self._generate_api_key_hash(api_key)
        
        await self.db.execute(
            update(Tenant)
            .where(Tenant.id == tenant_id)
            .values(
                api_key=api_key,
                api_key_hash=api_key_hash,
                api_key_name=api_key_name,
                api_key_last_used=None
            )
        )
        await self.db.commit()
    
    async def regenerate_api_key(self, tenant_id: UUID) -> str:
        """Regenerate API key for a tenant."""
        tenant = await self.get_tenant_by_id(tenant_id)
        if not tenant:
            raise ValueError("Tenant not found")
        
        # Generate new API key
        api_key = f"tenant_{tenant.slug}_{secrets.token_hex(16)}"
        
        await self.update_tenant_api_key(tenant_id, api_key, "Regenerated Key")
        return api_key
    
    async def revoke_api_key(self, tenant_id: UUID) -> None:
        """Revoke API key for a tenant."""
        await self.db.execute(
            update(Tenant)
            .where(Tenant.id == tenant_id)
            .values(
                api_key=None,
                api_key_hash=None,
                api_key_name=None,
                api_key_expires_at=None,
                api_key_last_used=None
            )
        )
        await self.db.commit()
    
    async def create_api_key(
        self, 
        tenant_id: UUID, 
        name: str, 
        description: str = "",
        expires_at: Optional[datetime] = None
    ) -> str:
        """Create a new API key for a tenant."""
        tenant = await self.get_tenant_by_id(tenant_id)
        if not tenant:
            raise ValueError("Tenant not found")
        
        # Generate new API key
        api_key = f"tenant_{tenant.slug}_{secrets.token_hex(16)}"
        
        await self.update_tenant_api_key(tenant_id, api_key, name)
        return api_key
    
    async def list_api_keys(self, tenant_id: UUID) -> List[Dict[str, Any]]:
        """List API keys for a tenant."""
        tenant = await self.get_tenant_by_id(tenant_id)
        if not tenant:
            return []
        
        # For now, return the single API key (can be extended for multiple keys)
        if tenant.api_key:
            return [{
                "id": f"key_{tenant.id}",  # Use a different ID format for API keys
                "name": tenant.api_key_name or "Default Key",
                "key_prefix": tenant.api_key[:8] + "..." + tenant.api_key[-8:] if len(tenant.api_key) > 16 else tenant.api_key,
                "is_active": tenant.is_active,
                "created_at": tenant.created_at,  # Return datetime object directly
                "expires_at": tenant.api_key_expires_at,  # Return datetime object directly
                "last_used": tenant.api_key_last_used  # Return datetime object directly
            }]
        
        return []
    
    async def delete_api_key(self, tenant_id: UUID, key_id: str) -> bool:
        """Delete API key for a tenant."""
        # For now, this revokes the API key (can be extended for multiple keys)
        await self.revoke_api_key(tenant_id)
        return True
    
    async def get_tenant_stats(self, tenant_id: UUID) -> Dict[str, Any]:
        """Get tenant statistics."""
        tenant = await self.get_tenant_by_id(tenant_id)
        if not tenant:
            return {}
        
        return {
            "id": str(tenant.id),
            "name": tenant.name,
            "slug": tenant.slug,
            "status": tenant.status,
            "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
            "last_activity": tenant.api_key_last_used.isoformat() if tenant.api_key_last_used else None,
            "auto_sync": tenant.auto_sync,
            "sync_interval": tenant.sync_interval,
            "has_api_key": bool(tenant.api_key)
        }


# Dependency function for FastAPI
async def get_tenant_service() -> TenantService:
    """Dependency to get tenant service with database session"""
    async for db in get_async_db():
        return TenantService(db)


# Global service functions for middleware
async def get_tenant_by_api_key(api_key: str) -> Optional[Tenant]:
    """Global function to get tenant by API key (for middleware)"""
    async for db in get_async_db():
        service = TenantService(db)
        return await service.get_tenant_by_api_key(api_key)


async def update_api_key_usage(tenant_id: UUID) -> None:
    """Global function to update API key usage (for middleware)"""
    async for db in get_async_db():
        service = TenantService(db)
        await service.update_api_key_last_used(tenant_id)