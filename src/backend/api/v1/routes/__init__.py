"""
API routes initialization.

This module imports and registers all API route modules.
"""

from fastapi import APIRouter

from .setup import router as setup_router
from .admin import router as admin_router
from .sync import router as sync_router
from .query import router as query_router
from .health import router as health_router
from .consistency import router as consistency_router
from .embeddings import router as embeddings_router

# Create main API router
api_router = APIRouter()

# Include all route modules
api_router.include_router(setup_router)
api_router.include_router(admin_router)
api_router.include_router(sync_router)
api_router.include_router(query_router)
api_router.include_router(health_router)
api_router.include_router(consistency_router)
api_router.include_router(embeddings_router, prefix="/embeddings", tags=["embeddings"])

# Export the main router
__all__ = ["api_router"] 