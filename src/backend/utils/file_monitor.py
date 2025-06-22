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
                # Return empty string if hash fails, e.g., file deleted during process
                return ""

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
                # Return empty string if hash fails, e.g., file deleted during process
                return ""


class FileMonitor:
    """
    File system monitor using Watchdog to detect and report file changes.
    """
    
    def __init__(self, config: MonitoringConfig = None):
        """Initialize the file monitor."""
        if not WATCHDOG_AVAILABLE:
            raise ImportError("Watchdog library is not installed. Please install it with: pip install watchdog")
        
        self.config = config or MonitoringConfig()
        self.observer = Observer()
        self.monitored_tenants: Dict[str, Dict[str, Any]] = {}  # tenant_id -> {handler, watch}
        self.event_queue = Queue()
        self._callbacks: Dict[str, List[Callable[[FileChangeEvent], None]]] = {}
        self._lock = threading.Lock()
        
        # Event processing thread
        self._processing_thread = threading.Thread(target=self._process_events, daemon=True)
        self._is_running = False

    def add_tenant_monitor(
        self, 
        tenant_id: str, 
        watch_path: str,
        callback: Callable[[FileChangeEvent], None] = None
    ) -> bool:
        """
        Add a new tenant directory to monitor.
        
        Args:
            tenant_id: Unique identifier for the tenant.
            watch_path: The directory path to monitor.
            callback: An optional callback to handle events for this tenant.
            
        Returns:
            True if the monitor was added successfully, False otherwise.
        """
        with self._lock:
            if tenant_id in self.monitored_tenants:
                logger.warning(f"Tenant '{tenant_id}' is already being monitored.")
                return False
            
            if not os.path.isdir(watch_path):
                logger.error(f"Cannot monitor non-existent directory: {watch_path}")
                return False
            
            try:
                event_handler = TenantFileEventHandler(tenant_id, self.config, self.event_queue)
                watch = self.observer.schedule(event_handler, watch_path, recursive=self.config.recursive)
                
                self.monitored_tenants[tenant_id] = {
                    "handler": event_handler,
                    "watch": watch,
                    "path": watch_path
                }
                
                if callback:
                    self.add_event_callback(tenant_id, callback)
                    
                logger.info(f"Started monitoring directory '{watch_path}' for tenant '{tenant_id}'.")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start monitoring for tenant '{tenant_id}': {e}")
                return False

    def remove_tenant_monitor(self, tenant_id: str) -> bool:
        """
        Stop monitoring a tenant directory.
        
        Args:
            tenant_id: The identifier of the tenant to stop monitoring.
            
        Returns:
            True if the monitor was removed successfully, False otherwise.
        """
        with self._lock:
            if tenant_id not in self.monitored_tenants:
                logger.warning(f"Tenant '{tenant_id}' is not being monitored.")
                return False
            
            try:
                watch = self.monitored_tenants[tenant_id]["watch"]
                self.observer.unschedule(watch)
                del self.monitored_tenants[tenant_id]
                
                # Remove associated callbacks
                if tenant_id in self._callbacks:
                    del self._callbacks[tenant_id]
                    
                logger.info(f"Stopped monitoring for tenant '{tenant_id}'.")
                return True
                
            except Exception as e:
                logger.error(f"Failed to stop monitoring for tenant '{tenant_id}': {e}")
                return False

    def add_event_callback(self, tenant_id: str, callback: Callable[[FileChangeEvent], None]):
        """Add a callback for a specific tenant's file change events."""
        with self._lock:
            if tenant_id not in self._callbacks:
                self._callbacks[tenant_id] = []
            self._callbacks[tenant_id].append(callback)

    def start(self):
        """Start the file monitoring service."""
        if self._is_running:
            return
            
        logger.info("Starting file monitor service...")
        self._is_running = True
        self.observer.start()
        self._processing_thread.start()
        logger.info("File monitor service started.")

    def stop(self):
        """Stop the file monitoring service."""
        if not self._is_running:
            return
            
        logger.info("Stopping file monitor service...")
        self._is_running = False
        self.observer.stop()
        self.observer.join()
        
        # Add a sentinel value to unblock the processing thread
        self.event_queue.put(None)
        self._processing_thread.join()
        logger.info("File monitor service stopped.")

    def _process_events(self):
        """Continuously process events from the queue."""
        while self._is_running:
            try:
                event = self.event_queue.get(timeout=1)
                
                if event is None:  # Sentinel value for stopping
                    break
                    
                self._handle_event(event)
                
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing file change event: {e}")

    def _handle_event(self, event: FileChangeEvent):
        """Invoke callbacks for a given event."""
        with self._lock:
            callbacks = self._callbacks.get(event.tenant_id, [])
        
        if not callbacks:
            logger.warning(f"No callback registered for tenant '{event.tenant_id}'. Event ignored.")
            return
            
        for callback in callbacks:
            try:
                # Run callback in a separate thread to avoid blocking
                threading.Thread(target=callback, args=(event,)).start()
            except Exception as e:
                logger.error(f"Error executing callback for tenant '{event.tenant_id}': {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the file monitor."""
        with self._lock:
            return {
                "is_running": self._is_running,
                "observer_is_alive": self.observer.is_alive(),
                "monitored_tenants_count": len(self.monitored_tenants),
                "monitored_paths": {
                    tenant_id: data["path"] 
                    for tenant_id, data in self.monitored_tenants.items()
                },
                "pending_events": self.event_queue.qsize()
            }


def create_default_monitor() -> FileMonitor:
    """Create a default file monitor with standard configuration."""
    return FileMonitor(MonitoringConfig())


def create_optimized_monitor(
    include_extensions: Set[str] = None,
    debounce_time: float = 1.0
) -> FileMonitor:
    """Create a file monitor with optimized settings."""
    config = MonitoringConfig(
        include_extensions=include_extensions,
        debounce_time=debounce_time
    )
    return FileMonitor(config) 