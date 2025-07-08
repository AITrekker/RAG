"""
Qdrant-based Authentication Middleware

This module provides the FastAPI dependencies for authenticating requests
using API keys stored and validated against a Qdrant collection.
"""
import logging
from typing import Optional

from fastapi import HTTPException, Request, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..services.tenant_service import TenantService, get_tenant_service

logger = logging.getLogger(__name__)

class APIKeyOrBearer(HTTPBearer):
    async def __call__(
        self, request: Request
    ) -> Optional[HTTPAuthorizationCredentials]:
        return await super().__call__(request)

api_key_security = APIKeyOrBearer()

def get_current_tenant_id(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(api_key_security),
    tenant_service: TenantService = Depends(get_tenant_service),
) -> str:
    """
    FastAPI dependency to get current tenant ID from API key credentials.
    """
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )
    
    tenant = tenant_service.get_tenant_by_api_key(creds.credentials)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
        )
        
    return str(tenant.id)

def require_authentication(
    tenant_id: str = Depends(get_current_tenant_id)
) -> str:
    """
    A simple dependency that just runs get_current_tenant_id to protect an endpoint.
    """
    return tenant_id 

def get_current_tenant(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(api_key_security),
    tenant_service: TenantService = Depends(get_tenant_service),
) -> dict:
    """
    FastAPI dependency to get the full tenant info from API key credentials.
    Returns the full tenant info dict (not just the ID).
    """
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )
    tenant = tenant_service.get_tenant_by_api_key(creds.credentials)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
        )
    
    # Convert tenant object to dict
    tenant_dict = {
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "status": tenant.status,
        "is_active": tenant.is_active
    }
    return tenant_dict

def require_admin(
    current_tenant: dict = Depends(get_current_tenant)
) -> dict:
    """
    Require admin tenant authentication.
    Only allows access if the current tenant is the admin tenant.
    """
    if current_tenant.get("name") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_tenant

def verify_tenant_access(
    target_tenant_id: str,
    current_tenant: dict = Depends(get_current_tenant)
) -> str:
    """
    Verify tenant has access to target tenant (admin or self).
    Returns the target tenant ID if access is granted.
    """
    if current_tenant.get("name") == "admin":
        return target_tenant_id
    if current_tenant.get("id") == target_tenant_id:
        return target_tenant_id
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied"
    )

def get_tenant_context(
    current_tenant: dict = Depends(get_current_tenant)
) -> dict:
    """
    Get enhanced tenant context with permissions.
    """
    # Add basic permission checking
    permissions = []
    if current_tenant.get("name") == "admin":
        permissions = ["admin", "tenant_management", "system_management"]
    else:
        permissions = ["tenant_operations", "document_access", "query_access"]
    
    return {
        **current_tenant,
        "permissions": permissions
    } 