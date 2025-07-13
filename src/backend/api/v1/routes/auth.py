"""
API Key Management Routes
"""

from fastapi import APIRouter, HTTPException, Depends, status, Request
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID

from src.backend.services.tenant_service import TenantService, get_tenant_service, get_tenant_by_api_key, update_api_key_usage
from src.backend.models.database import Tenant
from src.backend.middleware.api_key_auth import get_current_tenant

router = APIRouter()


class TenantResponse(BaseModel):
    """Tenant response model"""
    id: UUID
    name: str
    slug: str
    plan_tier: str
    storage_limit_gb: int
    max_users: int
    is_active: bool
    api_key_name: Optional[str] = None
    api_key_last_used: Optional[str] = None


class ApiKeyResponse(BaseModel):
    """API key response model"""
    api_key: str
    tenant_slug: str
    api_key_name: str
    message: str


class CreateTenantRequest(BaseModel):
    """Create tenant request"""
    name: str
    description: Optional[str] = None


@router.get("/tenants", response_model=List[TenantResponse])
async def list_tenants(
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """List all tenants (for admin/development use)"""
    tenants = await tenant_service.list_tenants()
    return [
        TenantResponse(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            plan_tier="free",  # Simplified - no plan_tier field
            storage_limit_gb=100,  # Simplified - no storage_limit field
            max_users=10,  # Simplified - no max_users field
            is_active=True,  # Simplified - all tenants active
            api_key_name="Default Key",  # Simplified - no api_key_name field
            api_key_last_used=tenant.updated_at.isoformat() if tenant.updated_at else None
        )
        for tenant in tenants
    ]


@router.post("/tenants", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    request: CreateTenantRequest,
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """Create a new tenant"""
    try:
        tenant_result = await tenant_service.create_tenant(
            name=request.name,
            description=request.description or "",
            auto_sync=True,
            sync_interval=60
        )
        
        # Get the created tenant for response
        tenant = await tenant_service.get_tenant_by_slug(tenant_result["slug"])
        
        return TenantResponse(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            plan_tier="free",  # Simplified - no plan_tier field
            storage_limit_gb=100,  # Simplified - no storage_limit field
            max_users=10,  # Simplified - no max_users field
            is_active=True  # Simplified - all tenants active
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create tenant: {str(e)}"
        )


@router.get("/tenants/{tenant_slug}", response_model=TenantResponse)
async def get_tenant(
    tenant_slug: str,
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """Get tenant by slug"""
    tenant = await tenant_service.get_tenant_by_slug(tenant_slug)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        plan_tier="free",  # Simplified - no plan_tier field
        storage_limit_gb=100,  # Simplified - no storage_limit field
        max_users=10,  # Simplified - no max_users field
        is_active=True,  # Simplified - all tenants active
        api_key_name="Default Key",  # Simplified - no api_key_name field
        api_key_last_used=tenant.updated_at.isoformat() if tenant.updated_at else None
    )


@router.post("/tenants/{tenant_slug}/api-key", response_model=ApiKeyResponse)
async def create_api_key(
    tenant_slug: str,
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """Create/regenerate API key for a tenant"""
    tenant = await tenant_service.get_tenant_by_slug(tenant_slug)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    try:
        api_key = await tenant_service.regenerate_api_key(tenant.id)
        
        return ApiKeyResponse(
            api_key=api_key,
            tenant_slug=tenant.slug,
            api_key_name="Development Key",
            message="API key created successfully"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create API key: {str(e)}"
        )


@router.get("/tenants/{tenant_slug}/api-key")
async def get_api_key_info(
    tenant_slug: str,
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """Get API key info for a tenant (without revealing the key)"""
    tenant = await tenant_service.get_tenant_by_slug(tenant_slug)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    return {
        "tenant_slug": tenant.slug,
        "api_key_name": "Default Key",  # Simplified - no api_key_name field
        "has_api_key": tenant.api_key is not None,
        "api_key_last_used": tenant.updated_at.isoformat() if tenant.updated_at else None,
        "api_key_expires_at": None  # Simplified - no expiration
    }


@router.delete("/tenants/{tenant_slug}/api-key")
async def revoke_api_key(
    tenant_slug: str,
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """Revoke API key for a tenant"""
    tenant = await tenant_service.get_tenant_by_slug(tenant_slug)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    try:
        await tenant_service.revoke_api_key(tenant.id)
        return {"message": f"API key revoked for tenant {tenant.slug}"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke API key: {str(e)}"
        )


@router.get("/tenant", response_model=TenantResponse)
async def get_current_tenant_info(
    tenant: Tenant = Depends(get_current_tenant)
):
    """Get current tenant from API key authentication"""
    # This endpoint requires API key authentication middleware
    # The tenant is injected by the middleware
    
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        plan_tier="free",  # Simplified - no plan_tier field
        storage_limit_gb=100,  # Simplified - no storage_limit field
        max_users=10,  # Simplified - no max_users field
        is_active=True,  # Simplified - all tenants active
        api_key_name="Default Key",  # Simplified - no api_key_name field
        api_key_last_used=tenant.updated_at.isoformat() if tenant.updated_at else None
    )