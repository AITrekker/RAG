"""
Tenant Context Middleware for API Requests

Middleware for FastAPI that extracts tenant information from requests,
validates authentication, and sets up tenant context for request processing.

Author: Enterprise RAG Platform Team
"""

from typing import Optional, Dict, Any, Callable, List, Tuple
import logging
from datetime import datetime, timezone
from fastapi import Request, Response, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.security.utils import get_authorization_scheme_param
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import hashlib
import uuid

from ..core.tenant_scoped_db import TenantContext, extract_tenant_from_api_key
from ..core.tenant_isolation import TenantSecurityError
from ..models.tenant import TenantApiKey, Tenant
from ..core.tenant_manager import get_tenant_manager

logger = logging.getLogger(__name__)

# Global tenant context storage (in production, use proper context management)
_tenant_context: Dict[str, Any] = {}


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract and validate tenant context from API requests
    """
    
    def __init__(
        self,
        app,
        db_session_factory: Callable,
        require_tenant_context: bool = True,
        excluded_paths: Optional[List[str]] = None
    ):
        super().__init__(app)
        self.db_session_factory = db_session_factory
        self.require_tenant_context = require_tenant_context
        self.excluded_paths = excluded_paths or [
            "/docs", "/redoc", "/openapi.json", "/health", "/ping",
            "/api/v1/health", "/api/v1/status"
        ]
        self.security = HTTPBearer(auto_error=False)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request through tenant context middleware
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/handler in chain
            
        Returns:
            Response object
        """
        # Clear any existing tenant context
        TenantContext.clear_context()
        
        try:
            # Check if path is excluded from tenant requirements
            if self._is_excluded_path(request.url.path):
                return await call_next(request)
            
            # Extract tenant context from request
            tenant_info = await self._extract_tenant_context(request)
            
            if tenant_info:
                tenant_id, user_id, api_key_record = tenant_info
                
                # Set tenant context
                TenantContext.set_current_tenant(tenant_id, user_id)
                
                # Add tenant info to request state
                request.state.tenant_id = tenant_id
                request.state.user_id = user_id
                request.state.api_key_record = api_key_record
                
                # Log tenant context
                logger.debug(
                    f"Set tenant context for request: {tenant_id} "
                    f"(user: {user_id}, path: {request.url.path})"
                )
                
            elif self.require_tenant_context:
                # Tenant context required but not found
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "error": "authentication_required",
                        "message": "Valid tenant authentication required",
                        "details": "Please provide a valid API key in the Authorization header"
                    }
                )
            
            # Process request
            response = await call_next(request)
            
            # Add tenant info to response headers (for debugging)
            if tenant_info:
                response.headers["X-Tenant-ID"] = tenant_info[0]
            
            return response
            
        except TenantSecurityError as e:
            logger.warning(f"Tenant security error: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "access_denied",
                    "message": "Tenant access denied",
                    "details": str(e)
                }
            )
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": "authentication_error",
                    "message": e.detail,
                    "details": "Authentication failed"
                }
            )
        except Exception as e:
            logger.error(f"Unexpected error in tenant middleware: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "internal_error",
                    "message": "Internal server error during authentication",
                    "details": "Please contact support"
                }
            )
        finally:
            # Always clear context after request
            TenantContext.clear_context()
    
    async def _extract_tenant_context(self, request: Request) -> Optional[Tuple[str, Optional[str], TenantApiKey]]:
        """
        Extract tenant context from request headers and validate
        
        Args:
            request: FastAPI request object
            
        Returns:
            Tuple of (tenant_id, user_id, api_key_record) or None
        """
        # Try to get API key from Authorization header
        api_key = await self._extract_api_key(request)
        if not api_key:
            # Try alternative headers
            api_key = self._extract_api_key_from_headers(request)
        
        if not api_key:
            return None
        
        # Validate API key and get tenant info
        with self.db_session_factory() as db:
            tenant_manager = get_tenant_manager(db)
            api_key_record = tenant_manager.validate_api_key(api_key)
            
            if not api_key_record:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired API key"
                )
            
            # Check if tenant is active
            tenant = tenant_manager.get_tenant(api_key_record.tenant_id)
            if not tenant:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Tenant not found"
                )
            
            if tenant.status != "active":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Tenant is {tenant.status}"
                )
            
            # Extract user ID if available (could come from JWT or other auth)
            user_id = self._extract_user_id(request)
            
            return api_key_record.tenant_id, user_id, api_key_record
    
    async def _extract_api_key(self, request: Request) -> Optional[str]:
        """
        Extract API key from Authorization header
        
        Args:
            request: FastAPI request object
            
        Returns:
            API key string or None
        """
        authorization = request.headers.get("Authorization")
        if not authorization:
            return None
        
        scheme, credentials = get_authorization_scheme_param(authorization)
        
        # Support Bearer token format
        if scheme.lower() == "bearer":
            return credentials
        
        # Support API key format
        if scheme.lower() == "api-key":
            return credentials
        
        return None
    
    def _extract_api_key_from_headers(self, request: Request) -> Optional[str]:
        """
        Extract API key from alternative headers
        
        Args:
            request: FastAPI request object
            
        Returns:
            API key string or None
        """
        # Check X-API-Key header
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return api_key
        
        # Check X-Auth-Token header
        auth_token = request.headers.get("X-Auth-Token")
        if auth_token:
            return auth_token
        
        return None
    
    def _extract_user_id(self, request: Request) -> Optional[str]:
        """
        Extract user ID from request (placeholder for future auth)
        
        Args:
            request: FastAPI request object
            
        Returns:
            User ID string or None
        """
        # Placeholder for JWT token parsing or other user identification
        return request.headers.get("X-User-ID")
    
    def _is_excluded_path(self, path: str) -> bool:
        """
        Check if path is excluded from tenant requirements
        
        Args:
            path: Request path
            
        Returns:
            True if excluded
        """
        return any(path.startswith(excluded) for excluded in self.excluded_paths)


