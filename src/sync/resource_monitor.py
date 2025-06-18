"""
Resource monitoring system for tracking usage, alerts, and reporting.

This module provides comprehensive monitoring of system resources,
usage tracking, alert generation, and detailed reporting.
"""

import asyncio
import logging
import psutil
import time
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Callable, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from collections import defaultdict, deque
import sqlite3
from contextlib import contextmanager
import threading

try:
    import GPUtil
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False
    GPUtil = None

from .resource_manager import ResourceType, ResourceAllocationSystem

logger = logging.getLogger(__name__)

class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class MetricType(Enum):
    """Types of metrics to track."""
    GAUGE = "gauge"  # Point-in-time values
    COUNTER = "counter"  # Cumulative values
    HISTOGRAM = "histogram"  # Distribution of values
    TIMER = "timer"  # Duration measurements

@dataclass
class MetricPoint:
    """A single metric data point."""
    timestamp: datetime
    value: float
    tags: Dict[str, str] = field(default_factory=dict)
    metric_type: MetricType = MetricType.GAUGE
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'value': self.value,
            'tags': self.tags,
            'metric_type': self.metric_type.value
        }

@dataclass
class Alert:
    """Represents a system alert."""
    alert_id: str
    alert_type: str
    severity: AlertSeverity
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tenant_id: Optional[str] = None
    resource_type: Optional[ResourceType] = None
    threshold_value: Optional[float] = None
    current_value: Optional[float] = None
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'alert_id': self.alert_id,
            'alert_type': self.alert_type,
            'severity': self.severity.value,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'tenant_id': self.tenant_id,
            'resource_type': self.resource_type.value if self.resource_type else None,
            'threshold_value': self.threshold_value,
            'current_value': self.current_value,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'metadata': self.metadata
        }

