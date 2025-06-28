"""
Comprehensive Monitoring and Logging System

This module provides structured logging, error tracking, performance monitoring,
and system metrics collection for the Enterprise RAG Platform.
"""

import logging
import logging.handlers
import json
import time
import psutil
import GPUtil
import traceback
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import threading
from contextlib import contextmanager

from fastapi import Request, Response
# from sqlalchemy.orm import Session
# from sqlalchemy import text

from ..config.settings import get_settings
# from ..db.session import get_db

settings = get_settings()


class LogLevel(Enum):
    """Enhanced log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO" 
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class MetricType(Enum):
    """Types of metrics we track."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class ErrorEvent:
    """Structured error event."""
    timestamp: datetime
    error_type: str
    error_message: str
    traceback: str
    tenant_id: Optional[str] = None
    request_id: Optional[str] = None
    endpoint: Optional[str] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    severity: str = "ERROR"
    tags: Dict[str, str] = None


@dataclass
class PerformanceMetric:
    """Performance metric data."""
    timestamp: datetime
    metric_name: str
    metric_type: MetricType
    value: float
    tags: Dict[str, str] = None
    description: Optional[str] = None


@dataclass
class SystemMetrics:
    """System resource metrics."""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    disk_usage_percent: float
    gpu_utilization: Optional[float] = None
    gpu_memory_percent: Optional[float] = None
    active_connections: int = 0
    
    
