"""
Connection pooling utilities for HR RAG Pipeline.

This module provides advanced connection pooling, monitoring,
and health checking for database connections.
"""

import time
import threading
from typing import Dict, Optional, List, Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from sqlalchemy.pool import QueuePool, StaticPool
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError
from sqlalchemy.orm import Session

from ..config import get_settings
from .engine import get_engine, get_session_factory

logger = logging.getLogger(__name__)

@dataclass
class ConnectionPoolStats:
    """Statistics for connection pool monitoring."""
    pool_size: int = 0
    checked_out: int = 0
    overflow: int = 0
    total_connections: int = 0
    failed_connections: int = 0
    successful_connections: int = 0
    connection_errors: int = 0
    avg_connection_time_ms: float = 0.0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class ConnectionPoolMonitor:
    """Monitor and manage database connection pool health."""
    
    def __init__(self):
        self.stats = ConnectionPoolStats()
        self.connection_times: List[float] = []
        self._lock = threading.Lock()
    
    def record_connection_attempt(self, success: bool, duration_ms: float, error: Optional[str] = None):
        """
        Record connection attempt statistics.
        
        Args:
            success: Whether connection was successful
            duration_ms: Connection attempt duration in milliseconds
            error: Error message if connection failed
        """
        with self._lock:
            if success:
                self.stats.successful_connections += 1
                self.connection_times.append(duration_ms)
                
                # Keep only last 100 connection times for average calculation
                if len(self.connection_times) > 100:
                    self.connection_times = self.connection_times[-100:]
                
                self.stats.avg_connection_time_ms = sum(self.connection_times) / len(self.connection_times)
            else:
                self.stats.failed_connections += 1
                self.stats.connection_errors += 1
                self.stats.last_error = error
                self.stats.last_error_time = datetime.utcnow()
    
    def update_pool_stats(self, engine: Engine):
        """
        Update pool statistics from engine.
        
        Args:
            engine: SQLAlchemy engine
        """
        try:
            pool = engine.pool
            with self._lock:
                self.stats.pool_size = pool.size()
                self.stats.checked_out = pool.checkedout()
                if hasattr(pool, 'overflow'):
                    self.stats.overflow = pool.overflow()
                self.stats.total_connections = self.stats.pool_size + self.stats.overflow
        except Exception as e:
            logger.warning(f"Failed to update pool stats: {e}")
    
    def get_health_status(self) -> Dict[str, any]:
        """
        Get connection pool health status.
        
        Returns:
            Health status dictionary
        """
        with self._lock:
            total_attempts = self.stats.successful_connections + self.stats.failed_connections
            success_rate = (self.stats.successful_connections / total_attempts * 100) if total_attempts > 0 else 0
            
            return {
                "pool_size": self.stats.pool_size,
                "checked_out": self.stats.checked_out,
                "overflow": self.stats.overflow,
                "total_connections": self.stats.total_connections,
                "success_rate_percent": round(success_rate, 2),
                "avg_connection_time_ms": round(self.stats.avg_connection_time_ms, 2),
                "total_successful": self.stats.successful_connections,
                "total_failed": self.stats.failed_connections,
                "connection_errors": self.stats.connection_errors,
                "last_error": self.stats.last_error,
                "last_error_time": self.stats.last_error_time.isoformat() if self.stats.last_error_time else None,
                "healthy": success_rate >= 95 and self.stats.connection_errors < 10
            }

# Global connection pool monitor
_pool_monitor = ConnectionPoolMonitor()

def get_pool_monitor() -> ConnectionPoolMonitor:
    """Get the global connection pool monitor."""
    return _pool_monitor

@contextmanager
def monitored_connection():
    """
    Context manager for monitored database connections.
    
    Yields:
        Database session with connection monitoring
    """
    start_time = time.time()
    session = None
    
    try:
        session_factory = get_session_factory()
        session = session_factory()
        
        # Record successful connection
        duration_ms = (time.time() - start_time) * 1000
        _pool_monitor.record_connection_attempt(True, duration_ms)
        
        yield session
        session.commit()
        
    except Exception as e:
        # Record failed connection
        duration_ms = (time.time() - start_time) * 1000
        _pool_monitor.record_connection_attempt(False, duration_ms, str(e))
        
        if session:
            session.rollback()
        logger.error(f"Monitored connection error: {e}")
        raise
    finally:
        if session:
            session.close()

class ConnectionPoolManager:
    """Manage connection pool lifecycle and health."""
    
    def __init__(self):
        self.engine: Optional[Engine] = None
        self.health_check_interval = 60  # seconds
        self.last_health_check: Optional[datetime] = None
        self._lock = threading.Lock()
    
    def initialize(self):
        """Initialize connection pool."""
        with self._lock:
            if self.engine is None:
                self.engine = get_engine()
                logger.info("Connection pool initialized")
    
    def health_check(self) -> bool:
        """
        Perform connection pool health check.
        
        Returns:
            True if pool is healthy, False otherwise
        """
        if not self.engine:
            return False
        
        try:
            # Update pool statistics
            _pool_monitor.update_pool_stats(self.engine)
            
            # Test connection
            with monitored_connection() as session:
                session.execute("SELECT 1")
            
            self.last_health_check = datetime.utcnow()
            return True
            
        except Exception as e:
            logger.error(f"Connection pool health check failed: {e}")
            return False
    
    def should_run_health_check(self) -> bool:
        """Check if health check should be run."""
        if self.last_health_check is None:
            return True
        
        time_since_check = datetime.utcnow() - self.last_health_check
        return time_since_check.total_seconds() >= self.health_check_interval
    
    def get_pool_info(self) -> Dict[str, any]:
        """
        Get detailed connection pool information.
        
        Returns:
            Pool information dictionary
        """
        if not self.engine:
            return {"status": "not_initialized"}
        
        try:
            pool = self.engine.pool
            return {
                "status": "initialized",
                "pool_class": pool.__class__.__name__,
                "size": pool.size(),
                "checked_out": pool.checkedout(),
                "overflow": getattr(pool, 'overflow', lambda: 0)(),
                "checked_in": pool.checkedin(),
                "url": str(self.engine.url).split('@')[0] + "@***",  # Hide credentials
                "echo": self.engine.echo,
                "health_status": _pool_monitor.get_health_status()
            }
        except Exception as e:
            logger.error(f"Failed to get pool info: {e}")
            return {"status": "error", "error": str(e)}
    
    def cleanup(self):
        """Clean up connection pool resources."""
        with self._lock:
            if self.engine:
                self.engine.dispose()
                self.engine = None
                logger.info("Connection pool cleaned up")

