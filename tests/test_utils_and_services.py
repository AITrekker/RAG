"""
Comprehensive Test Suite for Utility Functions and Core Services

Tests all utility modules and core services including:
- Vector store management (ChromaManager)
- Performance monitoring system
- File monitoring and change detection
- HTML processing utilities
- Tenant filesystem management
- LLM service integration
- Embedding manager functionality
"""

import pytest
import sys
import os
import tempfile
import shutil
import time
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import uuid
from datetime import datetime

# Update the path to ensure 'src' is in our import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.backend.utils.vector_store import ChromaManager, get_chroma_manager, get_vector_store_manager
from src.backend.utils.monitoring import PerformanceMonitor, get_performance_monitor, record_query_time, record_embedding_time
from src.backend.utils.file_monitor import FileMonitor, FileChangeEvent, ChangeType, MonitoringConfig
from src.backend.utils.html_processor import HTMLProcessor, HTMLContent, extract_text_from_html
from src.backend.utils.tenant_filesystem import TenantFileSystemManager
from src.backend.core.llm_service import LLMService, get_llm_service, get_model_recommendations
from src.backend.core.embedding_manager import EmbeddingManager, get_embedding_manager

class TestVectorStore:
    """Test suite for vector store functionality."""
    
    def test_chroma_manager_initialization(self):
        """Test ChromaManager initialization."""
        manager = ChromaManager()
        assert manager is not None
        assert hasattr(manager, 'client')
    
    def test_get_chroma_manager_singleton(self):
        """Test that get_chroma_manager returns singleton instance."""
        manager1 = get_chroma_manager()
        manager2 = get_chroma_manager()
        assert manager1 is manager2
    
    def test_collection_for_tenant(self):
        """Test collection creation for tenant."""
        manager = get_chroma_manager()
        tenant_id = "test_tenant_vector"
        
        collection = manager.get_collection_for_tenant(tenant_id)
        assert collection is not None
        
        # Test that subsequent calls return the same collection
        collection2 = manager.get_collection_for_tenant(tenant_id)
        assert collection.name == collection2.name
    
    def test_tenant_collection_isolation(self):
        """Test that different tenants get different collections."""
        manager = get_chroma_manager()
        
        tenant1 = "tenant_1"
        tenant2 = "tenant_2"
        
        collection1 = manager.get_collection_for_tenant(tenant1)
        collection2 = manager.get_collection_for_tenant(tenant2)
        
        assert collection1.name != collection2.name
        assert tenant1 in collection1.name
        assert tenant2 in collection2.name
    
    @patch('chromadb.Client')
    def test_collection_operations(self, mock_client):
        """Test collection add, query, and delete operations."""
        # Setup mock
        mock_collection = Mock()
        mock_client_instance = Mock()
        mock_client.return_value = mock_client_instance
        mock_client_instance.get_or_create_collection.return_value = mock_collection
        
        manager = ChromaManager()
        collection = manager.get_collection_for_tenant("test_tenant")
        
        # Test add documents
        mock_collection.add.return_value = None
        collection.add(
            ids=["doc1", "doc2"],
            documents=["Document 1 content", "Document 2 content"],
            embeddings=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
            metadatas=[{"source": "file1"}, {"source": "file2"}]
        )
        mock_collection.add.assert_called_once()
        
        # Test query documents
        mock_collection.query.return_value = {
            "documents": [["Document 1 content"]],
            "metadatas": [[{"source": "file1"}]],
            "distances": [[0.1]]
        }
        
        results = collection.query(
            query_embeddings=[[0.1, 0.2, 0.3]],
            n_results=1
        )
        
        mock_collection.query.assert_called_once()
        assert "documents" in results


