"""
API Authentication and Security Middleware

This module provides comprehensive API authentication, rate limiting,
and security features for the Enterprise RAG Platform.
"""

import logging
import hashlib
import secrets
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from functools import wraps
import redis
import json

from fastapi import HTTPException, Request, Response, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy.orm import Session

from ..models.tenant import TenantApiKey, Tenant
from ..db.session import get_db
from ..config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class SecurityConfig:
    """Security configuration constants."""
    
    # Rate limiting defaults
    DEFAULT_RATE_LIMIT_PER_MINUTE = 60
    DEFAULT_RATE_LIMIT_PER_HOUR = 1000
    DEFAULT_RATE_LIMIT_PER_DAY = 10000
    
    # API key settings
    API_KEY_LENGTH = 32
    API_KEY_PREFIX_LENGTH = 8
    
    # Security headers
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';"
    }


class RateLimiter:
    """Redis-based rate limiter with tenant-specific limits."""
    
    def __init__(self):
        self.redis_client = None
        self.fallback_cache = {}  # In-memory fallback
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Initialize Redis connection
        if settings.redis_url:
            try:
                import redis
                self.redis_client = redis.from_url(
                    settings.redis_url,
                    password=settings.redis_password,
                    decode_responses=True
                )
                # Test connection
                self.redis_client.ping()
                self.logger.info("Connected to Redis for rate limiting")
            except Exception as e:
                self.logger.warning(f"Redis connection failed, using in-memory fallback: {e}")
                self.redis_client = None
    
    def _get_rate_limit_key(self, identifier: str, window: str) -> str:
        """Generate rate limit key for Redis."""
        return f"rate_limit:{identifier}:{window}"
    
    def _get_current_window(self, window_type: str) -> str:
        """Get current time window identifier."""
        now = datetime.now(timezone.utc)
        
        if window_type == "minute":
            return now.strftime("%Y%m%d%H%M")
        elif window_type == "hour":
            return now.strftime("%Y%m%d%H")
        elif window_type == "day":
            return now.strftime("%Y%m%d")
        else:
            raise ValueError(f"Invalid window type: {window_type}")
    
    def check_rate_limit(
        self, 
        identifier: str, 
        limits: Dict[str, int],
        increment: bool = True
    ) -> Tuple[bool, Dict[str, int]]:
        """
        Check rate limits for an identifier.
        
        Args:
            identifier: Unique identifier (e.g., API key, IP address)
            limits: Dict with 'minute', 'hour', 'day' limits
            increment: Whether to increment counters
            
        Returns:
            Tuple of (allowed, current_counts)
        """
        current_counts = {}
        
        for window_type, limit in limits.items():
            if limit <= 0:
                continue
                
            window = self._get_current_window(window_type)
            key = self._get_rate_limit_key(identifier, f"{window_type}:{window}")
            
            # Get current count
            if self.redis_client:
                try:
                    current = self.redis_client.get(key)
                    current_count = int(current) if current else 0
                except Exception as e:
                    self.logger.error(f"Redis error: {e}")
                    # Fallback to in-memory
                    current_count = self.fallback_cache.get(key, 0)
            else:
                current_count = self.fallback_cache.get(key, 0)
            
            current_counts[window_type] = current_count
            
            # Check limit
            if current_count >= limit:
                return False, current_counts
            
            # Increment if requested
            if increment:
                if self.redis_client:
                    try:
                        self.redis_client.incr(key)
                        # Set expiration based on window type
                        if window_type == "minute":
                            self.redis_client.expire(key, 120)  # 2 minutes
                        elif window_type == "hour":
                            self.redis_client.expire(key, 7200)  # 2 hours
                        elif window_type == "day":
                            self.redis_client.expire(key, 172800)  # 2 days
                    except Exception as e:
                        self.logger.error(f"Redis error: {e}")
                        self.fallback_cache[key] = current_count + 1
                else:
                    self.fallback_cache[key] = current_count + 1
        
        return True, current_counts


