"""
Resource management system for multi-tenant RAG pipeline.

This module provides comprehensive resource allocation, monitoring,
and optimization for GPU, CPU, memory, and disk I/O resources.
"""

import asyncio
import logging
import psutil
import threading
import time
from typing import Dict, List, Optional, Any, Set, Callable, Tuple
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from collections import defaultdict, deque
import json
from contextlib import asynccontextmanager

try:
    import GPUtil
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False
    GPUtil = None

logger = logging.getLogger(__name__)

class ResourceType(Enum):
    """Types of system resources."""
    GPU = "gpu"
    CPU = "cpu"
    MEMORY = "memory"
    DISK_IO = "disk_io"
    NETWORK_IO = "network_io"

class AllocationStatus(Enum):
    """Status of resource allocation."""
    PENDING = "pending"
    ALLOCATED = "allocated"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"

@dataclass
class ResourceLimits:
    """Resource limits for a tenant or operation."""
    max_gpu_memory_mb: float = 1024.0  # MB
    max_gpu_time_seconds: float = 300.0  # 5 minutes
    max_cpu_cores: float = 2.0
    max_cpu_time_seconds: float = 600.0  # 10 minutes
    max_memory_mb: float = 2048.0  # 2GB
    max_disk_io_mbps: float = 100.0  # MB/s
    max_operation_duration: float = 1800.0  # 30 minutes
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'max_gpu_memory_mb': self.max_gpu_memory_mb,
            'max_gpu_time_seconds': self.max_gpu_time_seconds,
            'max_cpu_cores': self.max_cpu_cores,
            'max_cpu_time_seconds': self.max_cpu_time_seconds,
            'max_memory_mb': self.max_memory_mb,
            'max_disk_io_mbps': self.max_disk_io_mbps,
            'max_operation_duration': self.max_operation_duration
        }

@dataclass
class ResourceUsage:
    """Current resource usage tracking."""
    gpu_memory_mb: float = 0.0
    gpu_time_seconds: float = 0.0
    cpu_cores: float = 0.0
    cpu_time_seconds: float = 0.0
    memory_mb: float = 0.0
    disk_io_mbps: float = 0.0
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'gpu_memory_mb': self.gpu_memory_mb,
            'gpu_time_seconds': self.gpu_time_seconds,
            'cpu_cores': self.cpu_cores,
            'cpu_time_seconds': self.cpu_time_seconds,
            'memory_mb': self.memory_mb,
            'disk_io_mbps': self.disk_io_mbps,
            'start_time': self.start_time.isoformat()
        }

@dataclass
class ResourceAllocation:
    """Represents a resource allocation for an operation."""
    allocation_id: str
    tenant_id: str
    operation_id: str
    resource_type: ResourceType
    allocated_amount: float
    allocated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    status: AllocationStatus = AllocationStatus.PENDING
    usage: ResourceUsage = field(default_factory=ResourceUsage)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'allocation_id': self.allocation_id,
            'tenant_id': self.tenant_id,
            'operation_id': self.operation_id,
            'resource_type': self.resource_type.value,
            'allocated_amount': self.allocated_amount,
            'allocated_at': self.allocated_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'status': self.status.value,
            'usage': self.usage.to_dict(),
            'metadata': self.metadata
        }

