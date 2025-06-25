"""
API v1 module.

This module provides the main API router for version 1 of the RAG Platform API.
"""

from fastapi import APIRouter

from .routes import api_router

# Create the main v1 router
router = APIRouter(prefix="/v1")

# Include all routes
router.include_router(api_router)

__all__ = ["router"] 