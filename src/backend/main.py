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
import hashlib
from datetime import datetime, timezone, timedelta
import uuid

from src.backend.config.settings import get_settings
from src.backend.api.v1.routes import query, tenants, sync, health, audit, documents
from src.backend.core.embeddings import get_embedding_service, EmbeddingService
from src.backend.core.rag_pipeline import get_rag_pipeline
from src.backend.utils.vector_store import VectorStoreManager
from src.backend.middleware.tenant_context import TenantContextMiddleware
from src.backend.db.session import SessionLocal
from src.backend.middleware.auth import require_authentication
from src.backend.utils.monitoring import initialize_monitoring, shutdown_monitoring, monitoring_middleware
from scripts.migrate_db import run_migrations

# Configure logging from settings
settings = get_settings()
log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
logging.basicConfig(level=log_level)

# Configure SQLAlchemy logging specifically - cover all SQLAlchemy loggers
sqlalchemy_loggers = [
    'sqlalchemy.engine',
    'sqlalchemy.engine.Engine', 
    'sqlalchemy.pool',
    'sqlalchemy.dialects',
    'sqlalchemy.orm'
]
for logger_name in sqlalchemy_loggers:
    sqlalchemy_logger = logging.getLogger(logger_name)
    sqlalchemy_logger.setLevel(log_level)

logger = logging.getLogger(__name__)

# Global services that need to be initialized
embedding_service: EmbeddingService = None
vector_store_manager: VectorStoreManager = None


# Mock tenant ID function for demo purposes
async def get_current_tenant_id() -> str:
    """Mock function to return default tenant ID for demo."""
    return "default"


def create_default_tenant_and_api_key():
    """Create default tenant and API key directly in the database."""
    try:
        from src.backend.db.session import get_db
        from sqlalchemy import text
        
        db = next(get_db())
        
        # Check if default tenant exists
        result = db.execute(text("SELECT id FROM tenants WHERE tenant_id = 'default'")).fetchone()
        
        if not result:
            logger.info("Creating default tenant...")
            now = datetime.now(timezone.utc)
            
            # Create default tenant
            db.execute(text("""
                INSERT INTO tenants (
                    id, tenant_id, name, display_name, tier, isolation_level, status,
                    created_at, updated_at, max_documents, max_storage_mb,
                    max_api_calls_per_day, max_concurrent_queries, contact_email
                ) VALUES (
                    gen_random_uuid(), 'default', 'Default Tenant', 'Default Development Tenant', 
                    'basic', 'logical', 'active', :now, :now, 1000, 5000, 10000, 10, 'dev@example.com'
                )
            """), {"now": now})
            
            # Get the newly created tenant
            result = db.execute(text("SELECT id FROM tenants WHERE tenant_id = 'default'")).fetchone()
        
        if result:
            tenant_id = result[0]
            logger.info(f"Default tenant found/created with ID: {tenant_id}")
            
            # Check if API key already exists
            existing_key = db.execute(text("""
                SELECT id FROM tenant_api_keys 
                WHERE tenant_id = :tenant_id AND key_name = 'Default Dev Key'
            """), {"tenant_id": tenant_id}).fetchone()
            
            if not existing_key:
                logger.info("Creating default API key...")
                now = datetime.now(timezone.utc)
                expires_at = now + timedelta(days=365)
                
                # Hash the API key
                api_key = "dev-api-key-123"
                key_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
                
                # Insert the new API key
                db.execute(text("""
                    INSERT INTO tenant_api_keys (
                        id, tenant_id, key_name, key_hash, key_prefix, scopes, 
                        created_at, updated_at, expires_at, is_active, usage_count
                    ) VALUES (
                        gen_random_uuid(), :tenant_id, 'Default Dev Key', :key_hash, 'dev-api', 
                        '{}', :now, :now, :expires_at, true, 0
                    )
                """), {
                    "tenant_id": tenant_id,
                    "key_hash": key_hash,
                    "now": now,
                    "expires_at": expires_at
                })
                
                db.commit()
                logger.info("Default API key created successfully")
            else:
                logger.info("Default API key already exists")
        
        db.close()
        return True
        
    except Exception as e:
        logger.error(f"Failed to create default tenant and API key: {e}", exc_info=True)
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    logger.info("Starting Enterprise RAG Platform API...")
    
    # Run database migrations on startup
    logger.info("Running database migrations...")
    try:
        run_migrations()
        logger.info("Database migrations completed successfully.")
    except Exception as e:
        logger.error(f"Database migrations failed: {e}", exc_info=True)
        # Depending on the desired behavior, you might want to exit here
        # For now, we'll log the error and continue, but this is risky
    
    global embedding_service, vector_store_manager
    
    try:
        # Initialize monitoring system
        logger.info("Initializing monitoring system...")
        initialize_monitoring()
        
        # Initialize services using singleton getters
        logger.info("Initializing embedding service...")
        embedding_service = get_embedding_service()
        
        logger.info("Initializing vector store manager...")
        from src.backend.utils.vector_store import get_vector_store_manager
        
        # Register default tenant in isolation strategy
        logger.info("Registering default tenant...")
        from src.backend.core.tenant_isolation import get_tenant_isolation_strategy, TenantTier
        isolation_strategy = get_tenant_isolation_strategy()
        isolation_strategy.register_tenant("default", TenantTier.BASIC)
        logger.info("Default tenant registered in isolation strategy")
        
        vector_store_manager = get_vector_store_manager()
        
        # Store services in app state for dependency injection
        app.state.embedding_service = embedding_service
        app.state.vector_store_manager = vector_store_manager
        
        # In production, you would configure proper database session factory
        
        logger.info("API startup completed successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Enterprise RAG Platform API...")
    
    try:
        # Shutdown monitoring system
        logger.info("Shutting down monitoring system...")
        shutdown_monitoring()
        
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

# Add Tenant Context Middleware - THIS MUST BE EARLY
app.add_middleware(TenantContextMiddleware, db_session_factory=SessionLocal)

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

# Add comprehensive monitoring middleware
app.middleware("http")(monitoring_middleware)


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
    prefix="/api/v1/health",
    tags=["health"]
)

app.include_router(
    query.router,
    prefix="/api/v1/query",
    tags=["query"]
)

app.include_router(
    tenants.router,
    prefix="/api/v1/tenants",
    tags=["tenants"]
)

app.include_router(
    sync.router,
    prefix="/api/v1/sync",
    tags=["Sync"]
)

app.include_router(
    audit.router,
    prefix="/api/v1/audit",
    tags=["Audit"]
)

app.include_router(
    documents.router,
    prefix="/api/v1/documents",
    tags=["Documents"]
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