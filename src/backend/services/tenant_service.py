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
        """Get tenant by API key."""
        if not api_key:
            return None
        
        result = await self.db.execute(
            select(Tenant).where(Tenant.api_key == api_key)
        )
        return result.scalar_one_or_none()
    
    async def get_tenant_by_id(self, tenant_id: UUID) -> Optional[Tenant]:
        """Get tenant by ID."""
        result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        return result.scalar_one_or_none()
    
    async def get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        """Get tenant by slug."""
        result = await self.db.execute(
            select(Tenant).where(Tenant.slug == slug)
        )
        return result.scalar_one_or_none()
    
    async def update_api_key_last_used(self, tenant_id: UUID) -> None:
        """Update tenant last used (simplified - no dedicated field)."""
        await self.db.execute(
            update(Tenant)
            .where(Tenant.id == tenant_id)
            .values(updated_at=func.now())
        )
        await self.db.commit()
    
    async def list_tenants(self) -> List[Tenant]:
        """List all tenants."""
        result = await self.db.execute(select(Tenant))
        return result.scalars().all()
    
    async def create_tenant(
        self, 
        name: str
    ) -> Dict[str, Any]:
        """Create a new tenant with API key."""
        # Generate slug from name
        slug = name.lower().replace(" ", "_").replace("-", "_")
        
        # Generate simple API key
        api_key = f"tenant_{slug}_{secrets.token_hex(16)}"
        
        # Create simple tenant
        tenant = Tenant(
            name=name,
            slug=slug,
            api_key=api_key
        )
        
        try:
            self.db.add(tenant)
            await self.db.commit()
            await self.db.refresh(tenant)
        except Exception as e:
            await self.db.rollback()
            raise e
        
        return {
            "id": str(tenant.id),
            "name": tenant.name,
            "slug": tenant.slug,
            "api_key": api_key,
            "created_at": tenant.created_at.isoformat() if tenant.created_at else None
        }
    
    async def update_tenant(
        self,
        tenant_id: UUID,
        name: Optional[str] = None,
        slug: Optional[str] = None
    ) -> Optional[Tenant]:
        """Update tenant details."""
        tenant = await self.get_tenant_by_id(tenant_id)
        if not tenant:
            return None
        
        # Update fields if provided
        if name is not None:
            tenant.name = name
        if slug is not None:
            tenant.slug = slug
        
        await self.db.commit()
        await self.db.refresh(tenant)
        return tenant
    
    async def delete_tenant(self, tenant_id: UUID) -> bool:
        """Delete a tenant."""
        tenant = await self.get_tenant_by_id(tenant_id)
        if not tenant:
            return False
        
        await self.db.delete(tenant)
        await self.db.commit()
        return True
    
    async def update_tenant_api_key(
        self, 
        tenant_id: UUID, 
        api_key: str
    ) -> None:
        """Update tenant API key."""
        await self.db.execute(
            update(Tenant)
            .where(Tenant.id == tenant_id)
            .values(api_key=api_key)
        )
        await self.db.commit()
    
    async def regenerate_api_key(self, tenant_id: UUID) -> str:
        """Regenerate API key for a tenant."""
        tenant = await self.get_tenant_by_id(tenant_id)
        if not tenant:
            raise ValueError("Tenant not found")
        
        # Generate new API key
        api_key = f"tenant_{tenant.slug}_{secrets.token_hex(16)}"
        
        await self.update_tenant_api_key(tenant_id, api_key)
        return api_key
    
    async def revoke_api_key(self, tenant_id: UUID) -> None:
        """Revoke API key for a tenant."""
        await self.db.execute(
            update(Tenant)
            .where(Tenant.id == tenant_id)
            .values(api_key=None)
        )
        await self.db.commit()
    
    async def create_api_key(
        self, 
        tenant_id: UUID
    ) -> str:
        """Create a new API key for a tenant."""
        tenant = await self.get_tenant_by_id(tenant_id)
        if not tenant:
            raise ValueError("Tenant not found")
        
        # Generate new API key
        api_key = f"tenant_{tenant.slug}_{secrets.token_hex(16)}"
        
        await self.update_tenant_api_key(tenant_id, api_key)
        return api_key
    
    async def list_api_keys(self, tenant_id: UUID) -> List[Dict[str, Any]]:
        """List API keys for a tenant."""
        tenant = await self.get_tenant_by_id(tenant_id)
        if not tenant:
            return []
        
        # Return the single API key
        if tenant.api_key:
            return [{
                "id": f"key_{tenant.id}",
                "name": "Default Key",
                "key_prefix": tenant.api_key[:8] + "..." + tenant.api_key[-8:] if len(tenant.api_key) > 16 else tenant.api_key,
                "is_active": True,
                "created_at": tenant.created_at,
                "expires_at": None,
                "last_used": tenant.updated_at
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
            "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
            "last_activity": tenant.updated_at.isoformat() if tenant.updated_at else None,
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