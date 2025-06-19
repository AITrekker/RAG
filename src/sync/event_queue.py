"""
Event queue system for file operations.

This module provides a robust event queue system for handling file operations
with batching, prioritization, and error handling.
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
from queue import PriorityQueue, Empty
from concurrent.futures import ThreadPoolExecutor

from ..config.settings import get_settings
from .sync_state import SyncStateManager, SyncState, SyncError, SyncErrorType
from .file_watcher import FileEvent, FileEventType

logger = logging.getLogger(__name__)

class EventPriority(Enum):
    """Priority levels for file events."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4

@dataclass(order=True)
class PrioritizedEvent:
    """Event with priority for queue ordering."""
    priority: EventPriority
    event: FileEvent = field(compare=False)
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
        compare=False
    )

class EventQueueConfig:
    """Configuration for event queue processing."""
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        self.max_queue_size = config.get("max_queue_size", 10000)
        self.max_batch_size = config.get("max_batch_size", 100)
        self.batch_timeout = config.get("batch_timeout", 5.0)  # seconds
        self.processing_threads = config.get("processing_threads", 4)
        self.retry_delay = config.get("retry_delay", 1.0)  # seconds
        self.max_retries = config.get("max_retries", 3)
        self.event_timeout = config.get("event_timeout", 60.0)  # seconds

class EventQueue:
    """Manages file operation events with batching and prioritization."""
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None
    ):
        """Initialize event queue.
        
        Args:
            config: Optional configuration dictionary
            tenant_id: Optional tenant identifier
        """
        self.config = EventQueueConfig(config)
        self.tenant_id = tenant_id
        
        # Initialize components
        self.state_manager = SyncStateManager()
        
        # Event queue
        self.queue: PriorityQueue[PrioritizedEvent] = PriorityQueue(
            maxsize=self.config.max_queue_size
        )
        
        # Event handlers
        self._event_handlers: Dict[FileEventType, List[Callable]] = {
            event_type: [] for event_type in FileEventType
        }
        
        # Processing state
        self._processing = False
        self._processing_thread = None
        self._executor = ThreadPoolExecutor(
            max_workers=self.config.processing_threads,
            thread_name_prefix="event_processor"
        )
        
        # Event tracking
        self._processed_events: Set[str] = set()
        self._processing_lock = threading.Lock()
        self._event_retries: Dict[str, int] = {}
        
        logger.info("Initialized event queue")
    
    def start(self):
        """Start event processing."""
        if self._processing:
            return
        
        self._processing = True
        self._processing_thread = threading.Thread(
            target=self._process_events,
            daemon=True
        )
        self._processing_thread.start()
        
        logger.info("Started event processing")
    
    def stop(self):
        """Stop event processing."""
        self._processing = False
        
        if self._processing_thread and self._processing_thread.is_alive():
            self._processing_thread.join(timeout=5.0)
        
        self._executor.shutdown(wait=True)
        
        logger.info("Stopped event processing")
    
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
    
    def queue_event(
        self,
        event: FileEvent,
        priority: EventPriority = EventPriority.NORMAL
    ):
        """Queue a file event for processing.
        
        Args:
            event: File event to queue
            priority: Event priority
        """
        try:
            prioritized_event = PrioritizedEvent(
                priority=priority,
                event=event
            )
            self.queue.put(prioritized_event, timeout=1.0)
            
            logger.debug(
                f"Queued {event.event_type.value} event for {event.src_path} "
                f"with priority {priority.value}"
            )
            
        except Exception as e:
            logger.error(f"Failed to queue event: {e}")
            
            # Update sync state
            if self.tenant_id:
                self.state_manager.update_state(
                    tenant_id=self.tenant_id,
                    folder_name=os.path.dirname(event.src_path),
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
                batch: List[PrioritizedEvent] = []
                batch_start = time.time()
                
                # Collect events for batch
                while (
                    len(batch) < self.config.max_batch_size
                    and time.time() - batch_start < self.config.batch_timeout
                ):
                    try:
                        event = self.queue.get(timeout=0.1)
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
                        folder_name="",  # No specific folder for batch error
                        new_state=SyncState.FAILED,
                        error=SyncError(
                            error_type=SyncErrorType.INTERNAL,
                            message=f"Batch processing error: {e}"
                        )
                    )
                
                # Short delay before retrying
                time.sleep(self.config.retry_delay)
    
    def _process_batch(self, batch: List[PrioritizedEvent]):
        """Process a batch of events.
        
        Args:
            batch: List of events to process
        """
        logger.debug(f"Processing batch of {len(batch)} events")
        
        # Group events by type
        events_by_type: Dict[FileEventType, List[FileEvent]] = {
            event_type: [] for event_type in FileEventType
        }
        
        for prioritized_event in batch:
            event = prioritized_event.event
            events_by_type[event.event_type].append(event)
        
        # Process each event type
        futures = []
        for event_type, events in events_by_type.items():
            if not events:
                continue
            
            # Call handlers for this event type
            for handler in self._event_handlers[event_type]:
                for event in events:
                    future = self._executor.submit(
                        self._handle_event,
                        handler,
                        event
                    )
                    futures.append(future)
        
        # Wait for all handlers to complete
        for future in futures:
            try:
                future.result(timeout=self.config.event_timeout)
            except Exception as e:
                logger.error(f"Event handler failed: {e}")
    
    def _handle_event(
        self,
        handler: Callable[[FileEvent], None],
        event: FileEvent
    ):
        """Handle a single event with retries.
        
        Args:
            handler: Event handler function
            event: File event to handle
        """
        event_key = f"{event.event_type.value}:{event.src_path}"
        retry_count = self._event_retries.get(event_key, 0)
        
        try:
            # Update sync state
            if self.tenant_id:
                self.state_manager.update_state(
                    tenant_id=self.tenant_id,
                    folder_name=os.path.dirname(event.src_path),
                    new_state=SyncState.SYNCING
                )
            
            # Handle event
            handler(event)
            
            # Mark as processed
            with self._processing_lock:
                self._processed_events.add(event_key)
                self._event_retries.pop(event_key, None)
            
            # Update sync state
            if self.tenant_id:
                self.state_manager.update_state(
                    tenant_id=self.tenant_id,
                    folder_name=os.path.dirname(event.src_path),
                    new_state=SyncState.IDLE
                )
            
        except Exception as e:
            logger.error(f"Error handling event {event_key}: {e}")
            
            # Update retry count
            retry_count += 1
            self._event_retries[event_key] = retry_count
            
            # Update sync state
            if self.tenant_id:
                self.state_manager.update_state(
                    tenant_id=self.tenant_id,
                    folder_name=os.path.dirname(event.src_path),
                    new_state=SyncState.FAILED,
                    error=SyncError(
                        error_type=SyncErrorType.INTERNAL,
                        message=f"Handler error: {e}"
                    )
                )
            
            # Requeue if retries remaining
            if retry_count < self.config.max_retries:
                self.queue_event(
                    event,
                    priority=EventPriority.HIGH  # Increase priority for retries
                )
            else:
                logger.error(
                    f"Event {event_key} failed after {retry_count} retries"
                )
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics.
        
        Returns:
            Dictionary of queue statistics
        """
        return {
            "queue_size": self.queue.qsize(),
            "processed_events": len(self._processed_events),
            "failed_events": len(self._event_retries),
            "is_processing": self._processing
        } 