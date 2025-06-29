"""
Pytest configuration and fixtures for RAG system tests.
"""

import asyncio
import pytest
import pytest_asyncio
import sys
import os
from pathlib import Path
from uuid import UUID, uuid4
from typing import AsyncGenerator

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set environment variables for testing
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://rag_user:rag_password@localhost:5432/rag_db")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

from src.backend.database import AsyncSessionLocal
from src.backend.models.database import Tenant, User, File, EmbeddingChunk

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture
async def db_session():
    """Provide a database session for testing."""
    async with AsyncSessionLocal() as session:
        yield session

@pytest.fixture
def test_tenant_id() -> UUID:
    """Provide a consistent test tenant ID."""
    return UUID("110174a1-8e2f-47a1-af19-1478f1be07a8")

@pytest.fixture
def test_user_id() -> UUID:
    """Provide a consistent test user ID."""
    return UUID("22028462-9f3e-48b2-b048-2568f2ce17b8")

@pytest.fixture
def sample_queries():
    """Provide sample queries for testing."""
    return [
        "company mission innovation",
        "work from home remote",
        "vacation time off policy",
        "culture team learning",
        "benefits healthcare",
        "code review process",
        "agile development methodology",
        "customer feedback analysis"
    ]

@pytest.fixture
def qdrant_config():
    """Provide Qdrant configuration for testing."""
    return {
        "url": "http://localhost:6333",
        "timeout": 30,
        "collection_prefix": "tenant_"
    }

@pytest.fixture
def embedding_config():
    """Provide embedding model configuration."""
    return {
        "model_name": "sentence-transformers/all-MiniLM-L6-v2",
        "device": "cuda",  # Will fallback to CPU if not available
        "dimensions": 384,
        "batch_size": 32
    }

@pytest.fixture
def test_file_metadata():
    """Provide sample file metadata for testing."""
    return {
        "filename": "test_document.txt",
        "content": "This is a test document for the RAG system. It contains information about company policies, remote work guidelines, and team collaboration processes.",
        "mime_type": "text/plain",
        "file_size": 1024
    }

class TestConfig:
    """Test configuration constants."""
    
    # Similarity thresholds
    MIN_SCORE_THRESHOLD = 0.3
    HIGH_SCORE_THRESHOLD = 0.7
    
    # Performance expectations
    MAX_QUERY_TIME = 2.0  # seconds
    MAX_EMBEDDING_TIME = 1.0  # seconds
    MIN_GPU_SPEEDUP = 2.0  # minimum expected GPU speedup
    
    # Test data limits
    MAX_TEST_CHUNKS = 100
    MIN_RESULT_COUNT = 1
    MAX_RESULT_COUNT = 50
    
    # File paths
    TEST_DATA_DIR = project_root / "data" / "test_uploads"
    SAMPLE_FILES_DIR = project_root / "data" / "uploads"