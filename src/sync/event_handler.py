"""
Event handling system for file system monitoring.

This module provides event processing, tenant-specific routing,
and prioritized event handling capabilities.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any, Set
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import defaultdict, deque
import threading
from contextlib import asynccontextmanager

from .file_watcher import FileEvent, FileEventType

logger = logging.getLogger(__name__)

class EventPriority(IntEnum):
    """Event priority levels (higher number = higher priority)."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class PrioritizedEvent:
    """Event with priority information."""
    event: FileEvent
    priority: EventPriority = EventPriority.NORMAL
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    attempts: int = 0
    max_attempts: int = 3
    
    def __lt__(self, other: 'PrioritizedEvent') -> bool:
        """Compare events for priority queue ordering."""
        if self.priority != other.priority:
            return self.priority > other.priority  # Higher priority first
        return self.created_at < other.created_at  # Older first if same priority

class EventProcessor:
    """Processes file system events with configurable handlers."""
    
    def __init__(self, max_concurrent_events: int = 10):
        self.event_handlers: Dict[FileEventType, List[Callable[[FileEvent], None]]] = defaultdict(list)
        self.global_handlers: List[Callable[[FileEvent], None]] = []
        self.max_concurrent_events = max_concurrent_events
        self.semaphore = asyncio.Semaphore(max_concurrent_events)
        self.stats = {
            'events_processed': 0,
            'events_failed': 0,
            'events_by_type': defaultdict(int),
            'processing_time_total': 0.0,
            'last_processed': None
        }
    
    def add_handler(
        self, 
        event_type: Optional[FileEventType], 
        handler: Callable[[FileEvent], None]
    ) -> None:
        """Add event handler for specific event type or all events."""
        if event_type is None:
            self.global_handlers.append(handler)
        else:
            self.event_handlers[event_type].append(handler)
        
        logger.debug(f"Added handler for {event_type or 'all'} events")
    
    def remove_handler(
        self, 
        event_type: Optional[FileEventType], 
        handler: Callable[[FileEvent], None]
    ) -> bool:
        """Remove event handler."""
        try:
            if event_type is None:
                self.global_handlers.remove(handler)
            else:
                self.event_handlers[event_type].remove(handler)
            logger.debug(f"Removed handler for {event_type or 'all'} events")
            return True
        except ValueError:
            logger.warning(f"Handler not found for {event_type or 'all'} events")
            return False
    
    async def process_event(self, event: FileEvent) -> bool:
        """Process a single event through all applicable handlers."""
        async with self.semaphore:
            start_time = datetime.now(timezone.utc)
            success = True
            
            try:
                # Get handlers for this event type
                handlers = []
                handlers.extend(self.global_handlers)
                handlers.extend(self.event_handlers.get(event.event_type, []))
                
                if not handlers:
                    logger.debug(f"No handlers registered for {event.event_type.value} events")
                    return True
                
                # Process through all handlers
                for handler in handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(event)
                        else:
                            handler(event)
                    except Exception as e:
                        logger.error(f"Handler failed for event {event.file_path}: {e}")
                        success = False
                
                # Update statistics
                self.stats['events_processed'] += 1
                self.stats['events_by_type'][event.event_type.value] += 1
                self.stats['last_processed'] = start_time
                
            except Exception as e:
                logger.error(f"Error processing event {event.file_path}: {e}")
                self.stats['events_failed'] += 1
                success = False
            
            finally:
                # Update processing time
                processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                self.stats['processing_time_total'] += processing_time
            
            return success
    
    def get_stats(self) -> Dict[str, Any]:
        """Get event processing statistics."""
        avg_processing_time = 0.0
        if self.stats['events_processed'] > 0:
            avg_processing_time = self.stats['processing_time_total'] / self.stats['events_processed']
        
        return {
            **self.stats,
            'average_processing_time': avg_processing_time,
            'handlers_registered': {
                'global': len(self.global_handlers),
                'by_type': {
                    event_type.value: len(handlers)
                    for event_type, handlers in self.event_handlers.items()
                }
            }
        }

