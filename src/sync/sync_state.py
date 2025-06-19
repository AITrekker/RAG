"""
Sync state management system.

This module provides robust state tracking for sync operations with
persistence, recovery, and comprehensive status reporting.
"""

import os
import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)

class SyncState(Enum):
    """States for sync operations."""
    IDLE = "idle"
    SCANNING = "scanning"
    SYNCING = "syncing"
    FAILED = "failed"
    RECOVERING = "recovering"
    PAUSED = "paused"
    CLEANUP = "cleanup"

class SyncErrorType(Enum):
    """Types of sync errors."""
    FILE_ACCESS = "file_access"
    NETWORK = "network"
    DISK_SPACE = "disk_space"
    PERMISSION = "permission"
    CONFLICT = "conflict"
    TIMEOUT = "timeout"
    INTERNAL = "internal"
    UNKNOWN = "unknown"

@dataclass
class SyncError:
    """Details about a sync error."""
    error_type: SyncErrorType
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    resolved: bool = False
    resolution: Optional[str] = None

@dataclass
class SyncProgress:
    """Progress information for sync operations."""
    total_files: int = 0
    processed_files: int = 0
    failed_files: int = 0
    bytes_transferred: int = 0
    current_file: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    estimated_remaining: Optional[float] = None
    current_speed: Optional[float] = None

@dataclass
class SyncStateInfo:
    """Complete state information for a sync operation."""
    tenant_id: str
    folder_name: str
    state: SyncState
    progress: SyncProgress = field(default_factory=SyncProgress)
    errors: List[SyncError] = field(default_factory=list)
    last_successful_sync: Optional[datetime] = None
    next_scheduled_sync: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class SyncStateManager:
    """Manages sync state with persistence and recovery."""
    
    def __init__(self, db_path: str = "data/sync_state.db"):
        """Initialize state manager.
        
        Args:
            db_path: Path to SQLite database for state persistence
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._lock = threading.Lock()
        self._states: Dict[str, SyncStateInfo] = {}
        
        # Initialize database
        self._init_db()
        
        # Load persisted states
        self._load_states()
        
        logger.info(f"Initialized sync state manager with database at {db_path}")
    
    def _init_db(self):
        """Initialize SQLite database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_states (
                    state_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    folder_name TEXT NOT NULL,
                    state TEXT NOT NULL,
                    progress_json TEXT,
                    errors_json TEXT,
                    last_successful_sync TIMESTAMP,
                    next_scheduled_sync TIMESTAMP,
                    metadata_json TEXT,
                    updated_at TIMESTAMP NOT NULL
                )
            """)
            conn.commit()
    
    def _load_states(self):
        """Load persisted states from database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM sync_states")
            
            for row in cursor:
                state_info = SyncStateInfo(
                    tenant_id=row['tenant_id'],
                    folder_name=row['folder_name'],
                    state=SyncState(row['state']),
                    progress=SyncProgress(**json.loads(row['progress_json'])),
                    errors=[SyncError(**err) for err in json.loads(row['errors_json'])],
                    last_successful_sync=datetime.fromisoformat(row['last_successful_sync']) if row['last_successful_sync'] else None,
                    next_scheduled_sync=datetime.fromisoformat(row['next_scheduled_sync']) if row['next_scheduled_sync'] else None,
                    metadata=json.loads(row['metadata_json'])
                )
                
                state_id = f"{state_info.tenant_id}:{state_info.folder_name}"
                self._states[state_id] = state_info
    
    def _persist_state(self, state_id: str, state_info: SyncStateInfo):
        """Persist state to database.
        
        Args:
            state_id: State identifier
            state_info: State information to persist
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sync_states (
                    state_id, tenant_id, folder_name, state,
                    progress_json, errors_json,
                    last_successful_sync, next_scheduled_sync,
                    metadata_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                state_id,
                state_info.tenant_id,
                state_info.folder_name,
                state_info.state.value,
                json.dumps(asdict(state_info.progress)),
                json.dumps([asdict(err) for err in state_info.errors]),
                state_info.last_successful_sync.isoformat() if state_info.last_successful_sync else None,
                state_info.next_scheduled_sync.isoformat() if state_info.next_scheduled_sync else None,
                json.dumps(state_info.metadata),
                datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()
    
    def get_state(self, tenant_id: str, folder_name: str) -> Optional[SyncStateInfo]:
        """Get current sync state.
        
        Args:
            tenant_id: Tenant identifier
            folder_name: Folder name
            
        Returns:
            Current state information or None if not found
        """
        state_id = f"{tenant_id}:{folder_name}"
        with self._lock:
            return self._states.get(state_id)
    
    def update_state(
        self,
        tenant_id: str,
        folder_name: str,
        new_state: SyncState,
        progress: Optional[SyncProgress] = None,
        error: Optional[SyncError] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update sync state.
        
        Args:
            tenant_id: Tenant identifier
            folder_name: Folder name
            new_state: New state
            progress: Optional progress update
            error: Optional error to add
            metadata: Optional metadata update
        """
        state_id = f"{tenant_id}:{folder_name}"
        
        with self._lock:
            state_info = self._states.get(state_id)
            
            if not state_info:
                state_info = SyncStateInfo(
                    tenant_id=tenant_id,
                    folder_name=folder_name,
                    state=new_state
                )
                self._states[state_id] = state_info
            
            # Update state
            state_info.state = new_state
            
            # Update progress if provided
            if progress:
                state_info.progress = progress
            
            # Add error if provided
            if error:
                state_info.errors.append(error)
                # Keep only last 100 errors
                if len(state_info.errors) > 100:
                    state_info.errors = state_info.errors[-100:]
            
            # Update metadata if provided
            if metadata:
                state_info.metadata.update(metadata)
            
            # Update timestamps for state transitions
            if new_state == SyncState.IDLE:
                state_info.last_successful_sync = datetime.now(timezone.utc)
            
            # Persist changes
            self._persist_state(state_id, state_info)
            
            logger.info(
                f"Updated sync state for tenant {tenant_id}, folder {folder_name} "
                f"to {new_state.value}"
            )
    
    def clear_errors(self, tenant_id: str, folder_name: str) -> None:
        """Clear all errors for a sync operation.
        
        Args:
            tenant_id: Tenant identifier
            folder_name: Folder name
        """
        state_id = f"{tenant_id}:{folder_name}"
        
        with self._lock:
            if state_info := self._states.get(state_id):
                state_info.errors = []
                self._persist_state(state_id, state_info)
    
    def get_all_states(self) -> Dict[str, SyncStateInfo]:
        """Get all current sync states.
        
        Returns:
            Dictionary of all sync states
        """
        with self._lock:
            return self._states.copy()
    
    def get_failed_states(self) -> List[SyncStateInfo]:
        """Get all sync operations in failed state.
        
        Returns:
            List of failed sync operations
        """
        with self._lock:
            return [
                state for state in self._states.values()
                if state.state == SyncState.FAILED
            ]
    
    def cleanup_old_states(self, days: int = 30) -> int:
        """Clean up old sync states.
        
        Args:
            days: Number of days of history to keep
            
        Returns:
            Number of states cleaned up
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cleaned = 0
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM sync_states
                WHERE updated_at < ? AND state != ?
            """, (
                cutoff.isoformat(),
                SyncState.FAILED.value
            ))
            cleaned = cursor.rowcount
            conn.commit()
        
        # Reload states
        with self._lock:
            self._states.clear()
            self._load_states()
        
        logger.info(f"Cleaned up {cleaned} old sync states")
        return cleaned 