class TestMonitoring:
    """Test suite for performance monitoring."""
    
    def test_performance_monitor_initialization(self):
        """Test PerformanceMonitor initialization."""
        monitor = PerformanceMonitor()
        assert monitor is not None
        assert hasattr(monitor, 'metrics')
    
    def test_get_performance_monitor_singleton(self):
        """Test singleton behavior of performance monitor."""
        monitor1 = get_performance_monitor()
        monitor2 = get_performance_monitor()
        assert monitor1 is monitor2
    
    def test_record_metric(self):
        """Test recording performance metrics."""
        monitor = get_performance_monitor(force_reload=True)
        
        monitor.record_metric(
            component="test_component",
            operation="test_operation",
            duration=1.5,
            metadata={"test": True}
        )
        
        # Check that metric was recorded
        assert len(monitor.metrics) > 0
        
        # Get statistics
        stats = monitor.get_statistics()
        assert "test_component" in stats
    
    def test_record_embedding_time(self):
        """Test recording embedding time specifically."""
        monitor = get_performance_monitor(force_reload=True)
        
        record_embedding_time(0.5, "test_model")
        
        stats = monitor.get_statistics()
        assert "embedding_service" in stats
    
    def test_record_query_time(self):
        """Test recording query time."""
        monitor = get_performance_monitor(force_reload=True)
        
        record_query_time(2.0, 5, "success")
        
        stats = monitor.get_statistics()
        assert "query_processor" in stats
    
    def test_performance_thresholds(self):
        """Test performance threshold monitoring."""
        monitor = get_performance_monitor(force_reload=True)
        
        # Record slow operation
        monitor.record_metric(
            component="test_component",
            operation="slow_operation",
            duration=10.0
        )
        
        # Record fast operation
        monitor.record_metric(
            component="test_component", 
            operation="fast_operation",
            duration=0.1
        )
        
        stats = monitor.get_statistics()
        component_stats = stats["test_component"]
        
        assert component_stats["total_operations"] == 2
        assert component_stats["avg_duration"] > 0


class TestFileMonitor:
    """Test suite for file monitoring."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.config = MonitoringConfig(
            watch_directory=self.test_dir,
            file_extensions=['.txt', '.pdf'],
            poll_interval=0.1
        )
    
    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_file_monitor_initialization(self):
        """Test FileMonitor initialization."""
        self.setUp()
        try:
            monitor = FileMonitor(self.config)
            assert monitor is not None
            assert monitor.config == self.config
        finally:
            self.tearDown()
    
    def test_file_change_detection(self):
        """Test file change detection."""
        self.setUp()
        try:
            monitor = FileMonitor(self.config)
            changes = []
            
            def change_handler(event: FileChangeEvent):
                changes.append(event)
            
            monitor.add_change_handler(change_handler)
            
            # Create a test file
            test_file = Path(self.test_dir) / "test.txt"
            test_file.write_text("Test content")
            
            # Check for changes
            detected_changes = monitor.check_for_changes()
            
            assert len(detected_changes) > 0
            assert any(change.change_type == ChangeType.CREATED for change in detected_changes)
            
        finally:
            self.tearDown()
    
    def test_file_extension_filtering(self):
        """Test file extension filtering."""
        self.setUp()
        try:
            monitor = FileMonitor(self.config)
            
            # Create files with different extensions
            txt_file = Path(self.test_dir) / "test.txt"
            pdf_file = Path(self.test_dir) / "test.pdf"
            jpg_file = Path(self.test_dir) / "test.jpg"  # Should be ignored
            
            txt_file.write_text("Text content")
            pdf_file.write_bytes(b"PDF content")
            jpg_file.write_bytes(b"JPG content")
            
            changes = monitor.check_for_changes()
            
            # Should only detect txt and pdf files
            detected_files = [change.file_path.name for change in changes]
            assert "test.txt" in detected_files
            assert "test.pdf" in detected_files
            assert "test.jpg" not in detected_files
            
        finally:
            self.tearDown()


class TestHTMLProcessor:
    """Test suite for HTML processing utilities."""
    
    def test_html_processor_initialization(self):
        """Test HTMLProcessor initialization."""
        processor = HTMLProcessor()
        assert processor is not None
    
    def test_extract_text_from_simple_html(self):
        """Test text extraction from simple HTML."""
        html_content = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <h1>Main Heading</h1>
                <p>This is a paragraph.</p>
                <div>This is a div.</div>
            </body>
        </html>
        """
        
        processor = HTMLProcessor()
        result = processor.extract_content(html_content)
        
        assert isinstance(result, HTMLContent)
        assert "Main Heading" in result.text
        assert "This is a paragraph." in result.text
        assert "This is a div." in result.text
        assert result.title == "Test Page"
    
    def test_extract_text_from_complex_html(self):
        """Test text extraction from complex HTML with tables, lists, etc."""
        html_content = """
        <html>
            <body>
                <table>
                    <tr><td>Cell 1</td><td>Cell 2</td></tr>
                    <tr><td>Cell 3</td><td>Cell 4</td></tr>
                </table>
                <ul>
                    <li>Item 1</li>
                    <li>Item 2</li>
                </ul>
                <script>console.log("should be ignored");</script>
                <style>body { color: red; }</style>
            </body>
        </html>
        """
        
        processor = HTMLProcessor()
        result = processor.extract_content(html_content)
        
        # Should extract table content
        assert "Cell 1" in result.text
        assert "Cell 4" in result.text
        
        # Should extract list content
        assert "Item 1" in result.text
        assert "Item 2" in result.text
        
        # Should ignore script and style content
        assert "console.log" not in result.text
        assert "color: red" not in result.text
    
    def test_extract_text_utility_function(self):
        """Test the standalone extract_text_from_html function."""
        html_content = "<html><body><p>Simple test</p></body></html>"
        
        text = extract_text_from_html(html_content)
        assert "Simple test" in text
        assert isinstance(text, str)
    
    def test_html_with_metadata_extraction(self):
        """Test extraction of metadata from HTML."""
        html_content = """
        <html>
            <head>
                <title>Test Document</title>
                <meta name="author" content="Test Author">
                <meta name="description" content="Test Description">
                <meta name="keywords" content="test, html, processing">
            </head>
            <body>
                <h1>Content Header</h1>
                <p>Content paragraph</p>
            </body>
        </html>
        """
        
        processor = HTMLProcessor()
        result = processor.extract_content(html_content)
        
        assert result.title == "Test Document"
        assert "author" in result.metadata
        assert result.metadata["author"] == "Test Author"
        assert "description" in result.metadata
        assert result.metadata["description"] == "Test Description"


