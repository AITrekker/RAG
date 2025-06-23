"""
Sync API endpoints for document synchronization operations.

Provides endpoints for:
- Triggering manual sync operations
- Monitoring sync status and progress
- Configuring sync settings
- Managing webhooks and notifications
"""

import asyncio
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Security
from sqlalchemy.orm import Session

from ....core.document_ingestion import DocumentIngestionPipeline
from ....db.session import get_db, SessionLocal
from ....middleware.auth import require_api_key, get_current_tenant
from ....middleware.tenant_context import get_current_tenant_id
from ....models.api_models import (
    SyncTriggerRequest, SyncResponse, SyncStatusResponse, SyncConfigRequest,
    SyncHistoryResponse, SyncMetricsResponse, DocumentSyncInfo,
    WebhookConfigRequest, SyncStatus, SyncType
)
from ....models.tenant import TenantDocument
from ....utils.file_monitor import get_file_monitor, MonitorConfig, WebhookConfig
from ....utils.vector_store import get_vector_store_manager

router = APIRouter(tags=["synchronization"])

# Initialize sync components (note: these will be replaced with proper dependency injection)
# tenant_manager = TenantManager()  # Requires db_session
# document_processor = DocumentProcessor()
# delta_sync = DeltaSync(tenant_manager, document_processor)

# Global sync operations tracking
_active_syncs: Dict[str, SyncResponse] = {}

logger = logging.getLogger(__name__)


@router.get("/test")
async def test_sync_endpoint():
    """Simple test endpoint to verify sync routes are working."""
    return {"message": "Sync routes are working!", "status": "success"}


@router.post("/")
async def trigger_sync_simple():
    """Simple POST endpoint at /sync root for frontend compatibility."""
    return {"message": "Sync triggered via simple endpoint", "status": "success"}