class GPUManager:
    """Manages GPU resource allocation and monitoring."""
    
    def __init__(self):
        self.available = GPU_AVAILABLE
        self.gpus = []
        self.gpu_allocations: Dict[int, List[ResourceAllocation]] = defaultdict(list)
        self.total_memory = {}
        self._lock = threading.Lock()
        
        if self.available:
            self._initialize_gpus()
    
    def _initialize_gpus(self) -> None:
        """Initialize GPU information."""
        try:
            self.gpus = GPUtil.getGPUs()
            for gpu in self.gpus:
                self.total_memory[gpu.id] = gpu.memoryTotal
            logger.info(f"Initialized {len(self.gpus)} GPUs")
        except Exception as e:
            logger.warning(f"Failed to initialize GPUs: {e}")
            self.available = False
    
    def get_gpu_status(self) -> Dict[str, Any]:
        """Get current GPU status."""
        if not self.available:
            return {'available': False, 'gpus': []}
        
        try:
            gpus = GPUtil.getGPUs()
            gpu_info = []
            
            for gpu in gpus:
                with self._lock:
                    allocations = self.gpu_allocations.get(gpu.id, [])
                    allocated_memory = sum(
                        alloc.allocated_amount 
                        for alloc in allocations 
                        if alloc.status == AllocationStatus.RUNNING
                    )
                
                gpu_info.append({
                    'id': gpu.id,
                    'name': gpu.name,
                    'memory_total': gpu.memoryTotal,
                    'memory_used': gpu.memoryUsed,
                    'memory_free': gpu.memoryFree,
                    'memory_allocated': allocated_memory,
                    'utilization': gpu.load * 100,
                    'temperature': gpu.temperature,
                    'active_allocations': len([
                        a for a in allocations 
                        if a.status == AllocationStatus.RUNNING
                    ])
                })
            
            return {
                'available': True,
                'gpu_count': len(gpus),
                'gpus': gpu_info
            }
            
        except Exception as e:
            logger.error(f"Failed to get GPU status: {e}")
            return {'available': False, 'error': str(e)}
    
    def allocate_gpu_memory(
        self, 
        tenant_id: str, 
        operation_id: str, 
        memory_mb: float,
        duration_seconds: Optional[float] = None
    ) -> Optional[ResourceAllocation]:
        """Allocate GPU memory for an operation."""
        if not self.available:
            logger.warning("GPU not available for allocation")
            return None
        
        try:
            gpus = GPUtil.getGPUs()
            
            # Find GPU with enough free memory
            best_gpu = None
            for gpu in gpus:
                with self._lock:
                    allocations = self.gpu_allocations.get(gpu.id, [])
                    allocated_memory = sum(
                        alloc.allocated_amount 
                        for alloc in allocations 
                        if alloc.status == AllocationStatus.RUNNING
                    )
                
                available_memory = gpu.memoryFree - allocated_memory
                if available_memory >= memory_mb:
                    if best_gpu is None or gpu.memoryFree > best_gpu.memoryFree:
                        best_gpu = gpu
            
            if best_gpu is None:
                logger.warning(f"No GPU with {memory_mb}MB available memory found")
                return None
            
            # Create allocation
            allocation_id = f"gpu_{best_gpu.id}_{tenant_id}_{int(time.time() * 1000000)}"
            allocation = ResourceAllocation(
                allocation_id=allocation_id,
                tenant_id=tenant_id,
                operation_id=operation_id,
                resource_type=ResourceType.GPU,
                allocated_amount=memory_mb,
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=duration_seconds) if duration_seconds else None,
                metadata={'gpu_id': best_gpu.id}
            )
            
            with self._lock:
                self.gpu_allocations[best_gpu.id].append(allocation)
            
            logger.info(f"Allocated {memory_mb}MB GPU memory on GPU {best_gpu.id} for {tenant_id}")
            return allocation
            
        except Exception as e:
            logger.error(f"Failed to allocate GPU memory: {e}")
            return None
    
    def release_allocation(self, allocation: ResourceAllocation) -> bool:
        """Release a GPU allocation."""
        try:
            gpu_id = allocation.metadata.get('gpu_id')
            if gpu_id is None:
                return False
            
            with self._lock:
                allocations = self.gpu_allocations.get(gpu_id, [])
                if allocation in allocations:
                    allocations.remove(allocation)
                    allocation.status = AllocationStatus.COMPLETED
                    logger.info(f"Released GPU allocation {allocation.allocation_id}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to release GPU allocation: {e}")
            return False

