"""
Basic error handling utilities.
"""

import logging
from typing import Dict, Any
from datetime import datetime
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class ResourceNotFoundError(Exception):
    """Resource not found error."""
    pass


class ValidationError(Exception):
    """Validation error."""
    pass


def log_error_context(
    error_type: str,
    error_message: str,
    tenant_id: str = None,
    endpoint: str = None,
    **kwargs
) -> Dict[str, Any]:
    """Log error with context information."""
    
    error_context = {
        "error_type": error_type,
        "error_message": error_message,
        "tenant_id": tenant_id,
        "endpoint": endpoint,
        "timestamp": datetime.utcnow().isoformat(),
        **kwargs
    }
    
    logger.error(f"Error occurred: {error_context}")
    return error_context


def handle_exception(exc: Exception, tenant_id: str = None, endpoint: str = None):
    """Handle exception with logging."""
    log_error_context(
        error_type=type(exc).__name__,
        error_message=str(exc),
        tenant_id=tenant_id,
        endpoint=endpoint
    )
    
    if isinstance(exc, ResourceNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc))
    elif isinstance(exc, ValidationError):
        raise HTTPException(status_code=422, detail=str(exc))
    else:
        raise HTTPException(status_code=500, detail="Internal server error")


def not_found_error(message: str, tenant_id: str = None):
    """Create not found error."""
    raise HTTPException(status_code=404, detail=message)


def validation_error(message: str, tenant_id: str = None):
    """Create validation error."""
    raise HTTPException(status_code=422, detail=message)


def internal_error(message: str, tenant_id: str = None):
    """Create internal error."""
    raise HTTPException(status_code=500, detail=message)