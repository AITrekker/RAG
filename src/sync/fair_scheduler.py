"""
Fair scheduling system for resource allocation.

This module provides round-robin scheduling, priority-based scheduling,
and burst handling for multi-tenant resource allocation.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Set, Callable, Deque
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from collections import defaultdict, deque
import heapq
import threading
from contextlib import asynccontextmanager

from .resource_manager import ResourceType, ResourceAllocationSystem, ResourceLimits

logger = logging.getLogger(__name__)

class SchedulingPolicy(Enum):
    """Scheduling policy types."""
    ROUND_ROBIN = "round_robin"
    PRIORITY = "priority"
    FAIR_SHARE = "fair_share"
    BURST_AWARE = "burst_aware"

class TaskPriority(IntEnum):
    """Task priority levels (higher number = higher priority)."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    EMERGENCY = 5

class TaskStatus(Enum):
    """Task execution status."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING_RESOURCES = "waiting_resources"

@dataclass
class ScheduledTask:
    """Represents a task to be scheduled."""
    task_id: str
    tenant_id: str
    priority: TaskPriority = TaskPriority.NORMAL
    resource_requirements: Dict[ResourceType, float] = field(default_factory=dict)
    estimated_duration: Optional[float] = None  # seconds
    max_duration: Optional[float] = None  # seconds
    deadline: Optional[datetime] = None
    submitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: TaskStatus = TaskStatus.QUEUED
    
    # Execution context
    task_function: Optional[Callable] = None
    task_args: tuple = field(default_factory=tuple)
    task_kwargs: dict = field(default_factory=dict)
    
    # Scheduling metadata
    retry_count: int = 0
    max_retries: int = 3
    last_scheduled_at: Optional[datetime] = None
    execution_time: Optional[float] = None
    
    def __lt__(self, other: 'ScheduledTask') -> bool:
        """Compare tasks for priority queue ordering."""
        # Higher priority first
        if self.priority != other.priority:
            return self.priority > other.priority
        
        # Earlier deadline first
        if self.deadline and other.deadline:
            return self.deadline < other.deadline
        elif self.deadline:
            return True
        elif other.deadline:
            return False
        
        # Earlier submission first
        return self.submitted_at < other.submitted_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'task_id': self.task_id,
            'tenant_id': self.tenant_id,
            'priority': self.priority.value,
            'resource_requirements': {rt.value: amount for rt, amount in self.resource_requirements.items()},
            'estimated_duration': self.estimated_duration,
            'max_duration': self.max_duration,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'submitted_at': self.submitted_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status.value,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'execution_time': self.execution_time
        }

@dataclass
class TenantQuota:
    """Resource quota and scheduling configuration for a tenant."""
    tenant_id: str
    
    # Resource quotas
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    
    # Scheduling configuration
    max_concurrent_tasks: int = 5
    max_queued_tasks: int = 100
    default_priority: TaskPriority = TaskPriority.NORMAL
    priority_boost: int = 0
    
    # Fair share configuration
    fair_share_weight: float = 1.0  # Relative weight for fair scheduling
    burst_capacity: float = 2.0  # Multiplier for burst allowance
    burst_duration: float = 300.0  # Max burst duration in seconds
    
    # Rate limiting
    max_tasks_per_minute: int = 10
    max_tasks_per_hour: int = 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'tenant_id': self.tenant_id,
            'resource_limits': self.resource_limits.to_dict(),
            'max_concurrent_tasks': self.max_concurrent_tasks,
            'max_queued_tasks': self.max_queued_tasks,
            'default_priority': self.default_priority.value,
            'priority_boost': self.priority_boost,
            'fair_share_weight': self.fair_share_weight,
            'burst_capacity': self.burst_capacity,
            'burst_duration': self.burst_duration,
            'max_tasks_per_minute': self.max_tasks_per_minute,
            'max_tasks_per_hour': self.max_tasks_per_hour
        }

class TenantUsageTracker:
    """Tracks resource usage and scheduling metrics for a tenant."""
    
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        
        # Current state
        self.running_tasks = 0
        self.queued_tasks = 0
        self.resource_usage: Dict[ResourceType, float] = defaultdict(float)
        
        # Rate limiting
        self.tasks_this_minute = 0
        self.tasks_this_hour = 0
        self.last_minute_reset = datetime.now(timezone.utc)
        self.last_hour_reset = datetime.now(timezone.utc)
        
        # Burst tracking
        self.burst_start_time: Optional[datetime] = None
        self.burst_resource_usage: Dict[ResourceType, float] = defaultdict(float)
        
        # Scheduling history
        self.task_history: Deque[ScheduledTask] = deque(maxlen=1000)
        self.execution_times: Deque[float] = deque(maxlen=100)
        
        # Fair share tracking
        self.allocated_time: float = 0.0
        self.fair_share_deficit: float = 0.0
        self.last_scheduled_time: Optional[datetime] = None
        
        self._lock = threading.Lock()
    
    def update_rate_limits(self) -> None:
        """Update rate limiting counters."""
        now = datetime.now(timezone.utc)
        
        with self._lock:
            # Reset minute counter
            if (now - self.last_minute_reset).total_seconds() >= 60:
                self.tasks_this_minute = 0
                self.last_minute_reset = now
            
            # Reset hour counter
            if (now - self.last_hour_reset).total_seconds() >= 3600:
                self.tasks_this_hour = 0
                self.last_hour_reset = now
    
    def can_schedule_task(self, quota: TenantQuota) -> tuple[bool, str]:
        """Check if a task can be scheduled for this tenant."""
        self.update_rate_limits()
        
        with self._lock:
            # Check concurrent task limit
            if self.running_tasks >= quota.max_concurrent_tasks:
                return False, f"Max concurrent tasks ({quota.max_concurrent_tasks}) reached"
            
            # Check queue limit
            if self.queued_tasks >= quota.max_queued_tasks:
                return False, f"Max queued tasks ({quota.max_queued_tasks}) reached"
            
            # Check rate limits
            if self.tasks_this_minute >= quota.max_tasks_per_minute:
                return False, f"Rate limit exceeded: {quota.max_tasks_per_minute} tasks/minute"
            
            if self.tasks_this_hour >= quota.max_tasks_per_hour:
                return False, f"Rate limit exceeded: {quota.max_tasks_per_hour} tasks/hour"
            
            return True, "OK"
    
    def task_started(self, task: ScheduledTask) -> None:
        """Record task start."""
        with self._lock:
            self.running_tasks += 1
            self.queued_tasks = max(0, self.queued_tasks - 1)
            self.tasks_this_minute += 1
            self.tasks_this_hour += 1
            
            # Update resource usage
            for resource_type, amount in task.resource_requirements.items():
                self.resource_usage[resource_type] += amount
    
    def task_completed(self, task: ScheduledTask) -> None:
        """Record task completion."""
        with self._lock:
            self.running_tasks = max(0, self.running_tasks - 1)
            
            # Update resource usage
            for resource_type, amount in task.resource_requirements.items():
                self.resource_usage[resource_type] = max(0, self.resource_usage[resource_type] - amount)
            
            # Add to history
            self.task_history.append(task)
            
            if task.execution_time:
                self.execution_times.append(task.execution_time)
                self.allocated_time += task.execution_time
    
    def task_queued(self) -> None:
        """Record task queued."""
        with self._lock:
            self.queued_tasks += 1
    
    def task_dequeued(self) -> None:
        """Record task removed from queue."""
        with self._lock:
            self.queued_tasks = max(0, self.queued_tasks - 1)
    
    def get_average_execution_time(self) -> float:
        """Get average execution time for tasks."""
        with self._lock:
            if self.execution_times:
                return sum(self.execution_times) / len(self.execution_times)
            return 0.0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive usage statistics."""
        with self._lock:
            return {
                'tenant_id': self.tenant_id,
                'running_tasks': self.running_tasks,
                'queued_tasks': self.queued_tasks,
                'resource_usage': dict(self.resource_usage),
                'tasks_this_minute': self.tasks_this_minute,
                'tasks_this_hour': self.tasks_this_hour,
                'total_tasks_completed': len(self.task_history),
                'average_execution_time': self.get_average_execution_time(),
                'allocated_time': self.allocated_time,
                'fair_share_deficit': self.fair_share_deficit,
                'last_scheduled_time': self.last_scheduled_time.isoformat() if self.last_scheduled_time else None
            }

