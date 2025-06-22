"""
Pytest-based test suite for the Document Processing foundation.

This module provides comprehensive tests for all components of the document 
processing system using pytest fixtures and assertions.
"""

import os
import tempfile
import shutil
import uuid
from pathlib import Path

import pytest
from unittest.mock import patch, MagicMock

# It's better to manage the python path using pytest's features or by running
# pytest from the project root, but for now, we keep this pattern for consistency.
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import components to be tested
from src.backend.models.document import (
    Document, DocumentChunk, DocumentStatus,
    create_document_from_file, create_document_chunk
)
from src.backend.core.document_processor import (
    DocumentProcessor, ChunkingConfig, ProcessingResult,
    create_default_processor, create_optimized_processor
)
from src.backend.core.document_ingestion import DocumentIngestionPipeline
from src.backend.utils.file_monitor import (
    FileMonitor, MonitorConfig
)


# --- Fixtures ---

@pytest.fixture(scope="module")
def test_environment():
    """
    Creates a temporary directory with test files for the test module.
    Yields the directory path and cleans up afterward.
    """
    test_dir = Path(tempfile.mkdtemp(prefix="rag_doc_test_"))
        
        # Create test files
    (test_dir / "test.txt").write_text("This is a simple text file for testing.")
    (test_dir / "test.html").write_text("<html><head><title>Test HTML</title></head><body><p>Hello</p></body></html>")
    (test_dir / "unsupported.dat").write_text("Unsupported file content.")
    
    yield test_dir
    
    # Teardown
    shutil.rmtree(test_dir)

@pytest.fixture
def tenant_id():
    """Provides a consistent, unique tenant ID for a test run."""
    return str(uuid.uuid4())

# --- Test Classes ---

class TestDocumentModels:
    """Tests for the document data models and utility functions."""

    def test_create_document_from_file(self, tenant_id, test_environment):
        """Test the creation of a Document object from a file path."""
        file_path = test_environment / "test.txt"
        doc = create_document_from_file(
            tenant_id=tenant_id,
            file_path=str(file_path),
            filename=file_path.name,
            file_size=file_path.stat().st_size,
            file_hash="dummy_hash"
        )
        assert isinstance(doc, Document)
        assert doc.tenant_id == uuid.UUID(tenant_id)
        assert doc.filename == "test.txt"
        assert doc.status == DocumentStatus.PENDING.value
        assert doc.to_dict()['filename'] == "test.txt"

    def test_create_document_chunk(self, tenant_id):
        """Test the creation of a DocumentChunk object."""
        doc_id = str(uuid.uuid4())
        chunk = create_document_chunk(
            document_id=doc_id,
            tenant_id=tenant_id,
            content="This is a test chunk.",
            chunk_index=1
        )
        assert isinstance(chunk, DocumentChunk)
        assert chunk.document_id == uuid.UUID(doc_id)
        assert chunk.chunk_index == 1
        assert chunk.token_count > 0
        assert chunk.to_dict()['chunk_index'] == 1


class TestDocumentProcessor:
    """Tests for the DocumentProcessor."""

    @pytest.fixture
    def default_processor(self):
        return create_default_processor()

    def test_initialization(self, default_processor):
        """Test the default and optimized processor factories."""
        assert default_processor is not None
        assert isinstance(default_processor.chunking_config, ChunkingConfig)
        
        optimized = create_optimized_processor(chunk_size=200, overlap=20)
        assert optimized.chunking_config.chunk_size == 200

    def test_file_support(self, default_processor, test_environment):
        """Test the is_supported_file method."""
        assert default_processor.is_supported_file(str(test_environment / "test.txt"))
        assert default_processor.is_supported_file(str(test_environment / "test.html"))
        assert not default_processor.is_supported_file(str(test_environment / "unsupported.dat"))

    def test_text_file_processing(self, default_processor, tenant_id, test_environment):
        """Test processing a simple .txt file."""
        file_path = str(test_environment / "test.txt")
        result = default_processor.process_file(file_path, tenant_id)
        
        assert isinstance(result, ProcessingResult)
        assert result.success
        assert result.document is not None
        assert result.document.status == DocumentStatus.COMPLETED.value
        assert len(result.chunks) > 0
        assert "processing_time_seconds" in result.processing_metadata

    def test_html_file_processing(self, default_processor, tenant_id, test_environment):
        """Test processing an .html file, including content cleaning."""
        file_path = str(test_environment / "test.html")
        result = default_processor.process_file(file_path, tenant_id)
        
        assert result.success
        assert result.document.document_type == "HTML"
        # The title is not extracted by default in the current implementation, so we don't test it.
        # This highlights a potential area for future improvement.
        
        # Check if basic content is extracted
        content_preview = " ".join(c.content for c in result.chunks)
        assert "Hello" in content_preview


