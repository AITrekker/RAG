"""
Resource optimization system for efficient resource utilization.

This module provides batch size optimization, parallel processing limits,
cache management, and automatic resource cleanup.
"""

import asyncio
import logging
import time
import gc
import threading
from typing import Dict, List, Optional, Any, Set, Callable, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from collections import defaultdict, deque
import heapq
import psutil
import weakref

from .resource_manager import ResourceType, ResourceAllocationSystem
from .resource_monitor import ResourceMonitor

logger = logging.getLogger(__name__)

class OptimizationStrategy(Enum):
    """Resource optimization strategies."""
    THROUGHPUT = "throughput"  # Maximize throughput
    LATENCY = "latency"  # Minimize latency
    EFFICIENCY = "efficiency"  # Maximize resource efficiency
    BALANCED = "balanced"  # Balance between throughput and latency

class CacheEvictionPolicy(Enum):
    """Cache eviction policies."""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In, First Out
    TTL = "ttl"  # Time To Live

@dataclass
class BatchConfiguration:
    """Configuration for batch processing optimization."""
    min_batch_size: int = 1
    max_batch_size: int = 100
    target_batch_size: int = 10
    batch_timeout_seconds: float = 30.0
    adaptive_sizing: bool = True
    throughput_target: Optional[float] = None  # items per second
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'min_batch_size': self.min_batch_size,
            'max_batch_size': self.max_batch_size,
            'target_batch_size': self.target_batch_size,
            'batch_timeout_seconds': self.batch_timeout_seconds,
            'adaptive_sizing': self.adaptive_sizing,
            'throughput_target': self.throughput_target
        }

@dataclass
class ParallelismConfiguration:
    """Configuration for parallel processing optimization."""
    min_workers: int = 1
    max_workers: int = 10
    target_workers: int = 4
    adaptive_scaling: bool = True
    scale_up_threshold: float = 0.8  # Queue utilization to scale up
    scale_down_threshold: float = 0.3  # Queue utilization to scale down
    worker_timeout_seconds: float = 300.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'min_workers': self.min_workers,
            'max_workers': self.max_workers,
            'target_workers': self.target_workers,
            'adaptive_scaling': self.adaptive_scaling,
            'scale_up_threshold': self.scale_up_threshold,
            'scale_down_threshold': self.scale_down_threshold,
            'worker_timeout_seconds': self.worker_timeout_seconds
        }

@dataclass
class CacheEntry:
    """Represents a cache entry."""
    key: str
    value: Any
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    access_count: int = 0
    size_bytes: int = 0
    ttl_seconds: Optional[float] = None
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        if self.ttl_seconds is None:
            return False
        
        age = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return age > self.ttl_seconds
    
    def touch(self) -> None:
        """Update access information."""
        self.last_accessed = datetime.now(timezone.utc)
        self.access_count += 1

