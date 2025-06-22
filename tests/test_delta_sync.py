"""
Tests for the DeltaSyncService.
"""

import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import os
import shutil

# This will be the class we are testing
from src.backend.core.delta_sync import DeltaSyncService

class TestDeltaSyncService(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory structure for testing."""
        self.test_tenant_id = "test_tenant"
        self.base_dir = Path(f"./test_sync_data_{self.test_tenant_id}")
        self.source_dir = self.base_dir / "uploads"
        self.target_dir = self.base_dir / "documents"

        # Create directories
        self.source_dir.mkdir(parents=True, exist_ok=True)
        self.target_dir.mkdir(parents=True, exist_ok=True)
        
        # Mocks
        self.mock_db_session = MagicMock()
        self.mock_ingestion_pipeline = MagicMock()
        # Mock the return of ingest_document to be a tuple
        self.mock_ingestion_pipeline.ingest_document.return_value = (MagicMock(), [])
        self.mock_audit_logger = MagicMock()

        self.sync_service = DeltaSyncService(
            tenant_id=self.test_tenant_id,
            db=self.mock_db_session,
            ingestion_pipeline=self.mock_ingestion_pipeline,
            sync_run_id="test-run-id",
            audit_logger=self.mock_audit_logger
        )
        self.sync_service.source_dir = self.source_dir
        self.sync_service.target_dir = self.target_dir

    def tearDown(self):
        """Clean up the temporary directory."""
        if self.base_dir.exists():
            shutil.rmtree(self.base_dir)

    def test_initialization(self):
        """Test that the service initializes correctly."""
        self.assertEqual(self.sync_service.tenant_id, self.test_tenant_id)
        self.assertTrue(self.sync_service.source_dir.exists())
        self.assertTrue(self.sync_service.target_dir.exists())

    def test_process_inclusions_and_updates(self):
        """Test the processing of new and updated files."""
        # 1. Create a new file and an updated file
        (self.source_dir / "new.txt").write_text("new file")
        (self.source_dir / "updated.txt").write_text("updated file v2")
        (self.target_dir / "updated.txt").write_text("updated file v1")

        new_files = [self.source_dir / "new.txt"]
        updated_files = [self.source_dir / "updated.txt"]

        # 2. Run inclusion and update processing
        self.sync_service._process_inclusions(new_files)
        self.sync_service._process_updates(updated_files)

        # 3. Assertions
        # Check that files were copied
        self.assertTrue((self.target_dir / "new.txt").exists())
        self.assertEqual((self.target_dir / "new.txt").read_text(), "new file")
        self.assertEqual((self.target_dir / "updated.txt").read_text(), "updated file v2")
        
        # Check that ingestion pipeline was called for both
        self.assertEqual(self.mock_ingestion_pipeline.ingest_document.call_count, 2)
        
        # Check the call arguments
        # Note: The order of calls might vary, so we check the paths passed.
        calls = self.mock_ingestion_pipeline.ingest_document.call_args_list
        called_paths = [call[0][1] for call in calls] # call[0] is args, [1] is the file_path Path object
        
        self.assertIn(self.target_dir / "new.txt", called_paths)
        self.assertIn(self.target_dir / "updated.txt", called_paths)

        # Check that the audit logger was called
        self.assertEqual(self.mock_audit_logger.log_sync_event.call_count, 2)
        
        # Check one of the calls to the audit logger
        first_audit_call_args = self.mock_audit_logger.log_sync_event.call_args_list[0].kwargs
        self.assertEqual(first_audit_call_args['status'], 'SUCCESS')
        self.assertIn(first_audit_call_args['event_type'], ['FILE_ADDED', 'FILE_UPDATED'])

    def test_process_deletions(self):
        """Test the processing of deleted files."""
        # 1. Setup a file to be deleted and a mock Document object
        file_to_delete = self.target_dir / "deleted.txt"
        file_to_delete.write_text("this will be deleted")
        
        mock_doc = MagicMock()
        mock_doc.id = 123
        
        # Configure the mock DB session to return our mock document
        self.mock_db_session.query.return_value.filter.return_value.first.return_value = mock_doc
        
        deleted_files = [file_to_delete]

        # 2. Run deletion processing
        self.sync_service._process_deletions(deleted_files)

        # 3. Assertions
        # Check that the file was physically deleted
        self.assertFalse(file_to_delete.exists())

        # Check that the ingestion pipeline's delete method was called with the correct ID
        self.mock_ingestion_pipeline.delete_document.assert_called_once_with(self.mock_db_session, 123)
        
        # Check that the audit logger was called
        self.mock_audit_logger.log_sync_event.assert_called_once()
        audit_call_args = self.mock_audit_logger.log_sync_event.call_args.kwargs
        self.assertEqual(audit_call_args['status'], 'SUCCESS')
        self.assertEqual(audit_call_args['event_type'], 'FILE_DELETED')

    def test_detect_changes(self):
        """Test the delta detection logic."""
        # Setup files
        # 1. New file: exists only in source
        (self.source_dir / "new_doc.txt").write_text("This is a new document.")
        
        # 2. Unchanged file: exists in both with same content
        (self.source_dir / "same_doc.txt").write_text("This content is identical.")
        (self.target_dir / "same_doc.txt").write_text("This content is identical.")

        # 3. Updated file: exists in both with different content
        (self.source_dir / "updated_doc.txt").write_text("This is the new, updated content.")
        (self.target_dir / "updated_doc.txt").write_text("This is the original content.")
        
        # 4. Deleted file: exists only in target
        (self.target_dir / "deleted_doc.txt").write_text("This document should be deleted.")

        # Run detection
        new, updated, deleted = self.sync_service._detect_changes()

        # Check results
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0].name, "new_doc.txt")

        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0].name, "updated_doc.txt")

        self.assertEqual(len(deleted), 1)
        self.assertEqual(deleted[0].name, "deleted_doc.txt")

if __name__ == '__main__':
    unittest.main() 