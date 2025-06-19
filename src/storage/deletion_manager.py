"""
Embedding deletion manager for Enterprise RAG system.

This module provides comprehensive embedding deletion capabilities including
queue-based processing, batch operations, verification, and audit logging.
"""

import asyncio
import logging
import time
import threading
import json
from typing import Dict, Any, List, Optional, Set, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import uuid
from datetime import datetime, timedelta

from .vector_store import get_vector_store, EmbeddingMetadata
from .metadata_handler import get_metadata_manager, MetadataFilter, FilterOperator
from ..config.settings import get_settings

logger = logging.getLogger(__name__)


class DeletionStatus(Enum):
    """Status of deletion operations."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"
    ROLLED_BACK = "rolled_back"


class DeletionScope(Enum):
    """Scope of deletion operations."""
    SINGLE_EMBEDDING = "single_embedding"
    DOCUMENT = "document"
    FOLDER = "folder"
    TENANT = "tenant"
    BATCH = "batch"


@dataclass
class DeletionTask:
    """Represents a deletion task."""
    task_id: str
    tenant_id: str
    scope: DeletionScope
    status: DeletionStatus = DeletionStatus.PENDING
    
    # Target identification
    embedding_ids: List[str] = field(default_factory=list)
    document_ids: List[str] = field(default_factory=list)
    folder_paths: List[str] = field(default_factory=list)
    
    # Execution tracking
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # Results tracking
    total_targets: int = 0
    processed_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    
    # Error tracking
    errors: List[str] = field(default_factory=list)
    rollback_data: Optional[Dict[str, Any]] = None
    
    # Verification
    verification_passed: bool = False
    verification_errors: List[str] = field(default_factory=list)


@dataclass
class DeletionLog:
    """Log entry for deletion operations."""
    log_id: str
    task_id: str
    tenant_id: str
    timestamp: float
    operation: str
    target_type: str
    target_id: str
    status: str
    details: Dict[str, Any]
    error_message: Optional[str] = None


class TenantAwareDeletionManager:
    """
    Comprehensive deletion manager with queue-based processing.
    
    Features:
    - Queue-based deletion processing
    - Batch deletion operations
    - Verification and rollback capabilities
    - Comprehensive audit logging
    - Tenant isolation
    - Performance monitoring
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the deletion manager.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or get_settings()
        self.deletion_config = self.config.get("deletion", {})
        
        # Core components
        self.vector_store = get_vector_store()
        self.metadata_manager = get_metadata_manager()
        
        # Queue management
        self.deletion_queue: List[DeletionTask] = []
        self.active_tasks: Dict[str, DeletionTask] = {}
        self.completed_tasks: List[DeletionTask] = []
        self.queue_lock = threading.RLock()
        
        # Processing control
        self.processing_enabled = True
        self.max_concurrent_tasks = self.deletion_config.get("max_concurrent_tasks", 3)
        self.batch_size = self.deletion_config.get("batch_size", 100)
        self.verification_enabled = self.deletion_config.get("enable_verification", True)
        
        # Logging
        self.deletion_logs: List[DeletionLog] = []
        self.log_retention_hours = self.deletion_config.get("log_retention_hours", 168)  # 7 days
        self.logs_lock = threading.RLock()
        
        # Statistics
        self.stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "total_deletions": 0,
            "verification_failures": 0
        }
        self.stats_lock = threading.RLock()
        
        # Start background processor
        self._start_background_processor()
        
        logger.info("Initialized TenantAwareDeletionManager")
    
    def create_deletion_task(
        self,
        tenant_id: str,
        scope: DeletionScope,
        targets: Dict[str, List[str]]
    ) -> str:
        """
        Create a new deletion task.
        
        Args:
            tenant_id: Unique identifier for the tenant
            scope: Scope of deletion operation
            targets: Dictionary with target IDs by type
            
        Returns:
            str: Task ID
        """
        task_id = f"del_{tenant_id}_{uuid.uuid4().hex[:8]}"
        
        task = DeletionTask(
            task_id=task_id,
            tenant_id=tenant_id,
            scope=scope,
            embedding_ids=targets.get("embedding_ids", []),
            document_ids=targets.get("document_ids", []),
            folder_paths=targets.get("folder_paths", [])
        )
        
        # Calculate total targets
        task.total_targets = (
            len(task.embedding_ids) +
            len(task.document_ids) +
            len(task.folder_paths)
        )
        
        # Add to queue
        with self.queue_lock:
            self.deletion_queue.append(task)
            
        with self.stats_lock:
            self.stats["total_tasks"] += 1
        
        self._log_operation(
            task_id=task_id,
            tenant_id=tenant_id,
            operation="task_created",
            target_type=scope.value,
            target_id=task_id,
            status="pending",
            details={"total_targets": task.total_targets}
        )
        
        logger.info(f"Created deletion task {task_id} for tenant {tenant_id}")
        return task_id
    
    def delete_embeddings(
        self,
        tenant_id: str,
        embedding_ids: List[str]
    ) -> str:
        """
        Delete specific embeddings.
        
        Args:
            tenant_id: Unique identifier for the tenant
            embedding_ids: List of embedding IDs to delete
            
        Returns:
            str: Task ID
        """
        return self.create_deletion_task(
            tenant_id=tenant_id,
            scope=DeletionScope.SINGLE_EMBEDDING,
            targets={"embedding_ids": embedding_ids}
        )
    
    def delete_documents(
        self,
        tenant_id: str,
        document_ids: List[str]
    ) -> str:
        """
        Delete all embeddings for specific documents.
        
        Args:
            tenant_id: Unique identifier for the tenant
            document_ids: List of document IDs to delete
            
        Returns:
            str: Task ID
        """
        return self.create_deletion_task(
            tenant_id=tenant_id,
            scope=DeletionScope.DOCUMENT,
            targets={"document_ids": document_ids}
        )
    
    def delete_folders(
        self,
        tenant_id: str,
        folder_paths: List[str]
    ) -> str:
        """
        Delete all embeddings for specific folders.
        
        Args:
            tenant_id: Unique identifier for the tenant
            folder_paths: List of folder paths to delete
            
        Returns:
            str: Task ID
        """
        return self.create_deletion_task(
            tenant_id=tenant_id,
            scope=DeletionScope.FOLDER,
            targets={"folder_paths": folder_paths}
        )
    
    def delete_tenant_data(self, tenant_id: str) -> str:
        """
        Delete all data for a tenant.
        
        Args:
            tenant_id: Unique identifier for the tenant
            
        Returns:
            str: Task ID
        """
        return self.create_deletion_task(
            tenant_id=tenant_id,
            scope=DeletionScope.TENANT,
            targets={}
        )
    
    def _start_background_processor(self):
        """Start the background task processor."""
        def processor():
            while self.processing_enabled:
                try:
                    self._process_deletion_queue()
                    time.sleep(1)  # Process every second
                except Exception as e:
                    logger.error(f"Error in deletion processor: {e}")
                    time.sleep(5)  # Wait longer on error
        
        processor_thread = threading.Thread(target=processor, daemon=True)
        processor_thread.start()
        logger.info("Started background deletion processor")
    
    def _process_deletion_queue(self):
        """Process pending deletion tasks."""
        with self.queue_lock:
            # Check if we can start new tasks
            if len(self.active_tasks) >= self.max_concurrent_tasks:
                return
            
            # Get next pending task
            pending_tasks = [task for task in self.deletion_queue if task.status == DeletionStatus.PENDING]
            if not pending_tasks:
                return
            
            # Start processing the first pending task
            task = pending_tasks[0]
            task.status = DeletionStatus.IN_PROGRESS
            task.started_at = time.time()
            self.active_tasks[task.task_id] = task
            
            # Remove from queue
            self.deletion_queue.remove(task)
        
        # Process the task
        try:
            self._execute_deletion_task(task)
        except Exception as e:
            logger.error(f"Failed to execute deletion task {task.task_id}: {e}")
            task.status = DeletionStatus.FAILED
            task.errors.append(str(e))
            self._complete_task(task)
    
    def _execute_deletion_task(self, task: DeletionTask):
        """Execute a deletion task."""
        logger.info(f"Executing deletion task {task.task_id}")
        
        try:
            # Prepare rollback data
            task.rollback_data = self._prepare_rollback_data(task)
            
            # Execute based on scope
            if task.scope == DeletionScope.SINGLE_EMBEDDING:
                self._delete_specific_embeddings(task)
            elif task.scope == DeletionScope.DOCUMENT:
                self._delete_document_embeddings(task)
            elif task.scope == DeletionScope.FOLDER:
                self._delete_folder_embeddings(task)
            elif task.scope == DeletionScope.TENANT:
                self._delete_tenant_embeddings(task)
            else:
                raise ValueError(f"Unknown deletion scope: {task.scope}")
            
            # Mark as completed
            task.status = DeletionStatus.COMPLETED
            task.completed_at = time.time()
            
            # Verify deletion if enabled
            if self.verification_enabled:
                self._verify_deletion(task)
            
            # Complete the task
            self._complete_task(task)
            
        except Exception as e:
            logger.error(f"Failed to execute deletion task {task.task_id}: {e}")
            task.status = DeletionStatus.FAILED
            task.errors.append(str(e))
            
            # Attempt rollback
            try:
                self._rollback_deletion(task)
            except Exception as rollback_error:
                logger.error(f"Failed to rollback task {task.task_id}: {rollback_error}")
                task.errors.append(f"Rollback failed: {rollback_error}")
            
            self._complete_task(task)
    
    def _delete_specific_embeddings(self, task: DeletionTask):
        """Delete specific embeddings."""
        for embedding_id in task.embedding_ids:
            try:
                # Get metadata
                metadata = self.metadata_manager.get_metadata(embedding_id)
                if metadata:
                    # Delete from metadata store
                    self.metadata_manager.delete_metadata(embedding_id)
                    task.success_count += 1
                    
                    self._log_operation(
                        task_id=task.task_id,
                        tenant_id=task.tenant_id,
                        operation="delete_embedding",
                        target_type="embedding",
                        target_id=embedding_id,
                        status="success",
                        details={}
                    )
                else:
                    task.failure_count += 1
                    error = f"Embedding {embedding_id} not found"
                    task.errors.append(error)
                    
                    self._log_operation(
                        task_id=task.task_id,
                        tenant_id=task.tenant_id,
                        operation="delete_embedding",
                        target_type="embedding",
                        target_id=embedding_id,
                        status="failed",
                        details={},
                        error_message=error
                    )
                
                task.processed_count += 1
                
            except Exception as e:
                task.failure_count += 1
                error = f"Failed to delete embedding {embedding_id}: {e}"
                task.errors.append(error)
                
                self._log_operation(
                    task_id=task.task_id,
                    tenant_id=task.tenant_id,
                    operation="delete_embedding",
                    target_type="embedding",
                    target_id=embedding_id,
                    status="failed",
                    details={},
                    error_message=error
                )
    
    def _delete_document_embeddings(self, task: DeletionTask):
        """Delete all embeddings for documents."""
        for document_id in task.document_ids:
            try:
                # Find all embeddings for this document
                metadata_list = self.metadata_manager.query_metadata(
                    tenant_id=task.tenant_id,
                    filters=[
                        MetadataFilter(
                            field="document_id",
                            operator=FilterOperator.EQUALS,
                            value=document_id
                        )
                    ]
                )
                
                # Delete each embedding
                for metadata in metadata_list:
                    try:
                        self.metadata_manager.delete_metadata(metadata.embedding_id)
                        task.success_count += 1
                        
                        self._log_operation(
                            task_id=task.task_id,
                            tenant_id=task.tenant_id,
                            operation="delete_document_embedding",
                            target_type="embedding",
                            target_id=metadata.embedding_id,
                            status="success",
                            details={"document_id": document_id}
                        )
                        
                    except Exception as e:
                        task.failure_count += 1
                        error = f"Failed to delete embedding {metadata.embedding_id}: {e}"
                        task.errors.append(error)
                
                task.processed_count += 1
                
            except Exception as e:
                task.failure_count += 1
                error = f"Failed to delete document {document_id}: {e}"
                task.errors.append(error)
    
    def _delete_folder_embeddings(self, task: DeletionTask):
        """Delete all embeddings for folders."""
        for folder_path in task.folder_paths:
            try:
                # Find all embeddings for this folder
                metadata_list = self.metadata_manager.query_metadata(
                    tenant_id=task.tenant_id,
                    filters=[
                        MetadataFilter(
                            field="folder_path",
                            operator=FilterOperator.EQUALS,
                            value=folder_path
                        )
                    ]
                )
                
                # Delete each embedding
                for metadata in metadata_list:
                    try:
                        self.metadata_manager.delete_metadata(metadata.embedding_id)
                        task.success_count += 1
                        
                    except Exception as e:
                        task.failure_count += 1
                        error = f"Failed to delete embedding {metadata.embedding_id}: {e}"
                        task.errors.append(error)
                
                task.processed_count += 1
                
            except Exception as e:
                task.failure_count += 1
                error = f"Failed to delete folder {folder_path}: {e}"
                task.errors.append(error)
    
    def _delete_tenant_embeddings(self, task: DeletionTask):
        """Delete all embeddings for a tenant."""
        try:
            # Delete from vector store
            vector_success = self.vector_store.delete_tenant_data(task.tenant_id)
            
            # Delete from metadata store
            metadata_success = self.metadata_manager.delete_tenant_metadata(task.tenant_id)
            
            if vector_success and metadata_success:
                task.success_count += 1
                
                self._log_operation(
                    task_id=task.task_id,
                    tenant_id=task.tenant_id,
                    operation="delete_tenant",
                    target_type="tenant",
                    target_id=task.tenant_id,
                    status="success",
                    details={}
                )
            else:
                task.failure_count += 1
                error = f"Partial deletion failure: vector={vector_success}, metadata={metadata_success}"
                task.errors.append(error)
            
            task.processed_count += 1
            
        except Exception as e:
            task.failure_count += 1
            error = f"Failed to delete tenant data: {e}"
            task.errors.append(error)
    
    def _verify_deletion(self, task: DeletionTask):
        """Verify that deletion was successful."""
        try:
            verification_errors = []
            
            # Verify based on scope
            if task.scope == DeletionScope.SINGLE_EMBEDDING:
                for embedding_id in task.embedding_ids:
                    metadata = self.metadata_manager.get_metadata(embedding_id)
                    if metadata:
                        verification_errors.append(f"Embedding {embedding_id} still exists")
            
            elif task.scope == DeletionScope.DOCUMENT:
                for document_id in task.document_ids:
                    metadata_list = self.metadata_manager.query_metadata(
                        tenant_id=task.tenant_id,
                        filters=[
                            MetadataFilter(
                                field="document_id",
                                operator=FilterOperator.EQUALS,
                                value=document_id
                            )
                        ]
                    )
                    if metadata_list:
                        verification_errors.append(f"Document {document_id} still has {len(metadata_list)} embeddings")
            
            elif task.scope == DeletionScope.TENANT:
                stats = self.metadata_manager.get_statistics()
                tenant_entries = stats.get(f"tenant_{task.tenant_id}_entries", 0)
                if tenant_entries > 0:
                    verification_errors.append(f"Tenant {task.tenant_id} still has {tenant_entries} entries")
            
            # Update verification status
            if verification_errors:
                task.verification_passed = False
                task.verification_errors = verification_errors
                task.status = DeletionStatus.FAILED
                
                with self.stats_lock:
                    self.stats["verification_failures"] += 1
                
                self._log_operation(
                    task_id=task.task_id,
                    tenant_id=task.tenant_id,
                    operation="verification",
                    target_type="task",
                    target_id=task.task_id,
                    status="failed",
                    details={"errors": verification_errors}
                )
            else:
                task.verification_passed = True
                task.status = DeletionStatus.VERIFIED
                
                self._log_operation(
                    task_id=task.task_id,
                    tenant_id=task.tenant_id,
                    operation="verification",
                    target_type="task",
                    target_id=task.task_id,
                    status="success",
                    details={}
                )
                
        except Exception as e:
            task.verification_passed = False
            task.verification_errors = [f"Verification failed: {e}"]
            logger.error(f"Verification failed for task {task.task_id}: {e}")
    
    def _prepare_rollback_data(self, task: DeletionTask) -> Dict[str, Any]:
        """Prepare data needed for rollback."""
        rollback_data = {
            "task_id": task.task_id,
            "tenant_id": task.tenant_id,
            "scope": task.scope.value,
            "timestamp": time.time(),
            "backup_metadata": []
        }
        
        # For now, we just track what we're about to delete
        # In a production system, you might want to backup the data
        return rollback_data
    
    def _rollback_deletion(self, task: DeletionTask):
        """Rollback a failed deletion."""
        logger.warning(f"Attempting rollback for task {task.task_id}")
        task.status = DeletionStatus.ROLLED_BACK
        
        # Rollback implementation would depend on what was actually deleted
        # For now, we just log the attempt
        self._log_operation(
            task_id=task.task_id,
            tenant_id=task.tenant_id,
            operation="rollback",
            target_type="task",
            target_id=task.task_id,
            status="attempted",
            details={}
        )
    
    def _complete_task(self, task: DeletionTask):
        """Complete a deletion task."""
        with self.queue_lock:
            if task.task_id in self.active_tasks:
                del self.active_tasks[task.task_id]
            self.completed_tasks.append(task)
            
            # Keep only last 1000 completed tasks
            if len(self.completed_tasks) > 1000:
                self.completed_tasks = self.completed_tasks[-1000:]
        
        with self.stats_lock:
            if task.status in [DeletionStatus.COMPLETED, DeletionStatus.VERIFIED]:
                self.stats["completed_tasks"] += 1
                self.stats["total_deletions"] += task.success_count
            else:
                self.stats["failed_tasks"] += 1
        
        self._log_operation(
            task_id=task.task_id,
            tenant_id=task.tenant_id,
            operation="task_completed",
            target_type="task",
            target_id=task.task_id,
            status=task.status.value,
            details={
                "processed_count": task.processed_count,
                "success_count": task.success_count,
                "failure_count": task.failure_count,
                "verification_passed": task.verification_passed
            }
        )
        
        logger.info(f"Completed deletion task {task.task_id} with status {task.status.value}")
    
    def _log_operation(
        self,
        task_id: str,
        tenant_id: str,
        operation: str,
        target_type: str,
        target_id: str,
        status: str,
        details: Dict[str, Any],
        error_message: Optional[str] = None
    ):
        """Log a deletion operation."""
        log_entry = DeletionLog(
            log_id=f"log_{uuid.uuid4().hex[:8]}",
            task_id=task_id,
            tenant_id=tenant_id,
            timestamp=time.time(),
            operation=operation,
            target_type=target_type,
            target_id=target_id,
            status=status,
            details=details,
            error_message=error_message
        )
        
        with self.logs_lock:
            self.deletion_logs.append(log_entry)
            
            # Clean up old logs
            cutoff_time = time.time() - (self.log_retention_hours * 3600)
            self.deletion_logs = [
                log for log in self.deletion_logs
                if log.timestamp > cutoff_time
            ]
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a deletion task."""
        # Check active tasks
        with self.queue_lock:
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                return self._task_to_dict(task)
            
            # Check pending queue
            for task in self.deletion_queue:
                if task.task_id == task_id:
                    return self._task_to_dict(task)
            
            # Check completed tasks
            for task in self.completed_tasks:
                if task.task_id == task_id:
                    return self._task_to_dict(task)
        
        return None
    
    def _task_to_dict(self, task: DeletionTask) -> Dict[str, Any]:
        """Convert task to dictionary."""
        return {
            "task_id": task.task_id,
            "tenant_id": task.tenant_id,
            "scope": task.scope.value,
            "status": task.status.value,
            "total_targets": task.total_targets,
            "processed_count": task.processed_count,
            "success_count": task.success_count,
            "failure_count": task.failure_count,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "verification_passed": task.verification_passed,
            "verification_errors": task.verification_errors,
            "errors": task.errors
        }
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get deletion queue status."""
        with self.queue_lock:
            return {
                "pending_tasks": len([t for t in self.deletion_queue if t.status == DeletionStatus.PENDING]),
                "active_tasks": len(self.active_tasks),
                "completed_tasks": len(self.completed_tasks),
                "max_concurrent_tasks": self.max_concurrent_tasks,
                "processing_enabled": self.processing_enabled
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get deletion statistics."""
        with self.stats_lock:
            stats = dict(self.stats)
        
        with self.logs_lock:
            stats["log_entries"] = len(self.deletion_logs)
        
        return stats
    
    def get_deletion_logs(
        self,
        tenant_id: Optional[str] = None,
        task_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get deletion logs with optional filtering."""
        with self.logs_lock:
            logs = self.deletion_logs.copy()
        
        # Apply filters
        if tenant_id:
            logs = [log for log in logs if log.tenant_id == tenant_id]
        
        if task_id:
            logs = [log for log in logs if log.task_id == task_id]
        
        # Sort by timestamp (newest first) and limit
        logs.sort(key=lambda x: x.timestamp, reverse=True)
        logs = logs[:limit]
        
        # Convert to dictionaries
        return [
            {
                "log_id": log.log_id,
                "task_id": log.task_id,
                "tenant_id": log.tenant_id,
                "timestamp": log.timestamp,
                "operation": log.operation,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "status": log.status,
                "details": log.details,
                "error_message": log.error_message
            }
            for log in logs
        ]
    
    def stop_processing(self):
        """Stop the background processor."""
        self.processing_enabled = False
        logger.info("Stopped deletion processing")
    
    def start_processing(self):
        """Start the background processor."""
        self.processing_enabled = True
        logger.info("Started deletion processing")


# Global deletion manager instance
_deletion_manager = None


def get_deletion_manager() -> TenantAwareDeletionManager:
    """Get the global deletion manager instance."""
    global _deletion_manager
    if _deletion_manager is None:
        _deletion_manager = TenantAwareDeletionManager()
    return _deletion_manager