class TestChunkingStrategy:
    """Tests for the chunking logic."""

    def test_fixed_size_chunking(self):
        """Test the behavior of the fixed-size chunker."""
        # This test would require a mockable chunking utility.
        # The current implementation in DocumentProcessor is tightly coupled.
        # For now, this is tested implicitly via TestDocumentProcessor.
        # A refactor would make this unit test possible.
        pass


class TestDocumentIngestionPipeline:
    """Tests for the end-to-end document ingestion pipeline."""

    @pytest.fixture
    def mock_dependencies(self, tenant_id):
        """Mock external dependencies for the ingestion pipeline."""
        with patch('src.backend.core.document_ingestion.VectorStoreManager') as MockVectorStoreManager, \
             patch('src.backend.core.document_ingestion.get_embedding_manager') as mock_get_embed_manager, \
             patch('src.backend.core.document_ingestion.DocumentProcessor') as MockDocumentProcessor:

            # Setup mocks
            mock_vs_manager_instance = MockVectorStoreManager.return_value
            mock_vector_store = MagicMock()
            mock_vs_manager_instance.get_vector_store.return_value = mock_vector_store

            mock_embed_manager_instance = mock_get_embed_manager.return_value
            mock_embedding_result = MagicMock(success=True, embeddings=[[0.1, 0.2]])
            mock_embed_manager_instance.process_async.return_value = mock_embedding_result
            
            mock_processor_instance = MockDocumentProcessor.return_value
            mock_doc_chunk = MagicMock(id=uuid.uuid4(), content="test chunk", embedding_vector=None)
            mock_proc_result = MagicMock(success=True, document=MagicMock(id=uuid.uuid4(), filename='test.txt', version=1), chunks=[mock_doc_chunk])
            mock_processor_instance.process_file.return_value = mock_proc_result

            yield {
                "vector_store_manager": mock_vs_manager_instance,
                "embedding_manager": mock_embed_manager_instance,
                "document_processor": mock_processor_instance,
                "vector_store": mock_vector_store
            }

    @pytest.fixture
    def pipeline_instance(self, tenant_id, mock_dependencies):
        """Provides a pipeline instance with mocked dependencies."""
        return DocumentIngestionPipeline(
            tenant_id=tenant_id,
            vector_store_manager=mock_dependencies["vector_store_manager"],
            embedding_manager=mock_dependencies["embedding_manager"],
            document_processor=mock_dependencies["document_processor"]
        )

    @pytest.mark.asyncio
    async def test_ingestion_pipeline_success(self, tenant_id, test_environment, pipeline_instance, mock_dependencies):
        """Test a successful run of the document ingestion pipeline."""
        file_path = test_environment / "test.txt"
        mock_session = MagicMock(spec=Session)

        new_doc, chunks = await pipeline_instance.ingest_document(mock_session, file_path)

        assert new_doc is not None
        assert new_doc.filename == 'test.txt'
        assert len(chunks) == 1
        mock_dependencies["vector_store"].add.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_ingestion_of_unsupported_file(self, tenant_id, test_environment, pipeline_instance):
        """Test that the pipeline correctly handles unsupported file types."""
        file_path = str(test_environment / "unsupported.dat")
        
        # The new implementation should raise an error during processing
        pipeline_instance.document_processor.process_file.return_value = ProcessingResult(
            success=False, error_message="Unsupported file type"
        )
        mock_session = MagicMock(spec=Session)

        with pytest.raises(RuntimeError, match="Failed to process file: Unsupported file type"):
            await pipeline_instance.ingest_document(mock_session, Path(file_path))