class TenantValidationMiddleware:
    """
    Additional middleware for tenant-specific validation and rate limiting
    """
    
    def __init__(self, db_session_factory: Callable):
        self.db_session_factory = db_session_factory
    
    async def validate_tenant_limits(self, request: Request) -> Optional[JSONResponse]:
        """
        Validate tenant usage limits and quotas
        
        Args:
            request: FastAPI request object
            
        Returns:
            Error response if limits exceeded, None otherwise
        """
        if not hasattr(request.state, 'tenant_id'):
            return None
        
        tenant_id = request.state.tenant_id
        
        try:
            with self.db_session_factory() as db:
                tenant_manager = get_tenant_manager(db)
                tenant = tenant_manager.get_tenant(tenant_id)
                
                if not tenant:
                    return JSONResponse(
                        status_code=status.HTTP_404_NOT_FOUND,
                        content={"error": "tenant_not_found", "message": "Tenant not found"}
                    )
                
                # Check API rate limits
                if hasattr(request.state, 'api_key_record'):
                    api_key = request.state.api_key_record
                    
                    # Simple rate limiting based on usage count
                    # In production, this would use Redis or similar
                    if self._check_rate_limit(api_key, tenant):
                        return JSONResponse(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            content={
                                "error": "rate_limit_exceeded",
                                "message": "API rate limit exceeded",
                                "details": f"Maximum {tenant.max_api_calls_per_day} calls per day"
                            }
                        )
                
                # Check concurrent request limits
                # This would be implemented with Redis in production
                
                return None
                
        except Exception as e:
            logger.error(f"Error validating tenant limits: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "validation_error", "message": "Error validating tenant limits"}
            )
    
    def _check_rate_limit(self, api_key: TenantApiKey, tenant: Tenant) -> bool:
        """
        Check if API key has exceeded rate limits
        
        Args:
            api_key: API key record
            tenant: Tenant record
            
        Returns:
            True if rate limit exceeded
        """
        # Simple daily limit check
        # In production, use Redis with sliding window
        today = datetime.now(timezone.utc).date()
        
        # This is a simplified check - real implementation would track calls per day
        if api_key.usage_count > tenant.max_api_calls_per_day:
            return True
        
        return False


