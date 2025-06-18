"""
Sync scheduler system for managing file synchronization operations.

This module provides tenant-aware scheduling, quota management,
and priority-based sync operations.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Set, Callable
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from collections import defaultdict, deque
import threading
from contextlib import asynccontextmanager
import heapq

logger = logging.getLogger(__name__)

class SyncPriority(IntEnum):
    """Sync operation priority levels (higher number = higher priority)."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

class SyncStatus(Enum):
    """Sync operation status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"

@dataclass
class SyncOperation:
    """Represents a sync operation to be scheduled."""
    operation_id: str
    tenant_id: str
    source_folder: str
    operation_type: str  # 'full_sync', 'delta_sync', 'file_sync'
    priority: SyncPriority = SyncPriority.NORMAL
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: SyncStatus = SyncStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)
    estimated_duration: Optional[float] = None  # seconds
    actual_duration: Optional[float] = None  # seconds
    error_message: Optional[str] = None
    
    def __lt__(self, other: 'SyncOperation') -> bool:
        """Compare operations for priority queue ordering."""
        # Higher priority first, then earlier scheduled time
        if self.priority != other.priority:
            return self.priority > other.priority
        return (self.scheduled_at or self.created_at) < (other.scheduled_at or other.created_at)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'operation_id': self.operation_id,
            'tenant_id': self.tenant_id,
            'source_folder': self.source_folder,
            'operation_type': self.operation_type,
            'priority': self.priority.value,
            'created_at': self.created_at.isoformat(),
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status.value,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'metadata': self.metadata,
            'estimated_duration': self.estimated_duration,
            'actual_duration': self.actual_duration,
            'error_message': self.error_message
        }

@dataclass
class TenantQuota:
    """Quota configuration for a tenant."""
    tenant_id: str
    max_concurrent_operations: int = 3
    max_daily_operations: int = 100
    max_hourly_operations: int = 20
    max_folder_operations: int = 10
    priority_boost: int = 0  # Add to operation priority
    allowed_operation_types: Set[str] = field(default_factory=lambda: {
        'full_sync', 'delta_sync', 'file_sync'
    })
    
    # Rate limiting
    min_interval_between_operations: float = 60.0  # seconds
    max_operation_duration: float = 3600.0  # 1 hour max per operation
    
    # Resource limits
    max_memory_usage_mb: float = 1024.0
    max_cpu_usage_percent: float = 50.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'tenant_id': self.tenant_id,
            'max_concurrent_operations': self.max_concurrent_operations,
            'max_daily_operations': self.max_daily_operations,
            'max_hourly_operations': self.max_hourly_operations,
            'max_folder_operations': self.max_folder_operations,
            'priority_boost': self.priority_boost,
            'allowed_operation_types': list(self.allowed_operation_types),
            'min_interval_between_operations': self.min_interval_between_operations,
            'max_operation_duration': self.max_operation_duration,
            'max_memory_usage_mb': self.max_memory_usage_mb,
            'max_cpu_usage_percent': self.max_cpu_usage_percent
        }

class TenantUsageTracker:
    """Tracks usage for quota enforcement."""
    
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.concurrent_operations = 0
        self.daily_operations = 0
        self.hourly_operations = 0
        self.folder_operations: Dict[str, int] = defaultdict(int)
        self.last_operation_time: Optional[datetime] = None
        self.operation_history: deque = deque(maxlen=1000)
        self.current_memory_usage = 0.0
        self.current_cpu_usage = 0.0
        self._lock = threading.Lock()
    
    def can_start_operation(
        self, 
        quota: TenantQuota, 
        operation_type: str, 
        folder: str
    ) -> tuple[bool, str]:
        """Check if operation can start based on quota."""
        with self._lock:
            now = datetime.now(timezone.utc)
            
            # Check operation type allowed
            if operation_type not in quota.allowed_operation_types:
                return False, f"Operation type '{operation_type}' not allowed"
            
            # Check concurrent operations
            if self.concurrent_operations >= quota.max_concurrent_operations:
                return False, f"Max concurrent operations ({quota.max_concurrent_operations}) reached"
            
            # Check daily quota
            if self.daily_operations >= quota.max_daily_operations:
                return False, f"Daily operation limit ({quota.max_daily_operations}) reached"
            
            # Check hourly quota
            if self.hourly_operations >= quota.max_hourly_operations:
                return False, f"Hourly operation limit ({quota.max_hourly_operations}) reached"
            
            # Check folder operations
            if self.folder_operations[folder] >= quota.max_folder_operations:
                return False, f"Folder operation limit ({quota.max_folder_operations}) reached for {folder}"
            
            # Check minimum interval
            if (self.last_operation_time and 
                (now - self.last_operation_time).total_seconds() < quota.min_interval_between_operations):
                return False, f"Minimum interval ({quota.min_interval_between_operations}s) not met"
            
            # Check resource usage
            if self.current_memory_usage > quota.max_memory_usage_mb:
                return False, f"Memory usage ({self.current_memory_usage}MB) exceeds limit"
            
            if self.current_cpu_usage > quota.max_cpu_usage_percent:
                return False, f"CPU usage ({self.current_cpu_usage}%) exceeds limit"
            
            return True, "OK"
    
    def start_operation(self, operation: SyncOperation) -> None:
        """Record operation start."""
        with self._lock:
            self.concurrent_operations += 1
            self.daily_operations += 1
            self.hourly_operations += 1
            self.folder_operations[operation.source_folder] += 1
            self.last_operation_time = datetime.now(timezone.utc)
            
            self.operation_history.append({
                'operation_id': operation.operation_id,
                'started_at': operation.started_at,
                'operation_type': operation.operation_type,
                'folder': operation.source_folder
            })
    
    def complete_operation(self, operation: SyncOperation) -> None:
        """Record operation completion."""
        with self._lock:
            self.concurrent_operations = max(0, self.concurrent_operations - 1)
    
    def reset_hourly_counters(self) -> None:
        """Reset hourly counters (called by scheduler)."""
        with self._lock:
            self.hourly_operations = 0
    
    def reset_daily_counters(self) -> None:
        """Reset daily counters (called by scheduler)."""
        with self._lock:
            self.daily_operations = 0
            self.folder_operations.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        with self._lock:
            return {
                'tenant_id': self.tenant_id,
                'concurrent_operations': self.concurrent_operations,
                'daily_operations': self.daily_operations,
                'hourly_operations': self.hourly_operations,
                'folder_operations': dict(self.folder_operations),
                'last_operation_time': self.last_operation_time.isoformat() if self.last_operation_time else None,
                'total_operations': len(self.operation_history),
                'current_memory_usage': self.current_memory_usage,
                'current_cpu_usage': self.current_cpu_usage
            }

class SyncScheduler:
    """Main sync scheduler with tenant-aware quota management."""
    
    def __init__(self, max_concurrent_operations: int = 10):
        self.operation_queue: List[SyncOperation] = []  # Priority queue
        self.running_operations: Dict[str, SyncOperation] = {}
        self.completed_operations: deque = deque(maxlen=10000)
        
        self.tenant_quotas: Dict[str, TenantQuota] = {}
        self.tenant_usage: Dict[str, TenantUsageTracker] = {}
        
        self.max_concurrent_operations = max_concurrent_operations
        self.is_running = False
        self.scheduler_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        
        self.operation_handlers: Dict[str, Callable] = {}
        self.stats = {
            'operations_scheduled': 0,
            'operations_completed': 0,
            'operations_failed': 0,
            'operations_cancelled': 0,
            'total_processing_time': 0.0
        }
        
        self._lock = threading.Lock()
    
    def set_tenant_quota(self, tenant_id: str, quota: TenantQuota) -> None:
        """Set quota configuration for a tenant."""
        with self._lock:
            self.tenant_quotas[tenant_id] = quota
            if tenant_id not in self.tenant_usage:
                self.tenant_usage[tenant_id] = TenantUsageTracker(tenant_id)
        
        logger.info(f"Set quota for tenant {tenant_id}: {quota.max_concurrent_operations} concurrent operations")
    
    def get_tenant_quota(self, tenant_id: str) -> TenantQuota:
        """Get quota for tenant, creating default if not exists."""
        if tenant_id not in self.tenant_quotas:
            self.set_tenant_quota(tenant_id, TenantQuota(tenant_id=tenant_id))
        return self.tenant_quotas[tenant_id]
    
    def register_operation_handler(self, operation_type: str, handler: Callable) -> None:
        """Register handler for specific operation type."""
        self.operation_handlers[operation_type] = handler
        logger.debug(f"Registered handler for operation type: {operation_type}")
    
    async def schedule_operation(
        self,
        tenant_id: str,
        source_folder: str,
        operation_type: str,
        priority: SyncPriority = SyncPriority.NORMAL,
        scheduled_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Schedule a sync operation."""
        
        # Generate operation ID
        operation_id = f"{tenant_id}_{operation_type}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
        
        # Get quota and check if operation can be scheduled
        quota = self.get_tenant_quota(tenant_id)
        usage = self.tenant_usage.get(tenant_id)
        if not usage:
            usage = TenantUsageTracker(tenant_id)
            self.tenant_usage[tenant_id] = usage
        
        # Apply priority boost from quota
        adjusted_priority = min(SyncPriority.CRITICAL, priority + quota.priority_boost)
        
        # Create operation
        operation = SyncOperation(
            operation_id=operation_id,
            tenant_id=tenant_id,
            source_folder=source_folder,
            operation_type=operation_type,
            priority=adjusted_priority,
            scheduled_at=scheduled_at,
            metadata=metadata or {}
        )
        
        # Add to queue
        with self._lock:
            heapq.heappush(self.operation_queue, operation)
            self.stats['operations_scheduled'] += 1
        
        logger.info(f"Scheduled {operation_type} operation {operation_id} for tenant {tenant_id} with priority {adjusted_priority.name}")
        
        return operation_id
    
    async def cancel_operation(self, operation_id: str) -> bool:
        """Cancel a pending or running operation."""
        with self._lock:
            # Check if it's running
            if operation_id in self.running_operations:
                operation = self.running_operations[operation_id]
                operation.status = SyncStatus.CANCELLED
                operation.completed_at = datetime.now(timezone.utc)
                
                # Move to completed
                del self.running_operations[operation_id]
                self.completed_operations.append(operation)
                self.stats['operations_cancelled'] += 1
                
                # Update usage
                if operation.tenant_id in self.tenant_usage:
                    self.tenant_usage[operation.tenant_id].complete_operation(operation)
                
                logger.info(f"Cancelled running operation {operation_id}")
                return True
            
            # Check if it's in queue
            for i, op in enumerate(self.operation_queue):
                if op.operation_id == operation_id:
                    op.status = SyncStatus.CANCELLED
                    op.completed_at = datetime.now(timezone.utc)
                    
                    # Remove from queue and add to completed
                    self.operation_queue.pop(i)
                    heapq.heapify(self.operation_queue)
                    self.completed_operations.append(op)
                    self.stats['operations_cancelled'] += 1
                    
                    logger.info(f"Cancelled queued operation {operation_id}")
                    return True
        
        logger.warning(f"Operation {operation_id} not found for cancellation")
        return False
    
    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        logger.info("Sync scheduler started")
        
        while self.is_running:
            try:
                await self._process_queue()
                await asyncio.sleep(1.0)  # Check every second
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(5.0)
        
        logger.info("Sync scheduler stopped")
    
    async def _process_queue(self) -> None:
        """Process operations from the queue."""
        if not self.operation_queue:
            return
        
        # Check if we can start more operations
        if len(self.running_operations) >= self.max_concurrent_operations:
            return
        
        with self._lock:
            if not self.operation_queue:
                return
            
            # Get highest priority operation
            operation = heapq.heappop(self.operation_queue)
        
        # Check if operation should run now
        now = datetime.now(timezone.utc)
        if operation.scheduled_at and operation.scheduled_at > now:
            # Put back in queue
            with self._lock:
                heapq.heappush(self.operation_queue, operation)
            return
        
        # Check quota
        quota = self.get_tenant_quota(operation.tenant_id)
        usage = self.tenant_usage[operation.tenant_id]
        
        can_run, reason = usage.can_start_operation(
            quota, 
            operation.operation_type, 
            operation.source_folder
        )
        
        if not can_run:
            logger.debug(f"Operation {operation.operation_id} cannot run: {reason}")
            # Put back in queue with delay
            operation.scheduled_at = now + timedelta(seconds=30)
            with self._lock:
                heapq.heappush(self.operation_queue, operation)
            return
        
        # Start operation
        await self._start_operation(operation)
    
    async def _start_operation(self, operation: SyncOperation) -> None:
        """Start executing an operation."""
        operation.status = SyncStatus.RUNNING
        operation.started_at = datetime.now(timezone.utc)
        
        with self._lock:
            self.running_operations[operation.operation_id] = operation
        
        # Update usage tracking
        self.tenant_usage[operation.tenant_id].start_operation(operation)
        
        logger.info(f"Starting operation {operation.operation_id} ({operation.operation_type}) for tenant {operation.tenant_id}")
        
        # Execute operation in background
        asyncio.create_task(self._execute_operation(operation))
    
    async def _execute_operation(self, operation: SyncOperation) -> None:
        """Execute the actual operation."""
        try:
            # Get handler
            handler = self.operation_handlers.get(operation.operation_type)
            if not handler:
                raise ValueError(f"No handler registered for operation type: {operation.operation_type}")
            
            # Execute with timeout
            quota = self.get_tenant_quota(operation.tenant_id)
            timeout = quota.max_operation_duration
            
            await asyncio.wait_for(handler(operation), timeout=timeout)
            
            # Mark as completed
            operation.status = SyncStatus.COMPLETED
            operation.completed_at = datetime.now(timezone.utc)
            operation.actual_duration = (operation.completed_at - operation.started_at).total_seconds()
            
            with self._lock:
                self.stats['operations_completed'] += 1
                self.stats['total_processing_time'] += operation.actual_duration
            
            logger.info(f"Completed operation {operation.operation_id} in {operation.actual_duration:.2f}s")
            
        except asyncio.TimeoutError:
            operation.status = SyncStatus.FAILED
            operation.error_message = f"Operation timed out after {quota.max_operation_duration}s"
            logger.error(f"Operation {operation.operation_id} timed out")
            
        except Exception as e:
            operation.status = SyncStatus.FAILED
            operation.error_message = str(e)
            operation.completed_at = datetime.now(timezone.utc)
            
            with self._lock:
                self.stats['operations_failed'] += 1
            
            logger.error(f"Operation {operation.operation_id} failed: {e}")
            
            # Check if we should retry
            if operation.retry_count < operation.max_retries:
                operation.retry_count += 1
                operation.status = SyncStatus.RETRYING
                operation.scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=5)
                
                with self._lock:
                    heapq.heappush(self.operation_queue, operation)
                
                logger.info(f"Retrying operation {operation.operation_id} (attempt {operation.retry_count + 1})")
        
        finally:
            # Clean up
            with self._lock:
                if operation.operation_id in self.running_operations:
                    del self.running_operations[operation.operation_id]
                
                if operation.status in [SyncStatus.COMPLETED, SyncStatus.FAILED]:
                    self.completed_operations.append(operation)
            
            # Update usage tracking
            self.tenant_usage[operation.tenant_id].complete_operation(operation)
    
    async def _cleanup_loop(self) -> None:
        """Cleanup loop for resetting counters."""
        logger.info("Sync scheduler cleanup started")
        
        last_hour_reset = datetime.now(timezone.utc).hour
        last_day_reset = datetime.now(timezone.utc).date()
        
        while self.is_running:
            try:
                now = datetime.now(timezone.utc)
                
                # Reset hourly counters
                if now.hour != last_hour_reset:
                    for usage in self.tenant_usage.values():
                        usage.reset_hourly_counters()
                    last_hour_reset = now.hour
                    logger.debug("Reset hourly operation counters")
                
                # Reset daily counters
                if now.date() != last_day_reset:
                    for usage in self.tenant_usage.values():
                        usage.reset_daily_counters()
                    last_day_reset = now.date()
                    logger.debug("Reset daily operation counters")
                
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(60)
        
        logger.info("Sync scheduler cleanup stopped")
    
    async def start_scheduler(self) -> None:
        """Start the scheduler."""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        self.is_running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("Sync scheduler started")
    
    async def stop_scheduler(self) -> None:
        """Stop the scheduler."""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return
        
        self.is_running = False
        
        # Cancel running tasks
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Cancel all running operations
        for operation_id in list(self.running_operations.keys()):
            await self.cancel_operation(operation_id)
        
        logger.info("Sync scheduler stopped")
    
    def get_operation_status(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific operation."""
        # Check running operations
        if operation_id in self.running_operations:
            return self.running_operations[operation_id].to_dict()
        
        # Check queue
        for operation in self.operation_queue:
            if operation.operation_id == operation_id:
                return operation.to_dict()
        
        # Check completed operations
        for operation in self.completed_operations:
            if operation.operation_id == operation_id:
                return operation.to_dict()
        
        return None
    
    def get_tenant_operations(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get all operations for a tenant."""
        operations = []
        
        # Running operations
        for operation in self.running_operations.values():
            if operation.tenant_id == tenant_id:
                operations.append(operation.to_dict())
        
        # Queued operations
        for operation in self.operation_queue:
            if operation.tenant_id == tenant_id:
                operations.append(operation.to_dict())
        
        # Recent completed operations
        for operation in self.completed_operations:
            if operation.tenant_id == tenant_id:
                operations.append(operation.to_dict())
        
        return sorted(operations, key=lambda x: x['created_at'], reverse=True)
    
    def get_scheduler_stats(self) -> Dict[str, Any]:
        """Get comprehensive scheduler statistics."""
        with self._lock:
            return {
                'scheduler': {
                    **self.stats,
                    'is_running': self.is_running,
                    'queued_operations': len(self.operation_queue),
                    'running_operations': len(self.running_operations),
                    'completed_operations': len(self.completed_operations),
                    'max_concurrent_operations': self.max_concurrent_operations
                },
                'tenants': {
                    tenant_id: {
                        'quota': quota.to_dict(),
                        'usage': self.tenant_usage[tenant_id].get_stats()
                    }
                    for tenant_id, quota in self.tenant_quotas.items()
                }
            }
    
    @asynccontextmanager
    async def managed_scheduler(self):
        """Context manager for scheduler lifecycle."""
        try:
            await self.start_scheduler()
            yield self
        finally:
            await self.stop_scheduler()

# Global sync scheduler instance
sync_scheduler = SyncScheduler() 