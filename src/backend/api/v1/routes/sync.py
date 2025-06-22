"""
Document Synchronization API Routes

This module provides comprehensive API endpoints for managing document
synchronization, monitoring sync status, and configuring sync settings.
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.orm import Session
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
import asyncio

from src.backend.db.session import get_db
from src.backend.core.delta_sync import DeltaSync, SyncResult
from src.backend.core.tenant_manager import TenantManager
from src.backend.core.document_processor import DocumentProcessor
from src.backend.middleware.auth import require_api_key, security_middleware
from src.backend.models.api_models import (
    SyncStatusResponse, SyncHistoryResponse, SyncConfigRequest,
    WebhookConfigRequest, SyncTriggerRequest, SyncMetricsResponse
)
from src.backend.utils.file_monitor import get_file_monitor, MonitorConfig, WebhookConfig

router = APIRouter(tags=["synchronization"])

# Initialize sync components (note: these will be replaced with proper dependency injection)
# tenant_manager = TenantManager()  # Requires db_session
# document_processor = DocumentProcessor()
# delta_sync = DeltaSync(tenant_manager, document_processor)


@router.get("/test")
async def test_sync_endpoint():
    """Simple test endpoint to verify sync routes are working."""
    return {"message": "Sync routes are working!", "status": "success"}


@router.post("/")
async def trigger_sync_simple():
    """Simple POST endpoint at /sync root for frontend compatibility."""
    return {"message": "Sync triggered via simple endpoint", "status": "success"}


@router.post("/trigger", response_model=Dict[str, str])
# @require_api_key(scopes=["sync:write"])  # Temporarily disabled for development
async def trigger_manual_sync(
    request: SyncTriggerRequest,
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(lambda: "default"),  # Default tenant for development
    db: Session = Depends(get_db)
):
    """
    Manually trigger synchronization for a tenant.
    """
    try:
        # Add sync to background tasks
        background_tasks.add_task(
            _perform_background_sync,
            tenant_id,
            "manual_trigger",
            request.force_full_sync,
            db
        )
        
        return {
            "message": "Sync triggered successfully",
            "tenant_id": tenant_id,
            "trigger_type": "manual"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger sync: {str(e)}"
        )


@router.get("/status", response_model=SyncStatusResponse)
# @require_api_key(scopes=["sync:read"])  # Temporarily disabled for development
async def get_sync_status(
    tenant_id: str = Depends(lambda: "default"),  # Default tenant for development
    db: Session = Depends(get_db)
):
    """
    Get current synchronization status for a tenant.
    """
    try:
        # Return a mock status response for development
        return SyncStatusResponse(
            tenant_id=tenant_id,
            sync_enabled=True,
            last_sync_time=datetime.now(timezone.utc).isoformat(),
            last_sync_success=True,
            sync_interval_minutes=1440,
            file_watcher_active=True,
            pending_changes=0,
            current_status="idle"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sync status: {str(e)}"
        )


@router.get("/history", response_model=List[SyncHistoryResponse])
# @require_api_key(scopes=["sync:read"])  # Temporarily disabled for development
async def get_sync_history(
    limit: int = 50,
    tenant_id: str = Depends(lambda: "default"),  # Default tenant for development
    db: Session = Depends(get_db)
):
    """
    Get synchronization history for a tenant.
    """
    try:
        # Return mock sync history for development
        return SyncHistoryResponse(
            syncs=[],  # Empty list for now - would contain SyncResponse objects
            total_count=0,
            page=1,
            page_size=limit
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sync history: {str(e)}"
        )


@router.put("/config", response_model=Dict[str, str])
@require_api_key(scopes=["sync:write"])
async def update_sync_config(
    config: SyncConfigRequest,
    tenant_id: str = Depends(lambda: None),  # Injected by middleware
    db: Session = Depends(get_db)
):
    """
    Update synchronization configuration for a tenant.
    """
    try:
        file_monitor = get_file_monitor()
        
        # Get tenant documents path
        tenant_config = tenant_manager.get_tenant_config(tenant_id)
        if not tenant_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        # Create webhook configs
        webhooks = []
        if config.webhooks:
            for webhook_data in config.webhooks:
                webhooks.append(WebhookConfig(
                    url=webhook_data.url,
                    secret=webhook_data.secret,
                    events=webhook_data.events,
                    timeout=webhook_data.timeout,
                    retry_count=webhook_data.retry_count
                ))
        
        # Create monitor config
        monitor_config = MonitorConfig(
            tenant_id=tenant_id,
            documents_path=tenant_config.documents_path,
            sync_interval_minutes=config.sync_interval_minutes,
            auto_sync_enabled=config.auto_sync_enabled,
            webhooks=webhooks,
            ignore_patterns=set(config.ignore_patterns or [])
        )
        
        # Remove existing monitoring and add new
        file_monitor.remove_tenant_monitoring(tenant_id)
        file_monitor.add_tenant_monitoring(monitor_config)
        
        return {
            "message": "Sync configuration updated successfully",
            "tenant_id": tenant_id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update sync config: {str(e)}"
        )


@router.get("/config", response_model=Dict[str, Any])
# @require_api_key(scopes=["sync:read"])  # Temporarily disabled for development
async def get_sync_config(
    tenant_id: str = Depends(lambda: "default"),  # Default tenant for development
    db: Session = Depends(get_db)
):
    """
    Get current synchronization configuration for a tenant.
    """
    try:
        # Return mock config for development
        return {
            "tenant_id": tenant_id,
            "auto_sync_enabled": True,
            "sync_interval_minutes": 1440,
            "documents_path": "./data/documents/default",
            "ignore_patterns": ["*.tmp", "*.log", ".DS_Store"],
            "webhooks": []
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sync config: {str(e)}"
        )


@router.post("/webhooks/test", response_model=Dict[str, str])
@require_api_key(scopes=["sync:write"])
async def test_webhook(
    webhook_config: WebhookConfigRequest,
    tenant_id: str = Depends(lambda: None),  # Injected by middleware
    db: Session = Depends(get_db)
):
    """
    Test a webhook configuration by sending a test event.
    """
    try:
        from src.backend.utils.file_monitor import WebhookNotifier
        
        webhook_notifier = WebhookNotifier()
        webhook = WebhookConfig(
            url=webhook_config.url,
            secret=webhook_config.secret,
            events=webhook_config.events,
            timeout=webhook_config.timeout,
            retry_count=webhook_config.retry_count
        )
        
        # Create test event data
        test_event_data = {
            'event_type': 'webhook_test',
            'tenant_id': tenant_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'message': 'This is a test webhook event'
        }
        
        # Send test webhook
        success = await webhook_notifier.send_webhook(webhook, test_event_data)
        
        if success:
            return {
                "message": "Webhook test successful",
                "url": webhook_config.url
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Webhook test failed"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test webhook: {str(e)}"
        )


@router.get("/metrics", response_model=SyncMetricsResponse)
# @require_api_key(scopes=["sync:read"])  # Temporarily disabled for development
async def get_sync_metrics(
    days: int = 7,
    tenant_id: str = Depends(lambda: "default"),  # Default tenant for development
    db: Session = Depends(get_db)
):
    """
    Get synchronization metrics and analytics for a tenant.
    """
    try:
        # Return mock metrics for development
        return SyncMetricsResponse(
            tenant_id=tenant_id,
            total_syncs=15,
            successful_syncs=14,
            failed_syncs=1,
            success_rate=93.3,
            total_files_processed=150,
            total_errors=3,
            average_duration=45.2,
            last_sync_time=datetime.now(timezone.utc)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sync metrics: {str(e)}"
        )


@router.post("/pause", response_model=Dict[str, str])
# @require_api_key(scopes=["sync:write"])  # Temporarily disabled for development
async def pause_sync(
    tenant_id: str = Depends(lambda: "default"),  # Default tenant for development
    db: Session = Depends(get_db)
):
    """
    Pause automatic synchronization for a tenant.
    """
    try:
        file_monitor = get_file_monitor()
        config = file_monitor.get_tenant_config(tenant_id)
        
        if config:
            config.auto_sync_enabled = False
            file_monitor.remove_tenant_monitoring(tenant_id)
            file_monitor.add_tenant_monitoring(config)
        
        return {
            "message": "Automatic sync paused",
            "tenant_id": tenant_id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to pause sync: {str(e)}"
        )


@router.post("/resume", response_model=Dict[str, str])
# @require_api_key(scopes=["sync:write"])  # Temporarily disabled for development
async def resume_sync(
    tenant_id: str = Depends(lambda: "default"),  # Default tenant for development
    db: Session = Depends(get_db)
):
    """
    Resume automatic synchronization for a tenant.
    """
    try:
        file_monitor = get_file_monitor()
        config = file_monitor.get_tenant_config(tenant_id)
        
        if config:
            config.auto_sync_enabled = True
            file_monitor.remove_tenant_monitoring(tenant_id)
            file_monitor.add_tenant_monitoring(config)
        
        return {
            "message": "Automatic sync resumed",
            "tenant_id": tenant_id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume sync: {str(e)}"
        )


async def _perform_background_sync(tenant_id: str, trigger_reason: str, force_full: bool = False, db_session: Session = None):
    """Perform synchronization in the background."""
    try:
        # Initialize components with proper dependencies
        if db_session is None:
            db_session = next(get_db())
        
        tenant_manager = TenantManager(db_session)
        document_processor = DocumentProcessor()
        delta_sync_instance = DeltaSync(tenant_manager, document_processor)
        
        print(f"Starting sync for tenant {tenant_id}, reason: {trigger_reason}, force_full: {force_full}")
        
        # Perform the actual sync
        result = delta_sync_instance.sync_documents(tenant_id, force_full)
        
        if result.success:
            print(f"Sync completed successfully for tenant {tenant_id}")
        else:
            print(f"Sync failed for tenant {tenant_id}: {result.errors}")
            
    except Exception as e:
        print(f"Background sync error for tenant {tenant_id}: {e}")
    finally:
        if db_session:
            db_session.close() 