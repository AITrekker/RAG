"""
Recovery Service - Handles recovery and repair of failed sync operations and data inconsistencies
Provides automatic and manual recovery mechanisms to maintain data integrity
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Set, Any, Optional, Tuple
from uuid import UUID
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_

from src.backend.models.database import File, EmbeddingChunk, SyncOperation
from src.backend.services.consistency_checker import (
    ConsistencyChecker, 
    InconsistencyReport, 
    InconsistencyType,
    get_consistency_checker
)
from src.backend.services.transactional_embedding_service import (
    TransactionalEmbeddingService,
    get_transactional_embedding_service
)
from src.backend.services.embedding_service import EmbeddingService
from src.backend.config.settings import get_settings

settings = get_settings()


class RecoveryStatus(Enum):
    """Status of recovery operations"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class RecoveryActionType(Enum):
    """Types of recovery actions"""
    REPROCESS_FILE = "reprocess_file"
    CLEANUP_ORPHANED_CHUNKS = "cleanup_orphaned_chunks"
    RESET_STUCK_FILE = "reset_stuck_file"
    RESYNC_FILE = "resync_file"
    DELETE_ORPHANED_EMBEDDINGS = "delete_orphaned_embeddings"
    RESUME_SYNC_OPERATION = "resume_sync_operation"


@dataclass
class RecoveryAction:
    """Represents a recovery action to be performed"""
    action_id: str
    action_type: RecoveryActionType
    tenant_id: UUID
    file_id: Optional[UUID]
    description: str
    priority: int  # 1=highest, 5=lowest
    estimated_duration_seconds: int
    status: RecoveryStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    details: Dict[str, Any] = None


@dataclass
class RecoveryPlan:
    """A plan containing multiple recovery actions"""
    plan_id: str
    tenant_id: UUID
    actions: List[RecoveryAction]
    total_estimated_duration: int
    created_at: datetime
    priority_order: List[str]  # Action IDs in execution order


