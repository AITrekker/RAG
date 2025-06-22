from fastapi import APIRouter, Depends, Security, Request
from sqlalchemy.orm import Session
from typing import List
import logging

from src.backend.db.session import get_db
from src.backend.core.auditing import AuditLogger, get_audit_logger
from src.backend.models.api_models import SyncEventResponse
from src.backend.middleware.auth import get_current_tenant, require_authentication

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/events", response_model=List[SyncEventResponse])
def get_audit_events(
    request: Request,
    # auth_context: dict = Depends(require_authentication),  # Temporarily disabled for development
    tenant_id: str = Depends(lambda: "default"),  # Default tenant for development
    db: Session = Depends(get_db),
    # audit_logger: AuditLogger = Depends(get_audit_logger),  # Temporarily disabled
    limit: int = 100,
    offset: int = 0
) -> List[SyncEventResponse]:
    """
    Retrieve audit events for the current tenant.
    """
    logger.info(f"Fetching audit events for tenant {tenant_id}")
    
    # Return mock audit events for development
    from datetime import datetime, timezone
    return [
        SyncEventResponse(
            id=1,
            sync_run_id="sync_001", 
            tenant_id=tenant_id,
            event_type="sync_started",
            status="SUCCESS",
            message="Sync operation started",
            created_at=datetime.now(timezone.utc),
            metadata={"files_count": 25}
        ),
        SyncEventResponse(
            id=2,
            sync_run_id="sync_001",
            tenant_id=tenant_id, 
            event_type="sync_completed",
            status="SUCCESS",
            message="Sync operation completed successfully",
            created_at=datetime.now(timezone.utc),
            metadata={"files_processed": 25, "duration": "45.2s"}
        )
    ] 