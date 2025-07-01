"""
API Key Authentication Middleware
"""

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
import logging

from src.backend.database import get_async_db
from src.backend.services.tenant_service import TenantService

logger = logging.getLogger(__name__)

# Public endpoints that don't require authentication
PUBLIC_ENDPOINTS = {
    "/",
    "/health",
    "/docs",
    "/openapi.json",
    "/api/v1/openapi.json",
    "/redoc",
    "/favicon.ico"
}

# API paths that start with these prefixes don't require auth
PUBLIC_PREFIXES = {
    "/api/v1/health",
    "/static/"
}


def is_public_endpoint(path: str) -> bool:
    """Check if endpoint is public and doesn't require authentication"""
    if path in PUBLIC_ENDPOINTS:
        return True
    
    for prefix in PUBLIC_PREFIXES:
        if path.startswith(prefix):
            return True
    
    return False


def extract_api_key(request: Request) -> str:
    """Extract API key from request headers"""
    # Try X-API-Key header first
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return api_key
    
    # Try Authorization header with Bearer token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]  # Remove "Bearer " prefix
    
    return None


async def api_key_auth_middleware(request: Request, call_next):
    """
    API Key Authentication Middleware
    
    Authenticates requests using tenant API keys and adds tenant context to request.
    """
    
    # Skip authentication for public endpoints
    if is_public_endpoint(request.url.path):
        return await call_next(request)
    
    try:
        # Extract API key from request
        api_key = extract_api_key(request)
        
        if not api_key:
            logger.warning(f"Missing API key for {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Missing API key",
                    "message": "Provide API key in X-API-Key header or Authorization: Bearer token"
                }
            )
        
        # Look up tenant by API key using service
        async for db in get_async_db():
            tenant_service = TenantService(db)
            tenant = await tenant_service.get_tenant_by_api_key(api_key)
            break
        
        if not tenant:
            logger.warning(f"Invalid API key attempted: {api_key[:20]}...")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Invalid API key",
                    "message": "The provided API key is invalid or has been revoked"
                }
            )
        
        if not tenant.is_active:
            logger.warning(f"Inactive tenant attempted access: {tenant.slug}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Tenant inactive",
                    "message": "The tenant account is inactive"
                }
            )
        
        # Check if API key has expired
        if tenant.api_key_expires_at and tenant.api_key_expires_at < tenant.updated_at:
            logger.warning(f"Expired API key attempted: {tenant.slug}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "API key expired",
                    "message": "The API key has expired"
                }
            )
        
        # Add tenant context to request state (convert UUID to string for JSON serialization)
        request.state.tenant_id = str(tenant.id)
        request.state.tenant = tenant  # Keep the full tenant object
        request.state.tenant_slug = tenant.slug
        request.state.api_key = api_key
        
        # Update API key last used timestamp (async, don't wait)
        try:
            async for db in get_async_db():
                tenant_service = TenantService(db)
                await tenant_service.update_api_key_last_used(tenant.id)
                break
        except Exception as e:
            # Don't fail request if we can't update usage
            logger.error(f"Failed to update API key usage: {e}")
        
        logger.info(f"Authenticated request for tenant: {tenant.slug}")
        
        # Process the request
        response = await call_next(request)
        
        # Add tenant info to response headers for debugging
        response.headers["X-Tenant-ID"] = str(tenant.id)
        response.headers["X-Tenant-Slug"] = tenant.slug
        
        return response
        
    except Exception as e:
        logger.error(f"Authentication middleware error: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Authentication error",
                "message": "An error occurred during authentication"
            }
        )


# FastAPI dependency to get current tenant from request state
def get_current_tenant(request: Request):
    """FastAPI dependency to get current authenticated tenant"""
    if not hasattr(request.state, 'tenant'):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authenticated tenant found"
        )
    return request.state.tenant


def get_current_tenant_id(request: Request):
    """FastAPI dependency to get current tenant ID as string"""
    if not hasattr(request.state, 'tenant_id'):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authenticated tenant found"
        )
    return request.state.tenant_id  # Already a string