"""
Comprehensive sync logging system.

This module provides detailed logging, metrics collection,
status tracking, and alerting for sync operations.
"""

import asyncio
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from collections import defaultdict, deque
import threading
import sqlite3
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class SyncEventType(Enum):
    """Types of sync events."""
    SYNC_STARTED = "sync_started"
    SYNC_COMPLETED = "sync_completed"
    SYNC_FAILED = "sync_failed"
    SYNC_CANCELLED = "sync_cancelled"
    FILE_PROCESSED = "file_processed"
    CONFLICT_DETECTED = "conflict_detected"
    CONFLICT_RESOLVED = "conflict_resolved"
    ERROR_OCCURRED = "error_occurred"
    WARNING_ISSUED = "warning_issued"
    QUOTA_EXCEEDED = "quota_exceeded"
    PERFORMANCE_ALERT = "performance_alert"

class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class SyncEvent:
    """Represents a sync-related event."""
    event_id: str
    event_type: SyncEventType
    tenant_id: str
    folder_name: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    operation_id: Optional[str] = None
    file_path: Optional[str] = None
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    duration: Optional[float] = None  # seconds
    bytes_processed: Optional[int] = None
    error_code: Optional[str] = None
    alert_level: AlertLevel = AlertLevel.INFO
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'tenant_id': self.tenant_id,
            'folder_name': self.folder_name,
            'timestamp': self.timestamp.isoformat(),
            'operation_id': self.operation_id,
            'file_path': self.file_path,
            'message': self.message,
            'details': self.details,
            'duration': self.duration,
            'bytes_processed': self.bytes_processed,
            'error_code': self.error_code,
            'alert_level': self.alert_level.value
        }

@dataclass
class SyncMetrics:
    """Metrics for sync operations."""
    tenant_id: str
    folder_name: str
    
    # Counters
    total_syncs: int = 0
    successful_syncs: int = 0
    failed_syncs: int = 0
    cancelled_syncs: int = 0
    
    # File metrics
    files_processed: int = 0
    files_created: int = 0
    files_updated: int = 0
    files_deleted: int = 0
    files_failed: int = 0
    
    # Data metrics
    bytes_transferred: int = 0
    bytes_failed: int = 0
    
    # Performance metrics
    avg_sync_duration: float = 0.0
    max_sync_duration: float = 0.0
    min_sync_duration: float = float('inf')
    
    # Conflict metrics
    conflicts_detected: int = 0
    conflicts_resolved: int = 0
    conflicts_manual: int = 0
    
    # Time range
    first_sync: Optional[datetime] = None
    last_sync: Optional[datetime] = None
    last_successful_sync: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'tenant_id': self.tenant_id,
            'folder_name': self.folder_name,
            'total_syncs': self.total_syncs,
            'successful_syncs': self.successful_syncs,
            'failed_syncs': self.failed_syncs,
            'cancelled_syncs': self.cancelled_syncs,
            'files_processed': self.files_processed,
            'files_created': self.files_created,
            'files_updated': self.files_updated,
            'files_deleted': self.files_deleted,
            'files_failed': self.files_failed,
            'bytes_transferred': self.bytes_transferred,
            'bytes_failed': self.bytes_failed,
            'avg_sync_duration': self.avg_sync_duration,
            'max_sync_duration': self.max_sync_duration,
            'min_sync_duration': self.min_sync_duration if self.min_sync_duration != float('inf') else 0,
            'conflicts_detected': self.conflicts_detected,
            'conflicts_resolved': self.conflicts_resolved,
            'conflicts_manual': self.conflicts_manual,
            'first_sync': self.first_sync.isoformat() if self.first_sync else None,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'last_successful_sync': self.last_successful_sync.isoformat() if self.last_successful_sync else None
        }

