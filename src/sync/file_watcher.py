"""
File system watcher for Enterprise RAG system.

This module provides real-time file system monitoring with event queuing
and batch processing capabilities.
"""

import os
import time
import logging
import asyncio
import threading
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from queue import Queue, Empty
from watchdog.observers import Observer
from watchdog.events import (
    FileSystemEventHandler,
    FileSystemEvent,
    FileCreatedEvent,
    FileModifiedEvent,
    FileDeletedEvent,
    FileMovedEvent
)

from ..config.settings import get_settings
from .sync_state import SyncStateManager, SyncState, SyncError, SyncErrorType

logger = logging.getLogger(__name__)

class FileEventType(Enum):
    """Types of file system events."""
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    MOVED = "moved"
    UNKNOWN = "unknown"

@dataclass
class FileEvent:
    """Represents a file system event."""
    event_type: FileEventType
    src_path: str
    dest_path: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tenant_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class BatchConfig:
    """Configuration for batch processing."""
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        self.max_batch_size = config.get("max_batch_size", 100)
        self.batch_timeout = config.get("batch_timeout", 5.0)  # seconds
        self.max_queue_size = config.get("max_queue_size", 10000)
        self.processing_threads = config.get("processing_threads", 4)
        self.retry_delay = config.get("retry_delay", 1.0)  # seconds
        self.max_retries = config.get("max_retries", 3)

class FileWatcher:
    """Watches file system for changes with event queuing and batch processing."""
    
    def __init__(
        self,
        master_dir: str,
        batch_config: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None
    ):
        """Initialize file watcher.
        
        Args:
            master_dir: Directory to watch
            batch_config: Optional batch processing configuration
            tenant_id: Optional tenant identifier
        """
        self.master_dir = Path(master_dir)
        self.tenant_id = tenant_id
        self.batch_config = BatchConfig(batch_config)
        
        # Initialize components
        self.state_manager = SyncStateManager()
        
        # Event queue
        self.event_queue: Queue[FileEvent] = Queue(maxsize=self.batch_config.max_queue_size)
        
        # File tracking
        self._processed_files: Set[str] = set()
        self._processing_lock = threading.Lock()
        
        # Event handlers
        self._event_handlers: Dict[FileEventType, List[Callable]] = {
            event_type: [] for event_type in FileEventType
        }
        
        # Initialize watchdog
        self._observer = Observer()
        self._event_handler = _FileSystemEventHandler(self)
        self._observer.schedule(
            self._event_handler,
            str(self.master_dir),
            recursive=True
        )
        
        # Processing state
        self._processing = False
        self._processing_thread = None
        
        logger.info(f"Initialized file watcher for {master_dir}")
    
    def start(self):
        """Start file system watching and event processing."""
        if self._processing:
            return
        
        self._processing = True
        
        # Start watchdog observer
        self._observer.start()
        
        # Start processing thread
        self._processing_thread = threading.Thread(
            target=self._process_events,
            daemon=True
        )
        self._processing_thread.start()
        
        logger.info("Started file watcher")
    
    def stop(self):
        """Stop file system watching and event processing."""
        self._processing = False
        
        if self._observer.is_alive():
            self._observer.stop()
            self._observer.join()
        
        if self._processing_thread and self._processing_thread.is_alive():
            self._processing_thread.join(timeout=5.0)
        
        logger.info("Stopped file watcher")
    
    def add_event_handler(
        self,
        event_type: FileEventType,
        handler: Callable[[FileEvent], None]
    ):
        """Add event handler for specific event type.
        
        Args:
            event_type: Type of event to handle
            handler: Handler function
        """
        self._event_handlers[event_type].append(handler)
    
    def queue_event(self, event: FileEvent):
        """Queue a file event for processing.
        
        Args:
            event: File event to queue
        """
        try:
            self.event_queue.put(event, timeout=1.0)
            logger.debug(f"Queued {event.event_type.value} event for {event.src_path}")
        except Exception as e:
            logger.error(f"Failed to queue event: {e}")
            
            # Update sync state
            if self.tenant_id:
                self.state_manager.update_state(
                    tenant_id=self.tenant_id,
                    folder_name=str(self.master_dir),
                    new_state=SyncState.FAILED,
                    error=SyncError(
                        error_type=SyncErrorType.INTERNAL,
                        message=f"Failed to queue event: {e}"
                    )
                )
    
    def _process_events(self):
        """Process queued events in batches."""
        while self._processing:
            try:
                # Initialize new batch
                batch: List[FileEvent] = []
                batch_start = time.time()
                
                # Collect events for batch
                while (
                    len(batch) < self.batch_config.max_batch_size
                    and time.time() - batch_start < self.batch_config.batch_timeout
                ):
                    try:
                        event = self.event_queue.get(timeout=0.1)
                        batch.append(event)
                    except Empty:
                        break
                
                if not batch:
                    continue
                
                # Process batch
                self._process_batch(batch)
                
            except Exception as e:
                logger.error(f"Error processing event batch: {e}")
                
                # Update sync state
                if self.tenant_id:
                    self.state_manager.update_state(
                        tenant_id=self.tenant_id,
                        folder_name=str(self.master_dir),
                        new_state=SyncState.FAILED,
                        error=SyncError(
                            error_type=SyncErrorType.INTERNAL,
                            message=f"Batch processing error: {e}"
                        )
                    )
                
                # Short delay before retrying
                time.sleep(self.batch_config.retry_delay)
    
    def _process_batch(self, batch: List[FileEvent]):
        """Process a batch of events.
        
        Args:
            batch: List of events to process
        """
        logger.debug(f"Processing batch of {len(batch)} events")
        
        # Update sync state
        if self.tenant_id:
            self.state_manager.update_state(
                tenant_id=self.tenant_id,
                folder_name=str(self.master_dir),
                new_state=SyncState.SYNCING
            )
        
        # Group events by type
        events_by_type: Dict[FileEventType, List[FileEvent]] = {
            event_type: [] for event_type in FileEventType
        }
        
        for event in batch:
            events_by_type[event.event_type].append(event)
        
        # Process each event type
        for event_type, events in events_by_type.items():
            if not events:
                continue
            
            # Call handlers for this event type
            for handler in self._event_handlers[event_type]:
                try:
                    for event in events:
                        handler(event)
                except Exception as e:
                    logger.error(
                        f"Error in handler for {event_type.value} events: {e}"
                    )
                    
                    # Update sync state
                    if self.tenant_id:
                        self.state_manager.update_state(
                            tenant_id=self.tenant_id,
                            folder_name=str(self.master_dir),
                            new_state=SyncState.FAILED,
                            error=SyncError(
                                error_type=SyncErrorType.INTERNAL,
                                message=f"Handler error for {event_type.value}: {e}"
                            )
                        )
        
        # Update sync state
        if self.tenant_id:
            self.state_manager.update_state(
                tenant_id=self.tenant_id,
                folder_name=str(self.master_dir),
                new_state=SyncState.IDLE
            )
        
        logger.debug("Completed batch processing")


