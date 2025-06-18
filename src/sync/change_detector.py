"""
Change detection system for file synchronization.

This module provides change detection capabilities with tenant isolation,
delta tracking, and file comparison utilities.
"""

import os
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
import asyncio
import json

logger = logging.getLogger(__name__)

class ChangeType(Enum):
    """Types of file changes."""
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"
    METADATA_CHANGED = "metadata_changed"

@dataclass
class FileChange:
    """Represents a detected file change."""
    change_type: ChangeType
    file_path: str
    tenant_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    old_path: Optional[str] = None  # For rename operations
    old_hash: Optional[str] = None
    new_hash: Optional[str] = None
    old_size: Optional[int] = None
    new_size: Optional[int] = None
    old_modified: Optional[datetime] = None
    new_modified: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert change to dictionary for serialization."""
        return {
            'change_type': self.change_type.value,
            'file_path': self.file_path,
            'tenant_id': self.tenant_id,
            'timestamp': self.timestamp.isoformat(),
            'old_path': self.old_path,
            'old_hash': self.old_hash,
            'new_hash': self.new_hash,
            'old_size': self.old_size,
            'new_size': self.new_size,
            'old_modified': self.old_modified.isoformat() if self.old_modified else None,
            'new_modified': self.new_modified.isoformat() if self.new_modified else None,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FileChange':
        """Create change from dictionary."""
        return cls(
            change_type=ChangeType(data['change_type']),
            file_path=data['file_path'],
            tenant_id=data['tenant_id'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            old_path=data.get('old_path'),
            old_hash=data.get('old_hash'),
            new_hash=data.get('new_hash'),
            old_size=data.get('old_size'),
            new_size=data.get('new_size'),
            old_modified=datetime.fromisoformat(data['old_modified']) if data.get('old_modified') else None,
            new_modified=datetime.fromisoformat(data['new_modified']) if data.get('new_modified') else None,
            metadata=data.get('metadata', {})
        )

@dataclass
class FileSnapshot:
    """Snapshot of file state at a point in time."""
    file_path: str
    exists: bool
    size: Optional[int] = None
    modified_time: Optional[datetime] = None
    hash_md5: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate file metadata after initialization."""
        if self.exists and os.path.exists(self.file_path):
            try:
                stat = os.stat(self.file_path)
                self.size = stat.st_size
                self.modified_time = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
                
                # Calculate hash for small files only
                if self.size and self.size < 50 * 1024 * 1024:  # 50MB limit
                    self.hash_md5 = self._calculate_hash()
            except (OSError, IOError) as e:
                logger.warning(f"Failed to get file info for {self.file_path}: {e}")
                self.exists = False
    
    def _calculate_hash(self) -> str:
        """Calculate MD5 hash of the file."""
        try:
            hasher = hashlib.md5()
            with open(self.file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (OSError, IOError):
            return ""
    
    def has_changed(self, other: 'FileSnapshot') -> bool:
        """Check if this snapshot differs from another."""
        if self.exists != other.exists:
            return True
        
        if not self.exists:  # Both don't exist
            return False
        
        # Check basic attributes
        if (self.size != other.size or 
            self.modified_time != other.modified_time):
            return True
        
        # Check hash if available
        if (self.hash_md5 and other.hash_md5 and 
            self.hash_md5 != other.hash_md5):
            return True
        
        return False

class ChangeDetector:
    """Detects changes in file system."""
    
    def __init__(self, tenant_id: str, source_folders: List[str]):
        self.tenant_id = tenant_id
        self.source_folders = [Path(folder).resolve() for folder in source_folders]
        self.current_snapshots: Dict[str, FileSnapshot] = {}
        self.previous_snapshots: Dict[str, FileSnapshot] = {}
        self.supported_extensions = {
            '.pdf', '.docx', '.doc', '.pptx', '.ppt', '.txt', '.md',
            '.xlsx', '.xls', '.csv'
        }
    
    def _is_supported_file(self, file_path: str) -> bool:
        """Check if file has supported extension."""
        return Path(file_path).suffix.lower() in self.supported_extensions
    
    def _scan_directory(self, directory: Path) -> Dict[str, FileSnapshot]:
        """Scan directory and create snapshots of all supported files."""
        snapshots = {}
        
        try:
            for file_path in directory.rglob('*'):
                if (file_path.is_file() and 
                    self._is_supported_file(str(file_path))):
                    
                    relative_path = str(file_path.resolve())
                    snapshots[relative_path] = FileSnapshot(
                        file_path=relative_path,
                        exists=True
                    )
        except Exception as e:
            logger.error(f"Error scanning directory {directory}: {e}")
        
        return snapshots
    
    async def create_baseline_snapshot(self) -> None:
        """Create initial baseline snapshot of all files."""
        logger.info(f"Creating baseline snapshot for tenant {self.tenant_id}")
        
        all_snapshots = {}
        
        for folder in self.source_folders:
            if folder.exists():
                folder_snapshots = self._scan_directory(folder)
                all_snapshots.update(folder_snapshots)
        
        self.current_snapshots = all_snapshots
        self.previous_snapshots = {}
        
        logger.info(f"Baseline snapshot created with {len(all_snapshots)} files for tenant {self.tenant_id}")
    
    async def detect_changes(self) -> List[FileChange]:
        """Detect changes since last snapshot."""
        # Move current to previous
        self.previous_snapshots = self.current_snapshots.copy()
        
        # Create new current snapshot
        new_snapshots = {}
        for folder in self.source_folders:
            if folder.exists():
                folder_snapshots = self._scan_directory(folder)
                new_snapshots.update(folder_snapshots)
        
        self.current_snapshots = new_snapshots
        
        # Detect changes
        changes = []
        
        # Find all files (current and previous)
        all_files = set(self.current_snapshots.keys()) | set(self.previous_snapshots.keys())
        
        for file_path in all_files:
            current = self.current_snapshots.get(file_path)
            previous = self.previous_snapshots.get(file_path)
            
            change = self._compare_snapshots(file_path, previous, current)
            if change:
                changes.append(change)
        
        logger.debug(f"Detected {len(changes)} changes for tenant {self.tenant_id}")
        return changes
    
    def _compare_snapshots(
        self, 
        file_path: str, 
        previous: Optional[FileSnapshot], 
        current: Optional[FileSnapshot]
    ) -> Optional[FileChange]:
        """Compare two snapshots and create change if different."""
        
        # File was added
        if previous is None and current and current.exists:
            return FileChange(
                change_type=ChangeType.ADDED,
                file_path=file_path,
                tenant_id=self.tenant_id,
                new_hash=current.hash_md5,
                new_size=current.size,
                new_modified=current.modified_time
            )
        
        # File was deleted
        if previous and previous.exists and (current is None or not current.exists):
            return FileChange(
                change_type=ChangeType.DELETED,
                file_path=file_path,
                tenant_id=self.tenant_id,
                old_hash=previous.hash_md5,
                old_size=previous.size,
                old_modified=previous.modified_time
            )
        
        # File was modified
        if (previous and previous.exists and 
            current and current.exists and 
            current.has_changed(previous)):
            
            return FileChange(
                change_type=ChangeType.MODIFIED,
                file_path=file_path,
                tenant_id=self.tenant_id,
                old_hash=previous.hash_md5,
                new_hash=current.hash_md5,
                old_size=previous.size,
                new_size=current.size,
                old_modified=previous.modified_time,
                new_modified=current.modified_time
            )
        
        return None
    
    def get_current_file_count(self) -> int:
        """Get number of files in current snapshot."""
        return len([s for s in self.current_snapshots.values() if s.exists])
    
    def get_file_info(self, file_path: str) -> Optional[FileSnapshot]:
        """Get current snapshot info for a specific file."""
        return self.current_snapshots.get(file_path)

class TenantChangeTracker:
    """Tracks changes across multiple tenants."""
    
    def __init__(self):
        self.detectors: Dict[str, ChangeDetector] = {}
        self.change_history: Dict[str, List[FileChange]] = {}
        self.max_history_per_tenant = 1000
    
    def add_tenant(self, tenant_id: str, source_folders: List[str]) -> ChangeDetector:
        """Add change detection for a tenant."""
        if tenant_id in self.detectors:
            logger.warning(f"Change detector for tenant {tenant_id} already exists")
            return self.detectors[tenant_id]
        
        detector = ChangeDetector(tenant_id, source_folders)
        self.detectors[tenant_id] = detector
        self.change_history[tenant_id] = []
        
        logger.info(f"Added change detector for tenant {tenant_id}")
        return detector
    
    def remove_tenant(self, tenant_id: str) -> bool:
        """Remove change detection for a tenant."""
        if tenant_id not in self.detectors:
            logger.warning(f"No change detector found for tenant {tenant_id}")
            return False
        
        del self.detectors[tenant_id]
        del self.change_history[tenant_id]
        
        logger.info(f"Removed change detector for tenant {tenant_id}")
        return True
    
    async def initialize_all_baselines(self) -> None:
        """Initialize baseline snapshots for all tenants."""
        tasks = []
        for detector in self.detectors.values():
            tasks.append(detector.create_baseline_snapshot())
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info(f"Initialized baselines for {len(self.detectors)} tenants")
    
    async def detect_all_changes(self) -> Dict[str, List[FileChange]]:
        """Detect changes for all tenants."""
        tasks = []
        tenant_ids = []
        
        for tenant_id, detector in self.detectors.items():
            tasks.append(detector.detect_changes())
            tenant_ids.append(tenant_id)
        
        if not tasks:
            return {}
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_changes = {}
        for tenant_id, result in zip(tenant_ids, results):
            if isinstance(result, Exception):
                logger.error(f"Error detecting changes for tenant {tenant_id}: {result}")
                all_changes[tenant_id] = []
            else:
                changes = result or []
                all_changes[tenant_id] = changes
                
                # Update history
                self.change_history[tenant_id].extend(changes)
                
                # Trim history if too long
                if len(self.change_history[tenant_id]) > self.max_history_per_tenant:
                    self.change_history[tenant_id] = self.change_history[tenant_id][-self.max_history_per_tenant:]
        
        return all_changes
    
    def get_tenant_changes(
        self, 
        tenant_id: str, 
        limit: Optional[int] = None,
        since: Optional[datetime] = None
    ) -> List[FileChange]:
        """Get change history for a specific tenant."""
        if tenant_id not in self.change_history:
            return []
        
        changes = self.change_history[tenant_id]
        
        # Filter by time if specified
        if since:
            changes = [c for c in changes if c.timestamp >= since]
        
        # Apply limit
        if limit:
            changes = changes[-limit:]
        
        return changes
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all tenant change detectors."""
        stats = {}
        
        for tenant_id, detector in self.detectors.items():
            stats[tenant_id] = {
                'file_count': detector.get_current_file_count(),
                'change_count': len(self.change_history.get(tenant_id, [])),
                'source_folders': [str(f) for f in detector.source_folders],
                'last_scan': datetime.now(timezone.utc).isoformat()
            }
        
        return stats
    
    def export_changes(self, tenant_id: str, file_path: str) -> bool:
        """Export changes to JSON file."""
        if tenant_id not in self.change_history:
            return False
        
        try:
            changes_data = [
                change.to_dict() 
                for change in self.change_history[tenant_id]
            ]
            
            with open(file_path, 'w') as f:
                json.dump(changes_data, f, indent=2)
            
            logger.info(f"Exported {len(changes_data)} changes for tenant {tenant_id} to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export changes for tenant {tenant_id}: {e}")
            return False

# Global change tracker instance
tenant_change_tracker = TenantChangeTracker() 