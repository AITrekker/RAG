"""
Pytest-based test suite for tenant isolation.

This suite verifies that tenant isolation is working correctly across the database,
vector store, filesystem, and configuration systems using pytest fixtures and assertions.
"""

import pytest
from unittest.mock import MagicMock, patch
import tempfile
import shutil
from pathlib import Path
import uuid

# Add project root to path for imports
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Components under test
from src.backend.core.tenant_isolation import TenantSecurityError
from src.backend.middleware.tenant_context import TenantContext
from src.backend.utils.tenant_filesystem import TenantFileSystemManager
from src.backend.utils.vector_store import VectorStoreManager
from unittest.mock import Mock
from sqlalchemy.orm import Session

from src.backend.models.tenant import Tenant
from src.backend.models.document import Document
from src.backend.core.tenant_manager import TenantManager

# --- Fixtures ---

@pytest.fixture
def temp_fs_environment():
    """Creates a temporary base directory for filesystem tests."""
    temp_dir = Path(tempfile.mkdtemp(prefix="tenant_iso_test_"))
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture(autouse=True)
def clear_tenant_context():
    """Ensures tenant context is cleared before and after each test."""
    TenantContext.clear_context()
    yield
    TenantContext.clear_context()
        
# --- Test Classes ---

class TestTenantContext:
    """Tests for tenant context management."""

    def test_context_setting_and_retrieval(self):
        """Test that tenant context can be set and retrieved correctly."""
        assert TenantContext.get_current_tenant_id() is None
        tenant_id = "tenant-context-test"
        TenantContext.set_current_tenant(tenant_id)
        assert TenantContext.get_current_tenant_id() == tenant_id

    def test_context_isolation(self):
        """Test that tenant context is isolated."""
        # This is implicitly tested by the autouse fixture,
        # but we can be explicit.
        TenantContext.set_current_tenant("tenant-1")
        assert TenantContext.get_current_tenant_id() == "tenant-1"
        TenantContext.clear_context()
        assert TenantContext.get_current_tenant_id() is None

class TestDatabaseIsolation:
    """Mocks at the DB query level to test isolation logic."""

    @patch('src.backend.db.session.Session')
    def test_tenant_scoped_query(self, mock_session):
        """
        Test that queries are automatically filtered by the current tenant context.
        This is a conceptual test, as the actual implementation might be in the ORM layer.
        """
        # A full test requires a live DB and ORM setup. Here we simulate the principle.
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query

        tenant_id = "tenant-db-iso-test"
        TenantContext.set_current_tenant(tenant_id)
        
        # In a real scenario, a repository or service would call session.query(Model)
        # and the scoped session would add the .filter(Model.tenant_id == tenant_id)
        # We can't easily test the internals of a scoped session here, so we assert the concept.
        # For a true test, we would need to test a repository function.
        pass # This highlights the need for integration testing with a real DB session.

class TestVectorStoreIsolation:
    """Tests for data isolation within the ChromaDB vector store."""

    @patch.object(VectorStoreManager, '__init__', lambda self, path: None)
    @patch.object(VectorStoreManager, 'client')
    def test_collection_naming_scheme(self, mock_chroma_client):
        """Test that collections are named using a tenant-specific prefix."""
        chroma_manager = VectorStoreManager(path="dummy/path")
        #...

    @patch.object(VectorStoreManager, '__init__', lambda self, path: None)
    @patch.object(VectorStoreManager, 'client')
    def test_get_collection_for_tenant(self, mock_chroma_client):
        """Test that get_collection_for_tenant calls chroma with the correct name."""
        chroma_manager = VectorStoreManager(path="dummy/path")
        
        tenant_id = "tenant-vs-get-test"
        expected_name = f"rag_collection_{tenant_id}"
        
        chroma_manager.get_collection_for_tenant(tenant_id)
        
        mock_chroma_client.get_or_create_collection.assert_called_once_with(name=expected_name)

class TestFilesystemIsolation:
    """Tests for tenant isolation on the filesystem."""

    def test_tenant_directory_creation(self, temp_fs_environment):
        """Test that a unique, secure directory is created for each tenant."""
        fs_manager = TenantFileSystemManager(base_data_path=str(temp_fs_environment))
        
        tenant_id = "tenant-fs-test"
        fs_manager.create_tenant_directories(tenant_id)
        tenant_dirs = fs_manager.get_tenant_directories(tenant_id)
        
        # Check that the root directory exists and contains the tenant_id
        root_path = tenant_dirs["root"]
        assert root_path.exists()
        assert root_path.is_dir()
        assert tenant_id in str(root_path)
        
        # Check for subdirectories
        assert tenant_dirs["documents"].exists()
        assert tenant_dirs["uploads"].exists()

    def test_file_access_is_isolated(self, temp_fs_environment):
        """Test that one tenant cannot access files of another."""
        fs_manager = TenantFileSystemManager(base_data_path=str(temp_fs_environment))

        tenant_a = "tenant-a"
        tenant_b = "tenant-b"

        # Create directories for both tenants
        fs_manager.create_tenant_directories(tenant_a)
        fs_manager.create_tenant_directories(tenant_b)

        # Tenant A creates a file in their documents directory
        tenant_a_docs_dir = fs_manager.get_tenant_directories(tenant_a)["documents"]
        (tenant_a_docs_dir / "secret.txt").write_text("tenant a's secret")
        
        # The new design doesn't have a `get_tenant_file_path` method that would
        # be vulnerable to path traversal. Access is through directory retrieval.
        # This test is now more about ensuring tenants get their own directories.
        tenant_b_docs_dir = fs_manager.get_tenant_directories(tenant_b)["documents"]
        assert not (tenant_b_docs_dir / "secret.txt").exists()
        assert tenant_a_docs_dir != tenant_b_docs_dir

    def test_deleting_tenant_directories(self, temp_fs_environment):
        """Test that tenant directories can be deleted completely."""
        fs_manager = TenantFileSystemManager(base_data_path=str(temp_fs_environment))
        tenant_id = "tenant-to-delete"

        # Create directories
        fs_manager.create_tenant_directories(tenant_id)
        root_dir = fs_manager.get_tenant_directories(tenant_id)["root"]
        assert root_dir.exists()

        # Delete them
        fs_manager.delete_tenant_directories(tenant_id)
        assert not root_dir.exists() 