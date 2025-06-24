"""
Sync API endpoints for document synchronization operations.

Provides an endpoint for triggering a manual sync operation for a tenant.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks

from src.backend.api.v1.providers import get_delta_sync
from src.backend.core.delta_sync import DeltaSync
from src.backend.middleware.auth import require_authentication
from src.backend.models.api_models import (
    SyncTriggerRequest, SyncResponse, SyncStatus, SyncType
)

router = APIRouter(tags=["synchronization"])

logger = logging.getLogger(__name__)

# This is a simplified in-memory store for sync status.
# In a real-world scenario, you would use a persistent job queue or database
# to track the status of background tasks.
_active_syncs: Dict[str, SyncResponse] = {}


@router.post("/trigger", response_model=SyncResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_manual_sync(
    request: SyncTriggerRequest,
    background_tasks: BackgroundTasks,
    tenant: str = Depends(require_authentication),
    delta_sync: DeltaSync = Depends(get_delta_sync),
):
    """
    Manually triggers a delta synchronization for the current tenant.

    This process will run in the background and perform the following steps:
    1. Scan the tenant's data source.
    2. Compare the current state with the last known state from Qdrant.
    3. Process new, modified, and deleted files.
    """
    # Note: The original logic to prevent concurrent syncs has been removed
    # for simplicity. A robust implementation would use a distributed lock
    # or a similar mechanism based on the tenant_id.

    sync_id = str(uuid.uuid4())
    sync_response = SyncResponse(
        sync_id=sync_id,
        tenant_id=tenant,
        status=SyncStatus.RUNNING,
        sync_type=SyncType.MANUAL,
        started_at=datetime.now(timezone.utc),
    )
    _active_syncs[sync_id] = sync_response

    # The actual sync logic runs in the background.
    background_tasks.add_task(
        _run_and_update_sync_status, sync_id, tenant, delta_sync
    )

    return sync_response


@router.get("/status/{sync_id}", response_model=SyncResponse)
async def get_sync_status(sync_id: str, tenant: str = Depends(require_authentication)):
    """
    Retrieves the status of a specific synchronization operation.
    """
    sync_operation = _active_syncs.get(sync_id)
    if not sync_operation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sync operation not found."
        )

    # Ensure the user can only access syncs for their own tenant.
    if sync_operation.tenant_id != tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied."
        )

    return sync_operation


async def _run_and_update_sync_status(sync_id: str, tenant_id: str, delta_sync: DeltaSync):
    """
    Wrapper task to run the sync and update its final status.
    """
    sync_op = _active_syncs[sync_id]
    logger.info(f"Background task started for sync {sync_id}, tenant '{tenant_id}'.")
    try:
        sync_results = await delta_sync.run_sync(tenant_id)
        # Note: The detailed results from the sync (new, updated, deleted files)
        # are now logged via the AuditLogger within DeltaSync. They are not
        # attached to this response object anymore to simplify the API.
        sync_op.status = SyncStatus.COMPLETED
        sync_op.total_files = (
            sync_results["new"] + sync_results["updated"] + sync_results["deleted"]
        )
        logger.info(f"Sync {sync_id} completed successfully.")
    except Exception as e:
        logger.error(f"Sync {sync_id} failed: {e}", exc_info=True)
        sync_op.status = SyncStatus.FAILED
        sync_op.error_message = str(e)
    finally:
        sync_op.finished_at = datetime.now(timezone.utc)
        logger.info(f"Background task finished for sync {sync_id}.") 