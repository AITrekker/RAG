"""
File monitoring utility for the Enterprise RAG Platform.

This module provides file system monitoring capabilities to detect document
changes and trigger processing workflows. Supports tenant-specific monitoring
with configurable filters and event handling.
"""

import os
import time
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Set, Optional, Callable, Any
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import threading
from queue import Queue, Empty
import hashlib

# Third-party imports for file watching
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = None
    FileSystemEvent = None

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """Types of file system changes."""
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    MOVED = "moved"


@dataclass
class FileChangeEvent:
    """Represents a file system change event."""
    tenant_id: str
    file_path: str
    change_type: ChangeType
    timestamp: datetime
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    old_path: Optional[str] = None  # For moved files
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary representation."""
        return {
            'tenant_id': self.tenant_id,
            'file_path': self.file_path,
            'change_type': self.change_type.value,
            'timestamp': self.timestamp.isoformat(),
            'file_size': self.file_size,
            'file_hash': self.file_hash,
            'old_path': self.old_path,
            'metadata': self.metadata
        }


@dataclass
class MonitoringConfig:
    """Configuration for file monitoring."""
    # File patterns to monitor
    include_extensions: Set[str] = None  # e.g., {'.pdf', '.docx', '.txt'}
    exclude_patterns: Set[str] = None    # e.g., {'temp*', '.*', '__pycache__'}
    
    # Monitoring behavior
    recursive: bool = True
    check_interval: int = 5  # seconds for polling fallback
    debounce_time: float = 2.0  # seconds to wait for file stability
    
    # Processing options
    calculate_hash: bool = True
    track_file_size: bool = True
    monitor_subdirectories: bool = True
    
    def __post_init__(self):
        if self.include_extensions is None:
            self.include_extensions = {'.pdf', '.doc', '.docx', '.txt', '.md', '.html', '.htm'}
        if self.exclude_patterns is None:
            self.exclude_patterns = {'temp*', '.*', '__pycache__', '*.tmp', '*.lock'}
    
    def should_monitor_file(self, file_path: str) -> bool:
        """Check if file should be monitored based on configuration."""
        path_obj = Path(file_path)
        
        # Check extension
        if self.include_extensions and path_obj.suffix.lower() not in self.include_extensions:
            return False
        
        # Check exclude patterns
        for pattern in self.exclude_patterns:
            if path_obj.match(pattern):
                return False
        
        return True


if WATCHDOG_AVAILABLE:
    class TenantFileEventHandler(FileSystemEventHandler):
        """File system event handler for tenant-specific monitoring."""
        
        def __init__(self, tenant_id: str, config: MonitoringConfig, event_queue: Queue):
            super().__init__()
            self.tenant_id = tenant_id
            self.config = config
            self.event_queue = event_queue
            self.debounce_events = {}  # path -> (timestamp, event)
            self._lock = threading.Lock()
            
            # Start debounce cleanup thread
            self._cleanup_thread = threading.Thread(target=self._cleanup_debounce, daemon=True)
            self._cleanup_thread.start()
        
        def on_created(self, event):
            """Handle file creation events."""
            if not event.is_directory and self.config.should_monitor_file(event.src_path):
                self._handle_event(event.src_path, ChangeType.CREATED)
        
        def on_modified(self, event):
            """Handle file modification events."""
            if not event.is_directory and self.config.should_monitor_file(event.src_path):
                self._handle_event(event.src_path, ChangeType.MODIFIED)
        
        def on_deleted(self, event):
            """Handle file deletion events."""
            if not event.is_directory and self.config.should_monitor_file(event.src_path):
                self._handle_event(event.src_path, ChangeType.DELETED)
        
        def on_moved(self, event):
            """Handle file move events."""
            if not event.is_directory:
                if (self.config.should_monitor_file(event.src_path) or 
                    self.config.should_monitor_file(event.dest_path)):
                    self._handle_move_event(event.src_path, event.dest_path)
        
        def _handle_event(self, file_path: str, change_type: ChangeType):
            """Handle individual file system events with debouncing."""
            with self._lock:
                now = time.time()
                
                # Store event for debouncing
                self.debounce_events[file_path] = (now, change_type)
        
        def _handle_move_event(self, old_path: str, new_path: str):
            """Handle file move events."""
            now = time.time()
            
            # Create file change event
            try:
                file_info = self._get_file_info(new_path) if os.path.exists(new_path) else {}
                
                event = FileChangeEvent(
                    tenant_id=self.tenant_id,
                    file_path=new_path,
                    change_type=ChangeType.MOVED,
                    timestamp=datetime.now(timezone.utc),
                    old_path=old_path,
                    **file_info
                )
                
                self.event_queue.put(event)
                logger.debug(f"File moved: {old_path} -> {new_path}")
                
            except Exception as e:
                logger.error(f"Error handling move event: {e}")
        
        def _cleanup_debounce(self):
            """Cleanup debounced events and emit stable events."""
            while True:
                try:
                    time.sleep(self.config.debounce_time / 2)
                    now = time.time()
                    
                    with self._lock:
                        stable_events = []
                        for file_path, (timestamp, change_type) in list(self.debounce_events.items()):
                            if now - timestamp >= self.config.debounce_time:
                                stable_events.append((file_path, change_type))
                                del self.debounce_events[file_path]
                    
                    # Process stable events
                    for file_path, change_type in stable_events:
                        self._emit_stable_event(file_path, change_type)
                        
                except Exception as e:
                    logger.error(f"Error in debounce cleanup: {e}")
        
        def _emit_stable_event(self, file_path: str, change_type: ChangeType):
            """Emit a stable file change event."""
            try:
                # Get file information if file exists
                if change_type != ChangeType.DELETED and os.path.exists(file_path):
                    file_info = self._get_file_info(file_path)
                else:
                    file_info = {}
                
                event = FileChangeEvent(
                    tenant_id=self.tenant_id,
                    file_path=file_path,
                    change_type=change_type,
                    timestamp=datetime.now(timezone.utc),
                    **file_info
                )
                
                self.event_queue.put(event)
                logger.info(f"File {change_type.value}: {file_path}")
                
            except Exception as e:
                logger.error(f"Error emitting stable event for {file_path}: {e}")
        
        def _get_file_info(self, file_path: str) -> Dict[str, Any]:
            """Get file information for event."""
            info = {}
            
            try:
                if self.config.track_file_size:
                    info['file_size'] = os.path.getsize(file_path)
                
                if self.config.calculate_hash:
                    info['file_hash'] = self._calculate_file_hash(file_path)
                    
            except Exception as e:
                logger.warning(f"Could not get file info for {file_path}: {e}")
            
            return info
        
        def _calculate_file_hash(self, file_path: str) -> str:
            """Calculate SHA-256 hash of file."""
            try:
                hash_sha256 = hashlib.sha256()
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hash_sha256.update(chunk)
                return hash_sha256.hexdigest()
            except Exception:
                return None

else:
    class TenantFileEventHandler:
        """Fallback file system event handler when watchdog is not available."""
        
        def __init__(self, tenant_id: str, config: MonitoringConfig, event_queue: Queue):
            self.tenant_id = tenant_id
            self.config = config
            self.event_queue = event_queue
            self.debounce_events = {}  # path -> (timestamp, event)
            self._lock = threading.Lock()
            
            # Start debounce cleanup thread
            self._cleanup_thread = threading.Thread(target=self._cleanup_debounce, daemon=True)
            self._cleanup_thread.start()
        
        def on_created(self, event):
            """Handle file creation events - stub for fallback mode."""
            pass
        
        def on_modified(self, event):
            """Handle file modification events - stub for fallback mode."""
            pass
        
        def on_deleted(self, event):
            """Handle file deletion events - stub for fallback mode."""
            pass
        
        def on_moved(self, event):
            """Handle file move events - stub for fallback mode."""
            pass
        
        def _handle_event(self, file_path: str, change_type: ChangeType):
            """Handle individual file system events with debouncing."""
            with self._lock:
                now = time.time()
                
                # Store event for debouncing
                self.debounce_events[file_path] = (now, change_type)
        
        def _handle_move_event(self, old_path: str, new_path: str):
            """Handle file move events."""
            now = time.time()
            
            # Create file change event
            try:
                file_info = self._get_file_info(new_path) if os.path.exists(new_path) else {}
                
                event = FileChangeEvent(
                    tenant_id=self.tenant_id,
                    file_path=new_path,
                    change_type=ChangeType.MOVED,
                    timestamp=datetime.now(timezone.utc),
                    old_path=old_path,
                    **file_info
                )
                
                self.event_queue.put(event)
                logger.debug(f"File moved: {old_path} -> {new_path}")
                
            except Exception as e:
                logger.error(f"Error handling move event: {e}")
        
        def _cleanup_debounce(self):
            """Cleanup debounced events and emit stable events."""
            while True:
                try:
                    time.sleep(self.config.debounce_time / 2)
                    now = time.time()
                    
                    with self._lock:
                        stable_events = []
                        for file_path, (timestamp, change_type) in list(self.debounce_events.items()):
                            if now - timestamp >= self.config.debounce_time:
                                stable_events.append((file_path, change_type))
                                del self.debounce_events[file_path]
                    
                    # Process stable events
                    for file_path, change_type in stable_events:
                        self._emit_stable_event(file_path, change_type)
                        
                except Exception as e:
                    logger.error(f"Error in debounce cleanup: {e}")
        
        def _emit_stable_event(self, file_path: str, change_type: ChangeType):
            """Emit a stable file change event."""
            try:
                # Get file information if file exists
                if change_type != ChangeType.DELETED and os.path.exists(file_path):
                    file_info = self._get_file_info(file_path)
                else:
                    file_info = {}
                
                event = FileChangeEvent(
                    tenant_id=self.tenant_id,
                    file_path=file_path,
                    change_type=change_type,
                    timestamp=datetime.now(timezone.utc),
                    **file_info
                )
                
                self.event_queue.put(event)
                logger.info(f"File {change_type.value}: {file_path}")
                
            except Exception as e:
                logger.error(f"Error emitting stable event for {file_path}: {e}")
        
        def _get_file_info(self, file_path: str) -> Dict[str, Any]:
            """Get file information for event."""
            info = {}
            
            try:
                if self.config.track_file_size:
                    info['file_size'] = os.path.getsize(file_path)
                
                if self.config.calculate_hash:
                    info['file_hash'] = self._calculate_file_hash(file_path)
                    
            except Exception as e:
                logger.warning(f"Could not get file info for {file_path}: {e}")
            
            return info
        
        def _calculate_file_hash(self, file_path: str) -> str:
            """Calculate SHA-256 hash of file."""
            try:
                hash_sha256 = hashlib.sha256()
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hash_sha256.update(chunk)
                return hash_sha256.hexdigest()
            except Exception:
                return None


class FileMonitor:
    """
    Main file monitoring service for tenant-specific document watching.
    
    Provides real-time file system monitoring with tenant isolation,
    configurable filters, and event handling capabilities.
    """
    
    def __init__(self, config: MonitoringConfig = None):
        """Initialize file monitor with configuration."""
        self.config = config or MonitoringConfig()
        self.event_queue = Queue()
        self.observers = {}  # tenant_id -> Observer
        self.event_handlers = {}  # tenant_id -> handler
        self.event_callbacks = {}  # tenant_id -> List[callback]
        self.is_running = False
        self._processing_thread = None
        
        if not WATCHDOG_AVAILABLE:
            logger.warning("Watchdog not available, falling back to polling mode")
    
    def add_tenant_monitor(
        self, 
        tenant_id: str, 
        watch_path: str,
        callback: Callable[[FileChangeEvent], None] = None
    ) -> bool:
        """
        Add monitoring for a tenant's directory.
        
        Args:
            tenant_id: Tenant identifier
            watch_path: Directory path to monitor
            callback: Optional callback function for events
            
        Returns:
            True if monitoring was successfully added
        """
        try:
            if not os.path.exists(watch_path):
                logger.error(f"Watch path does not exist: {watch_path}")
                return False
            
            if tenant_id in self.observers:
                logger.warning(f"Monitor already exists for tenant {tenant_id}")
                return False
            
            # Create event handler
            handler = TenantFileEventHandler(tenant_id, self.config, self.event_queue)
            self.event_handlers[tenant_id] = handler
            
            # Set up callback
            if callback:
                self.event_callbacks[tenant_id] = [callback]
            else:
                self.event_callbacks[tenant_id] = []
            
            # Create and start observer if watchdog is available
            if WATCHDOG_AVAILABLE:
                observer = Observer()
                observer.schedule(handler, watch_path, recursive=self.config.recursive)
                self.observers[tenant_id] = observer
                
                if self.is_running:
                    observer.start()
                    
                logger.info(f"Added file monitor for tenant {tenant_id} at {watch_path}")
            else:
                # Fallback to polling mode
                self._start_polling_monitor(tenant_id, watch_path)
                logger.info(f"Added polling monitor for tenant {tenant_id} at {watch_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding tenant monitor: {e}")
            return False
    
    def remove_tenant_monitor(self, tenant_id: str) -> bool:
        """Remove monitoring for a tenant."""
        try:
            if tenant_id in self.observers:
                observer = self.observers[tenant_id]
                if observer.is_alive():
                    observer.stop()
                    observer.join()
                del self.observers[tenant_id]
            
            if tenant_id in self.event_handlers:
                del self.event_handlers[tenant_id]
            
            if tenant_id in self.event_callbacks:
                del self.event_callbacks[tenant_id]
            
            logger.info(f"Removed file monitor for tenant {tenant_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error removing tenant monitor: {e}")
            return False
    
    def add_event_callback(self, tenant_id: str, callback: Callable[[FileChangeEvent], None]):
        """Add event callback for a tenant."""
        if tenant_id not in self.event_callbacks:
            self.event_callbacks[tenant_id] = []
        self.event_callbacks[tenant_id].append(callback)
    
    def start(self):
        """Start the file monitoring service."""
        if self.is_running:
            logger.warning("File monitor is already running")
            return
        
        self.is_running = True
        
        # Start all observers
        if WATCHDOG_AVAILABLE:
            for observer in self.observers.values():
                observer.start()
        
        # Start event processing thread
        self._processing_thread = threading.Thread(target=self._process_events, daemon=True)
        self._processing_thread.start()
        
        logger.info("File monitor service started")
    
    def stop(self):
        """Stop the file monitoring service."""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Stop all observers
        if WATCHDOG_AVAILABLE:
            for observer in self.observers.values():
                observer.stop()
            
            for observer in self.observers.values():
                observer.join()
        
        logger.info("File monitor service stopped")
    
    def _process_events(self):
        """Process file change events from the queue."""
        while self.is_running:
            try:
                # Get event from queue with timeout
                try:
                    event = self.event_queue.get(timeout=1)
                except Empty:
                    continue
                
                # Process event
                self._handle_event(event)
                
            except Exception as e:
                logger.error(f"Error processing event: {e}")
    
    def _handle_event(self, event: FileChangeEvent):
        """Handle a file change event."""
        try:
            tenant_id = event.tenant_id
            
            # Call registered callbacks
            if tenant_id in self.event_callbacks:
                for callback in self.event_callbacks[tenant_id]:
                    try:
                        callback(event)
                    except Exception as e:
                        logger.error(f"Error in event callback: {e}")
            
            logger.debug(f"Processed event: {event.to_dict()}")
            
        except Exception as e:
            logger.error(f"Error handling event: {e}")
    
    def _start_polling_monitor(self, tenant_id: str, watch_path: str):
        """Start polling-based monitoring as fallback."""
        # This is a simplified polling implementation
        # In a production system, you'd want a more sophisticated approach
        def polling_thread():
            last_scan = {}
            
            while self.is_running and tenant_id in self.event_handlers:
                try:
                    current_scan = self._scan_directory(watch_path)
                    
                    # Compare with last scan
                    if last_scan:
                        self._compare_scans(tenant_id, last_scan, current_scan)
                    
                    last_scan = current_scan
                    time.sleep(self.config.check_interval)
                    
                except Exception as e:
                    logger.error(f"Error in polling thread for {tenant_id}: {e}")
        
        thread = threading.Thread(target=polling_thread, daemon=True)
        thread.start()
    
    def _scan_directory(self, directory: str) -> Dict[str, Dict[str, Any]]:
        """Scan directory and return file information."""
        files = {}
        
        try:
            for root, dirs, filenames in os.walk(directory):
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    
                    if self.config.should_monitor_file(file_path):
                        try:
                            stat = os.stat(file_path)
                            files[file_path] = {
                                'size': stat.st_size,
                                'mtime': stat.st_mtime,
                                'exists': True
                            }
                        except (OSError, IOError):
                            continue
        except Exception as e:
            logger.error(f"Error scanning directory {directory}: {e}")
        
        return files
    
    def _compare_scans(self, tenant_id: str, old_scan: Dict, new_scan: Dict):
        """Compare directory scans and generate events."""
        all_files = set(old_scan.keys()) | set(new_scan.keys())
        
        for file_path in all_files:
            old_info = old_scan.get(file_path)
            new_info = new_scan.get(file_path)
            
            if old_info and not new_info:
                # File deleted
                event = FileChangeEvent(
                    tenant_id=tenant_id,
                    file_path=file_path,
                    change_type=ChangeType.DELETED,
                    timestamp=datetime.now(timezone.utc)
                )
                self.event_queue.put(event)
                
            elif not old_info and new_info:
                # File created
                event = FileChangeEvent(
                    tenant_id=tenant_id,
                    file_path=file_path,
                    change_type=ChangeType.CREATED,
                    timestamp=datetime.now(timezone.utc),
                    file_size=new_info['size']
                )
                self.event_queue.put(event)
                
            elif old_info and new_info and old_info['mtime'] != new_info['mtime']:
                # File modified
                event = FileChangeEvent(
                    tenant_id=tenant_id,
                    file_path=file_path,
                    change_type=ChangeType.MODIFIED,
                    timestamp=datetime.now(timezone.utc),
                    file_size=new_info['size']
                )
                self.event_queue.put(event)
    
    def get_status(self) -> Dict[str, Any]:
        """Get monitoring service status."""
        return {
            'is_running': self.is_running,
            'monitored_tenants': list(self.observers.keys()),
            'watchdog_available': WATCHDOG_AVAILABLE,
            'queue_size': self.event_queue.qsize(),
            'config': {
                'include_extensions': list(self.config.include_extensions),
                'exclude_patterns': list(self.config.exclude_patterns),
                'recursive': self.config.recursive,
                'check_interval': self.config.check_interval,
                'debounce_time': self.config.debounce_time
            }
        }


# Utility functions
def create_default_monitor() -> FileMonitor:
    """Create file monitor with default configuration."""
    return FileMonitor(MonitoringConfig())


def create_optimized_monitor(
    include_extensions: Set[str] = None,
    debounce_time: float = 1.0
) -> FileMonitor:
    """Create optimized file monitor for document processing."""
    config = MonitoringConfig(
        include_extensions=include_extensions,
        debounce_time=debounce_time,
        calculate_hash=True,
        track_file_size=True
    )
    return FileMonitor(config) 