class StructuredFormatter(logging.Formatter):
    """JSON structured logging formatter."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        
        # Base log data
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add extra fields if present
        if hasattr(record, 'tenant_id'):
            log_data['tenant_id'] = record.tenant_id
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
        if hasattr(record, 'duration'):
            log_data['duration'] = record.duration
        if hasattr(record, 'tags'):
            log_data['tags'] = record.tags
            
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': self.formatException(record.exc_info)
            }
            
        return json.dumps(log_data, default=str)


class ErrorTracker:
    """Centralized error tracking and notification system."""
    
    def __init__(self):
        self.error_handlers: List[Callable] = []
        self.error_cache: Dict[str, ErrorEvent] = {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
    def add_error_handler(self, handler: Callable[[ErrorEvent], None]):
        """Add an error event handler."""
        self.error_handlers.append(handler)
        
    def track_error(
        self, 
        error: Exception, 
        context: Dict[str, Any] = None,
        severity: str = "ERROR"
    ) -> str:
        """Track an error event and notify handlers."""
        
        error_id = f"{type(error).__name__}_{hash(str(error))}_{int(time.time())}"
        
        error_event = ErrorEvent(
            timestamp=datetime.now(timezone.utc),
            error_type=type(error).__name__,
            error_message=str(error),
            traceback=traceback.format_exc(),
            severity=severity,
            tenant_id=context.get('tenant_id') if context else None,
            request_id=context.get('request_id') if context else None,
            endpoint=context.get('endpoint') if context else None,
            user_agent=context.get('user_agent') if context else None,
            ip_address=context.get('ip_address') if context else None,
            tags=context.get('tags') if context else None
        )
        
        # Store in cache
        self.error_cache[error_id] = error_event
        
        # Notify handlers
        for handler in self.error_handlers:
            try:
                handler(error_event)
            except Exception as e:
                self.logger.error(f"Error handler failed: {e}")
                
        return error_id
        
    def get_error_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get error statistics for the specified time period."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        recent_errors = [
            error for error in self.error_cache.values()
            if error.timestamp > cutoff
        ]
        
        error_counts = {}
        for error in recent_errors:
            error_counts[error.error_type] = error_counts.get(error.error_type, 0) + 1
            
        return {
            'total_errors': len(recent_errors),
            'error_types': error_counts,
            'recent_errors': [
                {
                    'timestamp': error.timestamp.isoformat(),
                    'type': error.error_type,
                    'message': error.error_message,
                    'severity': error.severity,
                    'tenant_id': error.tenant_id
                }
                for error in sorted(recent_errors, key=lambda x: x.timestamp, reverse=True)[:10]
            ]
        }


class PerformanceMonitor:
    """Performance monitoring and alerting system."""
    
    def __init__(self):
        self.metrics: List[PerformanceMetric] = []
        self.thresholds: Dict[str, float] = {
            'query_time_ms': 2000,  # 2 seconds
            'sync_time_ms': 300000,  # 5 minutes
            'api_response_time_ms': 1000,  # 1 second
            'cpu_percent': 80,
            'memory_percent': 85,
            'gpu_utilization': 95
        }
        self.alert_handlers: List[Callable] = []
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
    def add_alert_handler(self, handler: Callable[[str, float, float], None]):
        """Add a performance alert handler."""
        self.alert_handlers.append(handler)
        
    def record_metric(
        self, 
        name: str, 
        value: float, 
        metric_type: MetricType = MetricType.GAUGE,
        tags: Dict[str, str] = None,
        description: str = None
    ):
        """Record a performance metric."""
        metric = PerformanceMetric(
            timestamp=datetime.now(timezone.utc),
            metric_name=name,
            metric_type=metric_type,
            value=value,
            tags=tags or {},
            description=description
        )
        
        self.metrics.append(metric)
        
        # Check thresholds
        threshold = self.thresholds.get(name)
        if threshold and value > threshold:
            self._trigger_alert(name, value, threshold)
            
        # Keep only recent metrics (last 24 hours)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        self.metrics = [m for m in self.metrics if m.timestamp > cutoff]
        
    def _trigger_alert(self, metric_name: str, value: float, threshold: float):
        """Trigger performance alert."""
        self.logger.warning(
            f"Performance threshold exceeded: {metric_name}={value:.2f} > {threshold:.2f}",
            extra={'metric_name': metric_name, 'value': value, 'threshold': threshold}
        )
        
        for handler in self.alert_handlers:
            try:
                handler(metric_name, value, threshold)
            except Exception as e:
                self.logger.error(f"Alert handler failed: {e}")
                
    @contextmanager
    def measure_time(self, operation_name: str, tags: Dict[str, str] = None):
        """Context manager to measure operation time."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = (time.time() - start_time) * 1000  # Convert to milliseconds
            self.record_metric(
                f"{operation_name}_time_ms",
                duration,
                MetricType.TIMER,
                tags,
                f"Execution time for {operation_name}"
            )
            
    def get_metrics_summary(self, hours: int = 1) -> Dict[str, Any]:
        """Get metrics summary for the specified time period."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        recent_metrics = [m for m in self.metrics if m.timestamp > cutoff]
        
        # Group by metric name
        grouped = {}
        for metric in recent_metrics:
            if metric.metric_name not in grouped:
                grouped[metric.metric_name] = []
            grouped[metric.metric_name].append(metric.value)
            
        # Calculate statistics
        summary = {}
        for name, values in grouped.items():
            if values:
                summary[name] = {
                    'count': len(values),
                    'min': min(values),
                    'max': max(values),
                    'avg': sum(values) / len(values),
                    'latest': values[-1]
                }
                
        return summary


class SystemMonitor:
    """System resource monitoring."""
    
    def __init__(self):
        self.metrics_history: List[SystemMetrics] = []
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
    def start_monitoring(self, interval_seconds: int = 60):
        """Start continuous system monitoring."""
        if self.monitoring_active:
            return
            
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self.monitor_thread.start()
        self.logger.info("System monitoring started")
        
    def stop_monitoring(self):
        """Stop system monitoring."""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        self.logger.info("System monitoring stopped")
        
    def _monitor_loop(self, interval_seconds: int):
        """Main monitoring loop."""
        while self.monitoring_active:
            try:
                metrics = self.collect_system_metrics()
                self.metrics_history.append(metrics)
                
                # Keep only last 24 hours of data
                cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                self.metrics_history = [
                    m for m in self.metrics_history if m.timestamp > cutoff
                ]
                
                time.sleep(interval_seconds)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(interval_seconds)
                
    def collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics."""
        # CPU and Memory
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # GPU metrics (if available)
        gpu_utilization = None
        gpu_memory_percent = None
        
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                # Use first GPU
                gpu = gpus[0]
                gpu_utilization = gpu.load * 100
                gpu_memory_percent = (gpu.memoryUsed / gpu.memoryTotal) * 100
        except Exception:
            pass  # GPU monitoring optional
            
        # Database connections (if possible)
        active_connections = 0
        try:
            pass  # DB connection count optional
        except Exception:
            pass  # DB connection count optional
            
        return SystemMetrics(
            timestamp=datetime.now(timezone.utc),
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            disk_usage_percent=disk.percent,
            gpu_utilization=gpu_utilization,
            gpu_memory_percent=gpu_memory_percent,
            active_connections=active_connections
        )
        
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status."""
        if not self.metrics_history:
            return {"status": "no_data"}
            
        latest = self.metrics_history[-1]
        
        # Determine overall health
        health_status = "healthy"
        if latest.cpu_percent > 80 or latest.memory_percent > 85:
            health_status = "warning"
        if latest.cpu_percent > 95 or latest.memory_percent > 95:
            health_status = "critical"
            
        return {
            "status": health_status,
            "timestamp": latest.timestamp.isoformat(),
            "cpu_percent": latest.cpu_percent,
            "memory_percent": latest.memory_percent,
            "disk_usage_percent": latest.disk_usage_percent,
            "gpu_utilization": latest.gpu_utilization,
            "gpu_memory_percent": latest.gpu_memory_percent,
            "active_connections": latest.active_connections,
            "metrics_count": len(self.metrics_history)
        }


class LogManager:
    """Centralized log management system."""
    
    def __init__(self):
        self.loggers: Dict[str, logging.Logger] = {}
        self.setup_logging()
        
    def setup_logging(self):
        """Configure structured logging."""
        
        # Create logs directory
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Root logger configuration
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, settings.log_level))
        
        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            
        # Console handler with structured formatting
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        if settings.debug:
            # Simple format for development
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        else:
            # Structured JSON format for production
            console_formatter = StructuredFormatter()
            
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        # File handler with rotation
        if settings.log_file:
            file_handler = logging.handlers.RotatingFileHandler(
                settings.log_file,
                maxBytes=50 * 1024 * 1024,  # 50MB
                backupCount=10
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(StructuredFormatter())
            root_logger.addHandler(file_handler)
        else:
            # Default rotating file handler
            file_handler = logging.handlers.RotatingFileHandler(
                log_dir / "rag_platform.log",
                maxBytes=50 * 1024 * 1024,  # 50MB
                backupCount=10
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(StructuredFormatter())
            root_logger.addHandler(file_handler)
            
        # Separate error log
        error_handler = logging.handlers.RotatingFileHandler(
            log_dir / "errors.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(error_handler)
        
    def get_logger(self, name: str) -> logging.Logger:
        """Get a configured logger."""
        if name not in self.loggers:
            self.loggers[name] = logging.getLogger(name)
        return self.loggers[name]


# Global instances
error_tracker = ErrorTracker()
performance_monitor = PerformanceMonitor()
system_monitor = SystemMonitor()
log_manager = LogManager()


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance."""
    return log_manager.get_logger(name)


