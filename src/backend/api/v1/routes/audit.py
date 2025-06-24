from fastapi import APIRouter, Depends
from typing import List
import logging

from src.backend.core.auditing import AuditLogger, get_audit_logger
from src.backend.models.api_models import SyncEventResponse
from src.backend.middleware.auth import require_authentication

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get(
    "/events", 
    response_model=List[SyncEventResponse],
    dependencies=[Depends(require_authentication)]
)
def get_audit_events(
    tenant_id: str = Depends(require_authentication), # Use the tenant_id from the auth key
    audit_logger: AuditLogger = Depends(get_audit_logger),
    limit: int = 100,
    offset: int = 0
) -> List[SyncEventResponse]:
    """
    Retrieve audit events for the current tenant.
    """
    logger.info(f"Fetching audit events for tenant {tenant_id}")
    
    events = audit_logger.get_events_for_tenant(
        tenant_id=tenant_id,
        limit=limit,
        offset=offset
    )
    # The events from Qdrant are dicts, we need to convert them to the Pydantic model.
    # This assumes the keys in the payload match the model fields.
    return [SyncEventResponse(**event) for event in events] 