class CPUManager:
    """Manages CPU resource allocation and monitoring."""
    
    def __init__(self):
        self.total_cores = psutil.cpu_count()
        self.cpu_allocations: List[ResourceAllocation] = []
        self._lock = threading.Lock()
        
        logger.info(f"Initialized CPU manager with {self.total_cores} cores")
    
    def get_cpu_status(self) -> Dict[str, Any]:
        """Get current CPU status."""
        try:
            with self._lock:
                allocated_cores = sum(
                    alloc.allocated_amount 
                    for alloc in self.cpu_allocations 
                    if alloc.status == AllocationStatus.RUNNING
                )
            
            cpu_percent = psutil.cpu_percent(interval=1)
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
            
            return {
                'total_cores': self.total_cores,
                'allocated_cores': allocated_cores,
                'available_cores': self.total_cores - allocated_cores,
                'utilization_percent': cpu_percent,
                'load_average': {
                    '1min': load_avg[0],
                    '5min': load_avg[1],
                    '15min': load_avg[2]
                },
                'active_allocations': len([
                    a for a in self.cpu_allocations 
                    if a.status == AllocationStatus.RUNNING
                ])
            }
            
        except Exception as e:
            logger.error(f"Failed to get CPU status: {e}")
            return {'error': str(e)}
    
    def allocate_cpu_cores(
        self, 
        tenant_id: str, 
        operation_id: str, 
        cores: float,
        duration_seconds: Optional[float] = None
    ) -> Optional[ResourceAllocation]:
        """Allocate CPU cores for an operation."""
        try:
            with self._lock:
                allocated_cores = sum(
                    alloc.allocated_amount 
                    for alloc in self.cpu_allocations 
                    if alloc.status == AllocationStatus.RUNNING
                )
                
                available_cores = self.total_cores - allocated_cores
                
                if available_cores < cores:
                    logger.warning(f"Not enough CPU cores available: requested {cores}, available {available_cores}")
                    return None
                
                # Create allocation
                allocation_id = f"cpu_{tenant_id}_{int(time.time() * 1000000)}"
                allocation = ResourceAllocation(
                    allocation_id=allocation_id,
                    tenant_id=tenant_id,
                    operation_id=operation_id,
                    resource_type=ResourceType.CPU,
                    allocated_amount=cores,
                    expires_at=datetime.now(timezone.utc) + timedelta(seconds=duration_seconds) if duration_seconds else None
                )
                
                self.cpu_allocations.append(allocation)
            
            logger.info(f"Allocated {cores} CPU cores for {tenant_id}")
            return allocation
            
        except Exception as e:
            logger.error(f"Failed to allocate CPU cores: {e}")
            return None
    
    def release_allocation(self, allocation: ResourceAllocation) -> bool:
        """Release a CPU allocation."""
        try:
            with self._lock:
                if allocation in self.cpu_allocations:
                    self.cpu_allocations.remove(allocation)
                    allocation.status = AllocationStatus.COMPLETED
                    logger.info(f"Released CPU allocation {allocation.allocation_id}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to release CPU allocation: {e}")
            return False

