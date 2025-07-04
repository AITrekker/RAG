"""
Sync Service - Handles delta sync operations and file synchronization
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from uuid import UUID
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from src.backend.models.database import File, SyncOperation, FileSyncHistory, User
from src.backend.services.file_service import FileService
from src.backend.services.embedding_service import EmbeddingService


class ChangeType(Enum):
    """Types of file changes detected during sync"""
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass
class FileChange:
    """Represents a file change detected during sync"""
    change_type: ChangeType
    file_path: str
    file_id: Optional[UUID] = None
    old_hash: Optional[str] = None
    new_hash: Optional[str] = None
    file_size: Optional[int] = None
    modified_time: Optional[datetime] = None


@dataclass
class SyncPlan:
    """Plan of changes to be made during sync"""
    tenant_id: UUID
    changes: List[FileChange]
    
    @property
    def new_files(self) -> List[FileChange]:
        return [c for c in self.changes if c.change_type == ChangeType.CREATED]
    
    @property
    def updated_files(self) -> List[FileChange]:
        return [c for c in self.changes if c.change_type == ChangeType.UPDATED]
    
    @property
    def deleted_files(self) -> List[FileChange]:
        return [c for c in self.changes if c.change_type == ChangeType.DELETED]
    
    @property
    def total_changes(self) -> int:
        return len(self.changes)


class SyncService:
    """Service for file synchronization and delta sync operations"""
    
    def __init__(
        self, 
        db_session: AsyncSession,
        file_service: FileService,
        embedding_service: EmbeddingService
    ):
        self.db = db_session
        self.file_service = file_service
        self.embedding_service = embedding_service
    
    async def get_or_create_system_user(self) -> UUID:
        """Get or create a system user for auto-discovered files"""
        # Try to find existing system user
        result = await self.db.execute(
            select(User).where(User.email == 'system@delta-sync.local')
        )
        system_user = result.scalar_one_or_none()
        
        if not system_user:
            # Create system user
            system_user = User(
                email='system@delta-sync.local',
                password_hash='system_user_no_login',
                full_name='Delta Sync System User',
                is_active=True
            )
            self.db.add(system_user)
            await self.db.commit()
            await self.db.refresh(system_user)
        
        return system_user.id
    
    async def detect_file_changes(self, tenant_id: UUID) -> SyncPlan:
        """
        Detect file changes by comparing filesystem with database
        
        Args:
            tenant_id: Tenant to scan for changes
            
        Returns:
            SyncPlan: Plan of changes to be executed
        """
        # Get current files from filesystem
        fs_files = await self.file_service.scan_tenant_files(tenant_id)
        fs_file_map = {f['path']: f for f in fs_files}
        
        # Get current files from database
        db_files = await self.file_service.list_files(tenant_id, limit=10000)
        db_file_map = {f.file_path: f for f in db_files}
        
        changes = []
        
        # Detect new and updated files
        for file_path, fs_file in fs_file_map.items():
            db_file = db_file_map.get(file_path)
            
            if not db_file:
                # New file
                changes.append(FileChange(
                    change_type=ChangeType.CREATED,
                    file_path=file_path,
                    new_hash=fs_file['hash'],
                    file_size=fs_file['size'],
                    modified_time=fs_file['modified_time']
                ))
            elif db_file.file_hash != fs_file['hash']:
                # Updated file
                changes.append(FileChange(
                    change_type=ChangeType.UPDATED,
                    file_path=file_path,
                    file_id=db_file.id,
                    old_hash=db_file.file_hash,
                    new_hash=fs_file['hash'],
                    file_size=fs_file['size'],
                    modified_time=fs_file['modified_time']
                ))
        
        # Detect deleted files
        for file_path, db_file in db_file_map.items():
            if file_path not in fs_file_map:
                changes.append(FileChange(
                    change_type=ChangeType.DELETED,
                    file_path=file_path,
                    file_id=db_file.id,
                    old_hash=db_file.file_hash
                ))
        
        return SyncPlan(tenant_id=tenant_id, changes=changes)
    
    async def execute_sync_plan(
        self, 
        sync_plan: SyncPlan,
        triggered_by: Optional[UUID] = None
    ) -> SyncOperation:
        """
        Execute a sync plan and update database/vector store
        
        Args:
            sync_plan: Plan of changes to execute
            triggered_by: User who triggered the sync (None for automatic)
            
        Returns:
            SyncOperation: Record of the sync operation
        """
        # Create sync operation record
        sync_op = SyncOperation(
            tenant_id=sync_plan.tenant_id,
            operation_type='delta_sync',
            triggered_by=triggered_by,
            status='running',
            started_at=datetime.utcnow()
        )
        self.db.add(sync_op)
        await self.db.commit()
        await self.db.refresh(sync_op)
        
        try:
            # Execute changes
            await self._execute_file_changes(sync_plan, sync_op)
            
            # Update sync operation status
            await self._complete_sync_operation(sync_op, sync_plan)
            
        except Exception as e:
            # Mark sync as failed
            await self._fail_sync_operation(sync_op, str(e))
            raise
        
        return sync_op
    
    async def _execute_file_changes(
        self, 
        sync_plan: SyncPlan, 
        sync_op: SyncOperation
    ):
        """Execute the actual file changes"""
        
        # Process new files
        for change in sync_plan.new_files:
            await self._process_new_file(change, sync_op)
        
        # Process updated files
        for change in sync_plan.updated_files:
            await self._process_updated_file(change, sync_op)
        
        # Process deleted files
        for change in sync_plan.deleted_files:
            await self._process_deleted_file(change, sync_op)
    
    async def _process_new_file(self, change: FileChange, sync_op: SyncOperation):
        """Process a new file by creating record and scheduling for processing"""
        try:
            # Use system user for auto-discovered files if no specific user
            uploaded_by = sync_op.triggered_by
            if uploaded_by is None:
                uploaded_by = await self.get_or_create_system_user()
            
            # Create file record for discovered file
            file_record = File(
                tenant_id=sync_op.tenant_id,
                uploaded_by=uploaded_by,
                filename=Path(change.file_path).name,
                file_path=change.file_path,
                file_size=change.file_size or 0,
                file_hash=change.new_hash,
                sync_status='pending'
            )
            
            self.db.add(file_record)
            await self.db.flush()  # Get ID without committing
            
            # Process the file immediately
            chunks = await self.embedding_service.process_file(file_record)
            embeddings = await self.embedding_service.generate_embeddings(chunks)
            await self.embedding_service.store_embeddings(file_record, chunks, embeddings)
            
            # Update file status to synced
            file_record.sync_status = 'synced'
            file_record.sync_completed_at = datetime.utcnow()
            
            # Create sync history record
            await self._create_sync_history(file_record.id, sync_op, change)
            
        except Exception as e:
            if 'file_record' in locals():
                file_record.sync_status = 'failed'
                file_record.sync_error = str(e)
            raise
    
    async def _process_updated_file(self, change: FileChange, sync_op: SyncOperation):
        """Process an updated file by reprocessing embeddings"""
        if not change.file_id:
            return
        
        try:
            # Update file hash and mark as processing
            await self.db.execute(
                update(File)
                .where(File.id == change.file_id)
                .values(
                    file_hash=change.new_hash,
                    file_size=change.file_size,
                    sync_status='processing',
                    sync_started_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            )
            
            # Get updated file record
            result = await self.db.execute(
                select(File).where(File.id == change.file_id)
            )
            file_record = result.scalar_one()
            
            # Delete old embeddings first
            deleted_count = await self.embedding_service.delete_file_embeddings(change.file_id)
            
            # Reprocess the file
            chunks = await self.embedding_service.process_file(file_record)
            embeddings = await self.embedding_service.generate_embeddings(chunks)
            await self.embedding_service.store_embeddings(file_record, chunks, embeddings)
            
            # Update file status to synced
            await self.db.execute(
                update(File)
                .where(File.id == change.file_id)
                .values(
                    sync_status='synced',
                    sync_completed_at=datetime.utcnow(),
                    sync_error=None
                )
            )
            
            # Create sync history record
            await self._create_sync_history(change.file_id, sync_op, change)
            
        except Exception as e:
            # Mark file as failed
            await self.db.execute(
                update(File)
                .where(File.id == change.file_id)
                .values(
                    sync_status='failed',
                    sync_completed_at=datetime.utcnow(),
                    sync_error=str(e)
                )
            )
            raise
    
    async def _process_deleted_file(self, change: FileChange, sync_op: SyncOperation):
        """Process a deleted file by cleaning up records and embeddings"""
        if not change.file_id:
            return
        
        try:
            # Delete embeddings first
            deleted_count = await self.embedding_service.delete_file_embeddings(change.file_id)
            
            # Soft delete file record
            await self.db.execute(
                update(File)
                .where(File.id == change.file_id)
                .values(
                    deleted_at=datetime.utcnow(),
                    sync_status='deleted'
                )
            )
            
            # Create sync history record
            await self._create_sync_history(change.file_id, sync_op, change)
            
        except Exception as e:
            # Log error but don't fail sync for cleanup issues
            await self._create_sync_history(change.file_id, sync_op, change)
    
    async def _create_sync_history(
        self, 
        file_id: Optional[UUID], 
        sync_op: SyncOperation, 
        change: FileChange
    ):
        """Create a sync history record"""
        if not file_id:
            return
        
        # For deleted files, new_hash should be the previous hash since file didn't change content
        new_hash = change.new_hash
        if change.change_type == ChangeType.DELETED and new_hash is None:
            new_hash = change.old_hash
        
        history = FileSyncHistory(
            file_id=file_id,
            sync_operation_id=sync_op.id,
            previous_hash=change.old_hash,
            new_hash=new_hash,
            change_type=change.change_type.value,
            synced_at=datetime.utcnow()
        )
        self.db.add(history)
    
    async def _complete_sync_operation(
        self, 
        sync_op: SyncOperation, 
        sync_plan: SyncPlan
    ):
        """Mark sync operation as completed"""
        await self.db.execute(
            update(SyncOperation)
            .where(SyncOperation.id == sync_op.id)
            .values(
                status='completed',
                completed_at=datetime.utcnow(),
                files_processed=sync_plan.total_changes,
                files_added=len(sync_plan.new_files),
                files_updated=len(sync_plan.updated_files),
                files_deleted=len(sync_plan.deleted_files)
            )
        )
        await self.db.commit()
    
    async def _fail_sync_operation(self, sync_op: SyncOperation, error: str):
        """Mark sync operation as failed"""
        await self.db.execute(
            update(SyncOperation)
            .where(SyncOperation.id == sync_op.id)
            .values(
                status='failed',
                completed_at=datetime.utcnow(),
                error_message=error
            )
        )
        await self.db.commit()
    
    async def trigger_full_sync(
        self, 
        tenant_id: UUID, 
        triggered_by: Optional[UUID] = None
    ) -> SyncOperation:
        """
        Trigger a full sync for a tenant
        
        Args:
            tenant_id: Tenant to sync
            triggered_by: User who triggered the sync
            
        Returns:
            SyncOperation: Record of the sync operation
        """
        sync_plan = await self.detect_file_changes(tenant_id)
        return await self.execute_sync_plan(sync_plan, triggered_by)
    
    async def trigger_file_sync(
        self, 
        file_id: UUID, 
        triggered_by: Optional[UUID] = None
    ) -> bool:
        """
        Trigger sync for a specific file
        
        Args:
            file_id: File to sync
            triggered_by: User who triggered the sync
            
        Returns:
            bool: True if sync was successful
        """
        # Get file record
        result = await self.db.execute(
            select(File).where(File.id == file_id)
        )
        file_record = result.scalar_one_or_none()
        
        if not file_record:
            return False
        
        # Create individual sync operation for this file
        sync_op = SyncOperation(
            tenant_id=file_record.tenant_id,
            operation_type='file_sync',
            triggered_by=triggered_by,
            status='running',
            started_at=datetime.utcnow()
        )
        self.db.add(sync_op)
        await self.db.commit()
        await self.db.refresh(sync_op)
        
        try:
            # Mark file as processing
            await self.db.execute(
                update(File)
                .where(File.id == file_id)
                .values(
                    sync_status='processing',
                    sync_started_at=datetime.utcnow()
                )
            )
            
            # Delete old embeddings if they exist
            await self.embedding_service.delete_file_embeddings(file_id)
            
            # Process file
            chunks = await self.embedding_service.process_file(file_record)
            embeddings = await self.embedding_service.generate_embeddings(chunks)
            await self.embedding_service.store_embeddings(file_record, chunks, embeddings)
            
            # Mark file as completed
            await self.db.execute(
                update(File)
                .where(File.id == file_id)
                .values(
                    sync_status='synced',
                    sync_completed_at=datetime.utcnow(),
                    sync_error=None
                )
            )
            
            # Mark sync operation as completed
            await self.db.execute(
                update(SyncOperation)
                .where(SyncOperation.id == sync_op.id)
                .values(
                    status='completed',
                    completed_at=datetime.utcnow(),
                    files_processed=1,
                    files_updated=1
                )
            )
            await self.db.commit()
            
            return True
            
        except Exception as e:
            # Mark file as failed
            await self.db.execute(
                update(File)
                .where(File.id == file_id)
                .values(
                    sync_status='failed',
                    sync_completed_at=datetime.utcnow(),
                    sync_error=str(e)
                )
            )
            
            # Mark sync operation as failed
            await self.db.execute(
                update(SyncOperation)
                .where(SyncOperation.id == sync_op.id)
                .values(
                    status='failed',
                    completed_at=datetime.utcnow(),
                    error_message=str(e)
                )
            )
            await self.db.commit()
            
            return False
    
    async def get_sync_status(self, tenant_id: UUID) -> Dict[str, Any]:
        """Get current sync status for a tenant"""
        # Get latest sync operation
        result = await self.db.execute(
            select(SyncOperation)
            .where(SyncOperation.tenant_id == tenant_id)
            .order_by(SyncOperation.started_at.desc())
            .limit(1)
        )
        latest_sync = result.scalar_one_or_none()
        
        # Get file counts by status
        pending_files = await self.file_service.get_files_by_sync_status(tenant_id, 'pending')
        processing_files = await self.file_service.get_files_by_sync_status(tenant_id, 'processing')
        failed_files = await self.file_service.get_files_by_sync_status(tenant_id, 'failed')
        
        return {
            'latest_sync': {
                'id': str(latest_sync.id) if latest_sync else None,
                'status': latest_sync.status if latest_sync else None,
                'started_at': latest_sync.started_at.isoformat() if latest_sync else None,
                'completed_at': latest_sync.completed_at.isoformat() if latest_sync and latest_sync.completed_at else None,
                'files_processed': latest_sync.files_processed if latest_sync else 0,
                'error_message': latest_sync.error_message if latest_sync else None
            },
            'file_status': {
                'pending': len(pending_files),
                'processing': len(processing_files),
                'failed': len(failed_files),
                'total': len(pending_files) + len(processing_files) + len(failed_files)
            }
        }
    
    async def get_sync_history(
        self, 
        tenant_id: UUID, 
        limit: int = 50
    ) -> List[SyncOperation]:
        """Get sync history for a tenant"""
        result = await self.db.execute(
            select(SyncOperation)
            .where(SyncOperation.tenant_id == tenant_id)
            .order_by(SyncOperation.started_at.desc())
            .limit(limit)
        )
        return result.scalars().all()


# Dependency function for FastAPI
async def get_sync_service(
    db_session: AsyncSession,
    file_service: FileService,
    embedding_service: EmbeddingService
) -> SyncService:
    """Dependency to get sync service with required dependencies"""
    return SyncService(db_session, file_service, embedding_service)


# Additional helper functions for sync operations
async def schedule_tenant_sync(tenant_id: UUID, triggered_by: Optional[UUID] = None):
    """Schedule a tenant sync operation (can be used by background tasks)"""
    # This would integrate with a task queue like Celery in production
    pass


async def get_pending_sync_operations(db_session: AsyncSession) -> List[SyncOperation]:
    """Get all pending sync operations for processing"""
    result = await db_session.execute(
        select(SyncOperation)
        .where(SyncOperation.status == 'running')
        .order_by(SyncOperation.started_at)
    )
    return result.scalars().all()