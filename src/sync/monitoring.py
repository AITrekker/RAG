"""
Monitoring and health checking for file system operations.

This module provides comprehensive monitoring, metrics collection,
and health checking for the file synchronization system.
"""

import asyncio
import logging
import psutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from collections import defaultdict, deque
import json
import threading
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

@dataclass
class MetricPoint:
    """A single metric data point."""
    timestamp: datetime
    value: float
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'value': self.value,
            'tags': self.tags
        }

@dataclass
class HealthStatus:
    """Health status for a component."""
    component: str
    is_healthy: bool
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'component': self.component,
            'is_healthy': self.is_healthy,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'details': self.details
        }

class MonitoringMetrics:
    """Collects and manages monitoring metrics."""
    
    def __init__(self, max_points_per_metric: int = 1000):
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_points_per_metric))
        self.max_points = max_points_per_metric
        self._lock = threading.Lock()
    
    def record_metric(
        self, 
        metric_name: str, 
        value: float, 
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a metric value."""
        with self._lock:
            point = MetricPoint(
                timestamp=datetime.now(timezone.utc),
                value=value,
                tags=tags or {}
            )
            self.metrics[metric_name].append(point)
    
    def get_metric_history(
        self, 
        metric_name: str, 
        since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[MetricPoint]:
        """Get historical values for a metric."""
        with self._lock:
            points = list(self.metrics.get(metric_name, []))
        
        # Filter by time if specified
        if since:
            points = [p for p in points if p.timestamp >= since]
        
        # Apply limit
        if limit:
            points = points[-limit:]
        
        return points
    
    def get_latest_value(self, metric_name: str) -> Optional[float]:
        """Get the latest value for a metric."""
        with self._lock:
            metric_deque = self.metrics.get(metric_name)
            if metric_deque:
                return metric_deque[-1].value
            return None
    
    def get_average_value(
        self, 
        metric_name: str, 
        since: Optional[datetime] = None
    ) -> Optional[float]:
        """Get average value for a metric over time period."""
        points = self.get_metric_history(metric_name, since=since)
        if points:
            return sum(p.value for p in points) / len(points)
        return None
    
    def get_all_metrics(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all metrics as dictionaries."""
        with self._lock:
            return {
                name: [point.to_dict() for point in points]
                for name, points in self.metrics.items()
            }
    
    def clear_metric(self, metric_name: str) -> bool:
        """Clear all data for a specific metric."""
        with self._lock:
            if metric_name in self.metrics:
                self.metrics[metric_name].clear()
                return True
            return False
    
    def clear_all_metrics(self) -> None:
        """Clear all metric data."""
        with self._lock:
            self.metrics.clear()

class HealthChecker:
    """Performs health checks on various system components."""
    
    def __init__(self):
        self.health_status: Dict[str, HealthStatus] = {}
        self.check_functions: Dict[str, callable] = {}
        self._lock = threading.Lock()
    
    def register_check(self, component: str, check_function: callable) -> None:
        """Register a health check function for a component."""
        self.check_functions[component] = check_function
        logger.debug(f"Registered health check for {component}")
    
    def unregister_check(self, component: str) -> bool:
        """Unregister a health check function."""
        if component in self.check_functions:
            del self.check_functions[component]
            with self._lock:
                if component in self.health_status:
                    del self.health_status[component]
            logger.debug(f"Unregistered health check for {component}")
            return True
        return False
    
    async def check_component(self, component: str) -> HealthStatus:
        """Perform health check for a specific component."""
        if component not in self.check_functions:
            return HealthStatus(
                component=component,
                is_healthy=False,
                message="No health check function registered"
            )
        
        try:
            check_function = self.check_functions[component]
            
            # Execute check function
            if asyncio.iscoroutinefunction(check_function):
                result = await check_function()
            else:
                result = check_function()
            
            # Handle different result types
            if isinstance(result, HealthStatus):
                status = result
            elif isinstance(result, bool):
                status = HealthStatus(
                    component=component,
                    is_healthy=result,
                    message="OK" if result else "Check failed"
                )
            elif isinstance(result, dict):
                status = HealthStatus(
                    component=component,
                    is_healthy=result.get('is_healthy', False),
                    message=result.get('message', 'Unknown status'),
                    details=result.get('details', {})
                )
            else:
                status = HealthStatus(
                    component=component,
                    is_healthy=False,
                    message=f"Invalid check result type: {type(result)}"
                )
            
            with self._lock:
                self.health_status[component] = status
            
            return status
            
        except Exception as e:
            status = HealthStatus(
                component=component,
                is_healthy=False,
                message=f"Health check failed: {str(e)}"
            )
            
            with self._lock:
                self.health_status[component] = status
            
            logger.error(f"Health check failed for {component}: {e}")
            return status
    
    async def check_all_components(self) -> Dict[str, HealthStatus]:
        """Perform health checks for all registered components."""
        if not self.check_functions:
            return {}
        
        # Run all checks concurrently
        tasks = []
        components = []
        
        for component in self.check_functions.keys():
            tasks.append(self.check_component(component))
            components.append(component)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        status_dict = {}
        for component, result in zip(components, results):
            if isinstance(result, Exception):
                status_dict[component] = HealthStatus(
                    component=component,
                    is_healthy=False,
                    message=f"Health check exception: {str(result)}"
                )
            else:
                status_dict[component] = result
        
        return status_dict
    
    def get_component_status(self, component: str) -> Optional[HealthStatus]:
        """Get latest health status for a component."""
        with self._lock:
            return self.health_status.get(component)
    
    def get_all_status(self) -> Dict[str, HealthStatus]:
        """Get all component health status."""
        with self._lock:
            return self.health_status.copy()
    
    def is_system_healthy(self) -> bool:
        """Check if all components are healthy."""
        with self._lock:
            return all(status.is_healthy for status in self.health_status.values())

class FileSystemMonitor:
    """Main monitoring system for file operations."""
    
    def __init__(self, check_interval: float = 30.0):
        self.metrics = MonitoringMetrics()
        self.health_checker = HealthChecker()
        self.check_interval = check_interval
        self.is_running = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.tenant_watchers: Dict[str, Any] = {}  # Will hold watcher references
        
        # Register default health checks
        self._register_default_checks()
    
    def _register_default_checks(self) -> None:
        """Register default system health checks."""
        self.health_checker.register_check("disk_space", self._check_disk_space)
        self.health_checker.register_check("memory_usage", self._check_memory_usage)
        self.health_checker.register_check("file_watchers", self._check_file_watchers)
    
    def _check_disk_space(self) -> HealthStatus:
        """Check available disk space."""
        try:
            # Check space for data directory
            data_path = Path("./data")
            if data_path.exists():
                usage = psutil.disk_usage(str(data_path))
                free_percentage = (usage.free / usage.total) * 100
                
                is_healthy = free_percentage > 10  # Alert if less than 10% free
                message = f"Disk usage: {100 - free_percentage:.1f}% used, {free_percentage:.1f}% free"
                
                return HealthStatus(
                    component="disk_space",
                    is_healthy=is_healthy,
                    message=message,
                    details={
                        'total_gb': usage.total / (1024**3),
                        'used_gb': usage.used / (1024**3),
                        'free_gb': usage.free / (1024**3),
                        'free_percentage': free_percentage
                    }
                )
            else:
                return HealthStatus(
                    component="disk_space",
                    is_healthy=False,
                    message="Data directory not found"
                )
        except Exception as e:
            return HealthStatus(
                component="disk_space",
                is_healthy=False,
                message=f"Failed to check disk space: {e}"
            )
    
    def _check_memory_usage(self) -> HealthStatus:
        """Check system memory usage."""
        try:
            memory = psutil.virtual_memory()
            used_percentage = memory.percent
            
            is_healthy = used_percentage < 90  # Alert if more than 90% used
            message = f"Memory usage: {used_percentage:.1f}%"
            
            return HealthStatus(
                component="memory_usage",
                is_healthy=is_healthy,
                message=message,
                details={
                    'total_gb': memory.total / (1024**3),
                    'used_gb': memory.used / (1024**3),
                    'available_gb': memory.available / (1024**3),
                    'used_percentage': used_percentage
                }
            )
        except Exception as e:
            return HealthStatus(
                component="memory_usage",
                is_healthy=False,
                message=f"Failed to check memory: {e}"
            )
    
    def _check_file_watchers(self) -> HealthStatus:
        """Check status of file watchers."""
        try:
            active_watchers = 0
            total_watchers = len(self.tenant_watchers)
            
            for tenant_id, watcher in self.tenant_watchers.items():
                if hasattr(watcher, 'is_active') and watcher.is_active:
                    active_watchers += 1
            
            is_healthy = active_watchers == total_watchers
            message = f"File watchers: {active_watchers}/{total_watchers} active"
            
            return HealthStatus(
                component="file_watchers",
                is_healthy=is_healthy,
                message=message,
                details={
                    'total_watchers': total_watchers,
                    'active_watchers': active_watchers,
                    'inactive_watchers': total_watchers - active_watchers
                }
            )
        except Exception as e:
            return HealthStatus(
                component="file_watchers",
                is_healthy=False,
                message=f"Failed to check file watchers: {e}"
            )
    
    def register_tenant_watcher(self, tenant_id: str, watcher: Any) -> None:
        """Register a tenant file watcher for monitoring."""
        self.tenant_watchers[tenant_id] = watcher
        logger.debug(f"Registered watcher for monitoring: {tenant_id}")
    
    def unregister_tenant_watcher(self, tenant_id: str) -> bool:
        """Unregister a tenant file watcher."""
        if tenant_id in self.tenant_watchers:
            del self.tenant_watchers[tenant_id]
            logger.debug(f"Unregistered watcher from monitoring: {tenant_id}")
            return True
        return False
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        logger.info("File system monitoring started")
        
        while self.is_running:
            try:
                # Collect system metrics
                await self._collect_system_metrics()
                
                # Collect file watcher metrics
                await self._collect_watcher_metrics()
                
                # Perform health checks
                await self.health_checker.check_all_components()
                
                # Wait for next interval
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)
        
        logger.info("File system monitoring stopped")
    
    async def _collect_system_metrics(self) -> None:
        """Collect system-level metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=None)
            self.metrics.record_metric("system.cpu_usage", cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.metrics.record_metric("system.memory_usage", memory.percent)
            self.metrics.record_metric("system.memory_available_gb", memory.available / (1024**3))
            
            # Disk usage for data directory
            data_path = Path("./data")
            if data_path.exists():
                usage = psutil.disk_usage(str(data_path))
                self.metrics.record_metric("system.disk_usage_percent", (usage.used / usage.total) * 100)
                self.metrics.record_metric("system.disk_free_gb", usage.free / (1024**3))
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
    
    async def _collect_watcher_metrics(self) -> None:
        """Collect file watcher metrics."""
        try:
            total_events = 0
            total_errors = 0
            active_watchers = 0
            
            for tenant_id, watcher in self.tenant_watchers.items():
                if hasattr(watcher, 'get_stats'):
                    stats = watcher.get_stats()
                    
                    # Per-tenant metrics
                    self.metrics.record_metric(
                        "watcher.events_processed", 
                        stats.get('events_processed', 0),
                        tags={'tenant_id': tenant_id}
                    )
                    
                    self.metrics.record_metric(
                        "watcher.errors", 
                        stats.get('errors', 0),
                        tags={'tenant_id': tenant_id}
                    )
                    
                    # Aggregate metrics
                    total_events += stats.get('events_processed', 0)
                    total_errors += stats.get('errors', 0)
                    
                    if stats.get('is_active', False):
                        active_watchers += 1
            
            # Global metrics
            self.metrics.record_metric("watcher.total_events", total_events)
            self.metrics.record_metric("watcher.total_errors", total_errors)
            self.metrics.record_metric("watcher.active_watchers", active_watchers)
            self.metrics.record_metric("watcher.total_watchers", len(self.tenant_watchers))
            
        except Exception as e:
            logger.error(f"Failed to collect watcher metrics: {e}")
    
    async def start_monitoring(self) -> None:
        """Start the monitoring system."""
        if self.is_running:
            logger.warning("Monitoring is already running")
            return
        
        self.is_running = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("File system monitoring started")
    
    async def stop_monitoring(self) -> None:
        """Stop the monitoring system."""
        if not self.is_running:
            logger.warning("Monitoring is not running")
            return
        
        self.is_running = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("File system monitoring stopped")
    
    def get_comprehensive_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        health_status = self.health_checker.get_all_status()
        
        # Get recent metrics
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        
        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'is_healthy': self.health_checker.is_system_healthy(),
            'health_checks': {
                name: status.to_dict() 
                for name, status in health_status.items()
            },
            'metrics_summary': {
                'cpu_usage': self.metrics.get_latest_value('system.cpu_usage'),
                'memory_usage': self.metrics.get_latest_value('system.memory_usage'),
                'disk_usage': self.metrics.get_latest_value('system.disk_usage_percent'),
                'active_watchers': self.metrics.get_latest_value('watcher.active_watchers'),
                'total_events_hour': sum(
                    p.value for p in self.metrics.get_metric_history('watcher.total_events', since=one_hour_ago)
                ),
            },
            'tenant_watchers': list(self.tenant_watchers.keys()),
            'monitoring': {
                'is_running': self.is_running,
                'check_interval': self.check_interval,
            }
        }
    
    @asynccontextmanager
    async def managed_monitoring(self):
        """Context manager for monitoring."""
        try:
            await self.start_monitoring()
            yield self
        finally:
            await self.stop_monitoring()

# Global monitoring instance
file_system_monitor = FileSystemMonitor() 