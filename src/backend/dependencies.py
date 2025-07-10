"""
FastAPI Dependencies - Service injection and dependency management
"""

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from functools import lru_cache

from src.backend.database import get_async_db, AsyncSessionLocal
from src.backend.models.database import Tenant
from src.backend.services.tenant_service import TenantService
from src.backend.services.file_service import FileService
from src.backend.services.embedding_service import EmbeddingService
from src.backend.services.sync_service import SyncService
from src.backend.services.rag_service import RAGService
# Removed transactional embedding service to simplify
from src.backend.middleware.api_key_auth import get_current_tenant
from src.backend.config.settings import get_settings


# Singleton Qdrant client dependency
@lru_cache(maxsize=1)
def get_qdrant_client():
    """Get singleton Qdrant client instance - cached across all requests"""
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams
        
        settings = get_settings()
        
        print(f"🔢 Initializing Qdrant client: {settings.qdrant_host}:{settings.qdrant_port}")
        
        client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            api_key=settings.qdrant_api_key if hasattr(settings, 'qdrant_api_key') else None,
            https=False,  # Force HTTP connection for local Qdrant
            timeout=30
        )
        
        print(f"✓ Qdrant client initialized successfully")
        return client
        
    except ImportError:
        print("⚠️ qdrant-client not available, returning None")
        return None
    except Exception as e:
        print(f"❌ Failed to initialize Qdrant client: {e}")
        return None


# Database dependency with connection monitoring
async def get_db():
    """Get database session for FastAPI dependency injection with monitoring"""
    session = None
    try:
        from sqlalchemy import text
        session = AsyncSessionLocal()
        # Set session-level timeout
        await session.execute(text("SET statement_timeout = '120s'"))  # 2 minutes for API operations
        yield session
    except Exception as e:
        if session:
            try:
                await session.rollback()
            except Exception:
                # Ignore rollback errors if session is already closed
                pass
        # Log connection pool issues
        from src.backend.database import async_engine
        pool = async_engine.pool
        if pool.checkedout() > 25:  # Warning threshold
            print(f"⚠️ High connection usage: {pool.checkedout()}/80 connections in use")
        raise e
    finally:
        if session:
            try:
                await session.close()
            except Exception:
                # Ignore close errors - session may already be closed or invalid
                pass


# Direct session access for non-dependency usage
async def get_db_session() -> AsyncSession:
    """Get database session directly (not for FastAPI dependencies)"""
    return AsyncSessionLocal()


# Singleton embedding model dependency with proper memory management
@lru_cache(maxsize=1)
def get_embedding_model():
    """Get singleton embedding model instance - cached across all requests"""
    try:
        from sentence_transformers import SentenceTransformer
        import torch
        settings = get_settings()
        
        print(f"🤖 Loading embedding model: {settings.embedding_model}")
        
        # Use GPU if available, otherwise CPU
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        model = SentenceTransformer(settings.embedding_model, device=device)
        
        # Clear any existing CUDA cache
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        print(f"✓ Embedding model loaded successfully on {device}")
        return model
        
    except Exception as e:
        print(f"❌ Failed to load embedding model: {e}")
        raise


# Service dependencies
async def get_tenant_service_dep(
    db: AsyncSession = Depends(get_db)
) -> TenantService:
    """Get tenant service"""
    return TenantService(db)


async def get_file_service_dep(
    db: AsyncSession = Depends(get_db)
) -> FileService:
    """Get file service"""
    return FileService(db)


async def get_embedding_service_dep(
    db: AsyncSession = Depends(get_db),
    embedding_model = Depends(get_embedding_model),
    qdrant_client = Depends(get_qdrant_client)
) -> EmbeddingService:
    """Get embedding service with singleton model and Qdrant client"""
    service = EmbeddingService(db, embedding_model, qdrant_client)
    # No need to call initialize() since dependencies are injected
    return service


async def get_sync_service_dep(
    db: AsyncSession = Depends(get_db),
    file_service: FileService = Depends(get_file_service_dep),
    embedding_service: EmbeddingService = Depends(get_embedding_service_dep)
) -> SyncService:
    """Get sync service with dependencies"""
    return SyncService(db, file_service, embedding_service)


async def get_rag_service_dep(
    db: AsyncSession = Depends(get_db),
    file_service: FileService = Depends(get_file_service_dep),
    qdrant_client = Depends(get_qdrant_client),
    embedding_model = Depends(get_embedding_model)
) -> RAGService:
    """Get RAG service with dependencies"""
    service = RAGService(db, file_service, qdrant_client, embedding_model)
    await service.initialize()
    return service


# Authentication dependencies
def get_current_tenant_dep(request: Request) -> Tenant:
    """Get current authenticated tenant"""
    return get_current_tenant(request)


def get_current_tenant_id(request: Request) -> str:
    """Get current tenant ID"""
    tenant = get_current_tenant(request)
    return str(tenant.id)


# Combined service bundle for complex operations
class ServiceBundle:
    """Bundle of all services for complex operations"""
    
    def __init__(
        self,
        db: AsyncSession,
        tenant_service: TenantService,
        file_service: FileService,
        embedding_service: EmbeddingService,
        sync_service: SyncService,
        rag_service: RAGService
    ):
        self.db = db
        self.tenant_service = tenant_service
        self.file_service = file_service
        self.embedding_service = embedding_service
        self.sync_service = sync_service
        self.rag_service = rag_service


async def get_service_bundle(
    db: AsyncSession = Depends(get_db),
    tenant_service: TenantService = Depends(get_tenant_service_dep),
    file_service: FileService = Depends(get_file_service_dep),
    embedding_service: EmbeddingService = Depends(get_embedding_service_dep),
    sync_service: SyncService = Depends(get_sync_service_dep),
    rag_service: RAGService = Depends(get_rag_service_dep)
) -> ServiceBundle:
    """Get bundle of all services"""
    return ServiceBundle(
        db=db,
        tenant_service=tenant_service,
        file_service=file_service,
        embedding_service=embedding_service,
        sync_service=sync_service,
        rag_service=rag_service
    )