class MemoryManager:
    """Manages memory resource allocation and monitoring."""
    
    def __init__(self):
        self.total_memory = psutil.virtual_memory().total / (1024 * 1024)  # MB
        self.memory_allocations: List[ResourceAllocation] = []
        self._lock = threading.Lock()
        
        logger.info(f"Initialized memory manager with {self.total_memory:.2f}MB total memory")
    
    def get_memory_status(self) -> Dict[str, Any]:
        """Get current memory status."""
        try:
            memory = psutil.virtual_memory()
            
            with self._lock:
                allocated_memory = sum(
                    alloc.allocated_amount 
                    for alloc in self.memory_allocations 
                    if alloc.status == AllocationStatus.RUNNING
                )
            
            return {
                'total_mb': self.total_memory,
                'used_mb': memory.used / (1024 * 1024),
                'available_mb': memory.available / (1024 * 1024),
                'allocated_mb': allocated_memory,
                'utilization_percent': memory.percent,
                'active_allocations': len([
                    a for a in self.memory_allocations 
                    if a.status == AllocationStatus.RUNNING
                ])
            }
            
        except Exception as e:
            logger.error(f"Failed to get memory status: {e}")
            return {'error': str(e)}
    
    def allocate_memory(
        self, 
        tenant_id: str, 
        operation_id: str, 
        memory_mb: float,
        duration_seconds: Optional[float] = None
    ) -> Optional[ResourceAllocation]:
        """Allocate memory for an operation."""
        try:
            memory = psutil.virtual_memory()
            available_mb = memory.available / (1024 * 1024)
            
            with self._lock:
                allocated_memory = sum(
                    alloc.allocated_amount 
                    for alloc in self.memory_allocations 
                    if alloc.status == AllocationStatus.RUNNING
                )
                
                # Keep some buffer (20% of total or 1GB, whichever is smaller)
                buffer_mb = min(self.total_memory * 0.2, 1024)
                usable_memory = available_mb - allocated_memory - buffer_mb
                
                if usable_memory < memory_mb:
                    logger.warning(f"Not enough memory available: requested {memory_mb}MB, usable {usable_memory:.2f}MB")
                    return None
                
                # Create allocation
                allocation_id = f"mem_{tenant_id}_{int(time.time() * 1000000)}"
                allocation = ResourceAllocation(
                    allocation_id=allocation_id,
                    tenant_id=tenant_id,
                    operation_id=operation_id,
                    resource_type=ResourceType.MEMORY,
                    allocated_amount=memory_mb,
                    expires_at=datetime.now(timezone.utc) + timedelta(seconds=duration_seconds) if duration_seconds else None
                )
                
                self.memory_allocations.append(allocation)
            
            logger.info(f"Allocated {memory_mb}MB memory for {tenant_id}")
            return allocation
            
        except Exception as e:
            logger.error(f"Failed to allocate memory: {e}")
            return None
    
    def release_allocation(self, allocation: ResourceAllocation) -> bool:
        """Release a memory allocation."""
        try:
            with self._lock:
                if allocation in self.memory_allocations:
                    self.memory_allocations.remove(allocation)
                    allocation.status = AllocationStatus.COMPLETED
                    logger.info(f"Released memory allocation {allocation.allocation_id}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to release memory allocation: {e}")
            return False

