"""
Sync Service - Handles delta sync operations and file synchronization
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from uuid import UUID
from dataclasses import dataclass
from enum import Enum
import os, psutil  # Add at the top if not present

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, text

from src.backend.models.database import File, SyncOperation
from src.backend.services.file_service import FileService
from src.backend.services.sync_embedding_service import SyncEmbeddingService
from src.backend.config.settings import get_settings

logger = logging.getLogger(__name__)





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
        embedding_model=None
    ):
        # Use the properly injected async session
        self.db = db_session
        self.file_service = file_service
        # Create synchronous embedding service
        self.sync_embedding_service = SyncEmbeddingService(embedding_model=embedding_model)
        self.settings = get_settings()
    
    async def check_for_running_syncs(self, tenant_id: UUID) -> Optional[SyncOperation]:
        """Check if there's already a running sync for this tenant"""
        result = await self.db.execute(
            select(SyncOperation).where(
                SyncOperation.tenant_id == tenant_id,
                SyncOperation.status == 'running'
            ).order_by(SyncOperation.started_at.desc())
        )
        return result.scalar_one_or_none()
    
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
        
        # Get current files from database (hard delete means no deleted_at filter needed)
        db_files = await self.file_service.list_files(tenant_id, limit=10000)
        db_file_map = {f.file_path: f for f in db_files}
        
        # DEBUG: Log what we found
        print(f"🔍 DEBUG Tenant {tenant_id}:")
        print(f"  Filesystem files: {len(fs_files)} - {list(fs_file_map.keys())[:3]}...")
        print(f"  Database files: {len(db_files)} - {list(db_file_map.keys())[:3]}...")
        
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
        sync_plan: SyncPlan
    ) -> SyncOperation:
        """
        Execute a sync plan with synchronous embedding and rich progress tracking
        
        Args:
            sync_plan: Plan of changes to execute
            
        Returns:
            SyncOperation: Record of the sync operation
        """
        # Check if there's already a running sync
        running_sync = await self.check_for_running_syncs(sync_plan.tenant_id)
        if running_sync:
            raise Exception(f"Sync already in progress for tenant {sync_plan.tenant_id}. Operation ID: {running_sync.id}")
        
        # Create sync operation record with detailed progress fields
        sync_op = SyncOperation(
            tenant_id=sync_plan.tenant_id,
            operation_type='delta_sync',
            status='running',
            started_at=datetime.utcnow(),
            total_files_to_process=sync_plan.total_changes,
            progress_stage='initializing',
            progress_percentage=0.0
        )
        self.db.add(sync_op)
        await self.db.commit()
        await self.db.refresh(sync_op)
        
        try:
            # Handle deletions first (async)
            if sync_plan.deleted_files:
                await self._process_deleted_files_async(sync_plan.deleted_files, sync_op)
            
            # Process new and updated files with synchronous embedding
            files_to_process = []
            for change in sync_plan.new_files + sync_plan.updated_files:
                if change.file_id:
                    # Get file record from database
                    result = await self.db.execute(
                        select(File).where(File.id == change.file_id)
                    )
                    file_record = result.scalar_one_or_none()
                    if file_record:
                        files_to_process.append(file_record)
            
            if files_to_process:
                # Use synchronous embedding service with progress tracking
                # This runs in the background to avoid blocking the async context
                result = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    self.sync_embedding_service.process_files_with_progress,
                    files_to_process,
                    sync_plan.tenant_id,
                    sync_op.id
                )
                
                # Update final counts
                await self.db.execute(
                    text("""
                        UPDATE sync_operations 
                        SET files_processed = :files_processed,
                            chunks_created = :chunks_created,
                            files_added = :files_added,
                            files_updated = :files_updated
                        WHERE id = :sync_op_id
                    """),
                    {
                        'sync_op_id': sync_op.id,
                        'files_processed': result['files_processed'],
                        'chunks_created': result['chunks_created'],
                        'files_added': len(sync_plan.new_files),
                        'files_updated': len(sync_plan.updated_files)
                    }
                )
                await self.db.commit()
            
            # Mark sync as completed
            await self.db.execute(
                text("""
                    UPDATE sync_operations 
                    SET status = 'completed',
                        completed_at = :completed_at,
                        progress_stage = 'completed',
                        progress_percentage = 100.0
                    WHERE id = :sync_op_id
                """),
                {
                    'sync_op_id': sync_op.id,
                    'completed_at': datetime.utcnow()
                }
            )
            await self.db.commit()
            
        except Exception as e:
            # Mark sync as failed
            await self.db.execute(
                text("""
                    UPDATE sync_operations 
                    SET status = 'failed',
                        completed_at = :completed_at,
                        error_message = :error_message,
                        progress_stage = 'failed'
                    WHERE id = :sync_op_id
                """),
                {
                    'sync_op_id': sync_op.id,
                    'completed_at': datetime.utcnow(),
                    'error_message': str(e)
                }
            )
            await self.db.commit()
            raise
        
        return sync_op
    
    async def _process_deleted_files_async(self, deleted_files: List[FileChange], sync_op: SyncOperation):
        """Process deleted files - remove from database and vector store"""
        for change in deleted_files:
            if change.file_id:
                # Delete embeddings
                await self.db.execute(
                    text("DELETE FROM embedding_chunks WHERE file_id = :file_id"),
                    {'file_id': change.file_id}
                )
                # Delete file record
                await self.db.execute(
                    text("DELETE FROM files WHERE id = :file_id"),
                    {'file_id': change.file_id}
                )
        await self.db.commit()
    
    async def _execute_file_changes(
        self, 
        sync_plan: SyncPlan, 
        sync_op: SyncOperation
    ):
        """Execute the actual file changes with optimized async/await concurrency"""
        
        print(f"🔍 DEBUG: _execute_file_changes called with {len(sync_plan.new_files)} new, {len(sync_plan.updated_files)} updated, {len(sync_plan.deleted_files)} deleted")
        
        # Process deletions sequentially (simplified)
        if sync_plan.deleted_files:
            await self._process_deleted_files_sequentially(sync_plan.deleted_files, sync_op)
        
        # Process new and updated files sequentially (simplified)
        await self._process_files_sequentially(sync_plan, sync_op)
    
    async def _process_files_sequentially(self, sync_plan: SyncPlan, sync_op: SyncOperation):
        """Process files one at a time (simplified for reliability)"""
        all_files = sync_plan.new_files + sync_plan.updated_files
        
        if not all_files:
            return
        
        print(f"🔄 Processing {len(all_files)} files sequentially")
        
        for i, change in enumerate(all_files):
            try:
                print(f"  📄 Processing file {i+1}/{len(all_files)}: {change.file_path}")
                
                if change.change_type == ChangeType.CREATED:
                    await self._process_new_file(change, sync_op)
                elif change.change_type == ChangeType.UPDATED:
                    await self._process_updated_file(change, sync_op)
                
                print(f"  ✅ Completed file {i+1}/{len(all_files)}")
                
            except Exception as e:
                print(f"  ❌ Failed to process file {change.file_path}: {e}")
                # Continue with next file instead of failing entire sync
                continue
    
    async def _process_deleted_files_sequentially(self, deleted_files: List[FileChange], sync_op: SyncOperation):
        """Process deleted files one at a time (simplified)"""
        print(f"🗑️ Processing {len(deleted_files)} deleted files sequentially")
        
        for i, change in enumerate(deleted_files):
            try:
                print(f"  🗑️ Deleting file {i+1}/{len(deleted_files)}: {change.file_path}")
                await self._process_deleted_file(change, sync_op)
                print(f"  ✅ Deleted file {i+1}/{len(deleted_files)}")
            except Exception as e:
                print(f"  ❌ Failed to delete file {change.file_path}: {e}")
                continue
    
    async def _process_files_concurrently(self, sync_plan: SyncPlan, sync_op: SyncOperation):
        """Process new and updated files with optimized concurrency"""
        
        # Combine new and updated files for processing
        all_files = sync_plan.new_files + sync_plan.updated_files
        
        if not all_files:
            return
        
        # Process in concurrent batches with memory management
        batch_size = 5  # Increased batch size for better throughput
        max_concurrent = 3  # Maximum concurrent file processing tasks
        
        print(f"🚀 Processing {len(all_files)} files with concurrent batching (batch_size={batch_size}, max_concurrent={max_concurrent})")
        
        for i in range(0, len(all_files), batch_size):
            batch = all_files[i:i + batch_size]
            
            # Create concurrent tasks for this batch
            tasks = []
            for j in range(0, len(batch), max_concurrent):
                concurrent_batch = batch[j:j + max_concurrent]
                
                # Create tasks for concurrent processing
                batch_tasks = []
                for change in concurrent_batch:
                    if change.change_type == ChangeType.CREATED:
                        batch_tasks.append(self._process_new_file(change, sync_op))
                    elif change.change_type == ChangeType.UPDATED:
                        batch_tasks.append(self._process_updated_file(change, sync_op))
                
                # Execute concurrent batch
                if batch_tasks:
                    tasks.extend(batch_tasks)
            
            # Execute all tasks in this batch concurrently
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Check for exceptions
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        print(f"⚠️ File processing failed: {result}")
                        # Continue processing other files
                
                # Force cleanup after each batch
                await self._cleanup_memory()
                
                print(f"  ✓ Completed batch {i//batch_size + 1}/{(len(all_files) + batch_size - 1)//batch_size}")
    
    async def _process_new_file_optimized(self, change: FileChange, sync_op: SyncOperation):
        """Process a new file with optimized async operations"""
        return await self._process_new_file(change, sync_op)
    
    async def _process_updated_file_optimized(self, change: FileChange, sync_op: SyncOperation):
        """Process an updated file with optimized async operations"""
        return await self._process_updated_file(change, sync_op)
    
    async def _cleanup_memory(self):
        """Clean up memory and GPU cache"""
        import gc
        gc.collect()
        
        # Clear GPU cache if available
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
        
        # Safely commit database changes to free connection resources
        try:
            if self.db.is_active:
                await self.db.commit()
        except Exception:
            # Ignore commit errors if session is already closed or invalid
            pass
    
    async def _process_deleted_files_batch(self, deleted_files: List[FileChange], sync_op: SyncOperation):
        """
        Process multiple deleted files in batch for better performance - HARD DELETE
        """
        valid_file_ids = [change.file_id for change in deleted_files if change.file_id is not None]
        
        if not valid_file_ids:
            return
        
        print(f"🗞️ Batch hard deleting {len(valid_file_ids)} files")
        
        try:
            # Create sync history records BEFORE deletion (since we need file IDs)
            for change in deleted_files:
                if change.file_id:
                    await self._create_sync_history(
                        change.file_id, 
                        sync_op, 
                        change, 
                        chunks_before=0,  # We don't have individual counts, but total is tracked
                        chunks_after=0
                    )
            
            # Bulk delete embeddings for all files at once
            total_chunks_deleted = await self.embedding_service.delete_multiple_files_embeddings(valid_file_ids)
            
            # Track embedding metrics
            sync_op.chunks_deleted = (sync_op.chunks_deleted or 0) + total_chunks_deleted
            await self.db.commit()
            
            # HARD DELETE all file records in one query
            from sqlalchemy import delete
            await self.db.execute(
                delete(File).where(File.id.in_(valid_file_ids))
            )
            
            print(f"✓ Batch hard deleted {len(valid_file_ids)} files and {total_chunks_deleted} chunks")
            
        except Exception as e:
            print(f"⚠️ Batch deletion failed: {e}, falling back to individual processing")
            await self.db.rollback()
            # Fall back to individual processing
            for change in deleted_files:
                try:
                    await self._process_deleted_file(change, sync_op)
                except Exception as e2:
                    print(f"⚠️ Failed to process deleted file {change.file_id}: {e2}")
                    continue
    
    async def cleanup_orphaned_embeddings(self, tenant_id: UUID) -> int:
        """
        Clean up orphaned embeddings for files that no longer exist
        With hard deletes, this should find chunks with no corresponding file records
        
        Returns:
            int: Number of orphaned chunks cleaned up
        """
        from src.backend.models.database import EmbeddingChunk
        
        # Find chunks that don't have corresponding file records (LEFT JOIN with NULL check)
        result = await self.db.execute(
            select(EmbeddingChunk.file_id)
            .outerjoin(File, EmbeddingChunk.file_id == File.id)
            .where(
                EmbeddingChunk.tenant_id == tenant_id,
                File.id.is_(None)  # No corresponding file record
            )
            .distinct()
        )
        
        orphaned_file_ids = [row[0] for row in result.fetchall()]
        
        if not orphaned_file_ids:
            print(f"✓ No orphaned embeddings found for tenant {tenant_id}")
            return 0
        
        print(f"🧙 Found {len(orphaned_file_ids)} files with orphaned embeddings")
        
        # Use bulk delete for efficiency
        chunks_deleted = await self.embedding_service.delete_multiple_files_embeddings(orphaned_file_ids)
        
        print(f"✓ Cleaned up {chunks_deleted} orphaned embedding chunks")
        return chunks_deleted
    
    async def _process_new_file(self, change: FileChange, sync_op: SyncOperation):
        try:
            # Files are auto-discovered by sync process
            
            # With hard delete, we just create a new file record (no soft-delete conflicts)
            file_record = File(
                tenant_id=sync_op.tenant_id,
                filename=Path(change.file_path).name,
                file_path=change.file_path,
                file_size=change.file_size or 0,
                file_hash=change.new_hash,
                sync_status='processing'  # Mark as processing immediately
            )
            
            self.db.add(file_record)
            await self.db.commit()  # Use commit instead of flush for concurrency
            await self.db.refresh(file_record)
            
            # Process the file immediately with memory management
            # Construct absolute file path
            from src.backend.config.settings import get_settings
            settings = get_settings()
            absolute_file_path = Path(settings.documents_path) / file_record.file_path
            
            chunks = await self.embedding_service.process_file_to_chunks(
                absolute_file_path, 
                file_record.tenant_id, 
                file_record
            )
            # Generate embeddings (now async)
            embeddings = await self.embedding_service.generate_embeddings(chunks)
            
            # Store embeddings using pgvector embedding service
            chunk_records = await self.embedding_service.store_embeddings(
                chunks, embeddings, file_record
            )
            success = True
            
            # Track embedding metrics
            chunks_created = len(chunk_records)
            
            # Use explicit SQL update to ensure persistence
            await self.db.execute(
                update(SyncOperation)
                .where(SyncOperation.id == sync_op.id)
                .values(
                    chunks_created=func.coalesce(SyncOperation.chunks_created, 0) + chunks_created,
                    files_added=func.coalesce(SyncOperation.files_added, 0) + 1
                )
            )
            await self.db.commit()  # Ensure sync_op changes are persisted
            
            # Update file status to synced only if embeddings were stored successfully
            if success:
                file_record.sync_status = 'synced'
                file_record.sync_completed_at = datetime.utcnow()
                file_record.sync_error = None
            else:
                file_record.sync_status = 'failed'
                file_record.sync_error = 'Failed to store embeddings'
            
            # Commit file status changes to database
            await self.db.commit()
            
            # Create sync history record with chunk metrics
            await self._create_sync_history(file_record.id, sync_op, change, chunks_before=0, chunks_after=chunks_created)
            
            # Clean up variables to free memory
            del chunks, embeddings, chunk_records
            
            # Force garbage collection
            import gc
            gc.collect()
            
        except Exception as e:
            # Handle errors gracefully to avoid breaking subsequent files
            print(f"    🔍 DEBUG: Exception in _process_new_file: {e}")
            
            try:
                # Rollback any pending transaction to clean session state
                await self.db.rollback()
                
                if 'file_record' in locals():
                    file_record.sync_status = 'failed'
                    file_record.sync_error = str(e)
                    file_record.sync_completed_at = datetime.utcnow()
                    await self.db.commit()  # Commit failed status
            except Exception as cleanup_error:
                print(f"    ⚠️ Error during cleanup: {cleanup_error}")
                
            # Don't raise - continue with next file
            return
        
    
    async def _process_updated_file(self, change: FileChange, sync_op: SyncOperation):
        
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
            
            # Reprocess the file with memory management
            # Construct absolute file path
            from src.backend.config.settings import get_settings
            settings = get_settings()
            absolute_file_path = Path(settings.documents_path) / file_record.file_path
            
            chunks = await self.embedding_service.process_file_to_chunks(
                absolute_file_path, 
                file_record.tenant_id, 
                file_record
            )
            # Generate embeddings (now async)
            embeddings = await self.embedding_service.generate_embeddings(chunks)
            
            # Simple embedding update - delete old then store new
            chunks_deleted = await self.embedding_service.delete_file_embeddings(change.file_id)
            chunk_records = await self.embedding_service.store_embeddings(
                chunks, embeddings, file_record
            )
            success = True
            
            # Track embedding metrics - for updates, we delete old and create new
            chunks_created = len(chunk_records)
            # Use explicit SQL update to ensure persistence
            await self.db.execute(
                update(SyncOperation)
                .where(SyncOperation.id == sync_op.id)
                .values(
                    chunks_deleted=func.coalesce(SyncOperation.chunks_deleted, 0) + chunks_deleted,
                    chunks_created=func.coalesce(SyncOperation.chunks_created, 0) + chunks_created,
                    chunks_updated=func.coalesce(SyncOperation.chunks_updated, 0) + chunks_created,
                    files_updated=func.coalesce(SyncOperation.files_updated, 0) + 1
                )
            )
            await self.db.commit()  # Ensure sync_op changes are persisted
            
            # Update file status to synced only if embeddings were updated successfully
            if success:
                await self.db.execute(
                    update(File)
                    .where(File.id == change.file_id)
                    .values(
                        sync_status='synced',
                        sync_completed_at=datetime.utcnow(),
                        sync_error=None
                    )
                )
            else:
                await self.db.execute(
                    update(File)
                    .where(File.id == change.file_id)
                    .values(
                        sync_status='failed',
                        sync_completed_at=datetime.utcnow(),
                        sync_error='Failed to update embeddings'
                    )
                )
            
            # Create sync history record with chunk metrics
            await self._create_sync_history(change.file_id, sync_op, change, chunks_before=chunks_deleted, chunks_after=chunks_created)
            
            # Clean up variables to free memory
            del chunks, embeddings, chunk_records
            
            # Force garbage collection
            import gc
            gc.collect()
            
        except Exception as e:
            # Handle errors gracefully to avoid breaking subsequent files
            print(f"    🔍 DEBUG: Exception in _process_updated_file: {e}")
            
            try:
                # Rollback any pending transaction to clean session state
                await self.db.rollback()
                
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
                await self.db.commit()
            except Exception as cleanup_error:
                print(f"    ⚠️ Error during cleanup: {cleanup_error}")
                
            # Don't raise - continue with next file
            return
        
    
    async def _process_deleted_file(self, change: FileChange, sync_op: SyncOperation):
        """Process a deleted file by cleaning up records and embeddings - HARD DELETE"""
        if not change.file_id:
            return
        
        try:
            # Create sync history record BEFORE deletion (since we need file ID)
            await self._create_sync_history(change.file_id, sync_op, change, chunks_before=0, chunks_after=0)
            
            # Use simple embedding service - no complex transactions
            chunks_deleted = await self.embedding_service.delete_file_embeddings(change.file_id)
            
            # Track embedding metrics - use explicit SQL update
            await self.db.execute(
                update(SyncOperation)
                .where(SyncOperation.id == sync_op.id)
                .values(
                    chunks_deleted=func.coalesce(SyncOperation.chunks_deleted, 0) + chunks_deleted,
                    files_deleted=func.coalesce(SyncOperation.files_deleted, 0) + 1
                )
            )
            
            # HARD DELETE file record
            from sqlalchemy import delete
            await self.db.execute(
                delete(File).where(File.id == change.file_id)
            )
            
            print(f"✓ Hard deleted file {change.file_id} and {chunks_deleted} chunks")
            
        except Exception as e:
            # Log error but don't fail sync for cleanup issues
            print(f"🔍 DEBUG: Exception in _process_deleted_file for file {change.file_id}: {e}")
            import traceback
            traceback.print_exc()
    
    async def _create_sync_history(
        self, 
        file_id: Optional[UUID], 
        sync_op: SyncOperation, 
        change: FileChange,
        chunks_before: int = 0,
        chunks_after: int = 0
    ):
        """Create a sync history record with chunk metrics"""
        if not file_id:
            return
        
        # FileSyncHistory table removed - using basic sync_operations tracking instead
        # Detailed sync history can be added back if needed for debugging
    
    async def _complete_sync_operation(
        self, 
        sync_op: SyncOperation, 
        sync_plan: SyncPlan
    ):
        """Mark sync operation as completed"""
        # Get current sync operation to preserve actual processing counts
        result = await self.db.execute(
            select(SyncOperation).where(SyncOperation.id == sync_op.id)
        )
        current_sync_op = result.scalar_one()
        
        # Calculate actual processed count from individual metrics
        actual_processed = (current_sync_op.files_added or 0) + (current_sync_op.files_updated or 0) + (current_sync_op.files_deleted or 0)
        
        await self.db.execute(
            update(SyncOperation)
            .where(SyncOperation.id == sync_op.id)
            .values(
                status='completed',
                completed_at=datetime.utcnow(),
                files_processed=actual_processed
                # Don't overwrite the individual counters - they were set during processing
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
        tenant_id: UUID
    ) -> SyncOperation:
        """
        Trigger a full sync for a tenant
        
        Args:
            tenant_id: Tenant to sync
            
        Returns:
            SyncOperation: Record of the sync operation
        """
        sync_plan = await self.detect_file_changes(tenant_id)
        return await self.execute_sync_plan(sync_plan)
    
    async def trigger_file_sync(
        self, 
        file_id: UUID
    ) -> bool:
        
        
        # Add timeout to prevent hanging
        try:
            return await asyncio.wait_for(self._trigger_file_sync_internal(file_id), timeout=60.0)
        except asyncio.TimeoutError:
            
            logger.error(f"❌ File sync timed out for {file_id}")
            return False
        except Exception as e:
            
            logger.error(f"❌ File sync failed for {file_id}: {e}")
            return False
    
    async def _trigger_file_sync_internal(
        self, 
        file_id: UUID
    ) -> bool:
        
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
            
            
            # Process file with memory management
            # Construct absolute file path
            
            from src.backend.config.settings import get_settings
            settings = get_settings()
            absolute_file_path = Path(settings.documents_path) / file_record.file_path
            
            
            # Process file to chunks
            
            chunks = await self.embedding_service.process_file_to_chunks(
                absolute_file_path, 
                file_record.tenant_id, 
                file_record
            )
            logger.info(f"Generated {len(chunks)} chunks for {file_id}")
            
            # Generate embeddings
            
            embeddings = await self.embedding_service.generate_embeddings(chunks)
            logger.info(f"Generated {len(embeddings)} embeddings for {file_id}")
            
            # Store embeddings
            
            await self.embedding_service.store_embeddings(chunks, embeddings, file_record)
            
            
            # Clean up variables to free memory
            
            del chunks, embeddings
            
            # Force garbage collection
            import gc
            gc.collect()
            
            
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
        # Use explicit transaction management to prevent rollbacks
        async with self.db.begin():
            # Get latest sync operation
            result = await self.db.execute(
                select(SyncOperation)
                .where(SyncOperation.tenant_id == tenant_id)
                .order_by(SyncOperation.started_at.desc())
                .limit(1)
            )
            latest_sync = result.scalar_one_or_none()
            
            # Get file counts by status using a single optimized query
            from sqlalchemy import func
            file_counts_result = await self.db.execute(
                select(
                    File.sync_status,
                    func.count(File.id).label('count')
                )
                .where(
                    File.tenant_id == tenant_id,
                    File.deleted_at.is_(None)
                )
                .group_by(File.sync_status)
            )
            
            # Convert to dictionary
            file_counts = {row.sync_status: row.count for row in file_counts_result.fetchall()}
            
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
                    'pending': file_counts.get('pending', 0),
                    'processing': file_counts.get('processing', 0),
                    'failed': file_counts.get('failed', 0),
                    'synced': file_counts.get('synced', 0),
                    'total': sum(file_counts.values())
                }
            }
    
    async def get_sync_history(
        self, 
        tenant_id: UUID, 
        limit: int = 50
    ) -> List[SyncOperation]:
        """Get sync history for a tenant"""
        # Use explicit transaction management to prevent rollbacks
        async with self.db.begin():
            result = await self.db.execute(
                select(SyncOperation)
                .where(SyncOperation.tenant_id == tenant_id)
                .order_by(SyncOperation.started_at.desc())
                .limit(limit)
            )
            return result.scalars().all()
    
    async def get_running_syncs(self, tenant_id: UUID) -> List[SyncOperation]:
        """Get all currently running sync operations for a tenant"""
        result = await self.db.execute(
            select(SyncOperation)
            .where(
                SyncOperation.tenant_id == tenant_id,
                SyncOperation.status == 'running'
            )
            .order_by(SyncOperation.started_at.desc())
        )
        return result.scalars().all()
    
    async def cancel_sync_operation(self, sync_id: UUID, tenant_id: UUID) -> bool:
        """Cancel a specific sync operation"""
        try:
            # Check if sync operation exists and belongs to tenant
            result = await self.db.execute(
                select(SyncOperation)
                .where(
                    SyncOperation.id == sync_id,
                    SyncOperation.tenant_id == tenant_id,
                    SyncOperation.status == 'running'
                )
            )
            sync_op = result.scalar_one_or_none()
            
            if not sync_op:
                return False
            
            # Update sync operation status to cancelled
            await self.db.execute(
                update(SyncOperation)
                .where(SyncOperation.id == sync_id)
                .values(
                    status='cancelled',
                    completed_at=datetime.utcnow(),
                    error_message='Cancelled by user'
                )
            )
            
            # Reset any files that were being processed by this sync
            await self.db.execute(
                update(File)
                .where(
                    File.tenant_id == tenant_id,
                    File.sync_status == 'processing'
                )
                .values(sync_status='pending')
            )
            
            await self.db.commit()
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error cancelling sync operation {sync_id}: {e}")
            return False
    
    async def cancel_all_running_syncs(self, tenant_id: UUID) -> int:
        """Cancel all running sync operations for a tenant"""
        try:
            # Get all running sync operations for this tenant
            result = await self.db.execute(
                select(SyncOperation)
                .where(
                    SyncOperation.tenant_id == tenant_id,
                    SyncOperation.status == 'running'
                )
            )
            running_syncs = result.scalars().all()
            
            if not running_syncs:
                return 0
            
            # Update all running syncs to cancelled
            await self.db.execute(
                update(SyncOperation)
                .where(
                    SyncOperation.tenant_id == tenant_id,
                    SyncOperation.status == 'running'
                )
                .values(
                    status='cancelled',
                    completed_at=datetime.utcnow(),
                    error_message='Cancelled during cleanup'
                )
            )
            
            # Reset any files that were being processed to pending
            await self.db.execute(
                update(File)
                .where(
                    File.tenant_id == tenant_id,
                    File.sync_status == 'processing'
                )
                .values(sync_status='pending')
            )
            
            await self.db.commit()
            
            cancelled_count = len(running_syncs)
            logger.info(f"Cancelled {cancelled_count} running sync operations for tenant {tenant_id}")
            return cancelled_count
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error cancelling all running syncs for tenant {tenant_id}: {e}")
            return 0


# Dependency function for FastAPI
async def get_sync_service(
    db_session: AsyncSession,
    file_service: FileService,
    embedding_model=None
) -> SyncService:
    """Dependency to get sync service with required dependencies"""
    return SyncService(db_session, file_service, embedding_model)


# Additional helper functions for sync operations
async def schedule_tenant_sync(tenant_id: UUID):
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


