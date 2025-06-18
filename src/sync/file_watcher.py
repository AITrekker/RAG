"""
Simplified file system watcher with multi-tenant support.

This module provides basic file system monitoring capabilities without
external dependencies, using polling-based monitoring.
"""

import os
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Callable, Any
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import threading
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class FileEventType(Enum):
    """Types of file system events."""
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    MOVED = "moved"

@dataclass
class FileEvent:
    """Represents a file system event."""
    event_type: FileEventType
    file_path: str
    tenant_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    old_path: Optional[str] = None  # For move events
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate file metadata after initialization."""
        if self.event_type != FileEventType.DELETED and os.path.exists(self.file_path):
            try:
                stat = os.stat(self.file_path)
                self.file_size = stat.st_size
                if self.file_size < 100 * 1024 * 1024:  # Only hash files < 100MB
                    self.file_hash = self._calculate_hash()
            except (OSError, IOError) as e:
                logger.warning(f"Failed to get file metadata for {self.file_path}: {e}")
    
    def _calculate_hash(self) -> str:
        """Calculate MD5 hash of the file."""
        try:
            hasher = hashlib.md5()
            with open(self.file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (OSError, IOError):
            return ""

class TenantFileWatcher:
    """Simple polling-based file watcher for a specific tenant."""
    
    def __init__(
        self,
        tenant_id: str,
        source_folders: List[str],
        supported_extensions: Optional[Set[str]] = None,
        event_callback: Optional[Callable[[FileEvent], None]] = None,
        poll_interval: float = 10.0
    ):
        self.tenant_id = tenant_id
        self.source_folders = [Path(folder).resolve() for folder in source_folders]
        self.supported_extensions = supported_extensions or {
            '.pdf', '.docx', '.doc', '.pptx', '.ppt', '.txt', '.md',
            '.xlsx', '.xls', '.csv'
        }
        self.event_callback = event_callback
        self.poll_interval = poll_interval
        self.is_active = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.file_states: Dict[str, float] = {}  # file_path -> mtime
        self.stats = {
            'events_processed': 0,
            'files_watched': 0,
            'last_event_time': None,
            'errors': 0
        }
        
        # Validate and create tenant directories
        self._validate_directories()
    
    def _validate_directories(self) -> None:
        """Validate and create tenant source directories."""
        valid_folders = []
        for folder in self.source_folders:
            try:
                # Create directory if it doesn't exist
                folder.mkdir(parents=True, exist_ok=True)
                
                # Check if directory is accessible
                if folder.exists() and folder.is_dir():
                    if os.access(folder, os.R_OK):
                        valid_folders.append(folder)
                        logger.info(f"Validated tenant {self.tenant_id} folder: {folder}")
                    else:
                        logger.error(f"No read access to folder {folder} for tenant {self.tenant_id}")
                else:
                    logger.error(f"Invalid directory {folder} for tenant {self.tenant_id}")
            except Exception as e:
                logger.error(f"Failed to validate directory {folder} for tenant {self.tenant_id}: {e}")
        
        self.source_folders = valid_folders
        if not self.source_folders:
            raise ValueError(f"No valid source folders found for tenant {self.tenant_id}")
    
    def _is_supported_file(self, file_path: str) -> bool:
        """Check if file has supported extension."""
        return Path(file_path).suffix.lower() in self.supported_extensions
    
    def _is_tenant_file(self, file_path: str) -> bool:
        """Check if file belongs to this tenant's directories."""
        file_path_obj = Path(file_path).resolve()
        return any(
            str(file_path_obj).startswith(str(folder))
            for folder in self.source_folders
        )
    
    def _scan_files(self) -> Dict[str, float]:
        """Scan all files and return their modification times."""
        current_files = {}
        
        for folder in self.source_folders:
            if not folder.exists():
                continue
                
            try:
                for file_path in folder.rglob('*'):
                    if (file_path.is_file() and 
                        self._is_supported_file(str(file_path))):
                        
                        try:
                            mtime = file_path.stat().st_mtime
                            current_files[str(file_path)] = mtime
                        except (OSError, IOError):
                            # File might have been deleted between scan and stat
                            continue
            except Exception as e:
                logger.error(f"Error scanning folder {folder}: {e}")
        
        return current_files
    
    def _detect_changes(self, current_files: Dict[str, float]) -> List[FileEvent]:
        """Detect changes between current scan and previous state."""
        events = []
        
        # Find new and modified files
        for file_path, mtime in current_files.items():
            if file_path not in self.file_states:
                # New file
                events.append(FileEvent(
                    event_type=FileEventType.CREATED,
                    file_path=file_path,
                    tenant_id=self.tenant_id
                ))
            elif self.file_states[file_path] != mtime:
                # Modified file
                events.append(FileEvent(
                    event_type=FileEventType.MODIFIED,
                    file_path=file_path,
                    tenant_id=self.tenant_id
                ))
        
        # Find deleted files
        for file_path in self.file_states:
            if file_path not in current_files:
                events.append(FileEvent(
                    event_type=FileEventType.DELETED,
                    file_path=file_path,
                    tenant_id=self.tenant_id
                ))
        
        return events
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        logger.info(f"Started monitoring for tenant {self.tenant_id}")
        
        # Initial scan
        self.file_states = self._scan_files()
        self.stats['files_watched'] = len(self.file_states)
        
        while self.is_active:
            try:
                # Scan for changes
                current_files = self._scan_files()
                events = self._detect_changes(current_files)
                
                # Process events
                for event in events:
                    try:
                        if self.event_callback:
                            self.event_callback(event)
                        
                        self.stats['events_processed'] += 1
                        self.stats['last_event_time'] = event.timestamp
                        
                        logger.debug(f"Processed {event.event_type.value} event for {event.file_path}")
                        
                    except Exception as e:
                        self.stats['errors'] += 1
                        logger.error(f"Error handling event for {event.file_path}: {e}")
                
                # Update state
                self.file_states = current_files
                self.stats['files_watched'] = len(current_files)
                
                # Wait for next poll
                await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                self.stats['errors'] += 1
                logger.error(f"Error in monitoring loop for tenant {self.tenant_id}: {e}")
                await asyncio.sleep(self.poll_interval)
        
        logger.info(f"Stopped monitoring for tenant {self.tenant_id}")
    
    async def start_watching(self) -> None:
        """Start watching tenant directories."""
        if self.is_active:
            logger.warning(f"Watcher for tenant {self.tenant_id} is already active")
            return
        
        self.is_active = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"File watcher started for tenant {self.tenant_id}")
    
    async def stop_watching(self) -> None:
        """Stop watching tenant directories."""
        if not self.is_active:
            return
            
        self.is_active = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info(f"File watcher stopped for tenant {self.tenant_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get watcher statistics."""
        return {
            **self.stats,
            'tenant_id': self.tenant_id,
            'source_folders': [str(f) for f in self.source_folders],
            'supported_extensions': list(self.supported_extensions),
            'is_active': self.is_active,
            'poll_interval': self.poll_interval
        }

class FileWatcherManager:
    """Manages file watchers for multiple tenants."""
    
    def __init__(self):
        self.watchers: Dict[str, TenantFileWatcher] = {}
        self.global_event_handlers: List[Callable[[FileEvent], None]] = []
        self.is_running = False
        self._lock = threading.Lock()
    
    def add_tenant_watcher(
        self,
        tenant_id: str,
        source_folders: List[str],
        supported_extensions: Optional[Set[str]] = None,
        poll_interval: float = 10.0
    ) -> TenantFileWatcher:
        """Add a file watcher for a tenant."""
        with self._lock:
            if tenant_id in self.watchers:
                logger.warning(f"Watcher for tenant {tenant_id} already exists")
                return self.watchers[tenant_id]
            
            watcher = TenantFileWatcher(
                tenant_id=tenant_id,
                source_folders=source_folders,
                supported_extensions=supported_extensions,
                event_callback=self._handle_global_event,
                poll_interval=poll_interval
            )
            
            self.watchers[tenant_id] = watcher
            logger.info(f"Added watcher for tenant {tenant_id}")
            
            # Start watcher if manager is running
            if self.is_running:
                asyncio.create_task(watcher.start_watching())
            
            return watcher
    
    def remove_tenant_watcher(self, tenant_id: str) -> bool:
        """Remove a file watcher for a tenant."""
        with self._lock:
            if tenant_id not in self.watchers:
                logger.warning(f"No watcher found for tenant {tenant_id}")
                return False
            
            watcher = self.watchers[tenant_id]
            if watcher.is_active:
                asyncio.create_task(watcher.stop_watching())
            
            del self.watchers[tenant_id]
            logger.info(f"Removed watcher for tenant {tenant_id}")
            return True
    
    def add_global_event_handler(self, handler: Callable[[FileEvent], None]) -> None:
        """Add a global event handler for all tenant events."""
        self.global_event_handlers.append(handler)
    
    def _handle_global_event(self, event: FileEvent) -> None:
        """Handle events from all tenant watchers."""
        for handler in self.global_event_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in global event handler: {e}")
    
    async def start_all_watchers(self) -> None:
        """Start all tenant watchers."""
        with self._lock:
            self.is_running = True
            start_tasks = []
            for watcher in self.watchers.values():
                if not watcher.is_active:
                    start_tasks.append(watcher.start_watching())
            
            if start_tasks:
                await asyncio.gather(*start_tasks, return_exceptions=True)
            
            logger.info(f"Started {len(self.watchers)} tenant watchers")
    
    async def stop_all_watchers(self) -> None:
        """Stop all tenant watchers."""
        with self._lock:
            self.is_running = False
            stop_tasks = []
            for watcher in self.watchers.values():
                if watcher.is_active:
                    stop_tasks.append(watcher.stop_watching())
            
            if stop_tasks:
                await asyncio.gather(*stop_tasks, return_exceptions=True)
            
            logger.info("Stopped all tenant watchers")
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all tenant watchers."""
        with self._lock:
            return {
                tenant_id: watcher.get_stats()
                for tenant_id, watcher in self.watchers.items()
            }
    
    def get_tenant_watcher(self, tenant_id: str) -> Optional[TenantFileWatcher]:
        """Get watcher for specific tenant."""
        return self.watchers.get(tenant_id)
    
    @asynccontextmanager
    async def managed_watchers(self):
        """Context manager for managing all watchers."""
        try:
            await self.start_all_watchers()
            yield self
        finally:
            await self.stop_all_watchers()

# Global file watcher manager instance
file_watcher_manager = FileWatcherManager() 