# Global connection pool manager
_pool_manager = ConnectionPoolManager()

def get_pool_manager() -> ConnectionPoolManager:
    """Get the global connection pool manager."""
    return _pool_manager

def initialize_connection_pool():
    """Initialize the global connection pool."""
    _pool_manager.initialize()

def check_pool_health() -> bool:
    """
    Check connection pool health.
    
    Returns:
        True if pool is healthy, False otherwise
    """
    return _pool_manager.health_check()

def get_pool_status() -> Dict[str, any]:
    """
    Get comprehensive connection pool status.
    
    Returns:
        Pool status dictionary
    """
    return _pool_manager.get_pool_info()

def cleanup_connection_pool():
    """Clean up connection pool resources."""
    _pool_manager.cleanup()

class TenantConnectionManager:
    """Manage tenant-specific connection patterns."""
    
    def __init__(self):
        self.tenant_stats: Dict[str, Dict[str, any]] = {}
        self._lock = threading.Lock()
    
    def record_tenant_activity(self, tenant_id: str, operation: str, duration_ms: float, success: bool):
        """
        Record tenant database activity.
        
        Args:
            tenant_id: Tenant identifier
            operation: Type of operation (read, write, transaction)
            duration_ms: Operation duration in milliseconds
            success: Whether operation was successful
        """
        with self._lock:
            if tenant_id not in self.tenant_stats:
                self.tenant_stats[tenant_id] = {
                    "total_operations": 0,
                    "successful_operations": 0,
                    "failed_operations": 0,
                    "total_duration_ms": 0.0,
                    "avg_duration_ms": 0.0,
                    "operations_by_type": {},
                    "last_activity": None
                }
            
            stats = self.tenant_stats[tenant_id]
            stats["total_operations"] += 1
            stats["total_duration_ms"] += duration_ms
            stats["avg_duration_ms"] = stats["total_duration_ms"] / stats["total_operations"]
            stats["last_activity"] = datetime.utcnow()
            
            if success:
                stats["successful_operations"] += 1
            else:
                stats["failed_operations"] += 1
            
            # Track by operation type
            if operation not in stats["operations_by_type"]:
                stats["operations_by_type"][operation] = {"count": 0, "total_duration_ms": 0.0}
            
            op_stats = stats["operations_by_type"][operation]
            op_stats["count"] += 1
            op_stats["total_duration_ms"] += duration_ms
            op_stats["avg_duration_ms"] = op_stats["total_duration_ms"] / op_stats["count"]
    
    def get_tenant_stats(self, tenant_id: str) -> Optional[Dict[str, any]]:
        """
        Get statistics for specific tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Tenant statistics or None
        """
        with self._lock:
            return self.tenant_stats.get(tenant_id, {}).copy()
    
    def get_all_tenant_stats(self) -> Dict[str, Dict[str, any]]:
        """
        Get statistics for all tenants.
        
        Returns:
            All tenant statistics
        """
        with self._lock:
            return {k: v.copy() for k, v in self.tenant_stats.items()}

# Global tenant connection manager
_tenant_manager = TenantConnectionManager()

def get_tenant_connection_manager() -> TenantConnectionManager:
    """Get the global tenant connection manager."""
    return _tenant_manager

@contextmanager
def monitored_tenant_connection(tenant_id: str, operation: str = "query"):
    """
    Context manager for tenant-aware monitored connections.
    
    Args:
        tenant_id: Tenant identifier
        operation: Type of operation being performed
        
    Yields:
        Database session with tenant and connection monitoring
    """
    start_time = time.time()
    session = None
    
    try:
        session_factory = get_session_factory()
        session = session_factory()
        
        yield session
        session.commit()
        
        # Record successful operation
        duration_ms = (time.time() - start_time) * 1000
        _tenant_manager.record_tenant_activity(tenant_id, operation, duration_ms, True)
        
    except Exception as e:
        # Record failed operation
        duration_ms = (time.time() - start_time) * 1000
        _tenant_manager.record_tenant_activity(tenant_id, operation, duration_ms, False)
        
        if session:
            session.rollback()
        logger.error(f"Tenant {tenant_id} connection error: {e}")
        raise
    finally:
        if session:
            session.close()

# Export commonly used functions and classes
__all__ = [
    "ConnectionPoolStats",
    "ConnectionPoolMonitor",
    "ConnectionPoolManager",
    "TenantConnectionManager",
    "get_pool_monitor",
    "get_pool_manager",
    "get_tenant_connection_manager",
    "monitored_connection",
    "monitored_tenant_connection",
    "initialize_connection_pool",
    "check_pool_health",
    "get_pool_status",
    "cleanup_connection_pool",
] 