class _FileSystemEventHandler(FileSystemEventHandler):
    """Internal watchdog event handler."""
    
    def __init__(self, watcher: FileWatcher):
        """Initialize handler.
        
        Args:
            watcher: Parent file watcher
        """
        self.watcher = watcher
    
    def on_created(self, event: FileCreatedEvent):
        """Handle file creation event."""
        if event.is_directory:
            return
        
        self.watcher.queue_event(
            FileEvent(
                event_type=FileEventType.CREATED,
                src_path=event.src_path,
                tenant_id=self.watcher.tenant_id
            )
        )
    
    def on_modified(self, event: FileModifiedEvent):
        """Handle file modification event."""
        if event.is_directory:
            return
        
        self.watcher.queue_event(
            FileEvent(
                event_type=FileEventType.MODIFIED,
                src_path=event.src_path,
                tenant_id=self.watcher.tenant_id
            )
        )
    
    def on_deleted(self, event: FileDeletedEvent):
        """Handle file deletion event."""
        if event.is_directory:
            return
        
        self.watcher.queue_event(
            FileEvent(
                event_type=FileEventType.DELETED,
                src_path=event.src_path,
                tenant_id=self.watcher.tenant_id
            )
        )
    
    def on_moved(self, event: FileMovedEvent):
        """Handle file move event."""
        if event.is_directory:
            return
        
        self.watcher.queue_event(
            FileEvent(
                event_type=FileEventType.MOVED,
                src_path=event.src_path,
                dest_path=event.dest_path,
                tenant_id=self.watcher.tenant_id
            )
        ) 