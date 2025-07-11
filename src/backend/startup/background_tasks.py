"""
Background Tasks Management
Handles long-running background tasks for sync cleanup and monitoring
"""

import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from src.backend.database import AsyncSessionLocal
from src.backend.services.sync_operations_manager import SyncOperationsManager, SyncOperationConfig
from src.backend.services.sync_service import SyncService
from src.backend.services.file_service import FileService
from src.backend.services.embedding_service import EmbeddingService
# DEPRECATED: Consistency checker and recovery service no longer needed with pgvector
# from src.backend.services.consistency_checker import get_consistency_checker
# from src.backend.services.recovery_service import get_recovery_service
from src.backend.monitoring.performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    """Manages all background tasks for the RAG system"""
    
    def __init__(self):
        self.tasks: Dict[str, asyncio.Task] = {}
        self.running = False
        self._cleanup_config = SyncOperationConfig()
    
    async def start_all_tasks(self):
        """Start all background tasks"""
        if self.running:
            logger.warning("Background tasks already running")
            return
        
        self.running = True
        logger.info("Starting simplified background tasks...")
        
        # DISABLED: sync cleanup task (causing complexity)
        # DISABLED: performance monitoring task (not essential)
        
        # Only start essential health check task
        self.tasks["health_check"] = asyncio.create_task(
            self._health_check_loop(),
            name="health_check"
        )
        
        # DEPRECATED: Consistency monitoring no longer needed with pgvector
        # self.tasks["consistency_monitor"] = asyncio.create_task(
        #     self._consistency_monitoring_loop(),
        #     name="consistency_monitor"
        # )
        
        # DEPRECATED: Auto-recovery no longer needed with pgvector
        # self.tasks["auto_recovery"] = asyncio.create_task(
        #     self._auto_recovery_loop(),
        #     name="auto_recovery"
        # )
        
        logger.info(f"Started {len(self.tasks)} background tasks")
    
    async def stop_all_tasks(self):
        """Stop all background tasks"""
        if not self.running:
            return
        
        self.running = False
        logger.info("Stopping background tasks...")
        
        # Cancel all tasks
        for task_name, task in self.tasks.items():
            if not task.done():
                logger.info(f"Cancelling task: {task_name}")
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.info(f"Task {task_name} cancelled successfully")
                except Exception as e:
                    logger.error(f"Error stopping task {task_name}: {e}")
        
        self.tasks.clear()
        logger.info("All background tasks stopped")
    
    async def _sync_cleanup_loop(self):
        """Background loop for sync operation cleanup"""
        logger.info("Started sync cleanup background task")
        
        while self.running:
            try:
                # Skip cleanup if database tables don't exist (e.g., after data clearing)
                try:
                    async with AsyncSessionLocal() as db_session:
                        # Test if tables exist by running a simple query
                        await db_session.execute(text("SELECT 1 FROM sync_operations LIMIT 1"))
                except Exception as e:
                    logger.info(f"Skipping cleanup - database not ready: {e}")
                    await asyncio.sleep(60)  # Wait 1 minute before retrying
                    continue
                
                # Database is ready, perform cleanup
                async with AsyncSessionLocal() as db_session:
                    # Cleanup operations would go here
                    # For now, just skip to avoid embedding model loading
                    pass
                
                # Wait for next cleanup cycle
                await asyncio.sleep(self._cleanup_config.cleanup_interval_seconds)
                
            except asyncio.CancelledError:
                logger.info("Sync cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in sync cleanup loop: {e}")
                # Wait a bit before retrying
                await asyncio.sleep(60)
    
    async def _performance_monitoring_loop(self):
        """Background loop for performance monitoring"""
        logger.info("Started performance monitoring background task")
        
        while self.running:
            try:
                # Create performance monitor
                async with AsyncSessionLocal() as db_session:
                    monitor = PerformanceMonitor(db_session)
                    
                    # Get system health
                    health_data = await monitor.get_system_health()
                    
                    # Log critical health issues
                    if health_data.get('memory_usage_percent', 0) > 90:
                        logger.warning(f"High memory usage: {health_data['memory_usage_percent']:.1f}%")
                    
                    if health_data.get('disk_usage_percent', 0) > 90:
                        logger.warning(f"High disk usage: {health_data['disk_usage_percent']:.1f}%")
                
                # Check every 5 minutes
                await asyncio.sleep(300)
                
            except asyncio.CancelledError:
                logger.info("Performance monitoring task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in performance monitoring loop: {e}")
                await asyncio.sleep(60)
    
    async def _health_check_loop(self):
        """Background loop for system health checks"""
        logger.info("Started health check background task")
        
        while self.running:
            try:
                # Perform basic health checks
                current_time = datetime.utcnow()
                
                # Check database connectivity
                try:
                    async with AsyncSessionLocal() as db_session:
                        await db_session.execute(text("SELECT 1"))
                    db_healthy = True
                except Exception as e:
                    logger.error(f"Database health check failed: {e}")
                    db_healthy = False
                
                # Log health status periodically (every hour)
                if current_time.minute == 0:  # Top of the hour
                    logger.info(f"System health check - DB: {'✓' if db_healthy else '✗'}")
                
                # Check every minute
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                logger.info("Health check task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(60)
    
    async def _consistency_monitoring_loop(self):
        """DEPRECATED: Background loop for consistency monitoring - no longer needed with pgvector"""
        logger.info("Consistency monitoring is deprecated with pgvector - data consistency is maintained automatically")
        # No longer needed - PostgreSQL ACID transactions handle consistency automatically
    
    async def _auto_recovery_loop(self):
        """DEPRECATED: Background loop for automatic recovery - no longer needed with pgvector"""
        logger.info("Auto-recovery is deprecated with pgvector - PostgreSQL transactions handle recovery automatically")
        # No longer needed - PostgreSQL ACID transactions handle recovery automatically

    def get_task_status(self) -> Dict[str, str]:
        """Get status of all background tasks"""
        status = {}
        for task_name, task in self.tasks.items():
            if task.done():
                if task.cancelled():
                    status[task_name] = "cancelled"
                elif task.exception():
                    status[task_name] = f"failed: {task.exception()}"
                else:
                    status[task_name] = "completed"
            else:
                status[task_name] = "running"
        
        return status


# Global background task manager instance
_background_manager: Optional[BackgroundTaskManager] = None


def get_background_manager() -> BackgroundTaskManager:
    """Get the global background task manager"""
    global _background_manager
    if _background_manager is None:
        _background_manager = BackgroundTaskManager()
    return _background_manager


async def start_background_tasks():
    """Start all background tasks"""
    manager = get_background_manager()
    await manager.start_all_tasks()


async def stop_background_tasks():
    """Stop all background tasks"""
    manager = get_background_manager()
    await manager.stop_all_tasks() 