class BatchOptimizer:
    """Optimizes batch sizes for processing operations."""
    
    def __init__(self):
        self.configurations: Dict[str, BatchConfiguration] = {}
        self.performance_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.current_batch_sizes: Dict[str, int] = {}
        self._lock = threading.Lock()
    
    def set_configuration(self, operation_type: str, config: BatchConfiguration) -> None:
        """Set batch configuration for an operation type."""
        with self._lock:
            self.configurations[operation_type] = config
            self.current_batch_sizes[operation_type] = config.target_batch_size
        
        logger.info(f"Set batch configuration for {operation_type}: target size {config.target_batch_size}")
    
    def get_optimal_batch_size(self, operation_type: str) -> int:
        """Get optimal batch size for an operation type."""
        with self._lock:
            return self.current_batch_sizes.get(operation_type, 10)
    
    def record_batch_performance(
        self,
        operation_type: str,
        batch_size: int,
        processing_time: float,
        success_count: int,
        error_count: int
    ) -> None:
        """Record performance data for a batch operation."""
        
        throughput = success_count / processing_time if processing_time > 0 else 0
        error_rate = error_count / (success_count + error_count) if (success_count + error_count) > 0 else 0
        
        performance_data = {
            'timestamp': datetime.now(timezone.utc),
            'batch_size': batch_size,
            'processing_time': processing_time,
            'throughput': throughput,
            'error_rate': error_rate,
            'success_count': success_count,
            'error_count': error_count
        }
        
        with self._lock:
            self.performance_history[operation_type].append(performance_data)
            
            # Update optimal batch size if adaptive sizing is enabled
            config = self.configurations.get(operation_type)
            if config and config.adaptive_sizing:
                self._update_optimal_batch_size(operation_type, config)
    
    def _update_optimal_batch_size(self, operation_type: str, config: BatchConfiguration) -> None:
        """Update optimal batch size based on performance history."""
        history = self.performance_history[operation_type]
        
        if len(history) < 5:  # Need at least 5 data points
            return
        
        # Analyze recent performance
        recent_data = list(history)[-10:]  # Last 10 batches
        
        # Calculate average throughput for different batch sizes
        throughput_by_size: Dict[int, List[float]] = defaultdict(list)
        
        for data in recent_data:
            if data['error_rate'] < 0.1:  # Only consider low-error batches
                throughput_by_size[data['batch_size']].append(data['throughput'])
        
        if not throughput_by_size:
            return
        
        # Find batch size with best average throughput
        best_batch_size = config.target_batch_size
        best_throughput = 0.0
        
        for batch_size, throughputs in throughput_by_size.items():
            avg_throughput = sum(throughputs) / len(throughputs)
            
            if avg_throughput > best_throughput:
                best_throughput = avg_throughput
                best_batch_size = batch_size
        
        # Adjust batch size towards optimal
        current_size = self.current_batch_sizes.get(operation_type, config.target_batch_size)
        
        if best_batch_size > current_size:
            new_size = min(current_size + 1, config.max_batch_size, best_batch_size)
        elif best_batch_size < current_size:
            new_size = max(current_size - 1, config.min_batch_size, best_batch_size)
        else:
            new_size = current_size
        
        if new_size != current_size:
            self.current_batch_sizes[operation_type] = new_size
            logger.debug(f"Adjusted batch size for {operation_type}: {current_size} -> {new_size}")
    
    def get_performance_stats(self, operation_type: str) -> Dict[str, Any]:
        """Get performance statistics for an operation type."""
        with self._lock:
            history = list(self.performance_history.get(operation_type, []))
            config = self.configurations.get(operation_type)
            current_size = self.current_batch_sizes.get(operation_type, 0)
        
        if not history:
            return {
                'operation_type': operation_type,
                'current_batch_size': current_size,
                'configuration': config.to_dict() if config else None,
                'performance_data': None
            }
        
        # Calculate statistics
        throughputs = [d['throughput'] for d in history]
        error_rates = [d['error_rate'] for d in history]
        processing_times = [d['processing_time'] for d in history]
        
        return {
            'operation_type': operation_type,
            'current_batch_size': current_size,
            'configuration': config.to_dict() if config else None,
            'performance_data': {
                'sample_count': len(history),
                'average_throughput': sum(throughputs) / len(throughputs),
                'max_throughput': max(throughputs),
                'average_error_rate': sum(error_rates) / len(error_rates),
                'average_processing_time': sum(processing_times) / len(processing_times),
                'recent_performance': history[-5:]  # Last 5 data points
            }
        }

