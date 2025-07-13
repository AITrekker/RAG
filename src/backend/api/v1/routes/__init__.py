"""
Simplified API routes initialization.

This module imports and registers core API route modules for teaching.
"""

from fastapi import APIRouter

from .admin import router as admin_router
from .sync import router as sync_router
from .query import router as query_router

# Create main API router
api_router = APIRouter()

# Include core route modules only
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(sync_router, prefix="/sync", tags=["sync"])
api_router.include_router(query_router, prefix="/query", tags=["query"])

# Export the main router
__all__ = ["api_router"] 