class MetricsDatabase:
    """Database for storing metrics and alerts."""
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize the database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    value REAL NOT NULL,
                    tags TEXT,
                    metric_type TEXT DEFAULT 'gauge'
                )
            """)
            
            # Alerts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    alert_id TEXT PRIMARY KEY,
                    alert_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    tenant_id TEXT,
                    resource_type TEXT,
                    threshold_value REAL,
                    current_value REAL,
                    resolved_at TEXT,
                    metadata TEXT
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_name_time ON metrics(metric_name, timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_tags ON metrics(tags)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_type_time ON alerts(alert_type, timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_tenant ON alerts(tenant_id)")
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper cleanup."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        try:
            yield conn
        finally:
            conn.close()
    
    def store_metric(self, metric_name: str, point: MetricPoint) -> None:
        """Store a metric point."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO metrics (metric_name, timestamp, value, tags, metric_type)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    metric_name,
                    point.timestamp.isoformat(),
                    point.value,
                    json.dumps(point.tags),
                    point.metric_type.value
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to store metric {metric_name}: {e}")
    
    def store_alert(self, alert: Alert) -> None:
        """Store an alert."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO alerts 
                    (alert_id, alert_type, severity, message, timestamp, tenant_id,
                     resource_type, threshold_value, current_value, resolved_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    alert.alert_id,
                    alert.alert_type,
                    alert.severity.value,
                    alert.message,
                    alert.timestamp.isoformat(),
                    alert.tenant_id,
                    alert.resource_type.value if alert.resource_type else None,
                    alert.threshold_value,
                    alert.current_value,
                    alert.resolved_at.isoformat() if alert.resolved_at else None,
                    json.dumps(alert.metadata)
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to store alert {alert.alert_id}: {e}")
    
    def get_metrics(
        self,
        metric_name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tags: Optional[Dict[str, str]] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Get metrics with filtering."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM metrics WHERE metric_name = ?"
                params = [metric_name]
                
                if start_time:
                    query += " AND timestamp >= ?"
                    params.append(start_time.isoformat())
                
                if end_time:
                    query += " AND timestamp <= ?"
                    params.append(end_time.isoformat())
                
                if tags:
                    for key, value in tags.items():
                        query += " AND tags LIKE ?"
                        params.append(f'%"{key}": "{value}"%')
                
                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                # Convert to dictionaries
                columns = [desc[0] for desc in cursor.description]
                metrics = []
                for row in rows:
                    metric_dict = dict(zip(columns, row))
                    # Parse JSON tags
                    if metric_dict['tags']:
                        metric_dict['tags'] = json.loads(metric_dict['tags'])
                    metrics.append(metric_dict)
                
                return metrics
                
        except Exception as e:
            logger.error(f"Failed to get metrics for {metric_name}: {e}")
            return []
    
    def get_alerts(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tenant_id: Optional[str] = None,
        severity: Optional[AlertSeverity] = None,
        resolved: Optional[bool] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Get alerts with filtering."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM alerts WHERE 1=1"
                params = []
                
                if start_time:
                    query += " AND timestamp >= ?"
                    params.append(start_time.isoformat())
                
                if end_time:
                    query += " AND timestamp <= ?"
                    params.append(end_time.isoformat())
                
                if tenant_id:
                    query += " AND tenant_id = ?"
                    params.append(tenant_id)
                
                if severity:
                    query += " AND severity = ?"
                    params.append(severity.value)
                
                if resolved is not None:
                    if resolved:
                        query += " AND resolved_at IS NOT NULL"
                    else:
                        query += " AND resolved_at IS NULL"
                
                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                # Convert to dictionaries
                columns = [desc[0] for desc in cursor.description]
                alerts = []
                for row in rows:
                    alert_dict = dict(zip(columns, row))
                    # Parse JSON metadata
                    if alert_dict['metadata']:
                        alert_dict['metadata'] = json.loads(alert_dict['metadata'])
                    alerts.append(alert_dict)
                
                return alerts
                
        except Exception as e:
            logger.error(f"Failed to get alerts: {e}")
            return []

class ResourceUsageTracker:
    """Tracks detailed resource usage over time."""
    
    def __init__(self):
        self.usage_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.current_usage: Dict[str, float] = {}
        self.peak_usage: Dict[str, float] = {}
        self.usage_totals: Dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()
    
    def record_usage(
        self,
        resource_key: str,
        value: float,
        timestamp: Optional[datetime] = None
    ) -> None:
        """Record resource usage."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        with self._lock:
            # Update current usage
            self.current_usage[resource_key] = value
            
            # Update peak usage
            if resource_key not in self.peak_usage or value > self.peak_usage[resource_key]:
                self.peak_usage[resource_key] = value
            
            # Add to history
            self.usage_history[resource_key].append({
                'timestamp': timestamp,
                'value': value
            })
            
            # Update totals (for cumulative metrics)
            self.usage_totals[resource_key] += value
    
    def get_current_usage(self, resource_key: str) -> float:
        """Get current usage for a resource."""
        with self._lock:
            return self.current_usage.get(resource_key, 0.0)
    
    def get_peak_usage(self, resource_key: str) -> float:
        """Get peak usage for a resource."""
        with self._lock:
            return self.peak_usage.get(resource_key, 0.0)
    
    def get_average_usage(
        self,
        resource_key: str,
        time_window: Optional[timedelta] = None
    ) -> float:
        """Get average usage over time window."""
        with self._lock:
            history = self.usage_history.get(resource_key, deque())
            if not history:
                return 0.0
            
            if time_window:
                cutoff = datetime.now(timezone.utc) - time_window
                relevant_points = [
                    point for point in history
                    if point['timestamp'] >= cutoff
                ]
            else:
                relevant_points = list(history)
            
            if not relevant_points:
                return 0.0
            
            return sum(point['value'] for point in relevant_points) / len(relevant_points)
    
    def get_usage_trend(
        self,
        resource_key: str,
        time_window: timedelta = timedelta(hours=1)
    ) -> float:
        """Get usage trend (positive = increasing, negative = decreasing)."""
        with self._lock:
            history = self.usage_history.get(resource_key, deque())
            if len(history) < 2:
                return 0.0
            
            cutoff = datetime.now(timezone.utc) - time_window
            relevant_points = [
                point for point in history
                if point['timestamp'] >= cutoff
            ]
            
            if len(relevant_points) < 2:
                return 0.0
            
            # Simple linear trend calculation
            first_value = relevant_points[0]['value']
            last_value = relevant_points[-1]['value']
            
            return last_value - first_value

