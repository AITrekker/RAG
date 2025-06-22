"""
Tests for the AuditLogger service using pytest.
"""

import pytest
from unittest.mock import MagicMock
from src.backend.core.auditing import AuditLogger
from src.backend.models.audit import SyncEvent

@pytest.fixture
def audit_logger():
    """Provides an instance of the AuditLogger."""
    return AuditLogger()

@pytest.fixture
def mock_db_session():
    """Provides a mock of the database session."""
    return MagicMock()

def test_log_sync_event(audit_logger, mock_db_session):
    """Test that a sync event is correctly created and added to the DB session."""
    
    # Call the logger
    audit_logger.log_sync_event(
        db=mock_db_session,
        sync_run_id="test-sync-123",
        tenant_id="test-tenant",
        event_type="FILE_ADDED",
        status="SUCCESS",
        message="File was added.",
        metadata={"file": "test.txt"}
    )

    # Assert that db.add was called once
    mock_db_session.add.assert_called_once()
    
    # Get the object that was passed to db.add
    added_object = mock_db_session.add.call_args[0][0]
    
    # Assert that the object is an instance of SyncEvent and has correct data
    assert isinstance(added_object, SyncEvent)
    assert added_object.sync_run_id == "test-sync-123"
    assert added_object.tenant_id == "test-tenant"
    assert added_object.event_type == "FILE_ADDED"
    assert added_object.status == "SUCCESS"
    assert added_object.message == "File was added."
    assert added_object.event_metadata == {"file": "test.txt"}

    # Assert that commit was called
    mock_db_session.commit.assert_called_once()

def test_log_failure_rolls_back(audit_logger, mock_db_session):
    """Test that the session is rolled back on a logging failure."""
    
    # Configure the mock session's add method to raise an exception
    mock_db_session.add.side_effect = Exception("Database connection failed")

    # Call the logger
    audit_logger.log_sync_event(
        db=mock_db_session,
        sync_run_id="test-sync-fail",
        tenant_id="test-tenant",
        event_type="SYNC_START",
        status="IN_PROGRESS"
    )
    
    # Assert that rollback was called
    mock_db_session.rollback.assert_called_once()

def test_get_events_for_tenant(audit_logger, mock_db_session):
    """Test retrieving audit events for a tenant."""
    
    # Setup mock query chain
    mock_query = mock_db_session.query.return_value
    mock_filter = mock_query.filter.return_value
    mock_order_by = mock_filter.order_by.return_value
    mock_limit = mock_order_by.limit.return_value
    mock_offset = mock_limit.offset.return_value
    
    # Mock return value for the full query
    mock_events = [SyncEvent(), SyncEvent()]
    mock_offset.all.return_value = mock_events

    # Call the method
    events = audit_logger.get_events_for_tenant(
        db=mock_db_session,
        tenant_id="test-tenant",
        limit=50,
        offset=10
    )

    # Assertions
    mock_db_session.query.assert_called_once_with(SyncEvent)
    mock_query.filter.assert_called_once() # More specific check on filter could be added
    mock_order_by.limit.assert_called_with(50)
    mock_limit.offset.assert_called_with(10)
    mock_offset.all.assert_called_once()
    assert events == mock_events

def test_get_events_handles_db_error(audit_logger, mock_db_session):
    """Test that an empty list is returned if the database query fails."""
    
    # Configure query to raise an exception
    mock_db_session.query.side_effect = Exception("Database is down")

    # Call the method
    events = audit_logger.get_events_for_tenant(
        db=mock_db_session,
        tenant_id="test-tenant-fail"
    )

    # Assert that an empty list is returned
    assert events == [] 