class DiskIOManager:
    """Manages disk I/O resource allocation and monitoring."""
    
    def __init__(self):
        self.max_throughput_mbps = 1000.0  # Configurable max disk throughput
        self.io_allocations: List[ResourceAllocation] = []
        self._lock = threading.Lock()
        
        logger.info(f"Initialized disk I/O manager with {self.max_throughput_mbps}MB/s max throughput")
    
    def get_disk_status(self) -> Dict[str, Any]:
        """Get current disk I/O status."""
        try:
            disk_io = psutil.disk_io_counters()
            
            with self._lock:
                allocated_throughput = sum(
                    alloc.allocated_amount 
                    for alloc in self.io_allocations 
                    if alloc.status == AllocationStatus.RUNNING
                )
            
            # Calculate current I/O rates (this is approximate)
            current_read_mbps = 0.0
            current_write_mbps = 0.0
            
            if hasattr(self, '_last_disk_io') and hasattr(self, '_last_check_time'):
                time_diff = time.time() - self._last_check_time
                if time_diff > 0:
                    read_diff = disk_io.read_bytes - self._last_disk_io.read_bytes
                    write_diff = disk_io.write_bytes - self._last_disk_io.write_bytes
                    
                    current_read_mbps = (read_diff / time_diff) / (1024 * 1024)
                    current_write_mbps = (write_diff / time_diff) / (1024 * 1024)
            
            self._last_disk_io = disk_io
            self._last_check_time = time.time()
            
            return {
                'max_throughput_mbps': self.max_throughput_mbps,
                'allocated_throughput_mbps': allocated_throughput,
                'available_throughput_mbps': self.max_throughput_mbps - allocated_throughput,
                'current_read_mbps': current_read_mbps,
                'current_write_mbps': current_write_mbps,
                'total_read_gb': disk_io.read_bytes / (1024 * 1024 * 1024),
                'total_write_gb': disk_io.write_bytes / (1024 * 1024 * 1024),
                'active_allocations': len([
                    a for a in self.io_allocations 
                    if a.status == AllocationStatus.RUNNING
                ])
            }
            
        except Exception as e:
            logger.error(f"Failed to get disk I/O status: {e}")
            return {'error': str(e)}
    
    def allocate_disk_io(
        self, 
        tenant_id: str, 
        operation_id: str, 
        throughput_mbps: float,
        duration_seconds: Optional[float] = None
    ) -> Optional[ResourceAllocation]:
        """Allocate disk I/O throughput for an operation."""
        try:
            with self._lock:
                allocated_throughput = sum(
                    alloc.allocated_amount 
                    for alloc in self.io_allocations 
                    if alloc.status == AllocationStatus.RUNNING
                )
                
                available_throughput = self.max_throughput_mbps - allocated_throughput
                
                if available_throughput < throughput_mbps:
                    logger.warning(f"Not enough disk I/O throughput available: requested {throughput_mbps}MB/s, available {available_throughput:.2f}MB/s")
                    return None
                
                # Create allocation
                allocation_id = f"disk_{tenant_id}_{int(time.time() * 1000000)}"
                allocation = ResourceAllocation(
                    allocation_id=allocation_id,
                    tenant_id=tenant_id,
                    operation_id=operation_id,
                    resource_type=ResourceType.DISK_IO,
                    allocated_amount=throughput_mbps,
                    expires_at=datetime.now(timezone.utc) + timedelta(seconds=duration_seconds) if duration_seconds else None
                )
                
                self.io_allocations.append(allocation)
            
            logger.info(f"Allocated {throughput_mbps}MB/s disk I/O for {tenant_id}")
            return allocation
            
        except Exception as e:
            logger.error(f"Failed to allocate disk I/O: {e}")
            return None
    
    def release_allocation(self, allocation: ResourceAllocation) -> bool:
        """Release a disk I/O allocation."""
        try:
            with self._lock:
                if allocation in self.io_allocations:
                    self.io_allocations.remove(allocation)
                    allocation.status = AllocationStatus.COMPLETED
                    logger.info(f"Released disk I/O allocation {allocation.allocation_id}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to release disk I/O allocation: {e}")
            return False