class SyncDatabase:
    """Database for storing sync events and metrics."""
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize the database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    folder_name TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    operation_id TEXT,
                    file_path TEXT,
                    message TEXT,
                    details TEXT,
                    duration REAL,
                    bytes_processed INTEGER,
                    error_code TEXT,
                    alert_level TEXT
                )
            """)
            
            # Metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_metrics (
                    tenant_id TEXT,
                    folder_name TEXT,
                    metric_date TEXT,
                    total_syncs INTEGER DEFAULT 0,
                    successful_syncs INTEGER DEFAULT 0,
                    failed_syncs INTEGER DEFAULT 0,
                    cancelled_syncs INTEGER DEFAULT 0,
                    files_processed INTEGER DEFAULT 0,
                    files_created INTEGER DEFAULT 0,
                    files_updated INTEGER DEFAULT 0,
                    files_deleted INTEGER DEFAULT 0,
                    files_failed INTEGER DEFAULT 0,
                    bytes_transferred INTEGER DEFAULT 0,
                    bytes_failed INTEGER DEFAULT 0,
                    avg_sync_duration REAL DEFAULT 0,
                    max_sync_duration REAL DEFAULT 0,
                    min_sync_duration REAL DEFAULT 0,
                    conflicts_detected INTEGER DEFAULT 0,
                    conflicts_resolved INTEGER DEFAULT 0,
                    conflicts_manual INTEGER DEFAULT 0,
                    first_sync TEXT,
                    last_sync TEXT,
                    last_successful_sync TEXT,
                    PRIMARY KEY (tenant_id, folder_name, metric_date)
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_tenant_folder ON sync_events(tenant_id, folder_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON sync_events(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON sync_events(event_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_tenant ON sync_metrics(tenant_id)")
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper cleanup."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        try:
            yield conn
        finally:
            conn.close()
    
    def store_event(self, event: SyncEvent) -> None:
        """Store a sync event."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO sync_events 
                    (event_id, event_type, tenant_id, folder_name, timestamp,
                     operation_id, file_path, message, details, duration,
                     bytes_processed, error_code, alert_level)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.event_id,
                    event.event_type.value,
                    event.tenant_id,
                    event.folder_name,
                    event.timestamp.isoformat(),
                    event.operation_id,
                    event.file_path,
                    event.message,
                    json.dumps(event.details),
                    event.duration,
                    event.bytes_processed,
                    event.error_code,
                    event.alert_level.value
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to store event {event.event_id}: {e}")
    
    def store_metrics(self, metrics: SyncMetrics, date: datetime) -> None:
        """Store daily metrics."""
        try:
            date_str = date.strftime('%Y-%m-%d')
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO sync_metrics 
                    (tenant_id, folder_name, metric_date, total_syncs, successful_syncs,
                     failed_syncs, cancelled_syncs, files_processed, files_created,
                     files_updated, files_deleted, files_failed, bytes_transferred,
                     bytes_failed, avg_sync_duration, max_sync_duration, min_sync_duration,
                     conflicts_detected, conflicts_resolved, conflicts_manual,
                     first_sync, last_sync, last_successful_sync)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metrics.tenant_id,
                    metrics.folder_name,
                    date_str,
                    metrics.total_syncs,
                    metrics.successful_syncs,
                    metrics.failed_syncs,
                    metrics.cancelled_syncs,
                    metrics.files_processed,
                    metrics.files_created,
                    metrics.files_updated,
                    metrics.files_deleted,
                    metrics.files_failed,
                    metrics.bytes_transferred,
                    metrics.bytes_failed,
                    metrics.avg_sync_duration,
                    metrics.max_sync_duration,
                    metrics.min_sync_duration if metrics.min_sync_duration != float('inf') else 0,
                    metrics.conflicts_detected,
                    metrics.conflicts_resolved,
                    metrics.conflicts_manual,
                    metrics.first_sync.isoformat() if metrics.first_sync else None,
                    metrics.last_sync.isoformat() if metrics.last_sync else None,
                    metrics.last_successful_sync.isoformat() if metrics.last_successful_sync else None
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to store metrics for {metrics.tenant_id}/{metrics.folder_name}: {e}")
    
    def get_events(
        self, 
        tenant_id: Optional[str] = None,
        folder_name: Optional[str] = None,
        event_type: Optional[SyncEventType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Get events with filtering."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM sync_events WHERE 1=1"
                params = []
                
                if tenant_id:
                    query += " AND tenant_id = ?"
                    params.append(tenant_id)
                
                if folder_name:
                    query += " AND folder_name = ?"
                    params.append(folder_name)
                
                if event_type:
                    query += " AND event_type = ?"
                    params.append(event_type.value)
                
                if start_time:
                    query += " AND timestamp >= ?"
                    params.append(start_time.isoformat())
                
                if end_time:
                    query += " AND timestamp <= ?"
                    params.append(end_time.isoformat())
                
                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                # Convert to dictionaries
                columns = [desc[0] for desc in cursor.description]
                events = []
                for row in rows:
                    event_dict = dict(zip(columns, row))
                    # Parse JSON details
                    if event_dict['details']:
                        event_dict['details'] = json.loads(event_dict['details'])
                    events.append(event_dict)
                
                return events
                
        except Exception as e:
            logger.error(f"Failed to get events: {e}")
            return []
    
    def get_metrics(
        self, 
        tenant_id: Optional[str] = None,
        folder_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get metrics with filtering."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM sync_metrics WHERE 1=1"
                params = []
                
                if tenant_id:
                    query += " AND tenant_id = ?"
                    params.append(tenant_id)
                
                if folder_name:
                    query += " AND folder_name = ?"
                    params.append(folder_name)
                
                if start_date:
                    query += " AND metric_date >= ?"
                    params.append(start_date.strftime('%Y-%m-%d'))
                
                if end_date:
                    query += " AND metric_date <= ?"
                    params.append(end_date.strftime('%Y-%m-%d'))
                
                query += " ORDER BY metric_date DESC"
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                # Convert to dictionaries
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            return []

class AlertManager:
    """Manages sync-related alerts and notifications."""
    
    def __init__(self):
        self.alert_handlers: List[Callable] = []
        self.alert_rules: Dict[str, Dict[str, Any]] = {
            'high_failure_rate': {
                'threshold': 0.5,  # 50% failure rate
                'window_minutes': 60
            },
            'slow_sync_performance': {
                'threshold': 300.0,  # 5 minutes
                'window_minutes': 30
            },
            'quota_exceeded': {
                'threshold': 0.9,  # 90% of quota
                'window_minutes': 10
            },
            'many_conflicts': {
                'threshold': 10,  # 10 conflicts
                'window_minutes': 60
            }
        }
    
    def register_alert_handler(self, handler: Callable) -> None:
        """Register an alert handler function."""
        self.alert_handlers.append(handler)
    
    async def check_alerts(self, database: SyncDatabase) -> List[Dict[str, Any]]:
        """Check for alert conditions and trigger alerts."""
        alerts = []
        now = datetime.now(timezone.utc)
        
        # Check high failure rate
        failure_alerts = await self._check_failure_rate(database, now)
        alerts.extend(failure_alerts)
        
        # Check slow performance
        performance_alerts = await self._check_performance(database, now)
        alerts.extend(performance_alerts)
        
        # Check conflicts
        conflict_alerts = await self._check_conflicts(database, now)
        alerts.extend(conflict_alerts)
        
        # Trigger alert handlers
        for alert in alerts:
            await self._trigger_alert(alert)
        
        return alerts
    
    async def _check_failure_rate(self, database: SyncDatabase, now: datetime) -> List[Dict[str, Any]]:
        """Check for high failure rates."""
        alerts = []
        rule = self.alert_rules['high_failure_rate']
        start_time = now - timedelta(minutes=rule['window_minutes'])
        
        # Get recent sync events
        events = database.get_events(
            event_type=SyncEventType.SYNC_COMPLETED,
            start_time=start_time,
            end_time=now
        )
        
        failed_events = database.get_events(
            event_type=SyncEventType.SYNC_FAILED,
            start_time=start_time,
            end_time=now
        )
        
        total_syncs = len(events) + len(failed_events)
        if total_syncs > 0:
            failure_rate = len(failed_events) / total_syncs
            
            if failure_rate >= rule['threshold']:
                alerts.append({
                    'alert_type': 'high_failure_rate',
                    'level': AlertLevel.ERROR.value,
                    'message': f"High failure rate detected: {failure_rate:.1%} ({len(failed_events)}/{total_syncs})",
                    'details': {
                        'failure_rate': failure_rate,
                        'failed_syncs': len(failed_events),
                        'total_syncs': total_syncs,
                        'window_minutes': rule['window_minutes']
                    },
                    'timestamp': now.isoformat()
                })
        
        return alerts
    
    async def _check_performance(self, database: SyncDatabase, now: datetime) -> List[Dict[str, Any]]:
        """Check for slow sync performance."""
        alerts = []
        rule = self.alert_rules['slow_sync_performance']
        start_time = now - timedelta(minutes=rule['window_minutes'])
        
        # Get recent completed sync events
        events = database.get_events(
            event_type=SyncEventType.SYNC_COMPLETED,
            start_time=start_time,
            end_time=now
        )
        
        slow_syncs = [
            event for event in events 
            if event.get('duration') and event['duration'] > rule['threshold']
        ]
        
        if slow_syncs:
            avg_duration = sum(event['duration'] for event in slow_syncs) / len(slow_syncs)
            alerts.append({
                'alert_type': 'slow_sync_performance',
                'level': AlertLevel.WARNING.value,
                'message': f"Slow sync performance: {len(slow_syncs)} syncs exceeded {rule['threshold']}s (avg: {avg_duration:.1f}s)",
                'details': {
                    'slow_syncs': len(slow_syncs),
                    'threshold': rule['threshold'],
                    'average_duration': avg_duration,
                    'window_minutes': rule['window_minutes']
                },
                'timestamp': now.isoformat()
            })
        
        return alerts
    
    async def _check_conflicts(self, database: SyncDatabase, now: datetime) -> List[Dict[str, Any]]:
        """Check for high number of conflicts."""
        alerts = []
        rule = self.alert_rules['many_conflicts']
        start_time = now - timedelta(minutes=rule['window_minutes'])
        
        # Get recent conflict events
        events = database.get_events(
            event_type=SyncEventType.CONFLICT_DETECTED,
            start_time=start_time,
            end_time=now
        )
        
        if len(events) >= rule['threshold']:
            alerts.append({
                'alert_type': 'many_conflicts',
                'level': AlertLevel.WARNING.value,
                'message': f"High number of conflicts: {len(events)} conflicts detected in {rule['window_minutes']} minutes",
                'details': {
                    'conflict_count': len(events),
                    'threshold': rule['threshold'],
                    'window_minutes': rule['window_minutes']
                },
                'timestamp': now.isoformat()
            })
        
        return alerts
    
    async def _trigger_alert(self, alert: Dict[str, Any]) -> None:
        """Trigger all registered alert handlers."""
        for handler in self.alert_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(alert)
                else:
                    handler(alert)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")

class SyncLogger:
    """Main sync logging system."""
    
    def __init__(self, log_directory: str = "./data/sync_logs"):
        self.log_directory = Path(log_directory)
        self.log_directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self.database = SyncDatabase(str(self.log_directory / "sync_data.db"))
        
        # Initialize alert manager
        self.alert_manager = AlertManager()
        
        # In-memory metrics cache
        self.metrics_cache: Dict[str, SyncMetrics] = {}
        self.event_counter = 0
        self.event_queue = deque(maxlen=10000)
        
        # Background tasks
        self.is_running = False
        self.metrics_task: Optional[asyncio.Task] = None
        self.alert_task: Optional[asyncio.Task] = None
        
        self._lock = threading.Lock()
    
    def log_event(
        self,
        event_type: SyncEventType,
        tenant_id: str,
        folder_name: str,
        message: str = "",
        operation_id: Optional[str] = None,
        file_path: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        duration: Optional[float] = None,
        bytes_processed: Optional[int] = None,
        error_code: Optional[str] = None,
        alert_level: AlertLevel = AlertLevel.INFO
    ) -> str:
        """Log a sync event."""
        
        with self._lock:
            self.event_counter += 1
            event_id = f"{tenant_id}_{event_type.value}_{self.event_counter:08d}"
        
        event = SyncEvent(
            event_id=event_id,
            event_type=event_type,
            tenant_id=tenant_id,
            folder_name=folder_name,
            message=message,
            operation_id=operation_id,
            file_path=file_path,
            details=details or {},
            duration=duration,
            bytes_processed=bytes_processed,
            error_code=error_code,
            alert_level=alert_level
        )
        
        # Store event
        self.database.store_event(event)
        
        # Add to queue for metrics processing
        self.event_queue.append(event)
        
        # Update metrics cache
        self._update_metrics_cache(event)
        
        logger.log(
            logging.ERROR if alert_level == AlertLevel.ERROR else
            logging.WARNING if alert_level == AlertLevel.WARNING else
            logging.INFO,
            f"[{tenant_id}/{folder_name}] {event_type.value}: {message}"
        )
        
        return event_id
    
    def _update_metrics_cache(self, event: SyncEvent) -> None:
        """Update in-memory metrics cache."""
        key = f"{event.tenant_id}:{event.folder_name}"
        
        if key not in self.metrics_cache:
            self.metrics_cache[key] = SyncMetrics(
                tenant_id=event.tenant_id,
                folder_name=event.folder_name
            )
        
        metrics = self.metrics_cache[key]
        
        # Update counters based on event type
        if event.event_type == SyncEventType.SYNC_STARTED:
            metrics.total_syncs += 1
            if not metrics.first_sync:
                metrics.first_sync = event.timestamp
            metrics.last_sync = event.timestamp
            
        elif event.event_type == SyncEventType.SYNC_COMPLETED:
            metrics.successful_syncs += 1
            metrics.last_successful_sync = event.timestamp
            
            if event.duration:
                # Update duration metrics
                if metrics.avg_sync_duration == 0:
                    metrics.avg_sync_duration = event.duration
                else:
                    metrics.avg_sync_duration = (metrics.avg_sync_duration + event.duration) / 2
                
                metrics.max_sync_duration = max(metrics.max_sync_duration, event.duration)
                metrics.min_sync_duration = min(metrics.min_sync_duration, event.duration)
            
            if event.bytes_processed:
                metrics.bytes_transferred += event.bytes_processed
                
        elif event.event_type == SyncEventType.SYNC_FAILED:
            metrics.failed_syncs += 1
            if event.bytes_processed:
                metrics.bytes_failed += event.bytes_processed
                
        elif event.event_type == SyncEventType.SYNC_CANCELLED:
            metrics.cancelled_syncs += 1
            
        elif event.event_type == SyncEventType.FILE_PROCESSED:
            metrics.files_processed += 1
            
            # Check details for specific operation
            operation_type = event.details.get('operation_type', '').lower()
            if 'create' in operation_type:
                metrics.files_created += 1
            elif 'update' in operation_type or 'modify' in operation_type:
                metrics.files_updated += 1
            elif 'delete' in operation_type:
                metrics.files_deleted += 1
            
            if event.details.get('failed', False):
                metrics.files_failed += 1
                
        elif event.event_type == SyncEventType.CONFLICT_DETECTED:
            metrics.conflicts_detected += 1
            
        elif event.event_type == SyncEventType.CONFLICT_RESOLVED:
            metrics.conflicts_resolved += 1
            
            if event.details.get('requires_manual', False):
                metrics.conflicts_manual += 1
    
    async def start_background_tasks(self) -> None:
        """Start background tasks for metrics and alerting."""
        if self.is_running:
            return
        
        self.is_running = True
        self.metrics_task = asyncio.create_task(self._metrics_loop())
        self.alert_task = asyncio.create_task(self._alert_loop())
        
        logger.info("Sync logger background tasks started")
    
    async def stop_background_tasks(self) -> None:
        """Stop background tasks."""
        self.is_running = False
        
        if self.metrics_task:
            self.metrics_task.cancel()
            try:
                await self.metrics_task
            except asyncio.CancelledError:
                pass
        
        if self.alert_task:
            self.alert_task.cancel()
            try:
                await self.alert_task
            except asyncio.CancelledError:
                pass
        
        # Save final metrics
        await self._save_metrics()
        
        logger.info("Sync logger background tasks stopped")
    
    async def _metrics_loop(self) -> None:
        """Background loop for saving metrics."""
        while self.is_running:
            try:
                await asyncio.sleep(300)  # Save every 5 minutes
                await self._save_metrics()
            except Exception as e:
                logger.error(f"Error in metrics loop: {e}")
                await asyncio.sleep(60)
    
    async def _alert_loop(self) -> None:
        """Background loop for checking alerts."""
        while self.is_running:
            try:
                await asyncio.sleep(120)  # Check every 2 minutes
                await self.alert_manager.check_alerts(self.database)
            except Exception as e:
                logger.error(f"Error in alert loop: {e}")
                await asyncio.sleep(60)
    
    async def _save_metrics(self) -> None:
        """Save metrics to database."""
        today = datetime.now(timezone.utc)
        
        with self._lock:
            for metrics in self.metrics_cache.values():
                self.database.store_metrics(metrics, today)
    
    def get_folder_status(self, tenant_id: str, folder_name: str) -> Dict[str, Any]:
        """Get current status for a folder."""
        key = f"{tenant_id}:{folder_name}"
        metrics = self.metrics_cache.get(key)
        
        if not metrics:
            return {
                'tenant_id': tenant_id,
                'folder_name': folder_name,
                'status': 'no_data',
                'metrics': {}
            }
        
        # Determine status
        status = 'healthy'
        if metrics.failed_syncs > metrics.successful_syncs:
            status = 'failing'
        elif metrics.conflicts_detected > metrics.conflicts_resolved:
            status = 'conflicts'
        elif not metrics.last_successful_sync:
            status = 'no_successful_sync'
        elif metrics.last_successful_sync < datetime.now(timezone.utc) - timedelta(hours=24):
            status = 'stale'
        
        return {
            'tenant_id': tenant_id,
            'folder_name': folder_name,
            'status': status,
            'metrics': metrics.to_dict(),
            'last_updated': datetime.now(timezone.utc).isoformat()
        }
    
    def get_tenant_summary(self, tenant_id: str) -> Dict[str, Any]:
        """Get summary of all folders for a tenant."""
        tenant_metrics = [
            metrics for key, metrics in self.metrics_cache.items()
            if key.startswith(f"{tenant_id}:")
        ]
        
        if not tenant_metrics:
            return {
                'tenant_id': tenant_id,
                'folder_count': 0,
                'total_syncs': 0,
                'folders': []
            }
        
        summary = {
            'tenant_id': tenant_id,
            'folder_count': len(tenant_metrics),
            'total_syncs': sum(m.total_syncs for m in tenant_metrics),
            'successful_syncs': sum(m.successful_syncs for m in tenant_metrics),
            'failed_syncs': sum(m.failed_syncs for m in tenant_metrics),
            'files_processed': sum(m.files_processed for m in tenant_metrics),
            'bytes_transferred': sum(m.bytes_transferred for m in tenant_metrics),
            'conflicts_detected': sum(m.conflicts_detected for m in tenant_metrics),
            'folders': [
                self.get_folder_status(tenant_id, metrics.folder_name)
                for metrics in tenant_metrics
            ]
        }
        
        return summary
    
    def get_recent_events(
        self, 
        tenant_id: Optional[str] = None,
        folder_name: Optional[str] = None,
        event_type: Optional[SyncEventType] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get recent events with filtering."""
        return self.database.get_events(
            tenant_id=tenant_id,
            folder_name=folder_name,
            event_type=event_type,
            limit=limit
        )
    
    def register_alert_handler(self, handler: Callable) -> None:
        """Register an alert handler."""
        self.alert_manager.register_alert_handler(handler)

# Global sync logger instance
sync_logger = SyncLogger()

# Example alert handler
async def log_alert(alert: Dict[str, Any]) -> None:
    """Example alert handler that logs alerts."""
    logger.warning(f"ALERT: {alert['alert_type']} - {alert['message']}")

# Register default alert handler
sync_logger.register_alert_handler(log_alert) 