class RoundRobinScheduler:
    """Round-robin scheduler for fair task distribution."""
    
    def __init__(self):
        self.tenant_queues: Dict[str, deque] = defaultdict(deque)
        self.tenant_order: List[str] = []
        self.current_tenant_index = 0
        self._lock = threading.Lock()
    
    def add_task(self, task: ScheduledTask) -> None:
        """Add task to tenant queue."""
        with self._lock:
            self.tenant_queues[task.tenant_id].append(task)
            
            # Add tenant to rotation if not present
            if task.tenant_id not in self.tenant_order:
                self.tenant_order.append(task.tenant_id)
    
    def get_next_task(self) -> Optional[ScheduledTask]:
        """Get next task using round-robin."""
        with self._lock:
            if not self.tenant_order:
                return None
            
            # Try to find a task from current tenant and subsequent tenants
            for _ in range(len(self.tenant_order)):
                if self.current_tenant_index >= len(self.tenant_order):
                    self.current_tenant_index = 0
                
                tenant_id = self.tenant_order[self.current_tenant_index]
                queue = self.tenant_queues[tenant_id]
                
                if queue:
                    task = queue.popleft()
                    self.current_tenant_index = (self.current_tenant_index + 1) % len(self.tenant_order)
                    return task
                
                self.current_tenant_index = (self.current_tenant_index + 1) % len(self.tenant_order)
            
            return None
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        with self._lock:
            return {
                'tenant_queues': {
                    tenant_id: len(queue) 
                    for tenant_id, queue in self.tenant_queues.items()
                },
                'total_queued': sum(len(queue) for queue in self.tenant_queues.values()),
                'active_tenants': len(self.tenant_order)
            }

