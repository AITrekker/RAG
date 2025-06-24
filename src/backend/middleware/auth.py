"""
Qdrant-based Authentication Middleware

This module provides the FastAPI dependencies for authenticating requests
using API keys stored and validated against a Qdrant collection.
"""
import logging
from typing import Optional

from fastapi import HTTPException, Request, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..core.tenant_service import TenantService, get_tenant_service

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
    
    tenant_info = tenant_service.validate_api_key(creds.credentials)
    if not tenant_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
        )
        
    return tenant_info["id"]

def require_authentication(
    tenant_id: str = Depends(get_current_tenant_id)
) -> str:
    """
    A simple dependency that just runs get_current_tenant_id to protect an endpoint.
    """
    return tenant_id 