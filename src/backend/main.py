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
from src.backend.api.v1.routes import query, sync, health, audit, documents
from src.backend.core.embeddings import get_embedding_service, EmbeddingService
from src.backend.utils.vector_store import get_vector_store_manager
from src.backend.utils.monitoring import initialize_monitoring, shutdown_monitoring, monitoring_middleware
from src.backend.middleware.tenant_context import TenantHeaderMiddleware

settings = get_settings()
log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)

embedding_service: EmbeddingService = None
vector_store_manager: VectorStoreManager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    logger.info("Starting Enterprise RAG Platform API...")
    
    global embedding_service, vector_store_manager
    
    try:
        logger.info("Initializing monitoring system...")
        initialize_monitoring()
        
        logger.info("Initializing embedding service...")
        embedding_service = get_embedding_service()
        logger.info("Embedding service initialized.")
        
        logger.info("Initializing vector store manager...")
        vector_store_manager = get_vector_store_manager()
        logger.info("Vector store manager initialized.")
        
        app.state.embedding_service = embedding_service
        app.state.vector_store_manager = vector_store_manager
        
        logger.info("API startup completed successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}", exc_info=True)
        raise
    
    yield
    
    logger.info("Shutting down Enterprise RAG Platform API...")
    try:
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

app.add_middleware(TenantHeaderMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.middleware("http")(monitoring_middleware)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred."},
    )

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

app.include_router(health.router, prefix=f"{settings.api_v1_str}/health", tags=["Health"])
app.include_router(query.router, prefix=f"{settings.api_v1_str}/query", tags=["Query"])
app.include_router(documents.router, prefix=f"{settings.api_v1_str}/documents", tags=["Documents"])
app.include_router(sync.router, prefix=f"{settings.api_v1_str}/sync", tags=["Sync"])
app.include_router(audit.router, prefix=f"{settings.api_v1_str}/audit", tags=["Audit"])

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