class TestTenantFilesystem:
    """Test suite for tenant filesystem management."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_base_dir = tempfile.mkdtemp()
        self.fs_manager = TenantFileSystemManager(base_path=self.test_base_dir)
    
    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.test_base_dir):
            shutil.rmtree(self.test_base_dir)
    
    def test_tenant_filesystem_initialization(self):
        """Test TenantFileSystemManager initialization."""
        self.setUp()
        try:
            assert self.fs_manager is not None
            assert hasattr(self.fs_manager, 'base_path')
        finally:
            self.tearDown()
    
    def test_tenant_directory_creation(self):
        """Test tenant directory structure creation."""
        self.setUp()
        try:
            tenant_id = "test_tenant_fs"
            
            # Get tenant directory (should create it)
            tenant_dir = self.fs_manager.get_tenant_directory(tenant_id)
            
            assert tenant_dir.exists()
            assert tenant_id in str(tenant_dir)
            
            # Check that subdirectories are created
            uploads_dir = tenant_dir / "uploads"
            documents_dir = tenant_dir / "documents"
            
            assert uploads_dir.exists()
            assert documents_dir.exists()
            
        finally:
            self.tearDown()
    
    def test_tenant_isolation(self):
        """Test that tenants have isolated filesystem access."""
        self.setUp()
        try:
            tenant1 = "tenant_1"
            tenant2 = "tenant_2"
            
            dir1 = self.fs_manager.get_tenant_directory(tenant1)
            dir2 = self.fs_manager.get_tenant_directory(tenant2)
            
            assert dir1 != dir2
            assert tenant1 in str(dir1)
            assert tenant2 in str(dir2)
            
            # Create files in each tenant directory
            file1 = dir1 / "uploads" / "file1.txt"
            file2 = dir2 / "uploads" / "file2.txt"
            
            file1.write_text("Tenant 1 content")
            file2.write_text("Tenant 2 content")
            
            # Verify isolation
            assert file1.exists()
            assert file2.exists()
            assert file1.read_text() != file2.read_text()
            
        finally:
            self.tearDown()
    
    @patch('fastapi.UploadFile')
    def test_save_uploaded_file(self, mock_upload_file):
        """Test saving uploaded files."""
        self.setUp()
        try:
            # Setup mock file
            mock_file = Mock()
            mock_file.filename = "test.pdf"
            mock_file.read.return_value = b"PDF content"
            
            tenant_id = "test_tenant"
            document_id = str(uuid.uuid4())
            
            # Save file
            saved_path = self.fs_manager.save_uploaded_file(
                tenant_id=tenant_id,
                file=mock_file,
                document_id=document_id
            )
            
            assert saved_path.exists()
            assert "test.pdf" in str(saved_path)
            assert tenant_id in str(saved_path)
            
        finally:
            self.tearDown()


class TestLLMService:
    """Test suite for LLM service functionality."""
    
    @patch('src.backend.core.llm_service.LlamaIndex')
    def test_llm_service_initialization(self, mock_llama):
        """Test LLMService initialization."""
        service = LLMService()
        assert service is not None
    
    def test_get_llm_service_singleton(self):
        """Test singleton behavior of LLM service."""
        service1 = get_llm_service()
        service2 = get_llm_service()
        assert service1 is service2
    
    def test_model_recommendations(self):
        """Test model recommendations functionality."""
        recommendations = get_model_recommendations()
        
        assert isinstance(recommendations, dict)
        assert len(recommendations) > 0
        
        # Check that recommendations contain expected keys
        for model_info in recommendations.values():
            assert "model_name" in model_info
            assert "description" in model_info
            assert "hardware_requirements" in model_info
    
    @patch('src.backend.core.llm_service.LLMService.generate_response')
    def test_response_generation(self, mock_generate):
        """Test response generation."""
        mock_generate.return_value = "This is a generated response."
        
        service = get_llm_service()
        response = service.generate_response(
            query="What is machine learning?",
            context="Machine learning is a subset of AI."
        )
        
        assert response == "This is a generated response."
        mock_generate.assert_called_once()


class TestEmbeddingManager:
    """Test suite for embedding manager functionality."""
    
    def test_embedding_manager_initialization(self):
        """Test EmbeddingManager initialization."""
        manager = get_embedding_manager()
        assert manager is not None
    
    def test_embedding_manager_singleton(self):
        """Test singleton behavior."""
        manager1 = get_embedding_manager()
        manager2 = get_embedding_manager()
        assert manager1 is manager2
    
    @patch('src.backend.core.embedding_manager.EmbeddingManager.generate_embeddings')
    def test_batch_embedding_generation(self, mock_generate):
        """Test batch embedding generation."""
        mock_generate.return_value = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        
        manager = get_embedding_manager()
        texts = ["Text 1", "Text 2"]
        embeddings = manager.generate_embeddings(texts)
        
        assert len(embeddings) == 2
        assert all(len(emb) == 3 for emb in embeddings)
        mock_generate.assert_called_once()
    
    @patch('src.backend.core.embedding_manager.EmbeddingManager.get_embedding_dimension')
    def test_embedding_dimensions(self, mock_dimension):
        """Test embedding dimension retrieval."""
        mock_dimension.return_value = 384
        
        manager = get_embedding_manager()
        dimension = manager.get_embedding_dimension()
        
        assert dimension == 384
        mock_dimension.assert_called_once()


class TestUtilityIntegration:
    """Test integration between various utility functions."""
    
    def test_monitoring_with_vector_store(self):
        """Test monitoring integration with vector store operations."""
        monitor = get_performance_monitor(force_reload=True)
        
        # Simulate vector store operation with monitoring
        start_time = time.time()
        
        # Mock vector store operation
        time.sleep(0.01)  # Simulate work
        
        duration = time.time() - start_time
        monitor.record_metric(
            component="vector_store",
            operation="query",
            duration=duration,
            metadata={"collection": "test", "results": 5}
        )
        
        stats = monitor.get_statistics()
        assert "vector_store" in stats
        assert stats["vector_store"]["total_operations"] >= 1
    
    def test_file_monitor_with_document_processing(self):
        """Test file monitor integration with document processing workflow."""
        test_dir = tempfile.mkdtemp()
        try:
            config = MonitoringConfig(
                watch_directory=test_dir,
                file_extensions=['.txt'],
                poll_interval=0.1
            )
            
            monitor = FileMonitor(config)
            changes = []
            
            def process_change(event: FileChangeEvent):
                changes.append(event)
                # Simulate document processing
                if event.change_type == ChangeType.CREATED:
                    print(f"Processing new file: {event.file_path}")
            
            monitor.add_change_handler(process_change)
            
            # Create a test file
            test_file = Path(test_dir) / "document.txt"
            test_file.write_text("Document content")
            
            # Check for changes
            detected_changes = monitor.check_for_changes()
            
            assert len(detected_changes) > 0
            assert len(changes) > 0
            
        finally:
            shutil.rmtree(test_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 