class ParallelismOptimizer:
    """Optimizes parallel processing configurations."""
    
    def __init__(self):
        self.configurations: Dict[str, ParallelismConfiguration] = {}
        self.current_worker_counts: Dict[str, int] = {}
        self.worker_utilization: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.queue_sizes: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self._lock = threading.Lock()
    
    def set_configuration(self, operation_type: str, config: ParallelismConfiguration) -> None:
        """Set parallelism configuration for an operation type."""
        with self._lock:
            self.configurations[operation_type] = config
            self.current_worker_counts[operation_type] = config.target_workers
        
        logger.info(f"Set parallelism configuration for {operation_type}: target {config.target_workers} workers")
    
    def get_optimal_worker_count(self, operation_type: str) -> int:
        """Get optimal worker count for an operation type."""
        with self._lock:
            return self.current_worker_counts.get(operation_type, 4)
    
    def record_utilization(
        self,
        operation_type: str,
        worker_count: int,
        queue_size: int,
        active_workers: int
    ) -> None:
        """Record utilization data for adaptive scaling."""
        
        utilization = active_workers / worker_count if worker_count > 0 else 0
        
        with self._lock:
            self.worker_utilization[operation_type].append({
                'timestamp': datetime.now(timezone.utc),
                'worker_count': worker_count,
                'utilization': utilization,
                'active_workers': active_workers
            })
            
            self.queue_sizes[operation_type].append({
                'timestamp': datetime.now(timezone.utc),
                'queue_size': queue_size,
                'worker_count': worker_count
            })
            
            # Update optimal worker count if adaptive scaling is enabled
            config = self.configurations.get(operation_type)
            if config and config.adaptive_scaling:
                self._update_optimal_worker_count(operation_type, config)
    
    def _update_optimal_worker_count(self, operation_type: str, config: ParallelismConfiguration) -> None:
        """Update optimal worker count based on utilization history."""
        
        # Analyze recent utilization
        utilization_history = list(self.worker_utilization[operation_type])
        queue_history = list(self.queue_sizes[operation_type])
        
        if len(utilization_history) < 5 or len(queue_history) < 5:
            return
        
        # Calculate average utilization and queue size over recent period
        recent_utilization = utilization_history[-10:]
        recent_queues = queue_history[-10:]
        
        avg_utilization = sum(u['utilization'] for u in recent_utilization) / len(recent_utilization)
        avg_queue_size = sum(q['queue_size'] for q in recent_queues) / len(recent_queues)
        
        current_workers = self.current_worker_counts.get(operation_type, config.target_workers)
        
        # Decide whether to scale up or down
        new_worker_count = current_workers
        
        # Scale up if high utilization or growing queue
        if (avg_utilization > config.scale_up_threshold or avg_queue_size > current_workers * 2):
            new_worker_count = min(current_workers + 1, config.max_workers)
        
        # Scale down if low utilization and small queue
        elif (avg_utilization < config.scale_down_threshold and avg_queue_size < current_workers):
            new_worker_count = max(current_workers - 1, config.min_workers)
        
        if new_worker_count != current_workers:
            self.current_worker_counts[operation_type] = new_worker_count
            logger.debug(f"Adjusted worker count for {operation_type}: {current_workers} -> {new_worker_count}")
    
    def get_utilization_stats(self, operation_type: str) -> Dict[str, Any]:
        """Get utilization statistics for an operation type."""
        with self._lock:
            utilization_history = list(self.worker_utilization.get(operation_type, []))
            queue_history = list(self.queue_sizes.get(operation_type, []))
            config = self.configurations.get(operation_type)
            current_workers = self.current_worker_counts.get(operation_type, 0)
        
        if not utilization_history:
            return {
                'operation_type': operation_type,
                'current_worker_count': current_workers,
                'configuration': config.to_dict() if config else None,
                'utilization_data': None
            }
        
        # Calculate statistics
        recent_utilization = utilization_history[-10:]
        recent_queues = queue_history[-10:]
        
        avg_utilization = sum(u['utilization'] for u in recent_utilization) / len(recent_utilization)
        avg_queue_size = sum(q['queue_size'] for q in recent_queues) / len(recent_queues)
        
        return {
            'operation_type': operation_type,
            'current_worker_count': current_workers,
            'configuration': config.to_dict() if config else None,
            'utilization_data': {
                'average_utilization': avg_utilization,
                'average_queue_size': avg_queue_size,
                'recent_utilization': recent_utilization,
                'recent_queues': recent_queues
            }
        }