class APIKeyValidator:
    """Validates API keys and manages authentication."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
    def generate_api_key(self) -> Tuple[str, str, str]:
        """
        Generate a new API key.
        
        Returns:
            Tuple of (full_key, key_hash, key_prefix)
        """
        # Generate random key
        key_bytes = secrets.token_bytes(SecurityConfig.API_KEY_LENGTH)
        full_key = key_bytes.hex()
        
        # Create prefix for identification
        key_prefix = full_key[:SecurityConfig.API_KEY_PREFIX_LENGTH]
        
        # Hash for storage
        key_hash = hashlib.sha256(full_key.encode()).hexdigest()
        
        return full_key, key_hash, key_prefix
    
    def validate_api_key(self, api_key: str, db: Session) -> Optional[TenantApiKey]:
        """
        Validate an API key and return the associated tenant key record.
        """
        if not api_key or len(api_key) < SecurityConfig.API_KEY_PREFIX_LENGTH:
            return None
        
        try:
            # Hash the provided key
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            
            # Look up in database
            tenant_key = db.query(TenantApiKey).filter(
                TenantApiKey.key_hash == key_hash,
                TenantApiKey.is_active == True
            ).first()
            
            if not tenant_key:
                return None
            
            # Check expiration
            if tenant_key.expires_at and tenant_key.expires_at < datetime.now(timezone.utc):
                self.logger.warning(f"Expired API key used: {tenant_key.key_prefix}")
                return None
            
            # Update usage statistics
            tenant_key.last_used_at = datetime.now(timezone.utc)
            tenant_key.usage_count += 1
            db.commit()
            
            return tenant_key
            
        except Exception as e:
            self.logger.error(f"Error validating API key: {e}")
            return None


class SecurityMiddleware:
    """Main security middleware for API authentication and protection."""
    
    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.api_key_validator = APIKeyValidator()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
    async def __call__(self, request: Request, call_next):
        """Process request through security middleware."""
        start_time = time.time()
        
        # Add security headers to response
        response = await call_next(request)
        
        for header, value in SecurityConfig.SECURITY_HEADERS.items():
            response.headers[header] = value
        
        # Add processing time header
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
    
    def authenticate_request(self, request: Request, db: Session) -> Tuple[Optional[str], Optional[TenantApiKey]]:
        """
        Authenticate a request and return tenant_id and tenant_key if valid.
        """
        # Extract API key from Authorization header
        authorization = request.headers.get("Authorization")
        if not authorization:
            return None, None
        
        scheme, credentials = get_authorization_scheme_param(authorization)
        if scheme.lower() != "bearer":
            return None, None
        
        # Validate API key
        tenant_key = self.api_key_validator.validate_api_key(credentials, db)
        if not tenant_key:
            return None, None
        
        # Get tenant information
        tenant = db.query(Tenant).filter(Tenant.id == tenant_key.tenant_id).first()
        if not tenant or tenant.status != "active":
            return None, None
        
        return tenant.tenant_id, tenant_key
    
    def check_rate_limits(self, tenant_key: TenantApiKey, request: Request) -> Tuple[bool, Dict]:
        """Check rate limits for a tenant API key."""
        # Get rate limits from tenant or use defaults
        tenant = tenant_key.tenant  # Assuming relationship is set up
        
        limits = {
            "minute": getattr(tenant, 'rate_limit_per_minute', SecurityConfig.DEFAULT_RATE_LIMIT_PER_MINUTE),
            "hour": getattr(tenant, 'rate_limit_per_hour', SecurityConfig.DEFAULT_RATE_LIMIT_PER_HOUR),
            "day": getattr(tenant, 'rate_limit_per_day', SecurityConfig.DEFAULT_RATE_LIMIT_PER_DAY)
        }
        
        # Use API key as identifier
        identifier = f"api_key:{tenant_key.key_prefix}"
        
        return self.rate_limiter.check_rate_limit(identifier, limits)
    
    def validate_request_size(self, request: Request) -> bool:
        """Validate request size limits."""
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                max_size = settings.max_file_size_mb * 1024 * 1024  # Convert to bytes
                return size <= max_size
            except ValueError:
                return False
        return True


# Global security middleware instance
security_middleware = SecurityMiddleware()


def require_api_key(scopes: List[str] = None):
    """
    Decorator to require API key authentication for endpoints.
    
    Args:
        scopes: List of required scopes for the endpoint
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request and db from function arguments
            request = kwargs.get('request') or args[0] if args else None
            db = kwargs.get('db') or next(get_db())
            
            if not request:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Request object not found"
                )
            
            # Authenticate request
            tenant_id, tenant_key = security_middleware.authenticate_request(request, db)
            
            if not tenant_id or not tenant_key:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or missing API key",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            # Check scopes if specified
            if scopes:
                key_scopes = tenant_key.scopes or []
                if not any(scope in key_scopes for scope in scopes):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Insufficient permissions"
                    )
            
            # Check rate limits
            allowed, current_counts = security_middleware.check_rate_limits(tenant_key, request)
            
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                    headers={
                        "X-RateLimit-Limit-Minute": str(current_counts.get('minute', 0)),
                        "X-RateLimit-Limit-Hour": str(current_counts.get('hour', 0)),
                        "X-RateLimit-Limit-Day": str(current_counts.get('day', 0))
                    }
                )
            
            # Validate request size
            if not security_middleware.validate_request_size(request):
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Request too large"
                )
            
            # Add tenant context to kwargs
            kwargs['tenant_id'] = tenant_id
            kwargs['tenant_key'] = tenant_key
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def create_api_key(tenant_id: str, key_name: str, scopes: List[str], db: Session, expires_days: int = None) -> str:
    """
    Create a new API key for a tenant.
    
    Returns:
        The full API key (return this to the user only once)
    """
    validator = APIKeyValidator()
    full_key, key_hash, key_prefix = validator.generate_api_key()
    
    # Calculate expiration
    expires_at = None
    if expires_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)
    
    # Get tenant
    tenant = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
    if not tenant:
        raise ValueError(f"Tenant {tenant_id} not found")
    
    # Create database record
    tenant_key = TenantApiKey(
        tenant_id=tenant.id,
        key_name=key_name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        scopes=scopes,
        is_active=True,
        expires_at=expires_at,
        usage_count=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    
    db.add(tenant_key)
    db.commit()
    
    logger.info(f"Created API key {key_prefix} for tenant {tenant_id}")
    
    return full_key


def revoke_api_key(key_prefix: str, db: Session) -> bool:
    """Revoke an API key by its prefix."""
    try:
        tenant_key = db.query(TenantApiKey).filter(
            TenantApiKey.key_prefix == key_prefix
        ).first()
        
        if tenant_key:
            tenant_key.is_active = False
            tenant_key.updated_at = datetime.now(timezone.utc)
            db.commit()
            logger.info(f"Revoked API key {key_prefix}")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error revoking API key {key_prefix}: {e}")
        return False


def get_api_usage_stats(tenant_id: str, db: Session, days: int = 30) -> Dict:
    """Get API usage statistics for a tenant."""
    try:
        tenant = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
        if not tenant:
            return {}
        
        # Get API keys
        api_keys = db.query(TenantApiKey).filter(
            TenantApiKey.tenant_id == tenant.id
        ).all()
        
        total_usage = sum(key.usage_count for key in api_keys)
        active_keys = len([key for key in api_keys if key.is_active])
        
        return {
            'tenant_id': tenant_id,
            'total_api_keys': len(api_keys),
            'active_api_keys': active_keys,
            'total_usage_count': total_usage,
            'api_keys': [
                {
                    'key_prefix': key.key_prefix,
                    'key_name': key.key_name,
                    'is_active': key.is_active,
                    'usage_count': key.usage_count,
                    'last_used_at': key.last_used_at.isoformat() if key.last_used_at else None,
                    'expires_at': key.expires_at.isoformat() if key.expires_at else None,
                    'scopes': key.scopes
                }
                for key in api_keys
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting API usage stats for tenant {tenant_id}: {e}")
        return {}


# FastAPI Security dependencies
security = HTTPBearer()

class APIKeyOrBearer:
    """Custom security class that accepts either X-API-Key header or Bearer token."""
    
    def __call__(self, request: Request) -> str:
        """Extract API key from either X-API-Key header or Authorization Bearer."""
        # First try X-API-Key header
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return api_key
        
        # Then try Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                return parts[1]
        
        # No valid API key found
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Use X-API-Key header or Authorization: Bearer token",
            headers={"WWW-Authenticate": "Bearer"}
        )

# Create instance of custom security
api_key_security = APIKeyOrBearer()

def get_current_tenant(
    api_key: str = Depends(api_key_security),
    db: Session = Depends(get_db)
) -> str:
    """
    FastAPI dependency to get current tenant from API key credentials.
    
    Args:
        api_key: API key from X-API-Key header or Bearer token
        db: Database session
        
    Returns:
        The tenant ID associated with the API key
        
    Raises:
        HTTPException: If the API key is invalid
    """
    api_key_record = APIKeyValidator().validate_api_key(api_key, db)
    
    if not api_key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key"
        )
        
    return api_key_record.tenant_id


def get_current_tenant_info(
    api_key: str = Depends(api_key_security),
    db: Session = Depends(get_db)
) -> Tenant:
    """
    FastAPI dependency to get the full Tenant object.
    
    Args:
        api_key: API key from X-API-Key header or Bearer token
        db: Database session
        
    Returns:
        The full Tenant object
        
    Raises:
        HTTPException: If the API key is invalid
    """
    api_key_record = APIKeyValidator().validate_api_key(api_key, db)
    
    if not api_key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key"
        )
        
    return api_key_record.tenant


def require_authentication(
    api_key: str = Depends(api_key_security),
    db: Session = Depends(get_db)
) -> TenantApiKey:
    """
    FastAPI dependency to require authentication and return tenant key.
    
    Args:
        api_key: API key from X-API-Key header or Bearer token
        db: Database session
        
    Returns:
        TenantApiKey object
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        # Validate API key
        validator = APIKeyValidator()
        tenant_key = validator.validate_api_key(api_key, db)
        
        if not tenant_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Check if key is expired
        if tenant_key.expires_at and tenant_key.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key has expired",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Update last used timestamp
        tenant_key.last_used_at = datetime.now(timezone.utc)
        tenant_key.usage_count += 1
        db.commit()
        
        return tenant_key
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        ) 