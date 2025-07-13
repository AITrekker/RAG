"""
FastAPI Dependencies - Service injection and dependency management
"""

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from functools import lru_cache

from src.backend.database import get_async_db, AsyncSessionLocal
from src.backend.models.database import Tenant
# Services removed - using simplified core modules now
from src.backend.middleware.api_key_auth import get_current_tenant
from src.backend.config.settings import get_settings


# Database dependency with connection monitoring
async def get_db():
    """Get database session for FastAPI dependency injection with monitoring"""
    session = None
    try:
        from sqlalchemy import text
        session = AsyncSessionLocal()
        # Timeout removed - was causing hangs
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


# Direct session access for non-dependency usage - USE CONTEXT MANAGER
def get_db_session():
    """Get database session context manager for direct usage"""
    return AsyncSessionLocal()


# Singleton embedding model dependency with proper memory management
@lru_cache(maxsize=1)
def get_embedding_model():
    """Get singleton embedding model instance - cached across all requests"""
    try:
        from sentence_transformers import SentenceTransformer
        import torch
        import os
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


# Service dependencies removed - using core modules directly


# Old complex service dependencies removed
# Now using simplified core modules directly in endpoints


# Singleton LLM model with FastAPI caching (keeps performance, removes complexity)
@lru_cache(maxsize=1)
def get_llm_model():
    """Get singleton LLM model instance - cached across all requests"""
    try:
        from transformers import pipeline
        import torch
        settings = get_settings()
        
        print(f"🧠 Loading LLM model: {settings.rag_llm_model}")
        
        # Use GPU if available, otherwise CPU
        device = 0 if torch.cuda.is_available() else -1
        
        # Create text generation pipeline with configurable settings
        llm_config = settings.get_rag_llm_config()
        model = pipeline(
            "text-generation",
            model=settings.rag_llm_model,
            device=device,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            max_length=llm_config["max_length"],
            truncation=True,
            do_sample=llm_config["do_sample"],
            temperature=llm_config["temperature"],
            top_p=llm_config["top_p"],
            top_k=llm_config["top_k"],
            repetition_penalty=llm_config["repetition_penalty"],
            pad_token_id=50256  # GPT-2 EOS token
        )
        
        print(f"✓ LLM model loaded successfully on {'GPU' if device == 0 else 'CPU'}")
        return model
        
    except Exception as e:
        print(f"❌ Failed to load LLM model: {e}")
        # Return None to allow graceful degradation
        return None


# Removed complex RAG service dependency - using simplified core modules


# Authentication dependencies
def get_current_tenant_dep(request: Request) -> Tenant:
    """Get current authenticated tenant"""
    return get_current_tenant(request)


def get_current_tenant_id(request: Request) -> str:
    """Get current tenant ID"""
    tenant = get_current_tenant(request)
    return str(tenant.slug)