class CacheManager:
    """Manages caching with configurable eviction policies."""
    
    def __init__(
        self,
        max_size_mb: float = 512.0,
        eviction_policy: CacheEvictionPolicy = CacheEvictionPolicy.LRU,
        default_ttl_seconds: Optional[float] = None
    ):
        self.max_size_bytes = int(max_size_mb * 1024 * 1024)
        self.eviction_policy = eviction_policy
        self.default_ttl_seconds = default_ttl_seconds
        
        self.cache: Dict[str, CacheEntry] = {}
        self.current_size_bytes = 0
        
        # Data structures for different eviction policies
        self.access_order: deque = deque()  # For LRU
        self.access_frequency: Dict[str, int] = defaultdict(int)  # For LFU
        self.insertion_order: deque = deque()  # For FIFO
        
        self._lock = threading.Lock()
        
        # Background cleanup task
        self.cleanup_task: Optional[asyncio.Task] = None
        self.is_running = False
    
    def put(
        self,
        key: str,
        value: Any,
        size_bytes: Optional[int] = None,
        ttl_seconds: Optional[float] = None
    ) -> bool:
        """Put a value in the cache."""
        
        if size_bytes is None:
            size_bytes = self._estimate_size(value)
        
        if ttl_seconds is None:
            ttl_seconds = self.default_ttl_seconds
        
        with self._lock:
            # Check if key already exists
            if key in self.cache:
                old_entry = self.cache[key]
                self.current_size_bytes -= old_entry.size_bytes
                self._remove_from_eviction_structures(key)
            
            # Check if we have enough space
            if size_bytes > self.max_size_bytes:
                logger.warning(f"Cache item too large: {size_bytes} bytes > {self.max_size_bytes} bytes")
                return False
            
            # Evict items if necessary
            while self.current_size_bytes + size_bytes > self.max_size_bytes:
                if not self._evict_one_item():
                    logger.warning("Failed to evict cache items to make space")
                    return False
            
            # Create and store entry
            entry = CacheEntry(
                key=key,
                value=value,
                size_bytes=size_bytes,
                ttl_seconds=ttl_seconds
            )
            
            self.cache[key] = entry
            self.current_size_bytes += size_bytes
            
            # Update eviction structures
            self._add_to_eviction_structures(key)
            
            return True
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache."""
        with self._lock:
            entry = self.cache.get(key)
            
            if entry is None:
                return None
            
            # Check if expired
            if entry.is_expired():
                self._remove_entry(key)
                return None
            
            # Update access information
            entry.touch()
            self._update_eviction_structures(key)
            
            return entry.value
    
    def delete(self, key: str) -> bool:
        """Delete a key from the cache."""
        with self._lock:
            if key in self.cache:
                self._remove_entry(key)
                return True
            return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self.cache.clear()
            self.current_size_bytes = 0
            self.access_order.clear()
            self.access_frequency.clear()
            self.insertion_order.clear()
    
    def _estimate_size(self, value: Any) -> int:
        """Estimate the size of a value in bytes."""
        import sys
        return sys.getsizeof(value)
    
    def _add_to_eviction_structures(self, key: str) -> None:
        """Add key to eviction policy data structures."""
        if self.eviction_policy == CacheEvictionPolicy.LRU:
            self.access_order.append(key)
        elif self.eviction_policy == CacheEvictionPolicy.LFU:
            self.access_frequency[key] = 1
        elif self.eviction_policy == CacheEvictionPolicy.FIFO:
            self.insertion_order.append(key)
    
    def _update_eviction_structures(self, key: str) -> None:
        """Update eviction policy data structures on access."""
        if self.eviction_policy == CacheEvictionPolicy.LRU:
            # Move to end of access order
            try:
                self.access_order.remove(key)
            except ValueError:
                pass
            self.access_order.append(key)
        elif self.eviction_policy == CacheEvictionPolicy.LFU:
            self.access_frequency[key] += 1
    
    def _remove_from_eviction_structures(self, key: str) -> None:
        """Remove key from eviction policy data structures."""
        if self.eviction_policy == CacheEvictionPolicy.LRU:
            try:
                self.access_order.remove(key)
            except ValueError:
                pass
        elif self.eviction_policy == CacheEvictionPolicy.LFU:
            self.access_frequency.pop(key, None)
        elif self.eviction_policy == CacheEvictionPolicy.FIFO:
            try:
                self.insertion_order.remove(key)
            except ValueError:
                pass
    
    def _evict_one_item(self) -> bool:
        """Evict one item based on the eviction policy."""
        if not self.cache:
            return False
        
        victim_key = None
        
        if self.eviction_policy == CacheEvictionPolicy.LRU:
            if self.access_order:
                victim_key = self.access_order[0]
        
        elif self.eviction_policy == CacheEvictionPolicy.LFU:
            if self.access_frequency:
                victim_key = min(self.access_frequency.keys(), key=lambda k: self.access_frequency[k])
        
        elif self.eviction_policy == CacheEvictionPolicy.FIFO:
            if self.insertion_order:
                victim_key = self.insertion_order[0]
        
        elif self.eviction_policy == CacheEvictionPolicy.TTL:
            # Find expired items first, then fall back to LRU
            now = datetime.now(timezone.utc)
            expired_keys = [
                key for key, entry in self.cache.items()
                if entry.ttl_seconds and (now - entry.created_at).total_seconds() > entry.ttl_seconds
            ]
            
            if expired_keys:
                victim_key = expired_keys[0]
            elif self.access_order:
                victim_key = self.access_order[0]
        
        if victim_key:
            self._remove_entry(victim_key)
            return True
        
        return False
    
    def _remove_entry(self, key: str) -> None:
        """Remove an entry from the cache."""
        entry = self.cache.pop(key, None)
        if entry:
            self.current_size_bytes -= entry.size_bytes
            self._remove_from_eviction_structures(key)
    
    async def start_cleanup_task(self) -> None:
        """Start background cleanup task for expired entries."""
        if self.is_running:
            return
        
        self.is_running = True
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Started cache cleanup task")
    
    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        self.is_running = False
        
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped cache cleanup task")
    
    async def _cleanup_loop(self) -> None:
        """Background loop for cleaning up expired entries."""
        while self.is_running:
            try:
                await self._cleanup_expired_entries()
                await asyncio.sleep(60)  # Clean every minute
            except Exception as e:
                logger.error(f"Error in cache cleanup loop: {e}")
                await asyncio.sleep(60)
    
    async def _cleanup_expired_entries(self) -> None:
        """Remove expired entries from the cache."""
        now = datetime.now(timezone.utc)
        expired_keys = []
        
        with self._lock:
            for key, entry in self.cache.items():
                if entry.is_expired():
                    expired_keys.append(key)
        
        for key in expired_keys:
            with self._lock:
                self._remove_entry(key)
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                'max_size_mb': self.max_size_bytes / (1024 * 1024),
                'current_size_mb': self.current_size_bytes / (1024 * 1024),
                'utilization_percent': (self.current_size_bytes / self.max_size_bytes) * 100,
                'entry_count': len(self.cache),
                'eviction_policy': self.eviction_policy.value,
                'default_ttl_seconds': self.default_ttl_seconds,
                'hit_rate': self._calculate_hit_rate()
            }
    
    def _calculate_hit_rate(self) -> float:
        """Calculate cache hit rate (simplified implementation)."""
        # This would require tracking hits/misses in a production implementation
        return 0.0

class ResourceOptimizer:
    """Main resource optimization system."""
    
    def __init__(
        self,
        resource_allocator: ResourceAllocationSystem,
        resource_monitor: ResourceMonitor
    ):
        self.resource_allocator = resource_allocator
        self.resource_monitor = resource_monitor
        
        # Optimizers
        self.batch_optimizer = BatchOptimizer()
        self.parallelism_optimizer = ParallelismOptimizer()
        self.cache_manager = CacheManager()
        
        # Configuration
        self.optimization_strategy = OptimizationStrategy.BALANCED
        self.optimization_interval = 300.0  # 5 minutes
        
        # Background tasks
        self.is_running = False
        self.optimization_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        
        # Weak references for automatic cleanup
        self.managed_objects: Set[weakref.ref] = set()
    
    def set_optimization_strategy(self, strategy: OptimizationStrategy) -> None:
        """Set the optimization strategy."""
        self.optimization_strategy = strategy
        logger.info(f"Set optimization strategy to {strategy.value}")
    
    async def optimize_batch_configuration(self, operation_type: str) -> BatchConfiguration:
        """Optimize batch configuration for an operation type."""
        
        # Get current performance stats
        stats = self.batch_optimizer.get_performance_stats(operation_type)
        
        # Default configuration
        config = BatchConfiguration()
        
        if stats['performance_data']:
            perf_data = stats['performance_data']
            
            if self.optimization_strategy == OptimizationStrategy.THROUGHPUT:
                # Optimize for maximum throughput
                config.target_batch_size = min(50, config.max_batch_size)
                config.batch_timeout_seconds = 60.0
            
            elif self.optimization_strategy == OptimizationStrategy.LATENCY:
                # Optimize for minimum latency
                config.target_batch_size = max(5, config.min_batch_size)
                config.batch_timeout_seconds = 10.0
            
            elif self.optimization_strategy == OptimizationStrategy.EFFICIENCY:
                # Optimize for resource efficiency
                avg_throughput = perf_data['average_throughput']
                if avg_throughput > 0:
                    # Target batch size that maximizes throughput per resource unit
                    config.target_batch_size = min(int(avg_throughput * 10), config.max_batch_size)
            
            else:  # BALANCED
                # Balance between throughput and latency
                config.target_batch_size = 20
                config.batch_timeout_seconds = 30.0
        
        self.batch_optimizer.set_configuration(operation_type, config)
        return config
    
    async def optimize_parallelism_configuration(self, operation_type: str) -> ParallelismConfiguration:
        """Optimize parallelism configuration for an operation type."""
        
        # Get system resources
        system_status = self.resource_allocator.get_system_status()
        cpu_status = system_status.get('cpu', {})
        
        # Get current utilization stats
        stats = self.parallelism_optimizer.get_utilization_stats(operation_type)
        
        # Default configuration
        config = ParallelismConfiguration()
        
        # Adjust based on available CPU cores
        available_cores = cpu_status.get('available_cores', 4)
        
        if self.optimization_strategy == OptimizationStrategy.THROUGHPUT:
            # Use more workers for throughput
            config.target_workers = min(int(available_cores * 0.8), config.max_workers)
            config.scale_up_threshold = 0.6
        
        elif self.optimization_strategy == OptimizationStrategy.LATENCY:
            # Use fewer workers to reduce contention
            config.target_workers = min(int(available_cores * 0.4), 6)
            config.scale_up_threshold = 0.9
        
        elif self.optimization_strategy == OptimizationStrategy.EFFICIENCY:
            # Optimize for resource efficiency
            config.target_workers = min(int(available_cores * 0.6), config.max_workers)
            config.adaptive_scaling = True
        
        else:  # BALANCED
            config.target_workers = min(int(available_cores * 0.5), config.max_workers)
        
        self.parallelism_optimizer.set_configuration(operation_type, config)
        return config
    
    async def optimize_cache_configuration(self) -> None:
        """Optimize cache configuration based on system resources."""
        
        # Get system memory status
        system_status = self.resource_allocator.get_system_status()
        memory_status = system_status.get('memory', {})
        
        available_memory_mb = memory_status.get('available_mb', 1024)
        
        # Allocate percentage of available memory for cache
        cache_allocation_percent = 0.1  # 10%
        
        if self.optimization_strategy == OptimizationStrategy.THROUGHPUT:
            cache_allocation_percent = 0.2  # 20% for better caching
        elif self.optimization_strategy == OptimizationStrategy.EFFICIENCY:
            cache_allocation_percent = 0.15  # 15% for efficiency
        
        cache_size_mb = available_memory_mb * cache_allocation_percent
        
        # Create new cache manager if size changed significantly
        current_max = self.cache_manager.max_size_bytes / (1024 * 1024)
        if abs(cache_size_mb - current_max) > current_max * 0.2:  # 20% difference
            
            # Choose eviction policy based on strategy
            if self.optimization_strategy == OptimizationStrategy.LATENCY:
                eviction_policy = CacheEvictionPolicy.LRU
            elif self.optimization_strategy == OptimizationStrategy.THROUGHPUT:
                eviction_policy = CacheEvictionPolicy.LFU
            else:
                eviction_policy = CacheEvictionPolicy.LRU
            
            logger.info(f"Optimizing cache: {cache_size_mb:.1f}MB with {eviction_policy.value} eviction")
            
            # Note: In production, you'd want to migrate existing cache entries
            self.cache_manager = CacheManager(
                max_size_mb=cache_size_mb,
                eviction_policy=eviction_policy,
                default_ttl_seconds=3600.0  # 1 hour default TTL
            )
    
    async def cleanup_resources(self) -> None:
        """Perform comprehensive resource cleanup."""
        
        logger.info("Starting comprehensive resource cleanup")
        
        # Force garbage collection
        gc.collect()
        
        # Clean up weak references
        dead_refs = []
        for ref in self.managed_objects:
            if ref() is None:
                dead_refs.append(ref)
        
        for ref in dead_refs:
            self.managed_objects.discard(ref)
        
        # Clean up cache
        await self.cache_manager._cleanup_expired_entries()
        
        # Get memory usage before and after
        memory_before = psutil.virtual_memory().used / (1024 * 1024)
        
        # Additional cleanup based on memory pressure
        memory_status = self.resource_allocator.get_system_status().get('memory', {})
        memory_utilization = memory_status.get('utilization_percent', 0)
        
        if memory_utilization > 85:  # High memory pressure
            logger.warning(f"High memory utilization: {memory_utilization:.1f}%")
            
            # More aggressive cache cleanup
            cache_stats = self.cache_manager.get_cache_stats()
            if cache_stats['utilization_percent'] > 50:
                # Clear half the cache
                keys_to_remove = list(self.cache_manager.cache.keys())[:len(self.cache_manager.cache) // 2]
                for key in keys_to_remove:
                    self.cache_manager.delete(key)
                
                logger.info(f"Cleared {len(keys_to_remove)} cache entries due to memory pressure")
        
        memory_after = psutil.virtual_memory().used / (1024 * 1024)
        memory_freed = memory_before - memory_after
        
        logger.info(f"Resource cleanup completed: freed {memory_freed:.1f}MB")
    
    async def _optimization_loop(self) -> None:
        """Main optimization loop."""
        logger.info("Resource optimization started")
        
        while self.is_running:
            try:
                # Optimize cache configuration
                await self.optimize_cache_configuration()
                
                # Periodic resource cleanup
                await self.cleanup_resources()
                
                await asyncio.sleep(self.optimization_interval)
                
            except Exception as e:
                logger.error(f"Error in optimization loop: {e}")
                await asyncio.sleep(60)
        
        logger.info("Resource optimization stopped")
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while self.is_running:
            try:
                await self.cleanup_resources()
                await asyncio.sleep(1800)  # Cleanup every 30 minutes
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(1800)
    
    async def start_optimization(self) -> None:
        """Start the optimization system."""
        if self.is_running:
            return
        
        self.is_running = True
        
        # Start cache cleanup
        await self.cache_manager.start_cleanup_task()
        
        # Start optimization tasks
        self.optimization_task = asyncio.create_task(self._optimization_loop())
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("Resource optimization system started")
    
    async def stop_optimization(self) -> None:
        """Stop the optimization system."""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Cancel tasks
        if self.optimization_task:
            self.optimization_task.cancel()
            try:
                await self.optimization_task
            except asyncio.CancelledError:
                pass
        
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Stop cache cleanup
        await self.cache_manager.stop_cleanup_task()
        
        logger.info("Resource optimization system stopped")
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get comprehensive optimization statistics."""
        return {
            'optimization_strategy': self.optimization_strategy.value,
            'is_running': self.is_running,
            'optimization_interval': self.optimization_interval,
            'cache_stats': self.cache_manager.get_cache_stats(),
            'managed_objects': len(self.managed_objects),
            'system_resources': self.resource_allocator.get_system_status()
        }

# Global resource optimizer instance
from .resource_manager import resource_allocator
from .resource_monitor import resource_monitor
resource_optimizer = ResourceOptimizer(resource_allocator, resource_monitor) 