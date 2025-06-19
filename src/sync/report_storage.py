"""
Report storage and management system.

This module provides functionality for storing, retrieving, and managing sync
reports with configurable retention policies.
"""

import logging
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
import sqlite3
import threading
import schedule
import time

from ..config.settings import get_settings
from .sync_metrics import MetricType, MetricValue

logger = logging.getLogger(__name__)

@dataclass
class SyncReport:
    """Represents a sync task report."""
    task_id: str
    tenant_id: Optional[str]
    timestamp: datetime
    status: str
    metrics: Dict[MetricType, List[MetricValue]]
    details: Dict[str, Any] = field(default_factory=dict)

class ReportStorage:
    """Manages storage and retrieval of sync reports."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize report storage.
        
        Args:
            db_path: Optional path to SQLite database
        """
        self.db_path = db_path or Path(get_settings().data_dir) / "reports.db"
        self._lock = threading.Lock()
        self._cleanup_thread = None
        self._running = False
        
        # Initialize database
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    tenant_id TEXT,
                    timestamp DATETIME NOT NULL,
                    status TEXT NOT NULL,
                    metrics TEXT NOT NULL,
                    details TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reports_task_id ON reports(task_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reports_tenant_id ON reports(tenant_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reports_timestamp ON reports(timestamp)"
            )
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get SQLite connection with proper configuration."""
        conn = sqlite3.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        conn.row_factory = sqlite3.Row
        return conn
    
    def store_report(self, report: SyncReport):
        """Store a sync report.
        
        Args:
            report: Sync report to store
        """
        metrics_json = {
            metric_type.value: [
                {
                    "value": v.value,
                    "timestamp": v.timestamp.isoformat(),
                    "metadata": v.metadata
                }
                for v in values
            ]
            for metric_type, values in report.metrics.items()
        }
        
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO reports (
                    task_id, tenant_id, timestamp, status, metrics, details
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    report.task_id,
                    report.tenant_id,
                    report.timestamp,
                    report.status,
                    json.dumps(metrics_json),
                    json.dumps(report.details) if report.details else None
                )
            )
    
    def get_report(self, task_id: str) -> Optional[SyncReport]:
        """Get a sync report by task ID.
        
        Args:
            task_id: Task identifier
        
        Returns:
            Sync report if found, None otherwise
        """
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM reports WHERE task_id = ?",
                (task_id,)
            ).fetchone()
            
            if not row:
                return None
            
            metrics_json = json.loads(row["metrics"])
            metrics = {
                MetricType(metric_type): [
                    MetricValue(
                        value=v["value"],
                        timestamp=datetime.fromisoformat(v["timestamp"]),
                        metadata=v["metadata"]
                    )
                    for v in values
                ]
                for metric_type, values in metrics_json.items()
            }
            
            return SyncReport(
                task_id=row["task_id"],
                tenant_id=row["tenant_id"],
                timestamp=row["timestamp"],
                status=row["status"],
                metrics=metrics,
                details=json.loads(row["details"]) if row["details"] else {}
            )
    
    def get_reports(
        self,
        tenant_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[SyncReport]:
        """Get sync reports with optional filters.
        
        Args:
            tenant_id: Optional tenant filter
            start_time: Optional start time filter
            end_time: Optional end time filter
            status: Optional status filter
            limit: Maximum number of reports to return
        
        Returns:
            List of sync reports
        """
        query = "SELECT * FROM reports WHERE 1=1"
        params = []
        
        if tenant_id:
            query += " AND tenant_id = ?"
            params.append(tenant_id)
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            
            return [
                SyncReport(
                    task_id=row["task_id"],
                    tenant_id=row["tenant_id"],
                    timestamp=row["timestamp"],
                    status=row["status"],
                    metrics={
                        MetricType(metric_type): [
                            MetricValue(
                                value=v["value"],
                                timestamp=datetime.fromisoformat(v["timestamp"]),
                                metadata=v["metadata"]
                            )
                            for v in values
                        ]
                        for metric_type, values in json.loads(row["metrics"]).items()
                    },
                    details=json.loads(row["details"]) if row["details"] else {}
                )
                for row in rows
            ]
    
    def cleanup_old_reports(self, retention_days: int = 30):
        """Clean up reports older than retention period.
        
        Args:
            retention_days: Number of days to retain reports
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        
        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM reports WHERE timestamp < ?",
                (cutoff,)
            )
        
        logger.info(f"Cleaned up reports older than {retention_days} days")
    
    def start_cleanup_scheduler(self, retention_days: int = 30):
        """Start scheduled cleanup of old reports.
        
        Args:
            retention_days: Number of days to retain reports
        """
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            return
        
        self._running = True
        
        def cleanup_job():
            while self._running:
                try:
                    self.cleanup_old_reports(retention_days)
                except Exception as e:
                    logger.error(f"Error in cleanup job: {e}")
                time.sleep(24 * 60 * 60)  # Run daily
        
        self._cleanup_thread = threading.Thread(
            target=cleanup_job,
            daemon=True
        )
        self._cleanup_thread.start()
        
        logger.info("Started report cleanup scheduler")
    
    def stop_cleanup_scheduler(self):
        """Stop scheduled cleanup of old reports."""
        self._running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5.0)
        logger.info("Stopped report cleanup scheduler") 