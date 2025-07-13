"""
Main FastAPI application for the Enterprise RAG Platform.

This module sets up the FastAPI application with all necessary middleware,
CORS configuration, and API routes.
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
import logging
from contextlib import asynccontextmanager
import asyncio

from src.backend.config.settings import get_settings
from src.backend.api.v1.routes import api_router
from src.backend.middleware.error_handler import setup_exception_handlers, error_tracking_middleware
from src.backend.middleware.api_key_auth import api_key_auth_middleware
from src.backend.database import startup_database_checks, close_database
from src.backend.startup import wait_for_dependencies, verify_system_requirements, reload_environment_variables

settings = get_settings()
log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)

# Service instances removed - using simplified dependency injection

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    logger.info("🚀 Starting Enterprise RAG Platform API...")
    
    try:
        # Step 1: Wait for external dependencies
        logger.info("🔍 Waiting for external dependencies...")
        deps_success, deps_error = wait_for_dependencies()
        if not deps_success:
            logger.error(f"❌ Dependency check failed: {deps_error}")
            raise RuntimeError(f"Failed to connect to dependencies: {deps_error}")
        
        # Step 2: Reload environment variables (init container may have updated .env)
        logger.info("🔄 Reloading environment variables for init container updates...")
        reload_environment_variables()
        
        # Step 3: Verify system requirements
        logger.info("🔍 Verifying system requirements...")
        req_success, req_error = verify_system_requirements()
        if not req_success:
            logger.error(f"❌ System requirements check failed: {req_error}")
            raise RuntimeError(f"System requirements not met: {req_error}")
        
        # Step 4: Database startup checks
        logger.info("🗄️ Running database startup checks...")
        try:
            await startup_database_checks()
        except Exception as e:
            logger.error(f"❌ Database startup failed: {e}")
            logger.warning("⚠️ Continuing despite database startup issues (debugging mode)")
        
        logger.info("🎉 API startup completed successfully!")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}", exc_info=True)
        raise
    
    yield
    
    logger.info("Shutting down Enterprise RAG Platform API...")
    try:        
        logger.info("Closing database connections...")
        await close_database()
        
        logger.info("API shutdown completed successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


app = FastAPI(
    title=settings.project_name,
    description="Enterprise-grade RAG platform.",
    version="1.0.0",
    lifespan=lifespan,
    openapi_url=f"{settings.api_v1_str}/openapi.json"
)

# Add CORS middleware FIRST - must be before other middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Setup comprehensive error handling
setup_exception_handlers(app)

app.middleware("http")(api_key_auth_middleware)
app.middleware("http")(error_tracking_middleware)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    openapi_schema["info"]["x-logo"] = {
        "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Simplified API routes
app.include_router(api_router, prefix=settings.api_v1_str)

@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Enterprise RAG Platform API is running."}


if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting server on {settings.host}:{settings.port}")
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=settings.reload_on_change
    ) 