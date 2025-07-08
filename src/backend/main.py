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

from src.backend.config.settings import get_settings
from src.backend.api.v1.routes import (
    health as health_routes,
    admin as admin_routes,
    audit as audit_routes,
    setup as setup_routes,
    tenants as tenant_routes,
    auth as auth_routes,
    files as file_routes,
    sync as sync_routes,
    query as query_routes,
    analytics as analytics_routes
)
from src.backend.utils.monitoring import initialize_monitoring, shutdown_monitoring, monitoring_middleware
from src.backend.middleware.error_handler import setup_exception_handlers, error_tracking_middleware
from src.backend.middleware.api_key_auth import api_key_auth_middleware
from src.backend.database import startup_database_checks, close_database
from src.backend.startup import wait_for_dependencies, verify_system_requirements, run_health_checks

# Import service modules for initialization
from src.backend.services.tenant_service import TenantService
from src.backend.services.file_service import FileService
from src.backend.services.embedding_service import EmbeddingService
from src.backend.services.sync_service import SyncService
from src.backend.services.rag_service import RAGService

settings = get_settings()
log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)

# Service instances
tenant_service: TenantService = None
file_service: FileService = None
embedding_service: EmbeddingService = None
sync_service: SyncService = None
rag_service: RAGService = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    logger.info("🚀 Starting Enterprise RAG Platform API...")
    
    global tenant_service, file_service, embedding_service, sync_service, rag_service
    
    try:
        # Step 1: Wait for external dependencies
        logger.info("🔍 Waiting for external dependencies...")
        deps_success, deps_error = wait_for_dependencies()
        if not deps_success:
            logger.error(f"❌ Dependency check failed: {deps_error}")
            raise RuntimeError(f"Failed to connect to dependencies: {deps_error}")
        
        # Step 2: Verify system requirements
        logger.info("🔍 Verifying system requirements...")
        req_success, req_error = verify_system_requirements()
        if not req_success:
            logger.error(f"❌ System requirements check failed: {req_error}")
            raise RuntimeError(f"System requirements not met: {req_error}")
        
        # Step 3: Run health checks
        logger.info("🏥 Running health checks...")
        health_success, health_results = await run_health_checks()
        if not health_success:
            logger.error("❌ Health checks failed!")
            for check_name, result in health_results.items():
                if not result["success"]:
                    logger.error(f"   {check_name}: {result['message']}")
            raise RuntimeError("Health checks failed")
        
        # Step 4: Original database startup checks and service initialization
        logger.info("🗄️ Running database startup checks...")
        await startup_database_checks()
        
        # Step 5: Initialize monitoring system
        logger.info("📊 Initializing monitoring system...")
        initialize_monitoring()
        
        # Step 6: Initialize service architecture
        logger.info("⚙️ Initializing service layer...")
        from src.backend.database import get_async_db
        
        # Get database session for service initialization
        async for db in get_async_db():
            # Initialize core services
            tenant_service = TenantService(db)
            file_service = FileService(db)
            embedding_service = EmbeddingService(db)
            
            # Initialize services with dependencies
            sync_service = SyncService(db, file_service, embedding_service)
            rag_service = RAGService(db, file_service)
            
            # Initialize services that need async setup
            await embedding_service.initialize()
            await rag_service.initialize()
            
            logger.info("Service layer initialized successfully")
            break  # Only need first session for initialization
        
        # Set app state for services
        app.state.tenant_service = tenant_service
        app.state.file_service = file_service
        app.state.embedding_service = embedding_service
        app.state.sync_service = sync_service
        app.state.rag_service = rag_service
        
        logger.info("🎉 API startup completed successfully!")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}", exc_info=True)
        raise
    
    yield
    
    logger.info("Shutting down Enterprise RAG Platform API...")
    try:
        logger.info("Closing database connections...")
        await close_database()
        
        logger.info("Shutting down monitoring system...")
        shutdown_monitoring()
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
app.middleware("http")(monitoring_middleware)
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

# Core API routes
app.include_router(health_routes.router, prefix=f"{settings.api_v1_str}/health", tags=["Health"])
app.include_router(auth_routes.router, prefix=f"{settings.api_v1_str}/auth", tags=["Authentication"])
app.include_router(setup_routes.router, prefix=f"{settings.api_v1_str}/setup", tags=["Setup"])
app.include_router(admin_routes.router, prefix=f"{settings.api_v1_str}/admin", tags=["Admin"])
app.include_router(audit_routes.router, prefix=f"{settings.api_v1_str}/audit", tags=["Audit"])
app.include_router(tenant_routes.router, prefix=f"{settings.api_v1_str}/tenants", tags=["Tenants"])

# Service-based routes
app.include_router(file_routes.router, prefix=f"{settings.api_v1_str}/files", tags=["Files"])
app.include_router(sync_routes.router, prefix=f"{settings.api_v1_str}/sync", tags=["Sync"])
app.include_router(query_routes.router, prefix=f"{settings.api_v1_str}/query", tags=["Query"])
app.include_router(analytics_routes.router, prefix=f"{settings.api_v1_str}/analytics", tags=["Analytics"])

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