class PriorityScheduler:
    """Priority-based scheduler with fair share consideration."""
    
    def __init__(self):
        self.priority_queues: Dict[TaskPriority, List[ScheduledTask]] = {
            priority: [] for priority in TaskPriority
        }
        self._lock = threading.Lock()
    
    def add_task(self, task: ScheduledTask) -> None:
        """Add task to priority queue."""
        with self._lock:
            heapq.heappush(self.priority_queues[task.priority], task)
    
    def get_next_task(self) -> Optional[ScheduledTask]:
        """Get next task by priority."""
        with self._lock:
            # Check queues from highest to lowest priority
            for priority in reversed(TaskPriority):
                queue = self.priority_queues[priority]
                if queue:
                    return heapq.heappop(queue)
            
            return None
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        with self._lock:
            return {
                'priority_queues': {
                    priority.name: len(queue) 
                    for priority, queue in self.priority_queues.items()
                },
                'total_queued': sum(len(queue) for queue in self.priority_queues.values())
            }

class FairShareScheduler:
    """Fair share scheduler with deficit tracking."""
    
    def __init__(self):
        self.task_queue: List[ScheduledTask] = []
        self.tenant_weights: Dict[str, float] = defaultdict(lambda: 1.0)
        self.tenant_deficits: Dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()
    
    def set_tenant_weight(self, tenant_id: str, weight: float) -> None:
        """Set fair share weight for tenant."""
        with self._lock:
            self.tenant_weights[tenant_id] = weight
    
    def add_task(self, task: ScheduledTask) -> None:
        """Add task to fair share queue."""
        with self._lock:
            # Calculate effective priority based on fair share deficit
            tenant_weight = self.tenant_weights[task.tenant_id]
            deficit = self.tenant_deficits[task.tenant_id]
            
            # Higher deficit means higher effective priority
            effective_priority = task.priority.value + (deficit * tenant_weight)
            task.metadata = getattr(task, 'metadata', {})
            task.metadata['effective_priority'] = effective_priority
            
            self.task_queue.append(task)
            self.task_queue.sort(key=lambda t: t.metadata.get('effective_priority', 0), reverse=True)
    
    def get_next_task(self) -> Optional[ScheduledTask]:
        """Get next task based on fair share."""
        with self._lock:
            if self.task_queue:
                return self.task_queue.pop(0)
            return None
    
    def update_deficit(self, tenant_id: str, allocated_time: float, fair_share_time: float) -> None:
        """Update fair share deficit for tenant."""
        with self._lock:
            # Deficit increases when tenant gets less than fair share
            self.tenant_deficits[tenant_id] += fair_share_time - allocated_time
            
            # Prevent deficit from going too negative (over-allocation)
            self.tenant_deficits[tenant_id] = max(self.tenant_deficits[tenant_id], -fair_share_time)
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        with self._lock:
            return {
                'total_queued': len(self.task_queue),
                'tenant_deficits': dict(self.tenant_deficits),
                'tenant_weights': dict(self.tenant_weights)
            }