class TenantEventRouter:
    """Routes events to tenant-specific processors."""
    
    def __init__(self):
        self.tenant_processors: Dict[str, EventProcessor] = {}
        self.tenant_filters: Dict[str, Callable[[FileEvent], bool]] = {}
        self.global_processor = EventProcessor()
        self.routing_stats = defaultdict(int)
    
    def add_tenant_processor(
        self, 
        tenant_id: str, 
        processor: Optional[EventProcessor] = None,
        event_filter: Optional[Callable[[FileEvent], bool]] = None
    ) -> EventProcessor:
        """Add or get processor for a specific tenant."""
        if processor is None:
            processor = EventProcessor()
        
        self.tenant_processors[tenant_id] = processor
        
        if event_filter:
            self.tenant_filters[tenant_id] = event_filter
        
        logger.info(f"Added event processor for tenant {tenant_id}")
        return processor
    
    def remove_tenant_processor(self, tenant_id: str) -> bool:
        """Remove processor for a tenant."""
        if tenant_id not in self.tenant_processors:
            logger.warning(f"No processor found for tenant {tenant_id}")
            return False
        
        del self.tenant_processors[tenant_id]
        if tenant_id in self.tenant_filters:
            del self.tenant_filters[tenant_id]
        
        logger.info(f"Removed event processor for tenant {tenant_id}")
        return True
    
    def get_tenant_processor(self, tenant_id: str) -> Optional[EventProcessor]:
        """Get processor for a specific tenant."""
        return self.tenant_processors.get(tenant_id)
    
    def add_global_handler(
        self, 
        event_type: Optional[FileEventType], 
        handler: Callable[[FileEvent], None]
    ) -> None:
        """Add handler to global processor for all tenants."""
        self.global_processor.add_handler(event_type, handler)
    
    async def route_event(self, event: FileEvent) -> bool:
        """Route event to appropriate processor(s)."""
        success = True
        
        # Route to tenant-specific processor
        if event.tenant_id in self.tenant_processors:
            tenant_filter = self.tenant_filters.get(event.tenant_id)
            
            # Apply tenant filter if exists
            if tenant_filter is None or tenant_filter(event):
                processor = self.tenant_processors[event.tenant_id]
                tenant_success = await processor.process_event(event)
                if not tenant_success:
                    success = False
                
                self.routing_stats[f"tenant_{event.tenant_id}"] += 1
            else:
                logger.debug(f"Event filtered out for tenant {event.tenant_id}")
                self.routing_stats[f"filtered_{event.tenant_id}"] += 1
        else:
            logger.warning(f"No processor found for tenant {event.tenant_id}")
            self.routing_stats[f"no_processor_{event.tenant_id}"] += 1
        
        # Also route to global processor
        global_success = await self.global_processor.process_event(event)
        if not global_success:
            success = False
        
        self.routing_stats["global"] += 1
        
        return success
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all processors."""
        stats = {
            'global': self.global_processor.get_stats(),
            'tenants': {},
            'routing': dict(self.routing_stats)
        }
        
        for tenant_id, processor in self.tenant_processors.items():
            stats['tenants'][tenant_id] = processor.get_stats()
        
        return stats

class FileEventHandler:
    """Main file event handler with priority queue and tenant routing."""
    
    def __init__(self, max_queue_size: int = 1000):
        self.event_queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_queue_size)
        self.router = TenantEventRouter()
        self.is_running = False
        self.worker_tasks: List[asyncio.Task] = []
        self.num_workers = 3
        self.stats = {
            'queued_events': 0,
            'processed_events': 0,
            'failed_events': 0,
            'queue_full_errors': 0,
            'start_time': None
        }
        self._lock = threading.Lock()
    
    def calculate_priority(self, event: FileEvent) -> EventPriority:
        """Calculate event priority based on event characteristics."""
        # Critical priority for deletions
        if event.event_type == FileEventType.DELETED:
            return EventPriority.CRITICAL
        
        # High priority for new files
        if event.event_type == FileEventType.CREATED:
            return EventPriority.HIGH
        
        # High priority for large files or important file types
        if event.file_size and event.file_size > 10 * 1024 * 1024:  # > 10MB
            return EventPriority.HIGH
        
        file_ext = event.file_path.lower().split('.')[-1] if '.' in event.file_path else ''
        if file_ext in {'pdf', 'docx', 'pptx'}:
            return EventPriority.HIGH
        
        # Normal priority for modifications and other events
        return EventPriority.NORMAL
    
    async def enqueue_event(self, event: FileEvent) -> bool:
        """Add event to processing queue."""
        try:
            priority = self.calculate_priority(event)
            prioritized_event = PrioritizedEvent(event=event, priority=priority)
            
            # Try to add to queue (non-blocking)
            self.event_queue.put_nowait(prioritized_event)
            self.stats['queued_events'] += 1
            
            logger.debug(f"Queued {event.event_type.value} event for {event.file_path} with priority {priority.name}")
            return True
            
        except asyncio.QueueFull:
            self.stats['queue_full_errors'] += 1
            logger.error(f"Event queue full, dropping event for {event.file_path}")
            return False
        except Exception as e:
            logger.error(f"Failed to enqueue event for {event.file_path}: {e}")
            return False
    
    async def _event_worker(self, worker_id: int) -> None:
        """Worker coroutine for processing events."""
        logger.info(f"Event worker {worker_id} started")
        
        while self.is_running:
            try:
                # Get event from queue with timeout
                prioritized_event = await asyncio.wait_for(
                    self.event_queue.get(), 
                    timeout=1.0
                )
                
                # Process the event
                success = await self.router.route_event(prioritized_event.event)
                
                if success:
                    self.stats['processed_events'] += 1
                    logger.debug(f"Worker {worker_id} processed event for {prioritized_event.event.file_path}")
                else:
                    prioritized_event.attempts += 1
                    
                    # Retry if under max attempts
                    if prioritized_event.attempts < prioritized_event.max_attempts:
                        # Re-queue with lower priority
                        prioritized_event.priority = EventPriority.LOW
                        await self.event_queue.put(prioritized_event)
                        logger.warning(f"Re-queued failed event for {prioritized_event.event.file_path} (attempt {prioritized_event.attempts})")
                    else:
                        self.stats['failed_events'] += 1
                        logger.error(f"Event failed after {prioritized_event.max_attempts} attempts: {prioritized_event.event.file_path}")
                
                # Mark task as done
                self.event_queue.task_done()
                
            except asyncio.TimeoutError:
                # Normal timeout, continue loop
                continue
            except Exception as e:
                logger.error(f"Event worker {worker_id} error: {e}")
                # Continue processing other events
                continue
        
        logger.info(f"Event worker {worker_id} stopped")
    
    async def start_processing(self) -> None:
        """Start event processing workers."""
        if self.is_running:
            logger.warning("Event handler is already running")
            return
        
        with self._lock:
            self.is_running = True
            self.stats['start_time'] = datetime.now(timezone.utc)
            
            # Start worker tasks
            self.worker_tasks = []
            for i in range(self.num_workers):
                task = asyncio.create_task(self._event_worker(i))
                self.worker_tasks.append(task)
            
            logger.info(f"Started {self.num_workers} event processing workers")
    
    async def stop_processing(self, timeout: float = 30.0) -> None:
        """Stop event processing workers."""
        if not self.is_running:
            logger.warning("Event handler is not running")
            return
        
        with self._lock:
            self.is_running = False
        
        # Wait for queue to empty
        try:
            await asyncio.wait_for(self.event_queue.join(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for event queue to empty")
        
        # Cancel worker tasks
        for task in self.worker_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        
        self.worker_tasks.clear()
        logger.info("Stopped event processing workers")
    
    def add_tenant_handler(
        self, 
        tenant_id: str, 
        event_type: Optional[FileEventType], 
        handler: Callable[[FileEvent], None]
    ) -> None:
        """Add handler for specific tenant and event type."""
        processor = self.router.add_tenant_processor(tenant_id)
        processor.add_handler(event_type, handler)
    
    def add_global_handler(
        self, 
        event_type: Optional[FileEventType], 
        handler: Callable[[FileEvent], None]
    ) -> None:
        """Add handler for all tenants."""
        self.router.add_global_handler(event_type, handler)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics."""
        current_time = datetime.now(timezone.utc)
        uptime = 0.0
        if self.stats['start_time']:
            uptime = (current_time - self.stats['start_time']).total_seconds()
        
        return {
            'handler': {
                **self.stats,
                'uptime_seconds': uptime,
                'queue_size': self.event_queue.qsize(),
                'is_running': self.is_running,
                'num_workers': len(self.worker_tasks)
            },
            'router': self.router.get_all_stats()
        }
    
    @asynccontextmanager
    async def managed_processing(self):
        """Context manager for event processing."""
        try:
            await self.start_processing()
            yield self
        finally:
            await self.stop_processing()

# Global event handler instance
file_event_handler = FileEventHandler() 