"""
Authentication and Authorization for the Enterprise RAG Platform API.

This module provides the core security middleware for the FastAPI application.
It handles API key-based authentication, ensuring that incoming requests are
valid and associated with a specific tenant.

Key features include:
- API key extraction from request headers (`X-API-Key` or `Authorization: Bearer`).
- Secure validation of API keys against a stored (hashed) collection.
- A simple, in-memory rate-limiting mechanism to prevent abuse.
- Dependency injection functions (`require_authentication`, `require_permission`)
  to easily protect API endpoints.
- Management of a user context dictionary that is passed to downstream
  route handlers.
"""

from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging
from typing import Optional, Dict, Any
import time
import hashlib
from collections import defaultdict, deque
from datetime import datetime, timedelta

from ..config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Security scheme for API keys
security = HTTPBearer(auto_error=False)

# Rate limiting storage (in production, use Redis)
rate_limit_storage: Dict[str, deque] = defaultdict(deque)

# API key storage (in production, use database)
# Format: {api_key_hash: {tenant_id, permissions, created_at, last_used}}
API_KEYS = {
    # Example API keys (hashed)
    hashlib.sha256("dev-api-key-123".encode()).hexdigest(): {
        "tenant_id": "default",
        "permissions": ["read", "write"],
        "created_at": datetime.utcnow(),
        "last_used": datetime.utcnow(),
        "name": "Development Key"
    }
}


class RateLimitExceeded(HTTPException):
    """Custom exception for rate limit exceeded."""
    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(status_code=429, detail=detail)


class AuthenticationError(HTTPException):
    """Custom exception for authentication errors."""
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(status_code=401, detail=detail)