# Dependency functions for FastAPI
async def get_current_tenant_id(request: Request) -> str:
    """
    FastAPI dependency to get current tenant ID
    
    Args:
        request: FastAPI request object
        
    Returns:
        Current tenant ID
        
    Raises:
        HTTPException: If no tenant context
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No tenant context found"
        )
    
    return tenant_id


async def get_optional_tenant_id(request: Request) -> Optional[str]:
    """
    FastAPI dependency to get current tenant ID
    
    Args:
        request: FastAPI request object
        
    Returns:
        Current tenant ID or None
    """
    return getattr(request.state, "tenant_id", None)


def get_current_user_id(request: Request) -> Optional[str]:
    """
    FastAPI dependency to get current user ID
    
    Args:
        request: FastAPI request object
        
    Returns:
        Current user ID or None
    """
    return getattr(request.state, 'user_id', None)


def get_current_api_key(request: Request) -> TenantApiKey:
    """
    FastAPI dependency to get current API key record
    
    Args:
        request: FastAPI request object
        
    Returns:
        Current API key record
        
    Raises:
        HTTPException: If no API key context
    """
    if not hasattr(request.state, 'api_key_record'):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No API key context found"
        )
    
    return request.state.api_key_record


def require_tenant_scope(*allowed_scopes: str):
    """
    FastAPI dependency to require specific tenant scopes
    
    Args:
        allowed_scopes: Required scopes for the endpoint
        
    Returns:
        Dependency function
    """
    def check_scopes(api_key: TenantApiKey = get_current_api_key):
        if not api_key.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No scopes assigned to API key"
            )
        
        # Check if any of the required scopes are present
        if not any(scope in api_key.scopes for scope in allowed_scopes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required scopes: {list(allowed_scopes)}"
            )
        
        return api_key
    
    return check_scopes


# Utility functions for manual tenant context management
def set_tenant_context_from_request(request: Request) -> bool:
    """
    Manually set tenant context from request state
    
    Args:
        request: FastAPI request object
        
    Returns:
        True if context was set successfully
    """
    if hasattr(request.state, 'tenant_id'):
        TenantContext.set_current_tenant(
            request.state.tenant_id,
            getattr(request.state, 'user_id', None)
        )
        return True
    return False


def clear_tenant_context() -> None:
    """Clear the current tenant context"""
    TenantContext.clear_context()


# Decorators for route handlers
def with_tenant_context(func):
    """
    Decorator to ensure tenant context is set for route handlers
    
    Args:
        func: Route handler function
        
    Returns:
        Wrapped function
    """
    def wrapper(*args, **kwargs):
        # Find request object in arguments
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break
        
        if request and not set_tenant_context_from_request(request):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No tenant context available"
            )
        
        try:
            return func(*args, **kwargs)
        finally:
            clear_tenant_context()
    
    return wrapper


# Exception handlers for tenant-related errors
async def tenant_security_exception_handler(request: Request, exc: TenantSecurityError) -> JSONResponse:
    """
    Exception handler for tenant security errors
    
    Args:
        request: FastAPI request object
        exc: Tenant security exception
        
    Returns:
        JSON error response
    """
    logger.warning(f"Tenant security violation: {str(exc)} (path: {request.url.path})")
    
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "error": "tenant_security_error",
            "message": "Access denied due to tenant security policy",
            "details": str(exc)
        }
    )


# Configuration helper
def configure_tenant_middleware(
    app,
    db_session_factory: Callable,
    require_tenant_context: bool = True,
    excluded_paths: Optional[List[str]] = None
) -> None:
    """
    Configure tenant middleware for FastAPI app
    
    Args:
        app: FastAPI application instance
        db_session_factory: Database session factory
        require_tenant_context: Whether to require tenant context
        excluded_paths: Paths to exclude from tenant requirements
    """
    # Add tenant context middleware
    app.add_middleware(
        TenantContextMiddleware,
        db_session_factory=db_session_factory,
        require_tenant_context=require_tenant_context,
        excluded_paths=excluded_paths
    )
    
    # Add exception handler
    app.add_exception_handler(TenantSecurityError, tenant_security_exception_handler)
    
    logger.info("Tenant context middleware configured")


# Health check utilities
def create_tenant_health_check(db_session_factory: Callable):
    """
    Create a health check endpoint that validates tenant system
    
    Args:
        db_session_factory: Database session factory
        
    Returns:
        Health check function
    """
    async def health_check():
        try:
            with db_session_factory() as db:
                # Test database connectivity
                tenant_count = db.query(Tenant).count()
                
                return {
                    "status": "healthy",
                    "tenant_system": "operational",
                    "tenant_count": tenant_count,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
        except Exception as e:
            logger.error(f"Tenant health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "tenant_system": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    return health_check


class TenantContext:
    """Tenant context manager for storing tenant-specific data."""
    
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self._data: Dict[str, Any] = {}
    
    def set(self, key: str, value: Any) -> None:
        """Set a value in the tenant context."""
        self._data[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the tenant context."""
        return self._data.get(key, default)
    
    def clear(self) -> None:
        """Clear all data from the tenant context."""
        self._data.clear()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return {
            "tenant_id": self.tenant_id,
            "data": self._data.copy()
        }