class AlertManager:
    """Manages alert generation and notification."""
    
    def __init__(self, database: MetricsDatabase):
        self.database = database
        self.alert_handlers: List[Callable[[Alert], None]] = []
        self.alert_rules: Dict[str, Dict[str, Any]] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: deque = deque(maxlen=10000)
        self._lock = threading.Lock()
    
    def add_alert_handler(self, handler: Callable[[Alert], None]) -> None:
        """Add an alert handler function."""
        self.alert_handlers.append(handler)
        logger.debug(f"Added alert handler: {handler}")
    
    def add_alert_rule(
        self,
        rule_name: str,
        metric_name: str,
        threshold: float,
        comparison: str = "greater",  # greater, less, equal
        severity: AlertSeverity = AlertSeverity.WARNING,
        tenant_id: Optional[str] = None,
        resource_type: Optional[ResourceType] = None,
        time_window: timedelta = timedelta(minutes=5),
        min_duration: timedelta = timedelta(minutes=1)
    ) -> None:
        """Add an alert rule."""
        rule = {
            'metric_name': metric_name,
            'threshold': threshold,
            'comparison': comparison,
            'severity': severity,
            'tenant_id': tenant_id,
            'resource_type': resource_type,
            'time_window': time_window,
            'min_duration': min_duration,
            'last_triggered': None,
            'consecutive_violations': 0
        }
        
        self.alert_rules[rule_name] = rule
        logger.info(f"Added alert rule: {rule_name}")
    
    def check_alert_rules(self, current_metrics: Dict[str, float]) -> List[Alert]:
        """Check all alert rules against current metrics."""
        alerts = []
        now = datetime.now(timezone.utc)
        
        for rule_name, rule in self.alert_rules.items():
            metric_name = rule['metric_name']
            current_value = current_metrics.get(metric_name)
            
            if current_value is None:
                continue
            
            # Check if threshold is violated
            violated = False
            threshold = rule['threshold']
            comparison = rule['comparison']
            
            if comparison == "greater" and current_value > threshold:
                violated = True
            elif comparison == "less" and current_value < threshold:
                violated = True
            elif comparison == "equal" and abs(current_value - threshold) < 0.001:
                violated = True
            
            if violated:
                rule['consecutive_violations'] += 1
                
                # Check if violation has lasted long enough
                min_violations = max(1, int(rule['min_duration'].total_seconds() / 60))  # Assume 1 minute intervals
                
                if rule['consecutive_violations'] >= min_violations:
                    # Generate alert
                    alert_id = f"{rule_name}_{int(now.timestamp())}"
                    
                    alert = Alert(
                        alert_id=alert_id,
                        alert_type=rule_name,
                        severity=rule['severity'],
                        message=f"Metric {metric_name} {comparison} threshold: {current_value} {comparison} {threshold}",
                        tenant_id=rule['tenant_id'],
                        resource_type=rule['resource_type'],
                        threshold_value=threshold,
                        current_value=current_value,
                        metadata={
                            'rule_name': rule_name,
                            'consecutive_violations': rule['consecutive_violations']
                        }
                    )
                    
                    alerts.append(alert)
                    rule['last_triggered'] = now
            else:
                rule['consecutive_violations'] = 0
        
        return alerts
    
    async def trigger_alert(self, alert: Alert) -> None:
        """Trigger an alert and notify handlers."""
        with self._lock:
            # Check if this is a duplicate alert
            existing_alert_key = f"{alert.alert_type}_{alert.tenant_id}_{alert.resource_type}"
            
            if existing_alert_key in self.active_alerts:
                # Update existing alert
                existing_alert = self.active_alerts[existing_alert_key]
                existing_alert.current_value = alert.current_value
                existing_alert.timestamp = alert.timestamp
                alert = existing_alert
            else:
                # New alert
                self.active_alerts[existing_alert_key] = alert
                self.alert_history.append(alert)
        
        # Store in database
        self.database.store_alert(alert)
        
        # Notify handlers
        for handler in self.alert_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(alert)
                else:
                    handler(alert)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")
        
        logger.warning(f"Alert triggered: {alert.message}")
    
    async def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an active alert."""
        with self._lock:
            # Find and resolve alert
            for key, alert in self.active_alerts.items():
                if alert.alert_id == alert_id:
                    alert.resolved_at = datetime.now(timezone.utc)
                    del self.active_alerts[key]
                    
                    # Update in database
                    self.database.store_alert(alert)
                    
                    logger.info(f"Resolved alert: {alert_id}")
                    return True
        
        return False
    
    def get_active_alerts(
        self,
        tenant_id: Optional[str] = None,
        severity: Optional[AlertSeverity] = None
    ) -> List[Alert]:
        """Get currently active alerts."""
        with self._lock:
            alerts = list(self.active_alerts.values())
        
        if tenant_id:
            alerts = [a for a in alerts if a.tenant_id == tenant_id]
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        return alerts

class ResourceMonitor:
    """Main resource monitoring system."""
    
    def __init__(self, db_path: str = "./data/monitoring/metrics.db"):
        self.database = MetricsDatabase(db_path)
        self.usage_tracker = ResourceUsageTracker()
        self.alert_manager = AlertManager(self.database)
        
        # Monitoring configuration
        self.monitoring_interval = 60.0  # seconds
        self.metric_retention_days = 30
        
        # Background tasks
        self.is_running = False
        self.monitoring_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        
        # Resource allocator reference
        self.resource_allocator: Optional[ResourceAllocationSystem] = None
        
        self._setup_default_alerts()
    
    def set_resource_allocator(self, allocator: ResourceAllocationSystem) -> None:
        """Set the resource allocator to monitor."""
        self.resource_allocator = allocator
    
    def _setup_default_alerts(self) -> None:
        """Set up default alert rules."""
        # System resource alerts
        self.alert_manager.add_alert_rule(
            "high_cpu_usage",
            "cpu_utilization_percent",
            85.0,
            "greater",
            AlertSeverity.WARNING
        )
        
        self.alert_manager.add_alert_rule(
            "critical_cpu_usage",
            "cpu_utilization_percent",
            95.0,
            "greater",
            AlertSeverity.CRITICAL
        )
        
        self.alert_manager.add_alert_rule(
            "high_memory_usage",
            "memory_utilization_percent",
            85.0,
            "greater",
            AlertSeverity.WARNING
        )
        
        self.alert_manager.add_alert_rule(
            "critical_memory_usage",
            "memory_utilization_percent",
            95.0,
            "greater",
            AlertSeverity.CRITICAL
        )
        
        if GPU_AVAILABLE:
            self.alert_manager.add_alert_rule(
                "high_gpu_memory_usage",
                "gpu_memory_utilization_percent",
                90.0,
                "greater",
                AlertSeverity.WARNING
            )
    
    async def collect_system_metrics(self) -> Dict[str, float]:
        """Collect current system metrics."""
        metrics = {}
        timestamp = datetime.now(timezone.utc)
        
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            metrics['cpu_utilization_percent'] = cpu_percent
            
            # Memory metrics
            memory = psutil.virtual_memory()
            metrics['memory_total_mb'] = memory.total / (1024 * 1024)
            metrics['memory_used_mb'] = memory.used / (1024 * 1024)
            metrics['memory_available_mb'] = memory.available / (1024 * 1024)
            metrics['memory_utilization_percent'] = memory.percent
            
            # Disk metrics
            disk_usage = psutil.disk_usage('/')
            metrics['disk_total_gb'] = disk_usage.total / (1024 * 1024 * 1024)
            metrics['disk_used_gb'] = disk_usage.used / (1024 * 1024 * 1024)
            metrics['disk_free_gb'] = disk_usage.free / (1024 * 1024 * 1024)
            metrics['disk_utilization_percent'] = (disk_usage.used / disk_usage.total) * 100
            
            # Disk I/O metrics
            disk_io = psutil.disk_io_counters()
            if disk_io:
                metrics['disk_read_bytes_total'] = disk_io.read_bytes
                metrics['disk_write_bytes_total'] = disk_io.write_bytes
                metrics['disk_read_ops_total'] = disk_io.read_count
                metrics['disk_write_ops_total'] = disk_io.write_count
            
            # Network metrics
            network_io = psutil.net_io_counters()
            if network_io:
                metrics['network_bytes_sent_total'] = network_io.bytes_sent
                metrics['network_bytes_recv_total'] = network_io.bytes_recv
                metrics['network_packets_sent_total'] = network_io.packets_sent
                metrics['network_packets_recv_total'] = network_io.packets_recv
            
            # Load average (Unix-like systems)
            if hasattr(psutil, 'getloadavg'):
                load_avg = psutil.getloadavg()
                metrics['load_average_1min'] = load_avg[0]
                metrics['load_average_5min'] = load_avg[1]
                metrics['load_average_15min'] = load_avg[2]
            
            # GPU metrics
            if GPU_AVAILABLE:
                try:
                    gpus = GPUtil.getGPUs()
                    for i, gpu in enumerate(gpus):
                        metrics[f'gpu_{i}_memory_total_mb'] = gpu.memoryTotal
                        metrics[f'gpu_{i}_memory_used_mb'] = gpu.memoryUsed
                        metrics[f'gpu_{i}_memory_free_mb'] = gpu.memoryFree
                        metrics[f'gpu_{i}_utilization_percent'] = gpu.load * 100
                        metrics[f'gpu_{i}_temperature_celsius'] = gpu.temperature
                    
                    if gpus:
                        # Overall GPU metrics
                        total_memory = sum(gpu.memoryTotal for gpu in gpus)
                        used_memory = sum(gpu.memoryUsed for gpu in gpus)
                        metrics['gpu_memory_utilization_percent'] = (used_memory / total_memory) * 100 if total_memory > 0 else 0
                        metrics['gpu_average_utilization_percent'] = sum(gpu.load for gpu in gpus) * 100 / len(gpus)
                        
                except Exception as e:
                    logger.warning(f"Failed to collect GPU metrics: {e}")
            
            # Store metrics in database and usage tracker
            for metric_name, value in metrics.items():
                point = MetricPoint(
                    timestamp=timestamp,
                    value=value,
                    metric_type=MetricType.GAUGE
                )
                self.database.store_metric(metric_name, point)
                self.usage_tracker.record_usage(metric_name, value, timestamp)
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
        
        return metrics
    
    async def collect_resource_allocation_metrics(self) -> Dict[str, float]:
        """Collect resource allocation metrics."""
        metrics = {}
        
        if not self.resource_allocator:
            return metrics
        
        try:
            # Get system status from resource allocator
            status = self.resource_allocator.get_system_status()
            
            # CPU allocation metrics
            cpu_status = status.get('cpu', {})
            if cpu_status:
                metrics['allocated_cpu_cores'] = cpu_status.get('allocated_cores', 0)
                metrics['available_cpu_cores'] = cpu_status.get('available_cores', 0)
                metrics['cpu_allocation_percent'] = (
                    cpu_status.get('allocated_cores', 0) / cpu_status.get('total_cores', 1) * 100
                )
            
            # Memory allocation metrics
            memory_status = status.get('memory', {})
            if memory_status:
                metrics['allocated_memory_mb'] = memory_status.get('allocated_mb', 0)
                metrics['available_memory_mb'] = memory_status.get('available_mb', 0)
                metrics['memory_allocation_percent'] = (
                    memory_status.get('allocated_mb', 0) / memory_status.get('total_mb', 1) * 100
                )
            
            # GPU allocation metrics
            gpu_status = status.get('gpu', {})
            if gpu_status.get('available'):
                total_gpu_memory = sum(gpu['memory_total'] for gpu in gpu_status.get('gpus', []))
                allocated_gpu_memory = sum(gpu['memory_allocated'] for gpu in gpu_status.get('gpus', []))
                
                metrics['allocated_gpu_memory_mb'] = allocated_gpu_memory
                metrics['gpu_memory_allocation_percent'] = (
                    allocated_gpu_memory / total_gpu_memory * 100 if total_gpu_memory > 0 else 0
                )
            
            # Disk I/O allocation metrics
            disk_status = status.get('disk_io', {})
            if disk_status:
                metrics['allocated_disk_io_mbps'] = disk_status.get('allocated_throughput_mbps', 0)
                metrics['available_disk_io_mbps'] = disk_status.get('available_throughput_mbps', 0)
                metrics['disk_io_allocation_percent'] = (
                    disk_status.get('allocated_throughput_mbps', 0) / 
                    disk_status.get('max_throughput_mbps', 1) * 100
                )
            
            # Overall allocation metrics
            allocation_status = status.get('allocations', {})
            if allocation_status:
                metrics['total_active_allocations'] = allocation_status.get('total', 0)
                for status_name, count in allocation_status.get('by_status', {}).items():
                    metrics[f'allocations_{status_name}'] = count
            
            # Store metrics
            timestamp = datetime.now(timezone.utc)
            for metric_name, value in metrics.items():
                point = MetricPoint(
                    timestamp=timestamp,
                    value=value,
                    metric_type=MetricType.GAUGE
                )
                self.database.store_metric(metric_name, point)
                self.usage_tracker.record_usage(metric_name, value, timestamp)
        
        except Exception as e:
            logger.error(f"Failed to collect resource allocation metrics: {e}")
        
        return metrics
    
    async def collect_tenant_metrics(self) -> Dict[str, float]:
        """Collect per-tenant metrics."""
        metrics = {}
        
        if not self.resource_allocator:
            return metrics
        
        try:
            # Get tenant usage from resource allocator
            for tenant_id in self.resource_allocator.tenant_usage.keys():
                tenant_usage = self.resource_allocator.get_tenant_usage(tenant_id)
                
                # Current usage metrics
                current_usage = tenant_usage.get('current_usage', {})
                for resource_type, usage in current_usage.items():
                    metric_name = f'tenant_{tenant_id}_{resource_type}_usage'
                    metrics[metric_name] = usage
                
                # Allocation count metrics
                metrics[f'tenant_{tenant_id}_active_allocations'] = tenant_usage.get('active_allocations', 0)
                metrics[f'tenant_{tenant_id}_total_allocations'] = tenant_usage.get('total_allocations', 0)
            
            # Store metrics
            timestamp = datetime.now(timezone.utc)
            for metric_name, value in metrics.items():
                point = MetricPoint(
                    timestamp=timestamp,
                    value=value,
                    metric_type=MetricType.GAUGE,
                    tags={'metric_category': 'tenant'}
                )
                self.database.store_metric(metric_name, point)
                self.usage_tracker.record_usage(metric_name, value, timestamp)
        
        except Exception as e:
            logger.error(f"Failed to collect tenant metrics: {e}")
        
        return metrics
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        logger.info("Resource monitoring started")
        
        while self.is_running:
            try:
                # Collect all metrics
                system_metrics = await self.collect_system_metrics()
                allocation_metrics = await self.collect_resource_allocation_metrics()
                tenant_metrics = await self.collect_tenant_metrics()
                
                # Combine all metrics
                all_metrics = {**system_metrics, **allocation_metrics, **tenant_metrics}
                
                # Check alert rules
                alerts = self.alert_manager.check_alert_rules(all_metrics)
                
                # Trigger alerts
                for alert in alerts:
                    await self.alert_manager.trigger_alert(alert)
                
                # Wait for next interval
                await asyncio.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error
        
        logger.info("Resource monitoring stopped")
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop for old metrics."""
        while self.is_running:
            try:
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.metric_retention_days)
                
                # Clean up old metrics (simplified - in production you'd want proper cleanup)
                logger.debug(f"Cleaning up metrics older than {cutoff_date}")
                
                await asyncio.sleep(3600)  # Run cleanup every hour
                
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(3600)
    
    async def start_monitoring(self) -> None:
        """Start the monitoring system."""
        if self.is_running:
            return
        
        self.is_running = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("Resource monitoring system started")
    
    async def stop_monitoring(self) -> None:
        """Stop the monitoring system."""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Cancel tasks
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Resource monitoring system stopped")
    
    def generate_usage_report(
        self,
        start_time: datetime,
        end_time: datetime,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a comprehensive usage report."""
        report = {
            'report_period': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat()
            },
            'tenant_id': tenant_id,
            'system_metrics': {},
            'tenant_metrics': {},
            'alerts': [],
            'resource_efficiency': {}
        }
        
        try:
            # Get system metrics for the period
            system_metric_names = [
                'cpu_utilization_percent',
                'memory_utilization_percent',
                'disk_utilization_percent'
            ]
            
            for metric_name in system_metric_names:
                metrics = self.database.get_metrics(metric_name, start_time, end_time)
                if metrics:
                    values = [m['value'] for m in metrics]
                    report['system_metrics'][metric_name] = {
                        'average': sum(values) / len(values),
                        'maximum': max(values),
                        'minimum': min(values),
                        'data_points': len(values)
                    }
            
            # Get alerts for the period
            alerts = self.database.get_alerts(
                start_time=start_time,
                end_time=end_time,
                tenant_id=tenant_id
            )
            
            report['alerts'] = {
                'total_alerts': len(alerts),
                'by_severity': {},
                'by_type': {}
            }
            
            # Count alerts by severity and type
            for alert in alerts:
                severity = alert['severity']
                alert_type = alert['alert_type']
                
                report['alerts']['by_severity'][severity] = report['alerts']['by_severity'].get(severity, 0) + 1
                report['alerts']['by_type'][alert_type] = report['alerts']['by_type'].get(alert_type, 0) + 1
            
            # Calculate resource efficiency
            if 'cpu_utilization_percent' in report['system_metrics'] and 'allocated_cpu_cores' in report['system_metrics']:
                cpu_efficiency = (
                    report['system_metrics']['cpu_utilization_percent']['average'] /
                    max(1, report['system_metrics'].get('cpu_allocation_percent', {}).get('average', 1))
                )
                report['resource_efficiency']['cpu'] = cpu_efficiency
            
        except Exception as e:
            logger.error(f"Failed to generate usage report: {e}")
            report['error'] = str(e)
        
        return report
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring system status."""
        return {
            'is_running': self.is_running,
            'monitoring_interval': self.monitoring_interval,
            'active_alerts': len(self.alert_manager.get_active_alerts()),
            'alert_rules': len(self.alert_manager.alert_rules),
            'alert_handlers': len(self.alert_manager.alert_handlers),
            'metrics_collected': len(self.usage_tracker.current_usage),
            'database_path': str(self.database.db_path)
        }

# Global resource monitor instance
resource_monitor = ResourceMonitor() 