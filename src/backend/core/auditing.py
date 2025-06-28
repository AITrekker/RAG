"""
Auditing Service for the Enterprise RAG Platform.

This service provides a centralized mechanism for logging important system
events to a persistent store (now Qdrant). It is used to create an
immutable audit trail for key operations, such as document synchronization,
user actions, and configuration changes.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from qdrant_client import models

from ..utils.vector_store import get_vector_store_manager

logger = logging.getLogger(__name__)

class AuditLogger:
    """A service for logging audit events to Qdrant."""

    def __init__(self):
        self.vector_store_manager = get_vector_store_manager()

    def _get_audit_collection_name(self, tenant_id: str) -> str:
        """Returns the dedicated collection name for a tenant's audit logs."""
        return f"tenant_{tenant_id}_audit_logs"

    def log_sync_event(
        self,
        tenant_id: str,
        sync_run_id: str,
        event_type: str,
        status: str,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Logs a synchronization event to a dedicated Qdrant collection.

        Args:
            tenant_id: The ID of the tenant being synced.
            sync_run_id: The unique identifier for the entire sync operation.
            event_type: The type of event (e.g., 'SYNC_START', 'FILE_ADDED').
            status: The status of the event (e.g., 'SUCCESS', 'FAILURE').
            message: A human-readable message describing the event.
            metadata: A JSON-serializable dictionary for extra details.
        """
        try:
            collection_name = self._get_audit_collection_name(tenant_id)
            # Use the new generic method to ensure the audit collection exists.
            # We use a small vector size because the vectors are just dummies.
            self.vector_store_manager.ensure_collection_exists(collection_name, vector_size=1)

            event_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc).isoformat()

            payload = {
                "sync_run_id": sync_run_id,
                "event_type": event_type,
                "status": status,
                "message": message,
                "timestamp": timestamp,
                "metadata": metadata or {}
            }

            point = models.PointStruct(
                id=event_id,
                payload=payload,
                vector=[0.0] # Dummy vector
            )

            self.vector_store_manager.client.upsert(
                collection_name=collection_name,
                points=[point],
                wait=True
            )
            logger.debug(f"Logged audit event: {event_type} for sync {sync_run_id}")
        except Exception as e:
            logger.error(f"Failed to log audit event to Qdrant for sync {sync_run_id}: {e}", exc_info=True)

    def get_events_for_tenant(
        self,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Retrieve audit events for a specific tenant from Qdrant.

        Args:
            tenant_id: The ID of the tenant to get events for.
            limit: Maximum number of events to return.
            offset: Number of events to skip (for pagination).

        Returns:
            List of audit event payloads.
        """
        try:
            collection_name = self._get_audit_collection_name(tenant_id)

            # Scroll through points, sorted by timestamp
            scroll_result, _ = self.vector_store_manager.client.scroll(
                collection_name=collection_name,
                limit=limit,
                offset=offset,
                with_payload=True,
                with_vectors=False,
                order_by=models.OrderBy(
                    key="timestamp",
                    direction=models.OrderDirection.DESC
                )
            )
            
            events = [hit.payload for hit in scroll_result]
            logger.debug(f"Retrieved {len(events)} audit events for tenant {tenant_id}")
            return events

        except Exception as e:
            # If collection doesn't exist, it's not an error, just no events.
            if "not found" in str(e).lower():
                logger.warning(f"Audit collection for tenant {tenant_id} not found. Returning empty list.")
                return []
            
            logger.error(f"Failed to retrieve audit events from Qdrant for tenant {tenant_id}: {e}", exc_info=True)
            return []


# Singleton instance
audit_logger = AuditLogger()

def get_audit_logger() -> AuditLogger:
    """Returns the singleton instance of the AuditLogger."""
    return audit_logger 