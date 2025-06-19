"""
Deletion management system for Enterprise RAG.

This module provides comprehensive deletion handling with batch processing,
cleanup, and verification capabilities.
"""

import os
import logging
import asyncio
import threading
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
import sqlite3
import json

from .vector_store import get_vector_store
from .metadata_handler import get_metadata_manager
from .version_manager import get_version_manager
from ..config.settings import get_settings

logger = logging.getLogger(__name__)

class DeletionStatus(Enum):
    """Status of deletion operations."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"
    ROLLBACK = "rollback"

class DeletionPriority(Enum):
    """Priority levels for deletion operations."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4

@dataclass
class DeletionTask:
    """Represents a deletion task."""
    task_id: str
    tenant_id: str
    file_path: str
    priority: DeletionPriority
    status: DeletionStatus = DeletionStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

class DeletionManager:
    """Manages file and embedding deletion with batch processing."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize deletion manager.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or get_settings()
        self.deletion_config = self.config.get("deletion", {})
        
        # Initialize components
        self.vector_store = get_vector_store()
        self.metadata_manager = get_metadata_manager()
        self.version_manager = get_version_manager()
        
        # Configure batch settings
        self.batch_size = self.deletion_config.get("batch_size", 100)
        self.max_retries = self.deletion_config.get("max_retries", 3)
        self.verify_deletions = self.deletion_config.get("verify_deletions", True)
        
        # Initialize database
        db_path = self.deletion_config.get("database_path", "data/deletion.db")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        
        self._init_db()
        
        # Initialize state
        self._lock = threading.Lock()
        self._tasks: Dict[str, DeletionTask] = {}
        self._batch_in_progress = False
        
        # Load pending tasks
        self._load_tasks()
        
        logger.info(f"Initialized deletion manager with batch size {self.batch_size}")
    
    def _init_db(self):
        """Initialize SQLite database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS deletion_tasks (
                    task_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    error_message TEXT,
                    retry_count INTEGER NOT NULL,
                    metadata_json TEXT
                )
            """)
            conn.commit()
    
    def _load_tasks(self):
        """Load tasks from database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM deletion_tasks
                WHERE status IN (?, ?)
                ORDER BY priority DESC, created_at ASC
            """, (
                DeletionStatus.PENDING.value,
                DeletionStatus.IN_PROGRESS.value
            ))
            
            for row in cursor:
                task = DeletionTask(
                    task_id=row['task_id'],
                    tenant_id=row['tenant_id'],
                    file_path=row['file_path'],
                    priority=DeletionPriority(row['priority']),
                    status=DeletionStatus(row['status']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else None,
                    completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
                    error_message=row['error_message'],
                    retry_count=row['retry_count'],
                    metadata=json.loads(row['metadata_json'])
                )
                self._tasks[task.task_id] = task
    
    def _persist_task(self, task: DeletionTask):
        """Persist task to database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO deletion_tasks (
                    task_id, tenant_id, file_path, priority,
                    status, created_at, started_at, completed_at,
                    error_message, retry_count, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.task_id,
                task.tenant_id,
                task.file_path,
                task.priority.value,
                task.status.value,
                task.created_at.isoformat(),
                task.started_at.isoformat() if task.started_at else None,
                task.completed_at.isoformat() if task.completed_at else None,
                task.error_message,
                task.retry_count,
                json.dumps(task.metadata)
            ))
            conn.commit()
    
    async def queue_deletion(
        self,
        tenant_id: str,
        file_path: str,
        priority: DeletionPriority = DeletionPriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Queue a file for deletion.
        
        Args:
            tenant_id: Tenant identifier
            file_path: Path to file to delete
            priority: Deletion priority
            metadata: Optional metadata
            
        Returns:
            Task ID
        """
        task = DeletionTask(
            task_id=f"del_{tenant_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            tenant_id=tenant_id,
            file_path=file_path,
            priority=priority,
            metadata=metadata or {}
        )
        
        with self._lock:
            self._tasks[task.task_id] = task
            self._persist_task(task)
        
        logger.info(f"Queued deletion task {task.task_id} for {file_path}")
        
        # Start batch processing if not already running
        if not self._batch_in_progress:
            asyncio.create_task(self._process_batch())
        
        return task.task_id
    
    async def _process_batch(self):
        """Process a batch of deletion tasks."""
        if self._batch_in_progress:
            return
        
        self._batch_in_progress = True
        logger.info("Starting batch deletion processing")
        
        try:
            while True:
                # Get next batch of tasks
                batch = []
                with self._lock:
                    pending_tasks = sorted(
                        [t for t in self._tasks.values() if t.status == DeletionStatus.PENDING],
                        key=lambda t: (t.priority.value, t.created_at),
                        reverse=True
                    )
                    
                    if not pending_tasks:
                        break
                    
                    batch = pending_tasks[:self.batch_size]
                    for task in batch:
                        task.status = DeletionStatus.IN_PROGRESS
                        task.started_at = datetime.now(timezone.utc)
                        self._persist_task(task)
                
                # Process batch
                for task in batch:
                    try:
                        # Delete file
                        if os.path.exists(task.file_path):
                            os.remove(task.file_path)
                        
                        # Delete embeddings
                        await self.vector_store.delete_document_embeddings(
                            task.tenant_id,
                            task.file_path
                        )
                        
                        # Delete metadata
                        self.metadata_manager.delete_document_metadata(
                            task.tenant_id,
                            task.file_path
                        )
                        
                        # Archive versions
                        self.version_manager.delete_document_versions(
                            task.tenant_id,
                            task.file_path
                        )
                        
                        # Verify deletion if enabled
                        if self.verify_deletions:
                            verified = await self._verify_deletion(task)
                            task.status = (
                                DeletionStatus.VERIFIED if verified
                                else DeletionStatus.FAILED
                            )
                        else:
                            task.status = DeletionStatus.COMPLETED
                        
                        task.completed_at = datetime.now(timezone.utc)
                        logger.info(f"Completed deletion task {task.task_id}")
                        
                    except Exception as e:
                        task.error_message = str(e)
                        task.retry_count += 1
                        
                        if task.retry_count >= self.max_retries:
                            task.status = DeletionStatus.FAILED
                            logger.error(
                                f"Failed deletion task {task.task_id} after "
                                f"{task.retry_count} retries: {e}"
                            )
                        else:
                            task.status = DeletionStatus.PENDING
                            logger.warning(
                                f"Deletion task {task.task_id} failed, will retry: {e}"
                            )
                    
                    with self._lock:
                        self._persist_task(task)
                
                # Short delay between batches
                await asyncio.sleep(0.1)
        
        finally:
            self._batch_in_progress = False
            logger.info("Completed batch deletion processing")
    
    async def _verify_deletion(self, task: DeletionTask) -> bool:
        """Verify that a deletion task was successful.
        
        Args:
            task: Deletion task to verify
            
        Returns:
            True if deletion was verified
        """
        try:
            # Check file is gone
            if os.path.exists(task.file_path):
                return False
            
            # Check embeddings are gone
            embeddings = await self.vector_store.get_document_embeddings(
                task.tenant_id,
                task.file_path
            )
            if embeddings:
                return False
            
            # Check metadata is gone
            metadata = self.metadata_manager.get_document_metadata(
                task.tenant_id,
                task.file_path
            )
            if metadata:
                return False
            
            # Check versions are archived
            versions = self.version_manager.get_document_versions(
                task.tenant_id,
                task.file_path,
                include_archived=False
            )
            if versions:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to verify deletion for task {task.task_id}: {e}")
            return False
    
    def get_task_status(self, task_id: str) -> Optional[DeletionTask]:
        """Get status of a deletion task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task information or None if not found
        """
        with self._lock:
            return self._tasks.get(task_id)
    
    def get_pending_tasks(self) -> List[DeletionTask]:
        """Get all pending deletion tasks.
        
        Returns:
            List of pending tasks
        """
        with self._lock:
            return [
                task for task in self._tasks.values()
                if task.status == DeletionStatus.PENDING
            ]
    
    def get_failed_tasks(self) -> List[DeletionTask]:
        """Get all failed deletion tasks.
        
        Returns:
            List of failed tasks
        """
        with self._lock:
            return [
                task for task in self._tasks.values()
                if task.status == DeletionStatus.FAILED
            ]
    
    def cleanup_old_tasks(self, days: int = 30) -> int:
        """Clean up old completed tasks.
        
        Args:
            days: Number of days of history to keep
            
        Returns:
            Number of tasks cleaned up
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cleaned = 0
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM deletion_tasks
                WHERE completed_at < ?
                AND status IN (?, ?)
            """, (
                cutoff.isoformat(),
                DeletionStatus.COMPLETED.value,
                DeletionStatus.VERIFIED.value
            ))
            cleaned = cursor.rowcount
            conn.commit()
        
        # Reload tasks
        with self._lock:
            self._tasks.clear()
            self._load_tasks()
        
        logger.info(f"Cleaned up {cleaned} old deletion tasks")
        return cleaned