class ResourceAllocationSystem:
    """Main system for managing all resource allocations."""
    
    def __init__(self):
        self.gpu_manager = GPUManager()
        self.cpu_manager = CPUManager()
        self.memory_manager = MemoryManager()
        self.disk_manager = DiskIOManager()
        
        # Tenant resource limits
        self.tenant_limits: Dict[str, ResourceLimits] = {}
        self.tenant_usage: Dict[str, Dict[ResourceType, float]] = defaultdict(lambda: defaultdict(float))
        
        # All allocations for tracking
        self.all_allocations: Dict[str, ResourceAllocation] = {}
        
        # Background cleanup task
        self.cleanup_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        self._lock = threading.Lock()
    
    def set_tenant_limits(self, tenant_id: str, limits: ResourceLimits) -> None:
        """Set resource limits for a tenant."""
        with self._lock:
            self.tenant_limits[tenant_id] = limits
        
        logger.info(f"Set resource limits for tenant {tenant_id}")
    
    def get_tenant_limits(self, tenant_id: str) -> ResourceLimits:
        """Get resource limits for a tenant."""
        return self.tenant_limits.get(tenant_id, ResourceLimits())
    
    async def allocate_resources(
        self,
        tenant_id: str,
        operation_id: str,
        resource_requirements: Dict[ResourceType, float],
        duration_seconds: Optional[float] = None
    ) -> Dict[ResourceType, Optional[ResourceAllocation]]:
        """Allocate multiple resources for an operation."""
        
        # Check tenant limits
        limits = self.get_tenant_limits(tenant_id)
        allocations = {}
        failed_allocations = []
        
        try:
            # Allocate each requested resource
            for resource_type, amount in resource_requirements.items():
                
                # Check tenant limits
                if not self._check_tenant_limit(tenant_id, resource_type, amount, limits):
                    logger.warning(f"Resource request exceeds tenant limits: {tenant_id}, {resource_type.value}, {amount}")
                    allocations[resource_type] = None
                    failed_allocations.append(resource_type)
                    continue
                
                # Allocate resource
                allocation = None
                
                if resource_type == ResourceType.GPU:
                    allocation = self.gpu_manager.allocate_gpu_memory(
                        tenant_id, operation_id, amount, duration_seconds
                    )
                elif resource_type == ResourceType.CPU:
                    allocation = self.cpu_manager.allocate_cpu_cores(
                        tenant_id, operation_id, amount, duration_seconds
                    )
                elif resource_type == ResourceType.MEMORY:
                    allocation = self.memory_manager.allocate_memory(
                        tenant_id, operation_id, amount, duration_seconds
                    )
                elif resource_type == ResourceType.DISK_IO:
                    allocation = self.disk_manager.allocate_disk_io(
                        tenant_id, operation_id, amount, duration_seconds
                    )
                
                allocations[resource_type] = allocation
                
                if allocation:
                    allocation.status = AllocationStatus.ALLOCATED
                    with self._lock:
                        self.all_allocations[allocation.allocation_id] = allocation
                        self.tenant_usage[tenant_id][resource_type] += amount
                else:
                    failed_allocations.append(resource_type)
            
            # If any allocation failed, release successful ones
            if failed_allocations:
                logger.warning(f"Failed to allocate resources {failed_allocations} for {tenant_id}, releasing successful allocations")
                await self._release_allocations(list(allocations.values()))
                return {rt: None for rt in resource_requirements.keys()}
            
            logger.info(f"Successfully allocated resources for {tenant_id}: {list(resource_requirements.keys())}")
            return allocations
            
        except Exception as e:
            logger.error(f"Failed to allocate resources for {tenant_id}: {e}")
            await self._release_allocations(list(allocations.values()))
            return {rt: None for rt in resource_requirements.keys()}
    
    def _check_tenant_limit(
        self, 
        tenant_id: str, 
        resource_type: ResourceType, 
        amount: float, 
        limits: ResourceLimits
    ) -> bool:
        """Check if resource request is within tenant limits."""
        
        if resource_type == ResourceType.GPU:
            return amount <= limits.max_gpu_memory_mb
        elif resource_type == ResourceType.CPU:
            return amount <= limits.max_cpu_cores
        elif resource_type == ResourceType.MEMORY:
            return amount <= limits.max_memory_mb
        elif resource_type == ResourceType.DISK_IO:
            return amount <= limits.max_disk_io_mbps
        
        return True
    
    async def _release_allocations(self, allocations: List[Optional[ResourceAllocation]]) -> None:
        """Release a list of allocations."""
        for allocation in allocations:
            if allocation:
                await self.release_allocation(allocation.allocation_id)
    
    async def release_allocation(self, allocation_id: str) -> bool:
        """Release a specific allocation."""
        try:
            with self._lock:
                allocation = self.all_allocations.get(allocation_id)
                if not allocation:
                    logger.warning(f"Allocation {allocation_id} not found")
                    return False
                
                # Update tenant usage
                self.tenant_usage[allocation.tenant_id][allocation.resource_type] -= allocation.allocated_amount
                
                # Remove from tracking
                del self.all_allocations[allocation_id]
            
            # Release from appropriate manager
            success = False
            if allocation.resource_type == ResourceType.GPU:
                success = self.gpu_manager.release_allocation(allocation)
            elif allocation.resource_type == ResourceType.CPU:
                success = self.cpu_manager.release_allocation(allocation)
            elif allocation.resource_type == ResourceType.MEMORY:
                success = self.memory_manager.release_allocation(allocation)
            elif allocation.resource_type == ResourceType.DISK_IO:
                success = self.disk_manager.release_allocation(allocation)
            
            if success:
                logger.info(f"Released allocation {allocation_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to release allocation {allocation_id}: {e}")
            return False
    
    async def start_cleanup_task(self) -> None:
        """Start background cleanup task for expired allocations."""
        if self.is_running:
            return
        
        self.is_running = True
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Started resource allocation cleanup task")
    
    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        self.is_running = False
        
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped resource allocation cleanup task")
    
    async def _cleanup_loop(self) -> None:
        """Background loop for cleaning up expired allocations."""
        while self.is_running:
            try:
                now = datetime.now(timezone.utc)
                expired_allocations = []
                
                with self._lock:
                    for allocation in self.all_allocations.values():
                        if (allocation.expires_at and 
                            allocation.expires_at <= now and 
                            allocation.status in [AllocationStatus.ALLOCATED, AllocationStatus.RUNNING]):
                            expired_allocations.append(allocation.allocation_id)
                
                # Release expired allocations
                for allocation_id in expired_allocations:
                    await self.release_allocation(allocation_id)
                    logger.info(f"Released expired allocation {allocation_id}")
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in resource cleanup loop: {e}")
                await asyncio.sleep(60)
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system resource status."""
        return {
            'gpu': self.gpu_manager.get_gpu_status(),
            'cpu': self.cpu_manager.get_cpu_status(),
            'memory': self.memory_manager.get_memory_status(),
            'disk_io': self.disk_manager.get_disk_status(),
            'allocations': {
                'total': len(self.all_allocations),
                'by_status': {
                    status.value: len([
                        a for a in self.all_allocations.values() 
                        if a.status == status
                    ])
                    for status in AllocationStatus
                }
            }
        }
    
    def get_tenant_usage(self, tenant_id: str) -> Dict[str, Any]:
        """Get resource usage for a specific tenant."""
        with self._lock:
            usage = self.tenant_usage.get(tenant_id, {})
            limits = self.tenant_limits.get(tenant_id, ResourceLimits())
            
            tenant_allocations = [
                alloc for alloc in self.all_allocations.values()
                if alloc.tenant_id == tenant_id
            ]
        
        return {
            'tenant_id': tenant_id,
            'limits': limits.to_dict(),
            'current_usage': {rt.value: usage.get(rt, 0) for rt in ResourceType},
            'active_allocations': len([
                a for a in tenant_allocations 
                if a.status in [AllocationStatus.ALLOCATED, AllocationStatus.RUNNING]
            ]),
            'total_allocations': len(tenant_allocations)
        }
    
    @asynccontextmanager
    async def managed_allocation(
        self,
        tenant_id: str,
        operation_id: str,
        resource_requirements: Dict[ResourceType, float],
        duration_seconds: Optional[float] = None
    ):
        """Context manager for automatic resource allocation and cleanup."""
        allocations = await self.allocate_resources(
            tenant_id, operation_id, resource_requirements, duration_seconds
        )
        
        try:
            # Mark allocations as running
            for allocation in allocations.values():
                if allocation:
                    allocation.status = AllocationStatus.RUNNING
            
            yield allocations
            
        finally:
            # Release all allocations
            for allocation in allocations.values():
                if allocation:
                    await self.release_allocation(allocation.allocation_id)

# Global resource allocation system
resource_allocator = ResourceAllocationSystem() 