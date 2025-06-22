"""
Main FastAPI application for the Enterprise RAG Platform.

This module sets up the FastAPI application with all necessary middleware,
CORS configuration, and API routes.
"""

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
import time
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from .config.settings import get_settings
from .api.v1.routes import query, tenants, sync, health, audit
from .core.embeddings import get_embedding_service, EmbeddingService
from .core.rag_pipeline import get_rag_pipeline
from .utils.vector_store import VectorStoreManager
from .middleware.tenant_context import TenantContextMiddleware
from .middleware.auth import require_authentication

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

# Global services that need to be initialized
embedding_service: EmbeddingService = None
vector_store_manager: VectorStoreManager = None


# Mock tenant ID function for demo purposes
async def get_current_tenant_id() -> str:
    """Mock function to return default tenant ID for demo."""
    return "default"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    logger.info("Starting Enterprise RAG Platform API...")
    
    global embedding_service, vector_store_manager
    
    try:
        # Initialize services using singleton getters
        logger.info("Initializing embedding service...")
        embedding_service = get_embedding_service()
        
        logger.info("Initializing vector store manager...")
        from .utils.vector_store import get_vector_store_manager
        vector_store_manager = get_vector_store_manager()
        
        # Store services in app state for dependency injection
        app.state.embedding_service = embedding_service
        app.state.vector_store_manager = vector_store_manager
        
        logger.info("API startup completed successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Enterprise RAG Platform API...")
    
    try:
        # Cleanup services if needed
        if embedding_service:
            # Add any cleanup logic for embedding service
            pass
            
        if vector_store_manager:
            # Add any cleanup logic for vector store
            pass
            
        logger.info("API shutdown completed successfully")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Create FastAPI application
app = FastAPI(
    title="Enterprise RAG Platform API",
    description="A multi-tenant RAG platform for enterprise document search and retrieval",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Trusted Host Middleware (security)
if not settings.debug:
    app.add_middleware(
        TrustedHostMiddleware, 
        allowed_hosts=settings.allowed_hosts
    )

# Note: TenantContextMiddleware temporarily disabled for demo purposes
# In production, you would configure proper database session factory
# app.add_middleware(TenantContextMiddleware, db_session_factory=get_db_session)


# Performance monitoring middleware
@app.middleware("http")
async def performance_middleware(request: Request, call_next):
    """Monitor API performance and log slow requests."""
    start_time = time.time()
    
    # Add request ID for tracing
    request_id = f"{int(time.time() * 1000)}-{hash(request.url.path) % 10000}"
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    
    # Log performance metrics
    logger.info(
        f"Request {request_id}: {request.method} {request.url.path} "
        f"completed in {process_time:.3f}s with status {response.status_code}"
    )
    
    # Warn about slow requests
    if process_time > 5.0:  # 5 second threshold
        logger.warning(
            f"Slow request detected: {request.method} {request.url.path} "
            f"took {process_time:.3f}s"
        )
    
    # Add performance headers
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-Request-ID"] = request_id
    
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again later.",
            "request_id": getattr(request.state, "request_id", "unknown")
        }
    )


# HTTP Exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with proper logging."""
    logger.warning(f"HTTP {exc.status_code}: {exc.detail} for {request.url.path}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "request_id": getattr(request.state, "request_id", "unknown")
        }
    )


# Dependency injection for services
def get_embedding_service_dependency() -> EmbeddingService:
    """Dependency to get the embedding service."""
    if hasattr(app.state, 'embedding_service') and app.state.embedding_service is not None:
        return app.state.embedding_service
    # Fallback to singleton if not in app state
    return get_embedding_service()


def get_vector_store_manager_dependency() -> VectorStoreManager:
    """Dependency to get the vector store manager."""
    if hasattr(app.state, 'vector_store_manager') and app.state.vector_store_manager is not None:
        return app.state.vector_store_manager
    # Fallback to singleton if not in app state
    from .utils.vector_store import get_vector_store_manager
    return get_vector_store_manager()


# Include API routes
app.include_router(
    health.router,
    prefix="/api/v1",
    tags=["health"]
)

app.include_router(
    query.router,
    prefix="/api/v1",
    tags=["query"]
)

app.include_router(
    tenants.router,
    prefix="/api/v1",
    tags=["tenants"]
)

app.include_router(
    sync.router,
    prefix="/api/v1/sync",
    tags=["Sync"],
    dependencies=[Depends(require_authentication)]
)

app.include_router(
    audit.router,
    prefix="/api/v1/audit",
    tags=["Audit"],
    dependencies=[Depends(require_authentication)]
)


# Custom OpenAPI schema
def custom_openapi():
    """Generate custom OpenAPI schema with additional information."""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Enterprise RAG Platform API",
        version="1.0.0",
        description="""
        ## Enterprise RAG Platform API
        
        A multi-tenant Retrieval-Augmented Generation platform for enterprise document search and retrieval.
        
        ### Features
        - Multi-tenant document isolation
        - Natural language query processing
        - Source citation and relevance scoring
        - Real-time document synchronization
        - Performance monitoring and analytics
        
        ### Authentication
        API key authentication is required for all endpoints except health checks.
        Include your API key in the `X-API-Key` header.
        
        ### Rate Limiting
        API requests are rate-limited per tenant. See the response headers for current limits.
        """,
        routes=app.routes,
    )
    
    # Add security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "APIKeyHeader": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key"
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# Root endpoint
@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint with basic API information."""
    return {
        "message": "Welcome to the Enterprise RAG Platform API",
        "version": settings.version,
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }


if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting server on {settings.host}:{settings.port}")
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=settings.reload_on_change
    ) 