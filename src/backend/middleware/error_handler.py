"""
Basic error handling middleware.
"""

import logging
import traceback
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from src.backend.utils.error_handling import log_error_context

logger = logging.getLogger(__name__)


def setup_exception_handlers(app):
    """Setup basic exception handlers."""
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        error_context = log_error_context(
            error_type=type(exc).__name__,
            error_message=str(exc),
            endpoint=f"{request.method} {request.url.path}"
        )
        
        logger.error(f"Full traceback: {traceback.format_exc()}")
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "error_id": error_context["timestamp"]
            }
        )


async def error_tracking_middleware(request: Request, call_next):
    """Basic error tracking middleware."""
    try:
        response = await call_next(request)
        return response
    except Exception as exc:
        logger.error(f"Middleware caught error: {exc}")
        raise