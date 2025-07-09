"""
FastAPI Dependencies - Service injection and dependency management
"""

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from functools import lru_cache

from src.backend.database import get_async_db
from src.backend.models.database import Tenant
from src.backend.services.tenant_service import TenantService
from src.backend.services.file_service import FileService
from src.backend.services.embedding_service import EmbeddingService
from src.backend.services.sync_service import SyncService
from src.backend.services.rag_service import RAGService
from src.backend.middleware.api_key_auth import get_current_tenant
from src.backend.config.settings import get_settings


# Database dependency
async def get_db() -> AsyncSession:
    """Get database session"""
    async for session in get_async_db():
        yield session


# Singleton embedding model dependency
@lru_cache()
def get_embedding_model():
    """Get singleton embedding model instance - cached across all requests"""
    try:
        from sentence_transformers import SentenceTransformer
        settings = get_settings()
        
        print(f"🤖 Loading embedding model: {settings.embedding_model}")
        model = SentenceTransformer(settings.embedding_model)
        print(f"✓ Embedding model loaded successfully")
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
    embedding_model = Depends(get_embedding_model)
) -> EmbeddingService:
    """Get embedding service with singleton model"""
    service = EmbeddingService(db, embedding_model)
    # No need to call initialize() since model is injected
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
    file_service: FileService = Depends(get_file_service_dep)
) -> RAGService:
    """Get RAG service with dependencies"""
    service = RAGService(db, file_service)
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