def hash_api_key(api_key: str) -> str:
    """Hash an API key for secure storage."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def validate_api_key(api_key: str) -> Optional[Dict[str, Any]]:
    """Validate an API key and return associated metadata."""
    if not api_key:
        return None
    
    api_key_hash = hash_api_key(api_key)
    key_info = API_KEYS.get(api_key_hash)
    
    if key_info:
        # Update last used timestamp
        key_info["last_used"] = datetime.utcnow()
        logger.info(f"Valid API key used for tenant: {key_info['tenant_id']}")
        return key_info
    
    logger.warning(f"Invalid API key attempted: {api_key[:10]}...")
    return None


def check_rate_limit(identifier: str, max_requests: int = 100, window_minutes: int = 60) -> bool:
    """
    Check if the request is within rate limits.
    
    Args:
        identifier: Unique identifier (API key hash, IP, etc.)
        max_requests: Maximum requests allowed in the window
        window_minutes: Time window in minutes
    
    Returns:
        True if within limits, False if exceeded
    """
    now = time.time()
    window_start = now - (window_minutes * 60)
    
    # Get or create request queue for this identifier
    requests = rate_limit_storage[identifier]
    
    # Remove old requests outside the window
    while requests and requests[0] < window_start:
        requests.popleft()
    
    # Check if we're within limits
    if len(requests) >= max_requests:
        return False
    
    # Add current request
    requests.append(now)
    
    return True


async def get_api_key_from_header(request: Request) -> Optional[str]:
    """Extract API key from request headers."""
    # Check X-API-Key header first
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return api_key
    
    # Check Authorization header (Bearer token)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]  # Remove "Bearer " prefix
    
    return None


async def authenticate_request(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Dict[str, Any]:
    """
    Authenticate API request and return user context.
    
    This dependency can be used to protect endpoints that require authentication.
    """
    # Skip authentication for health checks, documentation, and OPTIONS requests (CORS preflight)
    if (request.url.path in ["/", "/health", "/api/v1/health", "/docs", "/redoc", "/openapi.json"] or 
        request.method == "OPTIONS"):
        return {"authenticated": False, "tenant_id": None}
    
    # Get API key from headers
    api_key = await get_api_key_from_header(request)
    
    # If no API key provided, check if endpoint allows anonymous access
    if not api_key:
        # For development, allow some endpoints without authentication
        if settings.debug and request.url.path.startswith("/api/v1/query"):
            return {
                "authenticated": False,
                "tenant_id": "default",
                "permissions": ["read"]
            }
        
        raise AuthenticationError("API key required")
    
    # Validate API key
    key_info = validate_api_key(api_key)
    if not key_info:
        raise AuthenticationError("Invalid API key")
    
    # Check rate limiting
    api_key_hash = hash_api_key(api_key)
    if not check_rate_limit(api_key_hash, max_requests=1000, window_minutes=60):
        logger.warning(f"Rate limit exceeded for API key: {api_key[:10]}...")
        raise RateLimitExceeded("API rate limit exceeded")
    
    # Return authentication context
    return {
        "authenticated": True,
        "tenant_id": key_info["tenant_id"],
        "permissions": key_info["permissions"],
        "api_key_name": key_info.get("name", "Unknown"),
        "api_key_hash": api_key_hash
    }


async def require_authentication(
    auth_context: Dict[str, Any] = Depends(authenticate_request)
) -> Dict[str, Any]:
    """
    Dependency that requires authentication.
    
    Use this for endpoints that must have valid authentication.
    """
    if not auth_context.get("authenticated", False):
        raise AuthenticationError("Authentication required")
    
    return auth_context


async def require_permission(permission: str):
    """
    Dependency factory for permission-based access control.
    
    Usage: Depends(require_permission("write"))
    """
    async def permission_checker(
        auth_context: Dict[str, Any] = Depends(require_authentication)
    ) -> Dict[str, Any]:
        permissions = auth_context.get("permissions", [])
        if permission not in permissions:
            raise HTTPException(
                status_code=403,
                detail=f"Permission '{permission}' required"
            )
        return auth_context
    
    return permission_checker


async def get_current_user_context(
    request: Request,
    auth_context: Dict[str, Any] = Depends(authenticate_request)
) -> Dict[str, Any]:
    """
    Get current user context with optional authentication.
    
    This allows endpoints to work with or without authentication.
    """
    # Add request metadata
    auth_context.update({
        "ip_address": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("User-Agent", "unknown"),
        "request_id": getattr(request.state, "request_id", "unknown")
    })
    
    return auth_context


# Middleware for request logging and security headers
async def security_middleware(request: Request, call_next):
    """Security middleware for adding security headers and logging."""
    
    # Log request
    logger.info(
        f"Request: {request.method} {request.url.path} "
        f"from {request.client.host if request.client else 'unknown'}"
    )
    
    # Process request
    response = await call_next(request)
    
    # Add security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    if not settings.debug:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    return response


# Utility functions for API key management
def create_api_key(tenant_id: str, name: str, permissions: list) -> str:
    """
    Create a new API key for a tenant.
    
    In production, this would be stored in a database.
    """
    import secrets
    
    # Generate secure random API key
    api_key = f"rag_{secrets.token_urlsafe(32)}"
    api_key_hash = hash_api_key(api_key)
    
    # Store API key info
    API_KEYS[api_key_hash] = {
        "tenant_id": tenant_id,
        "permissions": permissions,
        "created_at": datetime.utcnow(),
        "last_used": None,
        "name": name
    }
    
    logger.info(f"Created API key '{name}' for tenant {tenant_id}")
    return api_key


def revoke_api_key(api_key: str) -> bool:
    """
    Revoke an API key.
    
    Returns True if key was found and revoked, False otherwise.
    """
    api_key_hash = hash_api_key(api_key)
    
    if api_key_hash in API_KEYS:
        key_info = API_KEYS.pop(api_key_hash)
        logger.info(f"Revoked API key '{key_info.get('name', 'unknown')}' for tenant {key_info.get('tenant_id')}")
        return True
    
    return False


def list_api_keys(tenant_id: str) -> list:
    """
    List all API keys for a tenant.
    
    Returns list of API key info (without the actual keys).
    """
    keys = []
    for key_hash, key_info in API_KEYS.items():
        if key_info["tenant_id"] == tenant_id:
            keys.append({
                "hash": key_hash[:16] + "...",  # Partial hash for identification
                "name": key_info["name"],
                "permissions": key_info["permissions"],
                "created_at": key_info["created_at"],
                "last_used": key_info["last_used"]
            })
    
    return keys


async def get_current_tenant(
    request: Request,
    auth_context: Dict[str, Any] = Depends(authenticate_request)
) -> str:
    """
    Dependency to get the tenant_id from the authentication context.
    """
    # For OPTIONS requests (CORS preflight), return a default tenant
    if request.method == "OPTIONS":
        return "default"
    
    tenant_id = auth_context.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not determine tenant ID from request.",
        )
    return tenant_id 