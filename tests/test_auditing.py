"""
Tests for the AuditLogger service.
"""

import unittest
from unittest.mock import MagicMock, patch
from src.backend.core.auditing import AuditLogger
from src.backend.models.audit import SyncEvent

class TestAuditLogger(unittest.TestCase):

    def setUp(self):
        self.audit_logger = AuditLogger()
        self.mock_db_session = MagicMock()

    def test_log_sync_event(self):
        """Test that a sync event is correctly created and added to the DB session."""
        
        # Call the logger
        self.audit_logger.log_sync_event(
            db=self.mock_db_session,
            sync_run_id="test-sync-123",
            tenant_id="test-tenant",
            event_type="FILE_ADDED",
            status="SUCCESS",
            message="File was added.",
            metadata={"file": "test.txt"}
        )

        # 1. Assert that db.add was called once
        self.mock_db_session.add.assert_called_once()
        
        # 2. Get the object that was passed to db.add
        added_object = self.mock_db_session.add.call_args[0][0]
        
        # 3. Assert that the object is an instance of SyncEvent and has correct data
        self.assertIsInstance(added_object, SyncEvent)
        self.assertEqual(added_object.sync_run_id, "test-sync-123")
        self.assertEqual(added_object.tenant_id, "test-tenant")
        self.assertEqual(added_object.event_type, "FILE_ADDED")
        self.assertEqual(added_object.status, "SUCCESS")
        self.assertEqual(added_object.message, "File was added.")
        self.assertEqual(added_object.event_metadata, {"file": "test.txt"})

        # 4. Assert that commit was called
        self.mock_db_session.commit.assert_called_once()

    def test_log_failure_rolls_back(self):
        """Test that the session is rolled back on a logging failure."""
        
        # Configure the mock session's add method to raise an exception
        self.mock_db_session.add.side_effect = Exception("Database connection failed")

        # Call the logger
        self.audit_logger.log_sync_event(
            db=self.mock_db_session,
            sync_run_id="test-sync-fail",
            tenant_id="test-tenant",
            event_type="SYNC_START",
            status="IN_PROGRESS"
        )
        
        # Assert that rollback was called
        self.mock_db_session.rollback.assert_called_once()


if __name__ == '__main__':
    unittest.main() 