"""
Audit API endpoints for event logging and monitoring.

This module provides audit-related endpoints for:
- Retrieving audit events
- Filtering events by tenant
- Event monitoring and reporting

All endpoints require valid authentication.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from uuid import UUID
import logging

from src.backend.models.api_models import SyncEventResponse
from src.backend.core.auditing import AuditLogger, get_audit_logger
from src.backend.middleware.api_key_auth import get_current_tenant
from src.backend.utils.error_handling import handle_exception

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Audit"])

@router.get("/events", response_model=List[SyncEventResponse])
async def get_audit_events(
    limit: int = Query(100, ge=1, le=1000, description="Number of events to retrieve"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
    current_tenant: dict = Depends(get_current_tenant),
    audit_logger: AuditLogger = Depends(get_audit_logger)
) -> List[SyncEventResponse]:
    """
    Retrieve audit events for the current tenant.
    
    Args:
        limit: Maximum number of events to return (1-1000)
        offset: Number of events to skip for pagination
        current_tenant: Current tenant from authentication
        audit_logger: Audit logger service
        
    Returns:
        List[SyncEventResponse]: List of audit events
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        logger.info(f"Fetching audit events for tenant {current_tenant.id} (limit: {limit}, offset: {offset})")
        
        # Get tenant ID from current tenant
        tenant_id = str(current_tenant.id)
        if not tenant_id:
            raise HTTPException(
                status_code=400,
                detail="Tenant ID not found in authentication context"
            )
        
        # For admin tenant, get all events; for regular tenants, get only their events
        if current_tenant.name == "admin" or current_tenant.slug == "system_admin":
            # Admin can see all events
            events = audit_logger.get_events_for_tenant(
                tenant_id=None,  # None means all tenants
                limit=limit,
                offset=offset
            )
        else:
            # Regular tenant sees only their events
            events = audit_logger.get_events_for_tenant(
                tenant_id=tenant_id,
                limit=limit,
                offset=offset
            )
        
        return [SyncEventResponse(**event) for event in events]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch audit events: {e}", exc_info=True)
        raise handle_exception(e, endpoint="get_audit_events")

@router.get("/events/tenant/{tenant_id}", response_model=List[SyncEventResponse])
async def get_tenant_audit_events(
    tenant_id: str,
    limit: int = Query(100, ge=1, le=1000, description="Number of events to retrieve"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
    current_tenant: dict = Depends(get_current_tenant),
    audit_logger: AuditLogger = Depends(get_audit_logger)
) -> List[SyncEventResponse]:
    """
    Retrieve audit events for a specific tenant (Admin only).
    
    Args:
        tenant_id: Target tenant ID
        limit: Maximum number of events to return (1-1000)
        offset: Number of events to skip for pagination
        current_tenant: Current tenant from authentication
        audit_logger: Audit logger service
        
    Returns:
        List[SyncEventResponse]: List of audit events for the specified tenant
        
    Raises:
        HTTPException: If retrieval fails or insufficient permissions
    """
    try:
        logger.info(f"Fetching audit events for tenant {tenant_id} (admin request)")
        
        # Verify admin access
        if current_tenant.name != "admin" and current_tenant.slug != "system_admin":
            raise HTTPException(
                status_code=403,
                detail="Admin access required to view other tenant's audit events"
            )
        
        # Validate tenant ID format
        try:
            UUID(tenant_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid tenant ID format"
            )
        
        events = audit_logger.get_events_for_tenant(
            tenant_id=tenant_id,
            limit=limit,
            offset=offset
        )
        
        return [SyncEventResponse(**event) for event in events]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch audit events for tenant {tenant_id}: {e}", exc_info=True)
        raise handle_exception(e, endpoint="get_tenant_audit_events")