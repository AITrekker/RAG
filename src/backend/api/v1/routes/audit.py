from fastapi import APIRouter, Depends, Security
from sqlalchemy.orm import Session
from typing import List
import logging

from src.backend.db.session import get_db
from src.backend.core.auditing import AuditLogger, get_audit_logger
from src.backend.models.api_models import SyncEventResponse
from src.backend.middleware.auth import get_current_tenant

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/events", response_model=List[SyncEventResponse])
def get_audit_events(
    tenant_id: str = Security(get_current_tenant),
    db: Session = Depends(get_db),
    audit_logger: AuditLogger = Depends(get_audit_logger),
    limit: int = 100,
    offset: int = 0
) -> List[SyncEventResponse]:
    """
    Retrieve audit events for the current tenant.
    """
    logger.info(f"Fetching audit events for tenant {tenant_id}")
    events = audit_logger.get_events_for_tenant(
        db=db, 
        tenant_id=tenant_id, 
        limit=limit, 
        offset=offset
    )
    return [SyncEventResponse.from_orm(e) for e in events] 