def get_tenant_context(tenant_id: str) -> TenantContext:
    """Get or create tenant context for the given tenant ID."""
    global _tenant_context
    
    if tenant_id not in _tenant_context:
        _tenant_context[tenant_id] = TenantContext(tenant_id)
    
    return _tenant_context[tenant_id]


def clear_tenant_context(tenant_id: str) -> None:
    """Clear context for a specific tenant."""
    global _tenant_context
    
    if tenant_id in _tenant_context:
        _tenant_context[tenant_id].clear()


def clear_all_tenant_contexts() -> None:
    """Clear all tenant contexts (useful for testing)."""
    global _tenant_context
    _tenant_context.clear()


# Tenant-aware dependency injection helpers
def tenant_scoped_dependency(dependency_factory):
    """
    Create a tenant-scoped dependency that maintains separate instances per tenant.
    
    Usage:
        @tenant_scoped_dependency
        def get_tenant_service():
            return SomeService()
    """
    tenant_instances = {}
    
    async def scoped_dependency(tenant_id: str = Depends(get_current_tenant_id)):
        if tenant_id not in tenant_instances:
            tenant_instances[tenant_id] = dependency_factory()
        return tenant_instances[tenant_id]
    
    return scoped_dependency


# Utility functions for tenant management
def validate_tenant_access(tenant_id: str, user_tenant_id: str) -> bool:
    """
    Validate that a user has access to the specified tenant.
    
    Args:
        tenant_id: The tenant being accessed
        user_tenant_id: The user's tenant ID
    
    Returns:
        True if access is allowed, False otherwise
    """
    # Basic validation - user can only access their own tenant
    # In a more complex system, this might check for cross-tenant permissions
    return tenant_id == user_tenant_id


def get_tenant_database_name(tenant_id: str) -> str:
    """Get the database name for a specific tenant."""
    # Sanitize tenant ID for database name
    safe_tenant_id = tenant_id.replace("-", "_").replace(".", "_")
    return f"rag_tenant_{safe_tenant_id}"


def get_tenant_collection_name(tenant_id: str, collection_type: str = "documents") -> str:
    """Get the vector store collection name for a specific tenant."""
    # Sanitize tenant ID for collection name
    safe_tenant_id = tenant_id.replace("-", "_").replace(".", "_")
    return f"tenant_{safe_tenant_id}_{collection_type}"


def get_tenant_storage_path(tenant_id: str, base_path: str = "./documents") -> str:
    """Get the file storage path for a specific tenant."""
    import os
    # Sanitize tenant ID for file path
    safe_tenant_id = tenant_id.replace(".", "_").replace("/", "_").replace("\\", "_")
    return os.path.join(base_path, safe_tenant_id)


# Tenant isolation utilities
class TenantIsolationError(Exception):
    """Exception raised when tenant isolation is violated."""
    pass


def ensure_tenant_isolation(resource_tenant_id: str, request_tenant_id: str) -> None:
    """
    Ensure that a resource belongs to the requesting tenant.
    
    Raises TenantIsolationError if tenant isolation is violated.
    """
    if resource_tenant_id != request_tenant_id:
        raise TenantIsolationError(
            f"Access denied: Resource belongs to tenant '{resource_tenant_id}' "
            f"but request is from tenant '{request_tenant_id}'"
        )


def filter_by_tenant(query, tenant_id: str, tenant_column="tenant_id"):
    """
    Add tenant filtering to a SQLAlchemy query.
    
    Args:
        query: SQLAlchemy query object
        tenant_id: Tenant ID to filter by
        tenant_column: Name of the tenant column (default: "tenant_id")
    
    Returns:
        Filtered query object
    """
    return query.filter(getattr(query.column_descriptions[0]['type'], tenant_column) == tenant_id) 