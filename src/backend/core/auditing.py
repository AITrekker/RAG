"""
Auditing Service for the Enterprise RAG Platform.

This service provides a centralized mechanism for logging important system
events to a persistent store (the database). It is used to create an
immutable audit trail for key operations, such as document synchronization,
user actions, and configuration changes.
"""

import logging
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

from ..models.audit import SyncEvent

logger = logging.getLogger(__name__)

class AuditLogger:
    """A service for logging audit events to the database."""

    def log_sync_event(
        self,
        db: Session,
        sync_run_id: str,
        tenant_id: str,
        event_type: str,
        status: str,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Logs a synchronization event to the database.

        Args:
            db: The SQLAlchemy database session.
            sync_run_id: The unique identifier for the entire sync operation.
            tenant_id: The ID of the tenant being synced.
            event_type: The type of event (e.g., 'SYNC_START', 'FILE_ADDED').
            status: The status of the event (e.g., 'SUCCESS', 'FAILURE').
            message: A human-readable message describing the event.
            metadata: A JSON-serializable dictionary for extra details.
        """
        try:
            event = SyncEvent(
                sync_run_id=sync_run_id,
                tenant_id=tenant_id,
                event_type=event_type,
                status=status,
                message=message,
                event_metadata=metadata
            )
            db.add(event)
            db.commit()
            logger.debug(f"Logged audit event: {event_type} for sync {sync_run_id}")
        except Exception as e:
            logger.error(f"Failed to log audit event for sync {sync_run_id}: {e}", exc_info=True)
            db.rollback()

# Singleton instance
audit_logger = AuditLogger()

def get_audit_logger() -> AuditLogger:
    """Returns the singleton instance of the AuditLogger."""
    return audit_logger 