@router.post("/trigger", response_model=SyncResponse)
# @require_api_key(scopes=["sync:write"])  # Temporarily disabled for development
async def trigger_manual_sync(
    request: SyncTriggerRequest,
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Manually trigger synchronization for a tenant.
    """
    try:
        # Generate sync ID
        sync_id = str(uuid.uuid4())
        
        # Create sync response with initial status
        sync_response = SyncResponse(
            sync_id=sync_id,
            tenant_id=tenant_id,
            status=SyncStatus.RUNNING,
            sync_type=SyncType.MANUAL,
            started_at=datetime.now(timezone.utc),
            total_files=0,
            processed_files=0,
            successful_files=0,
            failed_files=0,
            total_chunks=0,
            documents=[]
        )
        
        # Store in active syncs
        _active_syncs[sync_id] = sync_response
        
        # Add sync to background tasks
        background_tasks.add_task(
            _perform_document_sync,
            sync_id,
            tenant_id,
            request.force_full_sync,
            db
        )
        
        return sync_response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger sync: {str(e)}"
        )


@router.get("/status", response_model=SyncStatusResponse)
# @require_api_key(scopes=["sync:read"])  # Temporarily disabled for development
async def get_sync_status(
    tenant_id: str = Security(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Get the current status of the synchronization service for the tenant.
    """
    try:
        # Check for active syncs for this tenant
        current_status = "idle"
        last_sync_time = None
        last_sync_success = None
        
        # First check for any running syncs in memory
        tenant_syncs = [sync for sync in _active_syncs.values() if sync.tenant_id == tenant_id]
        running_sync = next((sync for sync in tenant_syncs if sync.status == SyncStatus.RUNNING), None)
        
        active_sync_id = None
        if running_sync:
            current_status = "running"
            active_sync_id = running_sync.sync_id
        else:
            current_status = "idle"
            
            # Get most recent sync from database (TenantDocument table)
            most_recent_doc = db.query(TenantDocument).filter(
                TenantDocument.tenant_id == tenant_id,
                TenantDocument.processed_at.isnot(None)
            ).order_by(TenantDocument.processed_at.desc()).first()
            
            if most_recent_doc:
                last_sync_time = most_recent_doc.processed_at
                last_sync_success = most_recent_doc.status == "completed"
        
        # Check for pending changes by counting unprocessed files
        documents_path = Path(f"./data/tenants/{tenant_id}/uploads")
        pending_changes = 0
        
        if documents_path.exists():
            file_patterns = ["*.txt", "*.pdf", "*.docx", "*.md", "*.html", "*.htm"]
            for pattern in file_patterns:
                pending_changes += len(list(documents_path.glob(pattern)))
            
            # Subtract already processed files
            processed_count = db.query(TenantDocument).filter(
                TenantDocument.tenant_id == tenant_id,
                TenantDocument.status.in_(["completed", "failed"])
            ).count()
            
            pending_changes = max(0, pending_changes - processed_count)
        
        return SyncStatusResponse(
            tenant_id=tenant_id,
            sync_enabled=True,
            last_sync_time=last_sync_time,
            last_sync_success=last_sync_success,
            sync_interval_minutes=1440,
            file_watcher_active=False,  # Not implemented yet
            pending_changes=pending_changes,
            current_status=current_status,
            active_sync_id=active_sync_id
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sync status: {str(e)}"
        )


@router.get("/{sync_id}", response_model=SyncResponse)
# @require_api_key(scopes=["sync:read"])  # Temporarily disabled for development
async def get_sync_operation_direct(
    sync_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get the status of a specific sync operation directly by sync ID.
    """
    try:
        sync_response = _active_syncs.get(sync_id)
        
        if not sync_response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sync operation {sync_id} not found"
            )
        
        # Verify tenant access
        if sync_response.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this sync operation"
            )
        
        return sync_response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sync operation: {str(e)}"
        )


@router.get("/operation/{sync_id}", response_model=SyncResponse)
# @require_api_key(scopes=["sync:read"])  # Temporarily disabled for development
async def get_sync_operation(
    sync_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get the status of a specific sync operation (alternative endpoint).
    """
    # Use the same logic as the direct endpoint
    return await get_sync_operation_direct(sync_id, tenant_id, db)


@router.get("/history", response_model=List[SyncHistoryResponse])
# @require_api_key(scopes=["sync:read"])  # Temporarily disabled for development
async def get_sync_history(
    limit: int = 50,
    tenant_id: str = Depends(get_current_tenant_id),
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
    tenant_id: str = Depends(get_current_tenant_id),
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
    tenant_id: str = Depends(get_current_tenant_id),
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
    tenant_id: str = Depends(get_current_tenant_id),
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
    tenant_id: str = Depends(get_current_tenant_id),
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


async def _perform_document_sync(sync_id: str, tenant_id: str, force_full: bool = False, db_session: Session = None):
    """Perform document synchronization in the background."""
    sync_response = _active_syncs.get(sync_id)
    if not sync_response:
        return
    
    try:
        # Create a new database session for the background task
        with SessionLocal() as db:
            print(f"Starting document sync for tenant {tenant_id}, sync_id: {sync_id}")
            
            # Get tenant documents directory
            documents_path = Path(f"./data/tenants/{tenant_id}/uploads")
            
            if not documents_path.exists():
                sync_response.status = SyncStatus.FAILED
                sync_response.error_message = f"Documents directory not found: {documents_path}"
                return
            
            # Scan for files in the directory
            file_patterns = ["*.txt", "*.pdf", "*.docx", "*.md", "*.html", "*.htm"]
            found_files = []
            
            for pattern in file_patterns:
                found_files.extend(documents_path.glob(pattern))
            
            sync_response.total_files = len(found_files)
            documents_processed = []
            
            # Initialize ingestion pipeline
            vector_store_manager = get_vector_store_manager()
            ingestion_pipeline = DocumentIngestionPipeline(
                tenant_id=tenant_id,
                vector_store_manager=vector_store_manager
            )
            
            for file_path in found_files:
                try:
                    print(f"Processing file: {file_path}")
                    
                    # Calculate file hash
                    file_hash = _calculate_file_hash(file_path)
                    file_size = file_path.stat().st_size
                    file_modified = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
                    
                    # Check if file already exists in database
                    existing_doc = db.query(TenantDocument).filter(
                        TenantDocument.tenant_id == tenant_id,
                        TenantDocument.filename == file_path.name
                    ).first()
                    
                    # Skip if file hasn't changed and not forcing full sync
                    if existing_doc and not force_full and existing_doc.file_hash == file_hash:
                        print(f"Skipping unchanged file: {file_path.name}")
                        sync_response.processed_files += 1
                        documents_processed.append(DocumentSyncInfo(
                            filename=file_path.name,
                            file_path=str(file_path),
                            file_size=file_size,
                            last_modified=file_modified,
                            status="skipped",
                            chunks_created=existing_doc.chunk_count if existing_doc else 0
                        ))
                        continue
                    
                    # Process the document
                    processing_start = datetime.now(timezone.utc)
                    
                    try:
                        # Use the document ingestion pipeline with a fresh session for each document
                        with SessionLocal() as doc_db:
                            document, chunks = await ingestion_pipeline.ingest_document(
                                db=doc_db,
                                file_path=file_path,
                                force_reingest=force_full
                            )
                            print(f"DEBUG: ingest_document returned {len(chunks)} chunks for {file_path.name}")
                            
                            processing_time = (datetime.now(timezone.utc) - processing_start).total_seconds()
                            
                            # Update or create TenantDocument record in main session
                            if existing_doc:
                                existing_doc.file_hash = file_hash
                                existing_doc.file_size_bytes = file_size
                                existing_doc.status = "completed"
                                existing_doc.chunk_count = len(chunks)
                                existing_doc.processed_at = datetime.now(timezone.utc)
                                existing_doc.error_message = None
                                existing_doc.embedding_model = document.embedding_model
                                db.add(existing_doc)
                            else:
                                # Create new TenantDocument record
                                tenant_doc = TenantDocument(
                                    tenant_id=tenant_id,
                                    document_id=str(document.id),
                                    filename=file_path.name,
                                    file_path=str(file_path),
                                    file_hash=file_hash,
                                    file_size_bytes=file_size,
                                    mime_type=document.mime_type,
                                    document_type=document.document_type,
                                    status="completed",
                                    processed_at=datetime.now(timezone.utc),
                                    embedding_model=document.embedding_model,
                                    chunk_count=len(chunks)
                                )
                                db.add(tenant_doc)
                            
                            db.commit()
                        
                        sync_response.successful_files += 1
                        sync_response.total_chunks += len(chunks)
                        
                        documents_processed.append(DocumentSyncInfo(
                            filename=file_path.name,
                            file_path=str(file_path),
                            file_size=file_size,
                            last_modified=file_modified,
                            status="completed",
                            chunks_created=len(chunks),
                            processing_time=processing_time
                        ))
                        
                        print(f"Successfully processed {file_path.name}: {len(chunks)} chunks created")
                        
                    except Exception as e:
                        # Handle processing error - each document failure is isolated
                        print(f"Failed to process {file_path.name}: {e}")
                        
                        # Update TenantDocument record in main session
                        if existing_doc:
                            existing_doc.status = "failed"
                            existing_doc.error_message = str(e)
                            existing_doc.processed_at = datetime.now(timezone.utc)
                            db.add(existing_doc)
                        else:
                            tenant_doc = TenantDocument(
                                tenant_id=tenant_id,
                                document_id=str(uuid.uuid4()),
                                filename=file_path.name,
                                file_path=str(file_path),
                                file_hash=file_hash,
                                file_size_bytes=file_size,
                                status="failed",
                                error_message=str(e),
                                processed_at=datetime.now(timezone.utc),
                                chunk_count=0
                            )
                            db.add(tenant_doc)
                        
                        db.commit()
                        sync_response.failed_files += 1
                        
                        documents_processed.append(DocumentSyncInfo(
                            filename=file_path.name,
                            file_path=str(file_path),
                            file_size=file_size,
                            last_modified=file_modified,
                            status="failed",
                            error_message=str(e)
                        ))
                    
                    sync_response.processed_files += 1
                    
                except Exception as e:
                    print(f"Error processing file {file_path}: {e}")
                    sync_response.failed_files += 1
                    sync_response.processed_files += 1
            
            # Update final sync status
            sync_response.status = SyncStatus.COMPLETED
            sync_response.completed_at = datetime.now(timezone.utc)
            sync_response.documents = documents_processed
            sync_response.processing_time = (sync_response.completed_at - sync_response.started_at).total_seconds()
            
            print(f"Sync completed for tenant {tenant_id}: {sync_response.successful_files}/{sync_response.total_files} files processed successfully")
        
    except Exception as e:
        print(f"Background sync error for tenant {tenant_id}: {e}")
        sync_response.status = SyncStatus.FAILED
        sync_response.error_message = str(e)
        sync_response.completed_at = datetime.now(timezone.utc)


def _calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA-256 hash of a file."""
    hash_sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest() 