class FairScheduler:
    """Main fair scheduling system integrating multiple scheduling policies."""
    
    def __init__(self, resource_allocator: ResourceAllocationSystem):
        self.resource_allocator = resource_allocator
        
        # Schedulers
        self.round_robin = RoundRobinScheduler()
        self.priority = PriorityScheduler()
        self.fair_share = FairShareScheduler()
        
        # Configuration
        self.scheduling_policy = SchedulingPolicy.ROUND_ROBIN
        self.max_concurrent_tasks = 20
        
        # Tenant management
        self.tenant_quotas: Dict[str, TenantQuota] = {}
        self.tenant_usage: Dict[str, TenantUsageTracker] = {}
        
        # Task management
        self.running_tasks: Dict[str, ScheduledTask] = {}
        self.completed_tasks: deque = deque(maxlen=10000)
        
        # Background processing
        self.is_running = False
        self.scheduler_task: Optional[asyncio.Task] = None
        self.monitoring_task: Optional[asyncio.Task] = None
        
        self._lock = threading.Lock()
    
    def set_scheduling_policy(self, policy: SchedulingPolicy) -> None:
        """Set the scheduling policy."""
        self.scheduling_policy = policy
        logger.info(f"Set scheduling policy to {policy.value}")
    
    def set_tenant_quota(self, tenant_id: str, quota: TenantQuota) -> None:
        """Set quota for a tenant."""
        with self._lock:
            self.tenant_quotas[tenant_id] = quota
            
            if tenant_id not in self.tenant_usage:
                self.tenant_usage[tenant_id] = TenantUsageTracker(tenant_id)
            
            # Set fair share weight
            self.fair_share.set_tenant_weight(tenant_id, quota.fair_share_weight)
        
        # Set resource limits in allocator
        self.resource_allocator.set_tenant_limits(tenant_id, quota.resource_limits)
        
        logger.info(f"Set quota for tenant {tenant_id}")
    
    def get_tenant_quota(self, tenant_id: str) -> TenantQuota:
        """Get quota for tenant."""
        return self.tenant_quotas.get(tenant_id, TenantQuota(tenant_id=tenant_id))
    
    async def submit_task(
        self,
        tenant_id: str,
        task_function: Callable,
        resource_requirements: Dict[ResourceType, float],
        priority: TaskPriority = TaskPriority.NORMAL,
        estimated_duration: Optional[float] = None,
        deadline: Optional[datetime] = None,
        *args,
        **kwargs
    ) -> str:
        """Submit a task for scheduling."""
        
        # Generate task ID
        task_id = f"{tenant_id}_task_{int(time.time() * 1000000)}"
        
        # Get tenant quota and usage
        quota = self.get_tenant_quota(tenant_id)
        usage = self.tenant_usage.get(tenant_id)
        if not usage:
            usage = TenantUsageTracker(tenant_id)
            self.tenant_usage[tenant_id] = usage
        
        # Check if task can be scheduled
        can_schedule, reason = usage.can_schedule_task(quota)
        if not can_schedule:
            logger.warning(f"Cannot schedule task for {tenant_id}: {reason}")
            raise ValueError(f"Cannot schedule task: {reason}")
        
        # Apply priority boost
        effective_priority = min(TaskPriority.EMERGENCY, priority + quota.priority_boost)
        
        # Create task
        task = ScheduledTask(
            task_id=task_id,
            tenant_id=tenant_id,
            priority=effective_priority,
            resource_requirements=resource_requirements,
            estimated_duration=estimated_duration,
            deadline=deadline,
            task_function=task_function,
            task_args=args,
            task_kwargs=kwargs
        )
        
        # Add to appropriate scheduler
        if self.scheduling_policy == SchedulingPolicy.ROUND_ROBIN:
            self.round_robin.add_task(task)
        elif self.scheduling_policy == SchedulingPolicy.PRIORITY:
            self.priority.add_task(task)
        elif self.scheduling_policy == SchedulingPolicy.FAIR_SHARE:
            self.fair_share.add_task(task)
        
        # Update usage tracking
        usage.task_queued()
        
        logger.info(f"Submitted task {task_id} for tenant {tenant_id} with priority {effective_priority.name}")
        return task_id
    
    async def _get_next_task(self) -> Optional[ScheduledTask]:
        """Get next task based on current scheduling policy."""
        if self.scheduling_policy == SchedulingPolicy.ROUND_ROBIN:
            return self.round_robin.get_next_task()
        elif self.scheduling_policy == SchedulingPolicy.PRIORITY:
            return self.priority.get_next_task()
        elif self.scheduling_policy == SchedulingPolicy.FAIR_SHARE:
            return self.fair_share.get_next_task()
        
        return None
    
    async def _execute_task(self, task: ScheduledTask) -> None:
        """Execute a scheduled task."""
        start_time = time.time()
        
        try:
            # Update task status
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now(timezone.utc)
            
            # Update usage tracking
            usage = self.tenant_usage[task.tenant_id]
            usage.task_started(task)
            usage.task_dequeued()
            
            # Allocate resources
            async with self.resource_allocator.managed_allocation(
                task.tenant_id,
                task.task_id,
                task.resource_requirements,
                task.max_duration
            ) as allocations:
                
                # Check if all resources were allocated
                if any(alloc is None for alloc in allocations.values()):
                    task.status = TaskStatus.WAITING_RESOURCES
                    logger.warning(f"Task {task.task_id} waiting for resources")
                    return
                
                # Execute task function
                if task.task_function:
                    if asyncio.iscoroutinefunction(task.task_function):
                        await task.task_function(*task.task_args, **task.task_kwargs)
                    else:
                        task.task_function(*task.task_args, **task.task_kwargs)
                
                # Task completed successfully
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now(timezone.utc)
                task.execution_time = time.time() - start_time
                
                logger.info(f"Task {task.task_id} completed in {task.execution_time:.2f}s")
        
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now(timezone.utc)
            task.execution_time = time.time() - start_time
            
            logger.error(f"Task {task.task_id} failed: {e}")
            
            # Retry if possible
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.QUEUED
                
                # Re-add to scheduler
                if self.scheduling_policy == SchedulingPolicy.ROUND_ROBIN:
                    self.round_robin.add_task(task)
                elif self.scheduling_policy == SchedulingPolicy.PRIORITY:
                    self.priority.add_task(task)
                elif self.scheduling_policy == SchedulingPolicy.FAIR_SHARE:
                    self.fair_share.add_task(task)
                
                logger.info(f"Retrying task {task.task_id} (attempt {task.retry_count + 1})")
                return
        
        finally:
            # Update usage tracking
            usage = self.tenant_usage[task.tenant_id]
            usage.task_completed(task)
            
            # Remove from running tasks
            with self._lock:
                if task.task_id in self.running_tasks:
                    del self.running_tasks[task.task_id]
                
                # Add to completed tasks
                self.completed_tasks.append(task)
    
    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        logger.info("Fair scheduler started")
        
        while self.is_running:
            try:
                # Check if we can run more tasks
                if len(self.running_tasks) >= self.max_concurrent_tasks:
                    await asyncio.sleep(1.0)
                    continue
                
                # Get next task
                task = await self._get_next_task()
                if not task:
                    await asyncio.sleep(1.0)
                    continue
                
                # Add to running tasks
                with self._lock:
                    self.running_tasks[task.task_id] = task
                
                # Execute task in background
                asyncio.create_task(self._execute_task(task))
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(5.0)
        
        logger.info("Fair scheduler stopped")
    
    async def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        while self.is_running:
            try:
                # Update fair share deficits
                if self.scheduling_policy == SchedulingPolicy.FAIR_SHARE:
                    await self._update_fair_share_deficits()
                
                # Check for expired tasks
                await self._check_expired_tasks()
                
                await asyncio.sleep(30)  # Monitor every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)
    
    async def _update_fair_share_deficits(self) -> None:
        """Update fair share deficits for all tenants."""
        total_weight = sum(quota.fair_share_weight for quota in self.tenant_quotas.values())
        total_time = sum(usage.allocated_time for usage in self.tenant_usage.values())
        
        if total_weight > 0 and total_time > 0:
            for tenant_id, usage in self.tenant_usage.items():
                quota = self.tenant_quotas.get(tenant_id)
                if quota:
                    fair_share_time = (quota.fair_share_weight / total_weight) * total_time
                    self.fair_share.update_deficit(tenant_id, usage.allocated_time, fair_share_time)
    
    async def _check_expired_tasks(self) -> None:
        """Check for and handle expired tasks."""
        now = datetime.now(timezone.utc)
        expired_tasks = []
        
        with self._lock:
            for task in self.running_tasks.values():
                if (task.deadline and task.deadline <= now) or \
                   (task.max_duration and task.started_at and 
                    (now - task.started_at).total_seconds() > task.max_duration):
                    expired_tasks.append(task.task_id)
        
        for task_id in expired_tasks:
            await self.cancel_task(task_id)
            logger.warning(f"Cancelled expired task {task_id}")
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running or queued task."""
        with self._lock:
            # Check running tasks
            if task_id in self.running_tasks:
                task = self.running_tasks[task_id]
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now(timezone.utc)
                
                # Update usage
                usage = self.tenant_usage[task.tenant_id]
                usage.task_completed(task)
                
                del self.running_tasks[task_id]
                self.completed_tasks.append(task)
                
                logger.info(f"Cancelled running task {task_id}")
                return True
        
        # TODO: Remove from scheduler queues
        logger.warning(f"Task {task_id} not found for cancellation")
        return False
    
    async def start_scheduler(self) -> None:
        """Start the scheduler."""
        if self.is_running:
            return
        
        self.is_running = True
        
        # Start resource allocator cleanup
        await self.resource_allocator.start_cleanup_task()
        
        # Start scheduler tasks
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        logger.info("Fair scheduler started")
    
    async def stop_scheduler(self) -> None:
        """Stop the scheduler."""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Cancel background tasks
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        # Stop resource allocator
        await self.resource_allocator.stop_cleanup_task()
        
        # Cancel running tasks
        with self._lock:
            running_task_ids = list(self.running_tasks.keys())
        
        for task_id in running_task_ids:
            await self.cancel_task(task_id)
        
        logger.info("Fair scheduler stopped")
    
    def get_scheduler_stats(self) -> Dict[str, Any]:
        """Get comprehensive scheduler statistics."""
        with self._lock:
            running_count = len(self.running_tasks)
            completed_count = len(self.completed_tasks)
        
        # Get queue stats
        if self.scheduling_policy == SchedulingPolicy.ROUND_ROBIN:
            queue_stats = self.round_robin.get_queue_stats()
        elif self.scheduling_policy == SchedulingPolicy.PRIORITY:
            queue_stats = self.priority.get_queue_stats()
        elif self.scheduling_policy == SchedulingPolicy.FAIR_SHARE:
            queue_stats = self.fair_share.get_queue_stats()
        else:
            queue_stats = {}
        
        return {
            'scheduling_policy': self.scheduling_policy.value,
            'is_running': self.is_running,
            'running_tasks': running_count,
            'completed_tasks': completed_count,
            'max_concurrent_tasks': self.max_concurrent_tasks,
            'queue_stats': queue_stats,
            'tenant_stats': {
                tenant_id: usage.get_stats()
                for tenant_id, usage in self.tenant_usage.items()
            },
            'resource_status': self.resource_allocator.get_system_status()
        }
    
    @asynccontextmanager
    async def managed_scheduler(self):
        """Context manager for scheduler lifecycle."""
        try:
            await self.start_scheduler()
            yield self
        finally:
            await self.stop_scheduler()

# Create default fair scheduler instance
from .resource_manager import resource_allocator
fair_scheduler = FairScheduler(resource_allocator) 