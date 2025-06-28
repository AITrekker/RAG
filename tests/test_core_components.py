#!/usr/bin/env python3
"""
Pytest-based tests for core RAG components.
This suite validates the fundamental functionality of services like embeddings, 
vector store, and monitoring using a structured, assertion-based approach.
"""

import pytest
from unittest.mock import patch, MagicMock
import numpy as np

# Pytest fixtures provide a reusable setup for tests.
# 'scope="module"' means the fixture is created once per test file run.

@pytest.fixture(scope="module")
def embedding_service():
    """Fixture for the embedding service."""
    from src.backend.core.embeddings import get_embedding_service
    # We can add test-specific configurations here if needed
    return get_embedding_service()

@pytest.fixture(scope="module")
def chroma_manager():
    """Fixture for the ChromaDB manager."""
    from src.backend.utils.vector_store import get_chroma_manager
    return get_chroma_manager()

@pytest.fixture
def performance_monitor():
    """Fixture to get a fresh performance monitor for each test."""
    from src.backend.utils.monitoring import get_performance_monitor
    # force_reload=True ensures a clean state for each test function.
    return get_performance_monitor(force_reload=True)

# --- Test Cases ---

def test_core_imports():
    """Test that core components can be imported without error."""
    try:
        from src.backend.config.settings import settings
        from src.backend.core.embeddings import get_embedding_service
        from src.backend.utils.vector_store import get_chroma_manager
        from src.backend.utils.monitoring import get_performance_monitor
    except ImportError as e:
        pytest.fail(f"Core component import failed: {e}")

class TestEmbeddingFunctionality:
    """Grouped tests for the EmbeddingService."""

    def test_service_initialization(self, embedding_service):
        """Test that the embedding service initializes correctly."""
        assert embedding_service is not None
        assert hasattr(embedding_service, 'model')
        assert embedding_service.model_name is not None

    def test_single_text_encoding(self, embedding_service):
        """Test encoding a single piece of text."""
        text = "This is a test sentence."
        embedding = embedding_service.encode_single_text(text)
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (embedding_service.model.get_sentence_embedding_dimension(),)

    def test_batch_text_encoding(self, embedding_service):
        """Test encoding a batch of texts."""
        texts = ["First sentence.", "Second sentence."]
        embeddings = embedding_service.encode_batch_texts(texts)
        assert isinstance(embeddings, np.ndarray)
        assert embeddings.shape == (len(texts), embedding_service.model.get_sentence_embedding_dimension())

    def test_performance_stats(self, embedding_service):
        """Test that performance statistics are tracked."""
        # Reset stats for a clean test
        embedding_service.performance_tracker.reset()
        
        embedding_service.encode_batch_texts(["one", "two"])
        stats = embedding_service.get_performance_stats()
        
        assert stats['total_texts'] == 2
        assert stats['total_batches'] == 1
        assert stats['average_batch_size'] == 2.0

class TestVectorStore:
    """Grouped tests for vector store functionality."""

    @pytest.fixture
    def test_collection(self, chroma_manager):
        """Fixture to create and clean up a test collection."""
        tenant_id = "test_vector_store_tenant"
        collection = chroma_manager.get_collection_for_tenant(tenant_id)
        yield collection
        # Teardown: clean up the collection after the test
        chroma_manager.delete_collection_for_tenant(tenant_id)

    def test_collection_creation(self, test_collection):
        """Test that a collection can be created for a tenant."""
        assert test_collection is not None
        assert "test_vector_store_tenant" in test_collection.name

    def test_document_storage_and_retrieval(self, test_collection, embedding_service):
        """Test storing a document and retrieving it via similarity search."""
        doc_id = "test_doc_1"
        doc_text = "This is a test document for vector storage."
        embedding = embedding_service.encode_single_text(doc_text)

        test_collection.add(
            ids=[doc_id],
            documents=[doc_text],
            embeddings=[embedding.tolist()],
            metadatas=[{"tenant_id": "test_vector_store_tenant"}]
        )

        query_text = "A document about storage"
        query_embedding = embedding_service.encode_single_text(query_text)
        
        results = test_collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=1,
            where={"tenant_id": "test_vector_store_tenant"}
        )

        assert results['ids'][0][0] == doc_id
        assert results['documents'][0][0] == doc_text

class TestMonitoring:
    """Grouped tests for the performance monitoring system."""

    def test_monitor_initialization(self, performance_monitor):
        """Test that the performance monitor initializes correctly."""
        assert performance_monitor is not None
        stats = performance_monitor.get_overall_stats()
        assert stats['total_operations'] == 0

    def test_metric_recording(self, performance_monitor):
        """Test that metrics are recorded correctly."""
        performance_monitor.record_metric(
            component="test_component",
            operation="test_op",
            duration=1.23,
            metadata={"key": "value"}
        )
        stats = performance_monitor.get_overall_stats()
        assert stats['total_operations'] == 1
        assert stats['total_duration'] == 1.23
        
        component_stats = performance_monitor.get_stats_by_component()
        assert "test_component" in component_stats

    def test_convenience_functions(self, performance_monitor):
        """Test the convenience functions for recording specific metrics."""
        from src.backend.utils.monitoring import record_embedding_time, record_query_time
        
        record_embedding_time(duration=0.5, model="test_model")
        record_query_time(duration=1.5, tenant_id="test_tenant")

        stats = performance_monitor.get_overall_stats()
        assert stats['total_operations'] == 2

        op_stats = performance_monitor.get_stats_by_operation()
        assert "embedding_generation" in op_stats
        assert "rag_query" in op_stats

def test_simple_end_to_end_flow(embedding_service, chroma_manager):
    """A simple end-to-end test simulating document ingestion and query."""
    tenant_id = "e2e_test_tenant"
    collection = chroma_manager.get_collection_for_tenant(tenant_id)

    try:
        # 1. Ingestion
        docs = {
            "doc1": "Python is a programming language.",
            "doc2": "The sky is blue on a clear day.",
        }
        embeddings = embedding_service.encode_batch_texts(list(docs.values()))
        
        collection.add(
            ids=list(docs.keys()),
            documents=list(docs.values()),
            embeddings=embeddings.tolist(),
            metadatas=[{"tenant_id": tenant_id}] * len(docs)
        )
        assert collection.count() == 2

        # 2. Query
        query_text = "What color is the sky?"
        query_embedding = embedding_service.encode_single_text(query_text)

        results = collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=1,
            where={"tenant_id": tenant_id}
        )

        assert results['ids'][0][0] == "doc2"

    finally:
        # Teardown: ensure the test collection is deleted
        chroma_manager.delete_collection_for_tenant(tenant_id)

if __name__ == "__main__":
    pytest.main() 