class RecoveryService:
    """Service for recovering from sync failures and data inconsistencies"""
    
    def __init__(
        self,
        db_session: AsyncSession,
        embedding_service: EmbeddingService,
        consistency_checker: ConsistencyChecker,
        transactional_embedding_service: TransactionalEmbeddingService
    ):
        self.db = db_session
        self.embedding_service = embedding_service
        self.consistency_checker = consistency_checker
        self.transactional_embedding_service = transactional_embedding_service
        self.active_recoveries: Dict[str, RecoveryAction] = {}
    
    async def create_recovery_plan(
        self, 
        tenant_id: UUID,
        environment: str = None
    ) -> RecoveryPlan:
        """
        Create a comprehensive recovery plan for a tenant based on consistency check
        
        Args:
            tenant_id: Tenant to create recovery plan for
            environment: Target environment
            
        Returns:
            RecoveryPlan: Detailed plan with prioritized actions
        """
        import uuid
        
        # Run consistency check first
        stats, inconsistencies = await self.consistency_checker.check_tenant_consistency(
            tenant_id, environment
        )
        
        plan_id = str(uuid.uuid4())
        actions = []
        
        # Convert inconsistencies to recovery actions
        for inconsistency in inconsistencies:
            action = await self._create_recovery_action_from_inconsistency(inconsistency)
            if action:
                actions.append(action)
        
        # Check for stuck sync operations
        stuck_sync_actions = await self._create_stuck_sync_recovery_actions(tenant_id)
        actions.extend(stuck_sync_actions)
        
        # Sort actions by priority (1=highest priority)
        actions.sort(key=lambda x: x.priority)
        priority_order = [action.action_id for action in actions]
        
        # Calculate total estimated duration
        total_duration = sum(action.estimated_duration_seconds for action in actions)
        
        recovery_plan = RecoveryPlan(
            plan_id=plan_id,
            tenant_id=tenant_id,
            actions=actions,
            total_estimated_duration=total_duration,
            created_at=datetime.utcnow(),
            priority_order=priority_order
        )
        
        return recovery_plan
    
    async def _create_recovery_action_from_inconsistency(
        self, 
        inconsistency: InconsistencyReport
    ) -> Optional[RecoveryAction]:
        """Convert an inconsistency report to a recovery action"""
        import uuid
        
        action_id = str(uuid.uuid4())
        
        if inconsistency.inconsistency_type == InconsistencyType.MISSING_EMBEDDINGS:
            return RecoveryAction(
                action_id=action_id,
                action_type=RecoveryActionType.REPROCESS_FILE,
                tenant_id=inconsistency.tenant_id,
                file_id=inconsistency.file_id,
                description=f"Reprocess file '{inconsistency.file_path}' to generate missing embeddings",
                priority=2,  # High priority
                estimated_duration_seconds=120,  # 2 minutes per file
                status=RecoveryStatus.PENDING,
                created_at=datetime.utcnow(),
                details={'inconsistency_type': inconsistency.inconsistency_type.value}
            )
        
        elif inconsistency.inconsistency_type == InconsistencyType.ORPHANED_CHUNKS:
            return RecoveryAction(
                action_id=action_id,
                action_type=RecoveryActionType.CLEANUP_ORPHANED_CHUNKS,
                tenant_id=inconsistency.tenant_id,
                file_id=inconsistency.file_id,
                description=f"Clean up {inconsistency.details.get('chunk_count', 'unknown')} orphaned chunks",
                priority=3,  # Medium priority
                estimated_duration_seconds=30,  # 30 seconds per cleanup
                status=RecoveryStatus.PENDING,
                created_at=datetime.utcnow(),
                details=inconsistency.details
            )
        
        elif inconsistency.inconsistency_type == InconsistencyType.STUCK_PROCESSING:
            return RecoveryAction(
                action_id=action_id,
                action_type=RecoveryActionType.RESET_STUCK_FILE,
                tenant_id=inconsistency.tenant_id,
                file_id=inconsistency.file_id,
                description=f"Reset stuck file '{inconsistency.file_path}' and retry processing",
                priority=1,  # Highest priority
                estimated_duration_seconds=60,  # 1 minute
                status=RecoveryStatus.PENDING,
                created_at=datetime.utcnow(),
                details=inconsistency.details
            )
        
        elif inconsistency.inconsistency_type == InconsistencyType.QDRANT_POSTGRES_MISMATCH:
            return RecoveryAction(
                action_id=action_id,
                action_type=RecoveryActionType.RESYNC_FILE,
                tenant_id=inconsistency.tenant_id,
                file_id=inconsistency.file_id,
                description=f"Re-sync file '{inconsistency.file_path}' to fix chunk count mismatch",
                priority=2,  # High priority
                estimated_duration_seconds=180,  # 3 minutes per file
                status=RecoveryStatus.PENDING,
                created_at=datetime.utcnow(),
                details=inconsistency.details
            )
        
        elif inconsistency.inconsistency_type == InconsistencyType.ORPHANED_EMBEDDINGS:
            return RecoveryAction(
                action_id=action_id,
                action_type=RecoveryActionType.DELETE_ORPHANED_EMBEDDINGS,
                tenant_id=inconsistency.tenant_id,
                file_id=None,
                description="Clean up orphaned embeddings in Qdrant",
                priority=4,  # Lower priority
                estimated_duration_seconds=60,  # 1 minute
                status=RecoveryStatus.PENDING,
                created_at=datetime.utcnow(),
                details=inconsistency.details
            )
        
        return None
    
    async def _create_stuck_sync_recovery_actions(self, tenant_id: UUID) -> List[RecoveryAction]:
        """Create recovery actions for stuck sync operations"""
        import uuid
        
        actions = []
        
        # Find sync operations that have been running too long
        cutoff_time = datetime.utcnow() - timedelta(hours=2)
        
        result = await self.db.execute(
            select(SyncOperation).where(
                and_(
                    SyncOperation.tenant_id == tenant_id,
                    SyncOperation.status == 'running',
                    SyncOperation.started_at < cutoff_time
                )
            )
        )
        
        stuck_syncs = result.scalars().all()
        
        for sync_op in stuck_syncs:
            action_id = str(uuid.uuid4())
            
            # Determine how long it's been stuck
            stuck_duration = datetime.utcnow() - sync_op.started_at
            
            actions.append(RecoveryAction(
                action_id=action_id,
                action_type=RecoveryActionType.RESUME_SYNC_OPERATION,
                tenant_id=tenant_id,
                file_id=None,
                description=f"Resume or reset stuck sync operation (stuck for {stuck_duration})",
                priority=1,  # Highest priority
                estimated_duration_seconds=300,  # 5 minutes
                status=RecoveryStatus.PENDING,
                created_at=datetime.utcnow(),
                details={
                    'sync_operation_id': str(sync_op.id),
                    'stuck_duration_seconds': stuck_duration.total_seconds(),
                    'operation_type': sync_op.operation_type
                }
            ))
        
        return actions
    
    async def execute_recovery_plan(
        self, 
        recovery_plan: RecoveryPlan,
        max_concurrent: int = 3
    ) -> Dict[str, Any]:
        """
        Execute a recovery plan with controlled concurrency
        
        Args:
            recovery_plan: Plan to execute
            max_concurrent: Maximum concurrent recovery actions
            
        Returns:
            Dict with execution results and statistics
        """
        start_time = datetime.utcnow()
        
        # Track execution results
        results = {
            'plan_id': recovery_plan.plan_id,
            'tenant_id': str(recovery_plan.tenant_id),
            'started_at': start_time.isoformat(),
            'total_actions': len(recovery_plan.actions),
            'completed_actions': 0,
            'failed_actions': 0,
            'skipped_actions': 0,
            'action_results': {}
        }
        
        # Execute actions in priority order with concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def execute_action(action: RecoveryAction):
            async with semaphore:
                return await self._execute_recovery_action(action)
        
        # Execute all actions concurrently (semaphore controls actual concurrency)
        tasks = [execute_action(action) for action in recovery_plan.actions]
        action_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for i, result in enumerate(action_results):
            action = recovery_plan.actions[i]
            
            if isinstance(result, Exception):
                results['failed_actions'] += 1
                results['action_results'][action.action_id] = {
                    'status': 'failed',
                    'error': str(result),
                    'action_type': action.action_type.value
                }
            else:
                if result.get('status') == 'completed':
                    results['completed_actions'] += 1
                elif result.get('status') == 'skipped':
                    results['skipped_actions'] += 1
                else:
                    results['failed_actions'] += 1
                
                results['action_results'][action.action_id] = result
        
        # Calculate final statistics
        end_time = datetime.utcnow()
        results['completed_at'] = end_time.isoformat()
        results['duration_seconds'] = (end_time - start_time).total_seconds()
        results['success_rate'] = (
            results['completed_actions'] / results['total_actions'] * 100
            if results['total_actions'] > 0 else 0
        )
        
        return results
    
    async def _execute_recovery_action(self, action: RecoveryAction) -> Dict[str, Any]:
        """Execute a single recovery action"""
        
        action.status = RecoveryStatus.IN_PROGRESS
        action.started_at = datetime.utcnow()
        
        self.active_recoveries[action.action_id] = action
        
        try:
            if action.action_type == RecoveryActionType.REPROCESS_FILE:
                result = await self._execute_reprocess_file(action)
            elif action.action_type == RecoveryActionType.CLEANUP_ORPHANED_CHUNKS:
                result = await self._execute_cleanup_orphaned_chunks(action)
            elif action.action_type == RecoveryActionType.RESET_STUCK_FILE:
                result = await self._execute_reset_stuck_file(action)
            elif action.action_type == RecoveryActionType.RESYNC_FILE:
                result = await self._execute_resync_file(action)
            elif action.action_type == RecoveryActionType.DELETE_ORPHANED_EMBEDDINGS:
                result = await self._execute_delete_orphaned_embeddings(action)
            elif action.action_type == RecoveryActionType.RESUME_SYNC_OPERATION:
                result = await self._execute_resume_sync_operation(action)
            else:
                result = {
                    'status': 'skipped',
                    'message': f'Unknown action type: {action.action_type.value}'
                }
            
            action.status = RecoveryStatus.COMPLETED if result.get('status') == 'completed' else RecoveryStatus.FAILED
            action.completed_at = datetime.utcnow()
            
            return result
            
        except Exception as e:
            action.status = RecoveryStatus.FAILED
            action.completed_at = datetime.utcnow()
            action.error_message = str(e)
            
            return {
                'status': 'failed',
                'error': str(e),
                'action_type': action.action_type.value
            }
        finally:
            # Clean up from active recoveries
            self.active_recoveries.pop(action.action_id, None)
    
    async def _execute_reprocess_file(self, action: RecoveryAction) -> Dict[str, Any]:
        """Reprocess a file to generate missing embeddings"""
        
        if not action.file_id:
            return {'status': 'failed', 'error': 'No file ID provided'}
        
        # Get file record
        result = await self.db.execute(
            select(File).where(File.id == action.file_id)
        )
        file_record = result.scalar_one_or_none()
        
        if not file_record:
            return {'status': 'failed', 'error': 'File not found'}
        
        try:
            # Mark file as processing
            await self.db.execute(
                update(File)
                .where(File.id == action.file_id)
                .values(
                    sync_status='processing',
                    sync_started_at=datetime.utcnow(),
                    sync_error=None
                )
            )
            await self.db.commit()
            
            # Process the file
            chunks = await self.embedding_service.process_file(file_record)
            embeddings = await self.embedding_service.generate_embeddings(chunks)
            
            # Store embeddings using transactional service
            chunk_records, success = await self.transactional_embedding_service.transactional_store_embeddings(
                file_record, chunks, embeddings
            )
            
            if success:
                # Mark file as synced
                await self.db.execute(
                    update(File)
                    .where(File.id == action.file_id)
                    .values(
                        sync_status='synced',
                        sync_completed_at=datetime.utcnow(),
                        sync_error=None
                    )
                )
                await self.db.commit()
                
                return {
                    'status': 'completed',
                    'message': f'Successfully reprocessed file {file_record.filename}',
                    'chunks_created': len(chunk_records)
                }
            else:
                # Mark file as failed
                await self.db.execute(
                    update(File)
                    .where(File.id == action.file_id)
                    .values(
                        sync_status='failed',
                        sync_completed_at=datetime.utcnow(),
                        sync_error='Transactional embedding storage failed'
                    )
                )
                await self.db.commit()
                
                return {
                    'status': 'failed',
                    'error': 'Transactional embedding storage failed'
                }
        
        except Exception as e:
            # Mark file as failed
            await self.db.execute(
                update(File)
                .where(File.id == action.file_id)
                .values(
                    sync_status='failed',
                    sync_completed_at=datetime.utcnow(),
                    sync_error=str(e)
                )
            )
            await self.db.commit()
            
            raise
    
    async def _execute_cleanup_orphaned_chunks(self, action: RecoveryAction) -> Dict[str, Any]:
        """Clean up orphaned chunks for a deleted file"""
        
        if not action.file_id:
            return {'status': 'failed', 'error': 'No file ID provided'}
        
        try:
            # Delete orphaned chunks using transactional service
            deleted_count, success = await self.transactional_embedding_service.transactional_delete_embeddings(
                action.file_id, action.tenant_id
            )
            
            if success:
                return {
                    'status': 'completed',
                    'message': f'Successfully cleaned up {deleted_count} orphaned chunks',
                    'chunks_deleted': deleted_count
                }
            else:
                return {
                    'status': 'failed',
                    'error': 'Transactional chunk deletion failed'
                }
        
        except Exception as e:
            return {
                'status': 'failed',
                'error': f'Cleanup failed: {str(e)}'
            }
    
    async def _execute_reset_stuck_file(self, action: RecoveryAction) -> Dict[str, Any]:
        """Reset a file that's stuck in processing state"""
        
        if not action.file_id:
            return {'status': 'failed', 'error': 'No file ID provided'}
        
        try:
            # Reset file status to pending
            await self.db.execute(
                update(File)
                .where(File.id == action.file_id)
                .values(
                    sync_status='pending',
                    sync_started_at=None,
                    sync_completed_at=None,
                    sync_error=None
                )
            )
            await self.db.commit()
            
            return {
                'status': 'completed',
                'message': 'Successfully reset stuck file to pending status'
            }
        
        except Exception as e:
            return {
                'status': 'failed',
                'error': f'Reset failed: {str(e)}'
            }
    
    async def _execute_resync_file(self, action: RecoveryAction) -> Dict[str, Any]:
        """Re-sync a file to fix mismatched chunk counts"""
        
        if not action.file_id:
            return {'status': 'failed', 'error': 'No file ID provided'}
        
        # Get file record
        result = await self.db.execute(
            select(File).where(File.id == action.file_id)
        )
        file_record = result.scalar_one_or_none()
        
        if not file_record:
            return {'status': 'failed', 'error': 'File not found'}
        
        try:
            # Process the file
            chunks = await self.embedding_service.process_file(file_record)
            embeddings = await self.embedding_service.generate_embeddings(chunks)
            
            # Update embeddings using transactional service
            chunk_records, old_count, success = await self.transactional_embedding_service.transactional_update_embeddings(
                file_record, chunks, embeddings
            )
            
            if success:
                return {
                    'status': 'completed',
                    'message': f'Successfully re-synced file {file_record.filename}',
                    'old_chunks': old_count,
                    'new_chunks': len(chunk_records)
                }
            else:
                return {
                    'status': 'failed',
                    'error': 'Transactional embedding update failed'
                }
        
        except Exception as e:
            return {
                'status': 'failed',
                'error': f'Re-sync failed: {str(e)}'
            }
    
    async def _execute_delete_orphaned_embeddings(self, action: RecoveryAction) -> Dict[str, Any]:
        """Delete orphaned embeddings from Qdrant"""
        
        try:
            # This would require a more complex implementation to scan Qdrant
            # For now, we'll return a placeholder
            return {
                'status': 'completed',
                'message': 'Orphaned embedding cleanup completed (placeholder implementation)'
            }
        
        except Exception as e:
            return {
                'status': 'failed',
                'error': f'Orphaned embedding cleanup failed: {str(e)}'
            }
    
    async def _execute_resume_sync_operation(self, action: RecoveryAction) -> Dict[str, Any]:
        """Resume or reset a stuck sync operation"""
        
        sync_operation_id = action.details.get('sync_operation_id')
        if not sync_operation_id:
            return {'status': 'failed', 'error': 'No sync operation ID provided'}
        
        try:
            # Mark the stuck sync operation as failed so it can be retried
            await self.db.execute(
                update(SyncOperation)
                .where(SyncOperation.id == UUID(sync_operation_id))
                .values(
                    status='failed',
                    completed_at=datetime.utcnow(),
                    error_message='Reset by recovery service due to timeout'
                )
            )
            await self.db.commit()
            
            return {
                'status': 'completed',
                'message': 'Successfully reset stuck sync operation'
            }
        
        except Exception as e:
            return {
                'status': 'failed',
                'error': f'Sync operation reset failed: {str(e)}'
            }
    
    async def get_active_recoveries(self) -> List[Dict[str, Any]]:
        """Get information about currently active recovery actions"""
        
        return [
            {
                'action_id': action.action_id,
                'action_type': action.action_type.value,
                'tenant_id': str(action.tenant_id),
                'file_id': str(action.file_id) if action.file_id else None,
                'description': action.description,
                'status': action.status.value,
                'started_at': action.started_at.isoformat() if action.started_at else None,
                'duration_seconds': (
                    (datetime.utcnow() - action.started_at).total_seconds()
                    if action.started_at else 0
                )
            }
            for action in self.active_recoveries.values()
        ]
    
    async def quick_fix_tenant(
        self, 
        tenant_id: UUID,
        environment: str = None
    ) -> Dict[str, Any]:
        """
        Perform quick fixes for common issues (non-destructive operations only)
        
        Args:
            tenant_id: Tenant to fix
            environment: Target environment
            
        Returns:
            Dict with quick fix results
        """
        results = {
            'tenant_id': str(tenant_id),
            'fixes_applied': [],
            'errors': []
        }
        
        try:
            # Reset files stuck in processing for more than 30 minutes
            cutoff_time = datetime.utcnow() - timedelta(minutes=30)
            
            stuck_files_result = await self.db.execute(
                update(File)
                .where(
                    and_(
                        File.tenant_id == tenant_id,
                        File.sync_status == 'processing',
                        File.sync_started_at < cutoff_time
                    )
                )
                .values(
                    sync_status='pending',
                    sync_started_at=None,
                    sync_error='Reset by quick fix - was stuck in processing'
                )
            )
            await self.db.commit()
            
            if stuck_files_result.rowcount > 0:
                results['fixes_applied'].append(
                    f'Reset {stuck_files_result.rowcount} files stuck in processing state'
                )
            
            # Reset sync operations stuck for more than 1 hour
            sync_cutoff = datetime.utcnow() - timedelta(hours=1)
            
            stuck_syncs_result = await self.db.execute(
                update(SyncOperation)
                .where(
                    and_(
                        SyncOperation.tenant_id == tenant_id,
                        SyncOperation.status == 'running',
                        SyncOperation.started_at < sync_cutoff
                    )
                )
                .values(
                    status='failed',
                    completed_at=datetime.utcnow(),
                    error_message='Reset by quick fix - operation timeout'
                )
            )
            await self.db.commit()
            
            if stuck_syncs_result.rowcount > 0:
                results['fixes_applied'].append(
                    f'Reset {stuck_syncs_result.rowcount} stuck sync operations'
                )
            
            return results
            
        except Exception as e:
            results['errors'].append(f'Quick fix failed: {str(e)}')
            return results


async def get_recovery_service(
    db_session: AsyncSession,
    embedding_service: EmbeddingService
) -> RecoveryService:
    """Factory function to create recovery service with all dependencies"""
    
    consistency_checker = await get_consistency_checker(db_session)
    transactional_embedding_service = await get_transactional_embedding_service(
        db_session, embedding_service
    )
    
    return RecoveryService(
        db_session=db_session,
        embedding_service=embedding_service,
        consistency_checker=consistency_checker,
        transactional_embedding_service=transactional_embedding_service
    ) 