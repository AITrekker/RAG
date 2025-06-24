"""
Tenant Context Dependency for FastAPI.

This module provides a simple FastAPI dependency function to extract the
tenant ID from a request header. In the refactored Qdrant-based architecture,
complex tenant context middleware is not required for basic operation.
"""

import logging
from typing import Optional
from fastapi import Request, HTTPException, status

logger = logging.getLogger(__name__)

async def get_tenant_from_header(request: Request) -> str:
    """
    FastAPI dependency to get a tenant ID from the 'X-Tenant-Id' header.

    This is the primary mechanism for identifying tenants in the absence of
    a database-backed session or complex API key validation.

    Args:
        request: The incoming FastAPI request object.

    Returns:
        The tenant ID string if found in the header.

    Raises:
        HTTPException: If the 'X-Tenant-Id' header is missing or empty.
    """
    tenant_id = request.headers.get("X-Tenant-Id")
    
    if not tenant_id:
        logger.warning("Request received without X-Tenant-Id header.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-Id header is required."
        )
        
    logger.debug(f"Request identified for tenant: {tenant_id}")
    return tenant_id

async def get_optional_tenant_id(request: Request) -> Optional[str]:
    """
    FastAPI dependency to get an optional tenant ID from the 'X-Tenant-Id' header.
    
    This does not raise an error if the header is missing, allowing certain
    endpoints to operate without a tenant context.
    
    Args:
        request: The incoming FastAPI request object.
        
    Returns:
        The tenant ID string or None.
    """
    return request.headers.get("X-Tenant-Id") 