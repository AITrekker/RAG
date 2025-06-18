"""
Delta synchronization system for incremental file sync operations.

This module provides delta detection, folder-based change tracking,
and optimized sync operations.
"""

import asyncio
import logging
import hashlib
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import json
import shutil

logger = logging.getLogger(__name__)

class DeltaOperationType(Enum):
    """Types of delta operations."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    MOVE = "move"
    COPY = "copy"

class SyncDirection(Enum):
    """Sync direction."""
    SOURCE_TO_TARGET = "source_to_target"
    TARGET_TO_SOURCE = "target_to_source"
    BIDIRECTIONAL = "bidirectional"

@dataclass
class DeltaOperation:
    """Represents a delta sync operation."""
    operation_id: str
    operation_type: DeltaOperationType
    source_path: str
    target_path: str
    tenant_id: str
    folder_name: str
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    priority: int = 1  # 1=low, 2=normal, 3=high
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'operation_id': self.operation_id,
            'operation_type': self.operation_type.value,
            'source_path': self.source_path,
            'target_path': self.target_path,
            'tenant_id': self.tenant_id,
            'folder_name': self.folder_name,
            'file_size': self.file_size,
            'file_hash': self.file_hash,
            'timestamp': self.timestamp.isoformat(),
            'priority': self.priority,
            'metadata': self.metadata
        }

@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    operations_count: int
    bytes_transferred: int
    duration: float
    errors: List[str] = field(default_factory=list)
    operations: List[DeltaOperation] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'success': self.success,
            'operations_count': self.operations_count,
            'bytes_transferred': self.bytes_transferred,
            'duration': self.duration,
            'errors': self.errors,
            'operations': [op.to_dict() for op in self.operations]
        }

class FolderSnapshot:
    """Represents a snapshot of a folder's state."""
    
    def __init__(self, folder_path: str, supported_extensions: Optional[Set[str]] = None):
        self.folder_path = Path(folder_path)
        self.supported_extensions = supported_extensions or {
            '.pdf', '.docx', '.doc', '.pptx', '.ppt', '.txt', '.md',
            '.xlsx', '.xls', '.csv'
        }
        self.files: Dict[str, Dict[str, Any]] = {}
        self.snapshot_time: Optional[datetime] = None
    
    def create_snapshot(self) -> None:
        """Create a snapshot of the current folder state."""
        self.files = {}
        self.snapshot_time = datetime.now(timezone.utc)
        
        if not self.folder_path.exists():
            logger.warning(f"Folder does not exist: {self.folder_path}")
            return
        
        try:
            for file_path in self.folder_path.rglob('*'):
                if (file_path.is_file() and 
                    file_path.suffix.lower() in self.supported_extensions):
                    
                    relative_path = str(file_path.relative_to(self.folder_path))
                    
                    try:
                        stat = file_path.stat()
                        file_info = {
                            'size': stat.st_size,
                            'mtime': stat.st_mtime,
                            'hash': self._calculate_hash(file_path) if stat.st_size < 100 * 1024 * 1024 else None
                        }
                        self.files[relative_path] = file_info
                    except (OSError, IOError) as e:
                        logger.warning(f"Failed to get info for {file_path}: {e}")
        
        except Exception as e:
            logger.error(f"Error creating snapshot for {self.folder_path}: {e}")
    
    def _calculate_hash(self, file_path: Path) -> str:
        """Calculate MD5 hash of a file."""
        try:
            hasher = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (OSError, IOError):
            return ""
    
    def save_to_file(self, snapshot_file: str) -> None:
        """Save snapshot to file."""
        snapshot_data = {
            'folder_path': str(self.folder_path),
            'snapshot_time': self.snapshot_time.isoformat() if self.snapshot_time else None,
            'files': self.files
        }
        
        try:
            with open(snapshot_file, 'w') as f:
                json.dump(snapshot_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save snapshot to {snapshot_file}: {e}")
    
    def load_from_file(self, snapshot_file: str) -> bool:
        """Load snapshot from file."""
        try:
            with open(snapshot_file, 'r') as f:
                snapshot_data = json.load(f)
            
            self.folder_path = Path(snapshot_data['folder_path'])
            self.snapshot_time = datetime.fromisoformat(snapshot_data['snapshot_time']) if snapshot_data['snapshot_time'] else None
            self.files = snapshot_data['files']
            
            return True
        except Exception as e:
            logger.error(f"Failed to load snapshot from {snapshot_file}: {e}")
            return False
    
    def compare_with(self, other: 'FolderSnapshot') -> List[DeltaOperation]:
        """Compare with another snapshot and generate delta operations."""
        operations = []
        operation_counter = 0
        
        # Find all files from both snapshots
        all_files = set(self.files.keys()) | set(other.files.keys())
        
        for relative_path in all_files:
            operation_counter += 1
            operation_id = f"delta_{operation_counter:06d}"
            
            current_file = self.files.get(relative_path)
            other_file = other.files.get(relative_path)
            
            source_full_path = str(self.folder_path / relative_path)
            target_full_path = str(other.folder_path / relative_path)
            
            if current_file and not other_file:
                # File exists in current but not in other (CREATE)
                operations.append(DeltaOperation(
                    operation_id=operation_id,
                    operation_type=DeltaOperationType.CREATE,
                    source_path=source_full_path,
                    target_path=target_full_path,
                    tenant_id="",  # Will be set by caller
                    folder_name=self.folder_path.name,
                    file_size=current_file['size'],
                    file_hash=current_file.get('hash'),
                    priority=2
                ))
                
            elif not current_file and other_file:
                # File exists in other but not in current (DELETE)
                operations.append(DeltaOperation(
                    operation_id=operation_id,
                    operation_type=DeltaOperationType.DELETE,
                    source_path=target_full_path,
                    target_path=target_full_path,
                    tenant_id="",  # Will be set by caller
                    folder_name=self.folder_path.name,
                    file_size=other_file['size'],
                    file_hash=other_file.get('hash'),
                    priority=3  # Higher priority for deletions
                ))
                
            elif current_file and other_file:
                # File exists in both, check if different (UPDATE)
                if self._files_different(current_file, other_file):
                    operations.append(DeltaOperation(
                        operation_id=operation_id,
                        operation_type=DeltaOperationType.UPDATE,
                        source_path=source_full_path,
                        target_path=target_full_path,
                        tenant_id="",  # Will be set by caller
                        folder_name=self.folder_path.name,
                        file_size=current_file['size'],
                        file_hash=current_file.get('hash'),
                        priority=2
                    ))
        
        return operations
    
    def _files_different(self, file1: Dict[str, Any], file2: Dict[str, Any]) -> bool:
        """Check if two file records are different."""
        # Compare by hash if available
        if file1.get('hash') and file2.get('hash'):
            return file1['hash'] != file2['hash']
        
        # Fall back to size and mtime
        return (file1['size'] != file2['size'] or 
                abs(file1['mtime'] - file2['mtime']) > 1.0)

class DeltaSyncEngine:
    """Engine for performing delta synchronization operations."""
    
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.snapshots: Dict[str, FolderSnapshot] = {}
        self.sync_history: List[SyncResult] = []
        self.max_history = 100
    
    def register_folder(self, folder_name: str, folder_path: str) -> None:
        """Register a folder for delta sync tracking."""
        self.snapshots[folder_name] = FolderSnapshot(folder_path)
        logger.info(f"Registered folder {folder_name} at {folder_path} for tenant {self.tenant_id}")
    
    def create_baseline_snapshot(self, folder_name: str) -> bool:
        """Create initial baseline snapshot for a folder."""
        if folder_name not in self.snapshots:
            logger.error(f"Folder {folder_name} not registered for tenant {self.tenant_id}")
            return False
        
        try:
            snapshot = self.snapshots[folder_name]
            snapshot.create_snapshot()
            
            # Save snapshot to disk
            snapshot_dir = Path(f"./data/snapshots/{self.tenant_id}")
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            snapshot_file = snapshot_dir / f"{folder_name}_baseline.json"
            snapshot.save_to_file(str(snapshot_file))
            
            logger.info(f"Created baseline snapshot for {folder_name} ({len(snapshot.files)} files)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create baseline snapshot for {folder_name}: {e}")
            return False
    
    def load_baseline_snapshot(self, folder_name: str) -> bool:
        """Load baseline snapshot from disk."""
        if folder_name not in self.snapshots:
            logger.error(f"Folder {folder_name} not registered for tenant {self.tenant_id}")
            return False
        
        snapshot_file = Path(f"./data/snapshots/{self.tenant_id}/{folder_name}_baseline.json")
        if not snapshot_file.exists():
            logger.warning(f"No baseline snapshot found for {folder_name}")
            return False
        
        return self.snapshots[folder_name].load_from_file(str(snapshot_file))
    
    async def detect_changes(self, folder_name: str) -> List[DeltaOperation]:
        """Detect changes in a folder since last snapshot."""
        if folder_name not in self.snapshots:
            logger.error(f"Folder {folder_name} not registered for tenant {self.tenant_id}")
            return []
        
        try:
            # Load baseline snapshot
            baseline_snapshot = FolderSnapshot(self.snapshots[folder_name].folder_path)
            if not self.load_baseline_snapshot(folder_name):
                logger.warning(f"No baseline found for {folder_name}, creating new one")
                await self.create_baseline_snapshot(folder_name)
                return []
            
            baseline_snapshot.load_from_file(
                f"./data/snapshots/{self.tenant_id}/{folder_name}_baseline.json"
            )
            
            # Create current snapshot
            current_snapshot = FolderSnapshot(self.snapshots[folder_name].folder_path)
            current_snapshot.create_snapshot()
            
            # Compare snapshots
            operations = current_snapshot.compare_with(baseline_snapshot)
            
            # Set tenant_id for all operations
            for op in operations:
                op.tenant_id = self.tenant_id
            
            logger.info(f"Detected {len(operations)} changes in {folder_name}")
            return operations
            
        except Exception as e:
            logger.error(f"Failed to detect changes in {folder_name}: {e}")
            return []
    
    async def apply_delta_operations(
        self, 
        operations: List[DeltaOperation],
        dry_run: bool = False
    ) -> SyncResult:
        """Apply a list of delta operations."""
        start_time = datetime.now(timezone.utc)
        bytes_transferred = 0
        errors = []
        successful_operations = []
        
        # Sort operations by priority (higher first)
        sorted_operations = sorted(operations, key=lambda x: x.priority, reverse=True)
        
        for operation in sorted_operations:
            try:
                if dry_run:
                    logger.info(f"DRY RUN: {operation.operation_type.value} {operation.source_path}")
                    successful_operations.append(operation)
                    continue
                
                success, transferred_bytes = await self._execute_operation(operation)
                
                if success:
                    bytes_transferred += transferred_bytes
                    successful_operations.append(operation)
                    logger.debug(f"Completed {operation.operation_type.value} for {operation.source_path}")
                else:
                    errors.append(f"Failed {operation.operation_type.value} for {operation.source_path}")
                
            except Exception as e:
                error_msg = f"Error executing {operation.operation_type.value} for {operation.source_path}: {e}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        result = SyncResult(
            success=len(errors) == 0,
            operations_count=len(successful_operations),
            bytes_transferred=bytes_transferred,
            duration=duration,
            errors=errors,
            operations=successful_operations
        )
        
        # Store in history
        self.sync_history.append(result)
        if len(self.sync_history) > self.max_history:
            self.sync_history.pop(0)
        
        logger.info(f"Delta sync completed: {len(successful_operations)} operations, {bytes_transferred} bytes, {duration:.2f}s")
        
        return result
    
    async def _execute_operation(self, operation: DeltaOperation) -> Tuple[bool, int]:
        """Execute a single delta operation."""
        try:
            source_path = Path(operation.source_path)
            target_path = Path(operation.target_path)
            
            if operation.operation_type == DeltaOperationType.CREATE:
                # Copy file from source to target
                if not source_path.exists():
                    logger.warning(f"Source file does not exist: {source_path}")
                    return False, 0
                
                # Create target directory if needed
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy file
                shutil.copy2(source_path, target_path)
                return True, source_path.stat().st_size
                
            elif operation.operation_type == DeltaOperationType.UPDATE:
                # Update file (copy from source to target)
                if not source_path.exists():
                    logger.warning(f"Source file does not exist: {source_path}")
                    return False, 0
                
                # Create target directory if needed
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy file
                shutil.copy2(source_path, target_path)
                return True, source_path.stat().st_size
                
            elif operation.operation_type == DeltaOperationType.DELETE:
                # Delete target file
                if target_path.exists():
                    target_path.unlink()
                    return True, 0
                else:
                    logger.warning(f"Target file for deletion does not exist: {target_path}")
                    return True, 0  # Consider it successful
                
            elif operation.operation_type == DeltaOperationType.MOVE:
                # Move file from source to target
                if not source_path.exists():
                    logger.warning(f"Source file does not exist: {source_path}")
                    return False, 0
                
                # Create target directory if needed
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Move file
                shutil.move(source_path, target_path)
                return True, target_path.stat().st_size
                
            elif operation.operation_type == DeltaOperationType.COPY:
                # Copy file without removing source
                if not source_path.exists():
                    logger.warning(f"Source file does not exist: {source_path}")
                    return False, 0
                
                # Create target directory if needed
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy file
                shutil.copy2(source_path, target_path)
                return True, source_path.stat().st_size
            
            else:
                logger.error(f"Unknown operation type: {operation.operation_type}")
                return False, 0
                
        except Exception as e:
            logger.error(f"Failed to execute operation {operation.operation_type.value}: {e}")
            return False, 0
    
    async def sync_folder(
        self, 
        folder_name: str, 
        target_folder: str,
        sync_direction: SyncDirection = SyncDirection.SOURCE_TO_TARGET,
        dry_run: bool = False
    ) -> SyncResult:
        """Perform a complete folder sync operation."""
        logger.info(f"Starting {'dry run ' if dry_run else ''}sync for folder {folder_name} to {target_folder}")
        
        try:
            # Detect changes
            operations = await self.detect_changes(folder_name)
            
            if not operations:
                logger.info(f"No changes detected in folder {folder_name}")
                return SyncResult(
                    success=True,
                    operations_count=0,
                    bytes_transferred=0,
                    duration=0.0
                )
            
            # Update target paths for operations
            source_folder = self.snapshots[folder_name].folder_path
            target_path = Path(target_folder)
            
            for operation in operations:
                # Calculate relative path
                source_rel = Path(operation.source_path).relative_to(source_folder)
                operation.target_path = str(target_path / source_rel)
            
            # Apply operations
            result = await self.apply_delta_operations(operations, dry_run)
            
            # Update baseline snapshot if successful and not dry run
            if result.success and not dry_run:
                self.create_baseline_snapshot(folder_name)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to sync folder {folder_name}: {e}")
            return SyncResult(
                success=False,
                operations_count=0,
                bytes_transferred=0,
                duration=0.0,
                errors=[str(e)]
            )
    
    def get_sync_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get sync operation history."""
        history = self.sync_history.copy()
        if limit:
            history = history[-limit:]
        return [result.to_dict() for result in history]
    
    def get_folder_stats(self, folder_name: str) -> Dict[str, Any]:
        """Get statistics for a specific folder."""
        if folder_name not in self.snapshots:
            return {}
        
        snapshot = self.snapshots[folder_name]
        
        # Count recent sync operations for this folder
        recent_operations = 0
        recent_errors = 0
        for result in self.sync_history[-10:]:  # Last 10 syncs
            for op in result.operations:
                if op.folder_name == folder_name:
                    recent_operations += 1
            recent_errors += len(result.errors)
        
        return {
            'folder_name': folder_name,
            'folder_path': str(snapshot.folder_path),
            'last_snapshot_time': snapshot.snapshot_time.isoformat() if snapshot.snapshot_time else None,
            'file_count': len(snapshot.files),
            'total_size': sum(file_info['size'] for file_info in snapshot.files.values()),
            'recent_operations': recent_operations,
            'recent_errors': recent_errors
        }

class DeltaSyncManager:
    """Manages delta sync engines for multiple tenants."""
    
    def __init__(self):
        self.engines: Dict[str, DeltaSyncEngine] = {}
        self._lock = asyncio.Lock()
    
    async def get_engine(self, tenant_id: str) -> DeltaSyncEngine:
        """Get or create delta sync engine for tenant."""
        async with self._lock:
            if tenant_id not in self.engines:
                self.engines[tenant_id] = DeltaSyncEngine(tenant_id)
                logger.info(f"Created delta sync engine for tenant {tenant_id}")
            return self.engines[tenant_id]
    
    async def register_tenant_folder(
        self, 
        tenant_id: str, 
        folder_name: str, 
        folder_path: str
    ) -> bool:
        """Register a folder for a tenant."""
        engine = await self.get_engine(tenant_id)
        engine.register_folder(folder_name, folder_path)
        return await engine.create_baseline_snapshot(folder_name)
    
    async def sync_tenant_folder(
        self, 
        tenant_id: str, 
        folder_name: str, 
        target_folder: str,
        dry_run: bool = False
    ) -> SyncResult:
        """Sync a specific folder for a tenant."""
        engine = await self.get_engine(tenant_id)
        return await engine.sync_folder(folder_name, target_folder, dry_run=dry_run)
    
    async def get_tenant_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get comprehensive stats for a tenant."""
        if tenant_id not in self.engines:
            return {'tenant_id': tenant_id, 'folders': {}, 'sync_history': []}
        
        engine = self.engines[tenant_id]
        
        # Get stats for all folders
        folder_stats = {}
        for folder_name in engine.snapshots.keys():
            folder_stats[folder_name] = engine.get_folder_stats(folder_name)
        
        return {
            'tenant_id': tenant_id,
            'folders': folder_stats,
            'sync_history': engine.get_sync_history(limit=10),
            'total_syncs': len(engine.sync_history)
        }
    
    async def get_all_stats(self) -> Dict[str, Any]:
        """Get stats for all tenants."""
        stats = {}
        async with self._lock:
            for tenant_id in self.engines.keys():
                stats[tenant_id] = await self.get_tenant_stats(tenant_id)
        return stats

# Global delta sync manager
delta_sync_manager = DeltaSyncManager() 