async def monitoring_middleware(request: Request, call_next):
    """Middleware for request monitoring and logging."""
    start_time = time.time()
    request_id = f"req_{int(start_time * 1000)}"
    
    # Add request ID to request state
    request.state.request_id = request_id
    
    logger = get_logger("monitoring.requests")
    
    # Log request start
    logger.info(
        f"Request started: {request.method} {request.url.path}",
        extra={
            'request_id': request_id,
            'method': request.method,
            'path': request.url.path,
            'ip_address': request.client.host if request.client else None,
            'user_agent': request.headers.get('User-Agent')
        }
    )
    
    try:
        response = await call_next(request)
        
        # Record performance metric
        duration = (time.time() - start_time) * 1000
        performance_monitor.record_metric(
            "api_response_time_ms",
            duration,
            MetricType.TIMER,
            {
                'method': request.method,
                'path': request.url.path,
                'status_code': str(response.status_code)
            }
        )
        
        # Log request completion
        logger.info(
            f"Request completed: {request.method} {request.url.path} - {response.status_code}",
            extra={
                'request_id': request_id,
                'status_code': response.status_code,
                'duration': duration
            }
        )
        
        # Add monitoring headers
        response.headers['X-Request-ID'] = request_id
        response.headers['X-Response-Time'] = f"{duration:.2f}ms"
        
        return response
        
    except Exception as e:
        # Track error
        error_context = {
            'request_id': request_id,
            'endpoint': f"{request.method} {request.url.path}",
            'ip_address': request.client.host if request.client else None,
            'user_agent': request.headers.get('User-Agent')
        }
        
        error_id = error_tracker.track_error(e, error_context)
        
        logger.error(
            f"Request failed: {request.method} {request.url.path}",
            extra={
                'request_id': request_id,
                'error_id': error_id,
                'error_type': type(e).__name__,
                'error_message': str(e)
            },
            exc_info=True
        )
        
        raise


def track_query_performance(tenant_id: str, query_text: str, response_time: float, success: bool):
    """Track query performance metrics."""
    performance_monitor.record_metric(
        "query_time_ms",
        response_time * 1000,
        MetricType.TIMER,
        {
            'tenant_id': tenant_id,
            'success': str(success),
            'query_length': str(len(query_text))
        },
        "RAG query processing time"
    )


def initialize_monitoring():
    """Initialize all monitoring components."""
    # Start system monitoring
    system_monitor.start_monitoring(interval_seconds=60)
    
    # Add default error handler
    def log_error_handler(error_event: ErrorEvent):
        logger = get_logger("monitoring.errors")
        logger.error(
            f"Error tracked: {error_event.error_type} - {error_event.error_message}",
            extra={
                'error_type': error_event.error_type,
                'tenant_id': error_event.tenant_id,
                'request_id': error_event.request_id,
                'severity': error_event.severity
            }
        )
    
    error_tracker.add_error_handler(log_error_handler)
    
    # Add default performance alert handler
    def log_performance_alert(metric_name: str, value: float, threshold: float):
        logger = get_logger("monitoring.performance")
        logger.warning(
            f"Performance alert: {metric_name} exceeded threshold",
            extra={
                'metric_name': metric_name,
                'value': value,
                'threshold': threshold
            }
        )
    
    performance_monitor.add_alert_handler(log_performance_alert)
    
    logger = get_logger("monitoring")
    logger.info("Monitoring system initialized")


def shutdown_monitoring():
    """Shutdown monitoring components."""
    system_monitor.stop_monitoring()
    logger = get_logger("monitoring")
    logger.info("Monitoring system shutdown") 