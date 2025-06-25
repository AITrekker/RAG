"""
Tenant API routes for the Enterprise RAG Platform.

This module provides endpoints for tenant management and API key operations.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer
import logging

from src.backend.core.tenant_service import TenantService, get_tenant_service
from src.backend.models.api_models import (
    TenantResponse, 
    TenantListResponse, 
    ApiKeyResponse,
    ApiKeyCreateResponse,
    ApiKeyCreateRequest
)
from src.backend.middleware.auth import verify_api_key

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()

@router.get("/", response_model=TenantListResponse)
async def list_tenants(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Number of tenants per page"),
    _: str = Depends(verify_api_key),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    List all tenants with pagination.
    
    Args:
        page: Page number for pagination
        page_size: Number of tenants per page
        _: API key verification (required)
        tenant_service: Tenant service
        
    Returns:
        TenantListResponse: List of tenants with pagination
        
    Raises:
        HTTPException: If there's an error listing tenants
    """
    try:
        logger.info(f"Listing tenants (page {page}, size {page_size})")
        tenants = await tenant_service.list_tenants()
        
        # Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_tenants = tenants[start_idx:end_idx]
        
        return TenantListResponse(
            tenants=paginated_tenants,
            total_count=len(tenants)
        )
        
    except Exception as e:
        logger.error(f"Failed to list tenants: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list tenants: {str(e)}"
        )

@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    _: str = Depends(verify_api_key),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    Get tenant details by ID.
    
    Args:
        tenant_id: The unique identifier of the tenant
        _: API key verification (required)
        tenant_service: Tenant service
        
    Returns:
        TenantResponse: Tenant details
        
    Raises:
        HTTPException: If tenant not found or error occurs
    """
    try:
        logger.info(f"Getting tenant details: {tenant_id}")
        tenant = await tenant_service.get_tenant(tenant_id)
        
        if not tenant:
            raise HTTPException(
                status_code=404,
                detail=f"Tenant {tenant_id} not found"
            )
        
        return TenantResponse(**tenant)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tenant {tenant_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get tenant: {str(e)}"
        )

@router.get("/{tenant_id}/api-keys", response_model=List[ApiKeyResponse])
async def list_api_keys(
    tenant_id: str,
    _: str = Depends(verify_api_key),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    List API keys for a tenant.
    
    Args:
        tenant_id: The unique identifier of the tenant
        _: API key verification (required)
        tenant_service: Tenant service
        
    Returns:
        List[ApiKeyResponse]: List of API keys
        
    Raises:
        HTTPException: If tenant not found or error occurs
    """
    try:
        logger.info(f"Listing API keys for tenant: {tenant_id}")
        
        # Verify tenant exists
        tenant = await tenant_service.get_tenant(tenant_id)
        if not tenant:
            raise HTTPException(
                status_code=404,
                detail=f"Tenant {tenant_id} not found"
            )
        
        api_keys = await tenant_service.list_api_keys(tenant_id)
        return [ApiKeyResponse(**key) for key in api_keys]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list API keys for tenant {tenant_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list API keys: {str(e)}"
        )

@router.post("/{tenant_id}/api-keys", response_model=ApiKeyCreateResponse)
async def create_api_key(
    tenant_id: str,
    request: ApiKeyCreateRequest,
    _: str = Depends(verify_api_key),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    Create a new API key for a tenant.
    
    Args:
        tenant_id: The unique identifier of the tenant
        request: API key creation request
        _: API key verification (required)
        tenant_service: Tenant service
        
    Returns:
        ApiKeyCreateResponse: Created API key details
        
    Raises:
        HTTPException: If tenant not found or error occurs
    """
    try:
        logger.info(f"Creating API key for tenant: {tenant_id}")
        
        # Verify tenant exists
        tenant = await tenant_service.get_tenant(tenant_id)
        if not tenant:
            raise HTTPException(
                status_code=404,
                detail=f"Tenant {tenant_id} not found"
            )
        
        api_key = await tenant_service.create_api_key(
            tenant_id=tenant_id,
            key_name=request.name,
            permissions=[]  # Default empty permissions
        )
        
        return ApiKeyCreateResponse(
            api_key=api_key["api_key"],
            key_info=ApiKeyResponse(
                id=api_key["key_id"],
                name=api_key["key_name"],
                key_prefix=api_key["api_key"][:8] + "...",
                is_active=True,
                created_at=api_key["created_at"],
                expires_at=request.expires_at
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create API key for tenant {tenant_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create API key: {str(e)}"
        )

@router.delete("/{tenant_id}/api-keys/{key_id}")
async def delete_api_key(
    tenant_id: str,
    key_id: str,
    _: str = Depends(verify_api_key),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    Delete an API key for a tenant.
    
    Args:
        tenant_id: The unique identifier of the tenant
        key_id: The unique identifier of the API key
        _: API key verification (required)
        tenant_service: Tenant service
        
    Returns:
        dict: Success message
        
    Raises:
        HTTPException: If tenant or key not found or error occurs
    """
    try:
        logger.info(f"Deleting API key {key_id} for tenant: {tenant_id}")
        
        # Verify tenant exists
        tenant = await tenant_service.get_tenant(tenant_id)
        if not tenant:
            raise HTTPException(
                status_code=404,
                detail=f"Tenant {tenant_id} not found"
            )
        
        success = await tenant_service.delete_api_key(tenant_id, key_id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"API key {key_id} not found for tenant {tenant_id}"
            )
        
        return {"message": f"API key {key_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete API key {key_id} for tenant {tenant_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete API key: {str(e)}"
        ) 