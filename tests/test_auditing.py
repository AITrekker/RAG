"""
Tests for the AuditLogger service using pytest.
"""

import pytest
from unittest.mock import MagicMock, patch
from src.backend.core.auditing import AuditLogger
from qdrant_client import models
import uuid

@pytest.fixture
def mock_vector_store_manager():
    """Provides a mock VectorStoreManager."""
    with patch('src.backend.core.auditing.get_vector_store_manager') as mock_get:
        mock_manager = MagicMock()
        mock_get.return_value = mock_manager
        yield mock_manager

@pytest.fixture
def audit_logger():
    """Provides an instance of the AuditLogger, which will use the mocked manager."""
    return AuditLogger()

def test_log_sync_event(audit_logger, mock_vector_store_manager):
    """Test that a sync event is correctly converted to a Qdrant point and upserted."""
    
    # Call the logger
    audit_logger.log_sync_event(
        tenant_id="test-tenant",
        sync_run_id="test-sync-123",
        event_type="FILE_ADDED",
        status="SUCCESS",
        message="File was added.",
        metadata={"file": "test.txt"}
    )

    # Assert that get_collection_for_tenant was called
    mock_vector_store_manager.get_collection_for_tenant.assert_called_once_with(
        "test-tenant", embedding_size=1
    )

    # Assert that client.upsert was called
    mock_vector_store_manager.client.upsert.assert_called_once()
    
    # Get the arguments passed to upsert
    upsert_args = mock_vector_store_manager.client.upsert.call_args
    points = upsert_args.kwargs['points']
    collection_name = upsert_args.kwargs['collection_name']
    
    # Assert properties of the upsert call
    assert collection_name == "tenant_test-tenant_audit_logs"
    assert len(points) == 1
    point = points[0]
    
    # Assert the structure and payload of the created point
    assert isinstance(point, models.PointStruct)
    assert point.vector == [0.0]
    assert point.payload["sync_run_id"] == "test-sync-123"
    assert point.payload["event_type"] == "FILE_ADDED"
    assert point.payload["status"] == "SUCCESS"
    assert point.payload["message"] == "File was added."
    assert point.payload["metadata"] == {"file": "test.txt"}
    assert "timestamp" in point.payload

def test_get_events_for_tenant(audit_logger, mock_vector_store_manager):
    """Test retrieving audit events for a tenant from Qdrant."""
    
    # Mock the return value for the scroll API
    mock_payload = {"event_type": "SYNC_COMPLETE", "status": "SUCCESS"}
    mock_point = models.ScoredPoint(id=str(uuid.uuid4()), version=1, score=1.0, payload=mock_payload, vector=None)
    mock_vector_store_manager.client.scroll.return_value = ([mock_point], None)

    # Call the method
    events = audit_logger.get_events_for_tenant(
        tenant_id="test-tenant",
        limit=50,
        offset=10
    )

    # Assert that the scroll method was called with correct parameters
    mock_vector_store_manager.client.scroll.assert_called_once_with(
        collection_name="tenant_test-tenant_audit_logs",
        limit=50,
        offset=10,
        with_payload=True,
        with_vectors=False,
        order_by=models.OrderBy(key="timestamp", direction=models.OrderDirection.DESC)
    )

    # Assert that the returned events match the mocked payload
    assert len(events) == 1
    assert events[0] == mock_payload

def test_get_events_handles_qdrant_error(audit_logger, mock_vector_store_manager):
    """Test that an empty list is returned if the Qdrant query fails."""
    
    # Configure scroll to raise an exception
    mock_vector_store_manager.client.scroll.side_effect = Exception("Qdrant is down")

    # Call the method
    events = audit_logger.get_events_for_tenant(tenant_id="test-tenant-fail")

    # Assert that an empty list is returned
    assert events == [] 