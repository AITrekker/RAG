"""
FastAPI exception handler middleware for standardized error handling.

This module provides:
- Global exception handlers for all API endpoints
- Automatic error logging and monitoring
- Standardized error responses
- Request context tracking
"""

import logging
import traceback
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError

from ..utils.error_handling import (
    handle_exception,
    log_error,
    RAGPlatformException,
    ErrorCode,
    ErrorSeverity,
    create_error_response
)

logger = logging.getLogger(__name__)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTPException errors."""
    tenant_id = _extract_tenant_id(request)
    endpoint = f"{request.method} {request.url.path}"
    
    # Log the error
    log_error(exc, tenant_id, endpoint)
    
    # Create standardized error response
    error_response = create_error_response(
        message=exc.detail if isinstance(exc.detail, str) else "HTTP error occurred",
        error_code=ErrorCode.INTERNAL_ERROR,
        status_code=exc.status_code,
        tenant_id=tenant_id
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic validation errors."""
    tenant_id = _extract_tenant_id(request)
    endpoint = f"{request.method} {request.url.path}"
    
    # Log the validation error
    log_error(exc, tenant_id, endpoint)
    
    # Create detailed validation error response
    validation_errors = []
    for error in exc.errors():
        validation_errors.append({
            "field": " -> ".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    error_response = create_error_response(
        message="Input validation failed",
        error_code=ErrorCode.VALIDATION_ERROR,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        details={"validation_errors": validation_errors},
        tenant_id=tenant_id
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response
    )


async def pydantic_validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Handle Pydantic model validation errors."""
    tenant_id = _extract_tenant_id(request)
    endpoint = f"{request.method} {request.url.path}"
    
    # Log the validation error
    log_error(exc, tenant_id, endpoint)
    
    # Create detailed validation error response
    validation_errors = []
    for error in exc.errors():
        validation_errors.append({
            "field": " -> ".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    error_response = create_error_response(
        message="Model validation failed",
        error_code=ErrorCode.VALIDATION_ERROR,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        details={"validation_errors": validation_errors},
        tenant_id=tenant_id
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response
    )


async def rag_platform_exception_handler(request: Request, exc: RAGPlatformException) -> JSONResponse:
    """Handle RAG Platform specific exceptions."""
    tenant_id = _extract_tenant_id(request)
    endpoint = f"{request.method} {request.url.path}"
    
    # Log the error
    log_error(exc, tenant_id, endpoint)
    
    # Return the standardized error response
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all other exceptions."""
    tenant_id = _extract_tenant_id(request)
    endpoint = f"{request.method} {request.url.path}"
    
    # Log the error with full traceback
    logger.error(f"Unhandled exception in {endpoint}: {str(exc)}")
    logger.error(f"Full traceback: {traceback.format_exc()}")
    
    # Create internal error response
    error_response = create_error_response(
        message="An unexpected error occurred",
        error_code=ErrorCode.INTERNAL_ERROR,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        details={"original_error": str(exc)},
        tenant_id=tenant_id
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response
    )


def _extract_tenant_id(request: Request) -> Optional[str]:
    """Extract tenant ID from request context."""
    try:
        # Try to get tenant ID from request state (set by auth middleware)
        if hasattr(request.state, 'tenant_id'):
            return request.state.tenant_id
        
        # Try to get from headers
        tenant_header = request.headers.get('X-Tenant-ID')
        if tenant_header:
            return tenant_header
        
        # Try to get from query parameters
        tenant_param = request.query_params.get('tenant_id')
        if tenant_param:
            return tenant_param
        
        return None
    except Exception:
        return None


def setup_exception_handlers(app):
    """Setup all exception handlers for the FastAPI app."""
    
    # Register exception handlers
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)
    app.add_exception_handler(RAGPlatformException, rag_platform_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    
    logger.info("Exception handlers registered successfully")


# Middleware for request context tracking
async def error_tracking_middleware(request: Request, call_next):
    """Middleware to track request context for error handling."""
    # Add request start time
    request.state.start_time = request.headers.get('X-Request-Start-Time')
    
    # Add request ID for tracking
    request_id = request.headers.get('X-Request-ID')
    if not request_id:
        request_id = f"req_{id(request)}"
    request.state.request_id = request_id
    
    try:
        response = await call_next(request)
        return response
    except Exception as exc:
        # Log additional context for errors
        logger.error(f"Request failed: {request.method} {request.url.path}")
        logger.error(f"Request ID: {request.state.request_id}")
        logger.error(f"Headers: {dict(request.headers)}")
        raise 