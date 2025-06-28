"""
Tests for the DeltaSyncService using pytest.
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import shutil

from src.backend.core.delta_sync import DeltaSync

@pytest.fixture
def sync_test_environment():
    """
    Sets up a temporary directory structure for sync testing.
    Provides paths and cleans up afterward.
    """
    test_tenant_id = "test_sync_tenant"
    base_dir = Path(f"./test_sync_data_{test_tenant_id}")
    source_dir = base_dir / "uploads"
    target_dir = base_dir / "documents"

    source_dir.mkdir(parents=True, exist_ok=True)
    target_dir.mkdir(parents=True, exist_ok=True)

    yield test_tenant_id, source_dir, target_dir

    shutil.rmtree(base_dir)

@pytest.fixture
def mock_dependencies():
    """Provides mocks for db, ingestion pipeline, and audit logger."""
    return {
        "db": MagicMock(),
        "ingestion_pipeline": MagicMock(),
        "audit_logger": MagicMock()
    }

class TestDeltaSyncService:

    @pytest.fixture
    def sync_service(self, sync_test_environment, mock_dependencies):
        """Initializes the DeltaSyncService with a test environment and mocks."""
        tenant_id, source_dir, target_dir = sync_test_environment
        
        service = DeltaSync(
            tenant_id=tenant_id,
            db=mock_dependencies["db"],
            ingestion_pipeline=mock_dependencies["ingestion_pipeline"],
            sync_run_id="test-run-id",
            audit_logger=mock_dependencies["audit_logger"]
        )
        # Manually set the paths for testing purposes
        service.source_dir = source_dir
        service.target_dir = target_dir
        return service

    def test_initialization(self, sync_service, sync_test_environment):
        """Test that the service initializes correctly."""
        tenant_id, source_dir, _ = sync_test_environment
        assert sync_service.tenant_id == tenant_id
        assert sync_service.source_dir.exists()
        assert sync_service.target_dir.exists()

    def test_detect_changes(self, sync_service, sync_test_environment):
        """Test the delta detection logic."""
        _, source_dir, target_dir = sync_test_environment
        
        # 1. New file: exists only in source
        (source_dir / "new.txt").write_text("new")
        # 2. Unchanged file
        (source_dir / "same.txt").write_text("same")
        (target_dir / "same.txt").write_text("same")
        # 3. Updated file
        (source_dir / "updated.txt").write_text("v2")
        (target_dir / "updated.txt").write_text("v1")
        # 4. Deleted file: exists only in target
        (target_dir / "deleted.txt").write_text("to be deleted")

        new, updated, deleted = sync_service._detect_changes()

        assert len(new) == 1 and new[0].name == "new.txt"
        assert len(updated) == 1 and updated[0].name == "updated.txt"
        assert len(deleted) == 1 and deleted[0].name == "deleted.txt"

    def test_process_inclusions_and_updates(self, sync_service, sync_test_environment, mock_dependencies):
        """Test the processing of new and updated files."""
        _, source_dir, target_dir = sync_test_environment
        ingestion_pipeline = mock_dependencies["ingestion_pipeline"]
        audit_logger = mock_dependencies["audit_logger"]

        # Create new and updated files
        (source_dir / "new.txt").write_text("new content")
        (source_dir / "updated.txt").write_text("updated content")
        
        new_files = [source_dir / "new.txt"]
        updated_files = [source_dir / "updated.txt"]

        sync_service._process_inclusions(new_files)
        sync_service._process_updates(updated_files)

        # Assertions
        assert (target_dir / "new.txt").read_text() == "new content"
        assert (target_dir / "updated.txt").read_text() == "updated content"
        
        assert ingestion_pipeline.ingest_document.call_count == 2
        
        # Check that audit logger was called correctly
        assert audit_logger.log_sync_event.call_count == 2
        # Example check of one call's arguments
        first_call_kwargs = audit_logger.log_sync_event.call_args_list[0].kwargs
        assert first_call_kwargs['status'] == 'SUCCESS'
        assert first_call_kwargs['event_type'] in ['FILE_ADDED', 'FILE_UPDATED']

    def test_process_deletions(self, sync_service, sync_test_environment, mock_dependencies):
        """Test the processing of deleted files."""
        _, _, target_dir = sync_test_environment
        db = mock_dependencies["db"]
        ingestion_pipeline = mock_dependencies["ingestion_pipeline"]
        audit_logger = mock_dependencies["audit_logger"]

        # Setup a file to be deleted
        file_to_delete = target_dir / "deleted.txt"
        file_to_delete.write_text("delete this")
        
        mock_doc = MagicMock()
        mock_doc.id = "doc-to-delete-123"
        db.query.return_value.filter.return_value.first.return_value = mock_doc
        
        sync_service._process_deletions([file_to_delete])

        # Assertions
        assert not file_to_delete.exists()
        ingestion_pipeline.delete_document.assert_called_once_with(db, "doc-to-delete-123")
        
        audit_logger.log_sync_event.assert_called_once()
        audit_call_kwargs = audit_logger.log_sync_event.call_args.kwargs
        assert audit_call_kwargs['status'] == 'SUCCESS'
        assert audit_call_kwargs['event_type'] == 'FILE_DELETED' 