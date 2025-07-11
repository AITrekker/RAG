"""
Enterprise-level Sync Operations Manager
Provides heartbeat monitoring, adaptive timeouts, cleanup, and tenant-level locking
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, text, func, and_, or_, case
from sqlalchemy.orm import selectinload

from src.backend.models.database import SyncOperation, Tenant, File
from src.backend.services.sync_service import SyncService, SyncPlan

logger = logging.getLogger(__name__)


class SyncStage(Enum):
    """Sync operation stages for progress tracking"""
    INITIALIZING = "initializing"
    DETECTING_CHANGES = "detecting_changes"
    PROCESSING_FILES = "processing_files"
    UPDATING_EMBEDDINGS = "updating_embeddings"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SyncOperationConfig:
    """Configuration for sync operations"""
    base_timeout_seconds: int = 300  # 5 minutes base
    per_file_timeout_seconds: int = 10  # 10 seconds per file
    max_timeout_seconds: int = 7200  # 2 hours maximum
    min_timeout_seconds: int = 300  # 5 minutes minimum
    heartbeat_interval_seconds: int = 30  # Heartbeat every 30 seconds
    cleanup_interval_seconds: int = 300  # Cleanup check every 5 minutes
    stuck_threshold_multiplier: float = 2.0  # Mark as stuck after 2x expected duration


class SyncOperationsManager:
    """Enterprise-level sync operations management"""
    
    def __init__(
        self, 
        db_session: AsyncSession,
        sync_service: SyncService,
        config: Optional[SyncOperationConfig] = None
    ):
        self.db = db_session
        self.sync_service = sync_service
        self.config = config or SyncOperationConfig()
        self._active_syncs: Dict[UUID, asyncio.Task] = {}  # tenant_id -> task
        self._heartbeat_tasks: Dict[UUID, asyncio.Task] = {}  # sync_id -> heartbeat task
        
    async def request_sync(
        self, 
        tenant_id: UUID, 
        force_full_sync: bool = False,
        triggered_by: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Request a sync operation with intelligent queueing and conflict resolution
        
        Returns:
            Dict with status, sync_id, and message
        """
        try:
            # Check for existing running sync
            running_sync = await self._get_running_sync(tenant_id)
            
            if running_sync:
                # Check if the running sync is actually stuck
                if await self._is_sync_stuck(running_sync):
                    logger.warning(f"Detected stuck sync {running_sync.id} for tenant {tenant_id}, cleaning up")
                    await self._mark_sync_failed(
                        running_sync, 
                        "Detected as stuck, starting new sync"
                    )
                    # Cancel any heartbeat task
                    await self._cleanup_sync_tasks(running_sync.id)
                else:
                    # Sync is actively running
                    return {
                        "status": "conflict",
                        "sync_id": str(running_sync.id),
                        "message": f"Sync already in progress (stage: {running_sync.progress_stage})",
                        "progress": {
                            "stage": running_sync.progress_stage,
                            "percentage": running_sync.progress_percentage,
                            "current_file": running_sync.current_file_index,
                            "total_files": running_sync.total_files_to_process
                        }
                    }
            
            # Start new sync
            return await self._start_new_sync(tenant_id, force_full_sync, triggered_by)
            
        except Exception as e:
            logger.error(f"Error requesting sync for tenant {tenant_id}: {e}")
            return {
                "status": "error",
                "message": f"Failed to request sync: {str(e)}"
            }
    
    async def _start_new_sync(
        self, 
        tenant_id: UUID, 
        force_full_sync: bool,
        triggered_by: Optional[UUID]
    ) -> Dict[str, Any]:
        """Start a new sync operation with proper setup"""
        
        # Detect changes first to calculate timeout
        if force_full_sync:
            sync_plan = await self._create_full_sync_plan(tenant_id)
        else:
            sync_plan = await self.sync_service.detect_file_changes(tenant_id)
        
        # Calculate adaptive timeout
        expected_duration = self._calculate_timeout(sync_plan)
        
        # Create sync operation record with enhanced tracking
        sync_op = SyncOperation(
            tenant_id=tenant_id,
            operation_type='full_sync' if force_full_sync else 'delta_sync',
            triggered_by=triggered_by,
            status='running',
            started_at=datetime.now(timezone.utc),
            heartbeat_at=datetime.now(timezone.utc),
            expected_duration_seconds=expected_duration,
            progress_stage=SyncStage.INITIALIZING.value,
            progress_percentage=0.0,
            total_files_to_process=len(sync_plan.changes),
            current_file_index=0
        )
        
        self.db.add(sync_op)
        await self.db.commit()
        await self.db.refresh(sync_op)
        
        # Start heartbeat monitoring
        heartbeat_task = asyncio.create_task(
            self._heartbeat_monitor(sync_op.id)
        )
        self._heartbeat_tasks[sync_op.id] = heartbeat_task
        
        # Start sync operation with timeout
        sync_task = asyncio.create_task(
            self._execute_sync_with_monitoring(sync_op, sync_plan, force_full_sync)
        )
        self._active_syncs[tenant_id] = sync_task
        
        logger.info(f"Started sync {sync_op.id} for tenant {tenant_id} (timeout: {expected_duration}s)")
        
        return {
            "status": "started",
            "sync_id": str(sync_op.id),
            "message": "Sync operation started successfully",
            "expected_duration_seconds": expected_duration,
            "total_files": len(sync_plan.changes)
        }
    
    async def _execute_sync_with_monitoring(
        self, 
        sync_op: SyncOperation, 
        sync_plan: SyncPlan,
        force_full_sync: bool
    ):
        """Execute sync with comprehensive monitoring and error handling"""
        try:
            # Update progress: detecting changes
            await self._update_progress(
                sync_op.id, 
                SyncStage.DETECTING_CHANGES, 
                5.0
            )
            
            # Execute the actual sync with timeout
            await asyncio.wait_for(
                self._monitored_sync_execution(sync_op, sync_plan, force_full_sync),
                timeout=sync_op.expected_duration_seconds
            )
            
            # Mark as completed
            await self._complete_sync_operation(sync_op)
            
        except asyncio.TimeoutError:
            error_msg = f"Sync timed out after {sync_op.expected_duration_seconds} seconds"
            logger.error(f"Sync {sync_op.id} timed out")
            await self._mark_sync_failed(sync_op, error_msg)
            
        except Exception as e:
            error_msg = f"Sync failed with error: {str(e)}"
            logger.error(f"Sync {sync_op.id} failed: {e}")
            await self._mark_sync_failed(sync_op, error_msg)
            
        finally:
            # Cleanup tasks
            await self._cleanup_sync_tasks(sync_op.id)
            # Remove from active syncs
            if sync_op.tenant_id in self._active_syncs:
                del self._active_syncs[sync_op.tenant_id]
    
    async def _monitored_sync_execution(
        self, 
        sync_op: SyncOperation, 
        sync_plan: SyncPlan, 
        force_full_sync: bool
    ):
        """Execute sync with progress monitoring"""
        
        # Update progress: processing files
        await self._update_progress(
            sync_op.id, 
            SyncStage.PROCESSING_FILES, 
            10.0
        )
        
        # Execute the sync plan with progress callbacks
        await self._execute_with_progress(sync_op, sync_plan)
        
        # Update progress: finalizing
        await self._update_progress(
            sync_op.id, 
            SyncStage.FINALIZING, 
            95.0
        )
    
    async def _execute_with_progress(self, sync_op: SyncOperation, sync_plan: SyncPlan):
        """Execute sync plan with progress updates"""
        total_files = len(sync_plan.changes)
        
        if total_files == 0:
            await self._update_progress(sync_op.id, SyncStage.PROCESSING_FILES, 90.0)
            return
        
        # Process files with progress tracking
        for i, change in enumerate(sync_plan.changes):
            # Update current file progress
            progress = 10.0 + (80.0 * (i + 1) / total_files)  # 10% to 90%
            await self._update_file_progress(sync_op.id, i + 1, progress)
            
            # Process the file change
            try:
                if change.change_type.value == 'created':
                    await self.sync_service._process_new_file(change, sync_op)
                elif change.change_type.value == 'updated':
                    await self.sync_service._process_updated_file(change, sync_op)
                elif change.change_type.value == 'deleted':
                    await self.sync_service._process_deleted_file(change, sync_op)
            except Exception as e:
                logger.error(f"Error processing file {change.file_path}: {e}")
                # Continue processing other files
                continue
    
    async def _heartbeat_monitor(self, sync_id: UUID):
        """Monitor sync operation with periodic heartbeats"""
        from src.backend.database import AsyncSessionLocal
        
        try:
            while True:
                await asyncio.sleep(self.config.heartbeat_interval_seconds)
                
                # Use separate database session for heartbeat to avoid conflicts
                async with AsyncSessionLocal() as heartbeat_db:
                    await heartbeat_db.execute(
                        update(SyncOperation)
                        .where(SyncOperation.id == sync_id)
                        .values(heartbeat_at=datetime.now(timezone.utc))
                    )
                    await heartbeat_db.commit()
                
        except asyncio.CancelledError:
            logger.debug(f"Heartbeat monitor for sync {sync_id} cancelled")
        except Exception as e:
            logger.error(f"Heartbeat monitor error for sync {sync_id}: {e}")
    
    async def _update_progress(
        self, 
        sync_id: UUID, 
        stage: SyncStage, 
        percentage: float
    ):
        """Update sync operation progress"""
        from src.backend.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as progress_db:
            await progress_db.execute(
                update(SyncOperation)
                .where(SyncOperation.id == sync_id)
                .values(
                    progress_stage=stage.value,
                    progress_percentage=percentage,
                    heartbeat_at=datetime.now(timezone.utc)
                )
            )
            await progress_db.commit()
    
    async def _update_file_progress(
        self, 
        sync_id: UUID, 
        current_file: int, 
        percentage: float
    ):
        """Update current file processing progress"""
        from src.backend.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as progress_db:
            await progress_db.execute(
                update(SyncOperation)
                .where(SyncOperation.id == sync_id)
                .values(
                    current_file_index=current_file,
                    progress_percentage=percentage,
                    heartbeat_at=datetime.now(timezone.utc)
                )
            )
            await progress_db.commit()
    
    async def _complete_sync_operation(self, sync_op: SyncOperation):
        """Mark sync operation as completed"""
        from src.backend.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as completion_db:
            # Get current sync operation to preserve files_processed value set by sync service
            result = await completion_db.execute(
                select(SyncOperation).where(SyncOperation.id == sync_op.id)
            )
            current_sync = result.scalar_one()
            
            await completion_db.execute(
                update(SyncOperation)
                .where(SyncOperation.id == sync_op.id)
                .values(
                    status='completed',
                    completed_at=datetime.now(timezone.utc),
                    progress_stage=SyncStage.COMPLETED.value,
                    progress_percentage=100.0,
                    heartbeat_at=datetime.now(timezone.utc),
                    # Preserve files_processed value set by sync service
                    files_processed=current_sync.files_processed
                )
            )
            await completion_db.commit()
        logger.info(f"Sync {sync_op.id} completed successfully")
    
    async def _mark_sync_failed(self, sync_op: SyncOperation, error_message: str):
        """Mark sync operation as failed"""
        from src.backend.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as failure_db:
            await failure_db.execute(
                update(SyncOperation)
                .where(SyncOperation.id == sync_op.id)
                .values(
                    status='failed',
                    completed_at=datetime.now(timezone.utc),
                    progress_stage=SyncStage.FAILED.value,
                    error_message=error_message,
                    heartbeat_at=datetime.now(timezone.utc)
                )
            )
            await failure_db.commit()
        logger.warning(f"Sync {sync_op.id} marked as failed: {error_message}")
    
    async def _cleanup_sync_tasks(self, sync_id: UUID):
        """Clean up sync-related async tasks"""
        if sync_id in self._heartbeat_tasks:
            task = self._heartbeat_tasks.pop(sync_id)
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
    
    def _calculate_timeout(self, sync_plan: SyncPlan) -> int:
        """Calculate adaptive timeout based on workload"""
        total_files = len(sync_plan.changes)
        
        calculated_timeout = (
            self.config.base_timeout_seconds + 
            (total_files * self.config.per_file_timeout_seconds)
        )
        
        # Apply bounds
        return max(
            self.config.min_timeout_seconds,
            min(calculated_timeout, self.config.max_timeout_seconds)
        )
    
    async def _get_running_sync(self, tenant_id: UUID) -> Optional[SyncOperation]:
        """Get currently running sync operation for tenant"""
        result = await self.db.execute(
            select(SyncOperation)
            .where(
                and_(
                    SyncOperation.tenant_id == tenant_id,
                    SyncOperation.status == 'running'
                )
            )
            .order_by(SyncOperation.started_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def _is_sync_stuck(self, sync_op: SyncOperation) -> bool:
        """Check if a sync operation is stuck based on heartbeat and duration"""
        now = datetime.now(timezone.utc)
        
        # Check heartbeat staleness
        if sync_op.heartbeat_at:
            heartbeat_age = (now - sync_op.heartbeat_at).total_seconds()
            if heartbeat_age > (self.config.heartbeat_interval_seconds * 3):
                return True
        
        # Check if running longer than expected
        if sync_op.expected_duration_seconds:
            runtime = (now - sync_op.started_at).total_seconds()
            max_runtime = sync_op.expected_duration_seconds * self.config.stuck_threshold_multiplier
            if runtime > max_runtime:
                return True
        
        return False
    
    async def cleanup_stuck_operations(self) -> int:
        """Clean up stuck sync operations across all tenants"""
        now = datetime.now(timezone.utc)
        
        # Find potentially stuck operations
        stuck_threshold = timedelta(
            seconds=self.config.heartbeat_interval_seconds * 3
        )
        
        result = await self.db.execute(
            select(SyncOperation)
            .where(
                and_(
                    SyncOperation.status == 'running',
                    or_(
                        # No heartbeat for too long
                        SyncOperation.heartbeat_at < (now - stuck_threshold),
                        # No heartbeat at all and running too long
                        and_(
                            SyncOperation.heartbeat_at.is_(None),
                            SyncOperation.started_at < (now - timedelta(minutes=10))
                        )
                    )
                )
            )
        )
        
        stuck_operations = result.scalars().all()
        cleanup_count = 0
        
        for sync_op in stuck_operations:
            if await self._is_sync_stuck(sync_op):
                await self._mark_sync_failed(
                    sync_op, 
                    "Operation marked as stuck by cleanup job"
                )
                await self._cleanup_sync_tasks(sync_op.id)
                cleanup_count += 1
                
                # Remove from active syncs if present
                if sync_op.tenant_id in self._active_syncs:
                    task = self._active_syncs.pop(sync_op.tenant_id)
                    if not task.done():
                        task.cancel()
        
        if cleanup_count > 0:
            logger.info(f"Cleaned up {cleanup_count} stuck sync operations")
        
        return cleanup_count
    
    async def get_sync_status(self, tenant_id: UUID) -> Dict[str, Any]:
        """Get comprehensive sync status for tenant"""
        # Get latest sync operation
        result = await self.db.execute(
            select(SyncOperation)
            .where(SyncOperation.tenant_id == tenant_id)
            .order_by(SyncOperation.started_at.desc())
            .limit(1)
        )
        
        latest_sync = result.scalar_one_or_none()
        
        if not latest_sync:
            return {
                "latest_sync": None,
                "file_status": {"pending": 0, "processing": 0, "failed": 0, "total": 0}
            }
        
        # Get file status counts
        file_counts = await self.db.execute(
            select(
                func.count().label('total'),
                func.sum(case((File.sync_status == 'pending', 1), else_=0)).label('pending'),
                func.sum(case((File.sync_status == 'processing', 1), else_=0)).label('processing'),
                func.sum(case((File.sync_status == 'failed', 1), else_=0)).label('failed')
            )
            .where(File.tenant_id == tenant_id)
        )
        
        counts = file_counts.first()
        
        return {
            "latest_sync": {
                "id": str(latest_sync.id),
                "status": latest_sync.status,
                "started_at": latest_sync.started_at.isoformat(),
                "completed_at": latest_sync.completed_at.isoformat() if latest_sync.completed_at else None,
                "files_processed": latest_sync.files_processed,
                "error_message": latest_sync.error_message,
                "progress": {
                    "stage": latest_sync.progress_stage,
                    "percentage": latest_sync.progress_percentage,
                    "current_file": latest_sync.current_file_index,
                    "total_files": latest_sync.total_files_to_process
                },
                "heartbeat_at": latest_sync.heartbeat_at.isoformat() if latest_sync.heartbeat_at else None,
                "expected_duration_seconds": latest_sync.expected_duration_seconds
            },
            "file_status": {
                "pending": int(counts.pending or 0),
                "processing": int(counts.processing or 0),
                "failed": int(counts.failed or 0),
                "total": int(counts.total or 0)
            }
        }
    
    async def start_background_cleanup(self):
        """Start background cleanup task"""
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(self.config.cleanup_interval_seconds)
                    await self.cleanup_stuck_operations()
                except Exception as e:
                    logger.error(f"Background cleanup error: {e}")
        
        return asyncio.create_task(cleanup_loop())
    
    async def _create_full_sync_plan(self, tenant_id: UUID):
        """Create a sync plan that forces reprocessing of all files"""
        from .sync_service import SyncPlan, FileChange, ChangeType
        
        # Get all files from database
        db_files = await self.sync_service.file_service.list_files(tenant_id, limit=10000)
        
        # Create changes for all files to force reprocessing
        changes = []
        for db_file in db_files:
            changes.append(FileChange(
                change_type=ChangeType.UPDATED,
                file_path=db_file.file_path,
                file_id=db_file.id,
                old_hash=db_file.file_hash,
                new_hash=db_file.file_hash,  # Same hash, but force update
                file_size=db_file.file_size,
                modified_time=db_file.updated_at
            ))
        
        print(f"🔄 FULL SYNC: Force processing {len(changes)} files for tenant {tenant_id}")
        return SyncPlan(tenant_id=tenant_id, changes=changes) 