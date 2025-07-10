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
from src.backend.services.consistency_checker import get_consistency_checker
from src.backend.services.recovery_service import get_recovery_service
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
        logger.info("Starting background tasks...")
        
        # Start sync cleanup task
        self.tasks["sync_cleanup"] = asyncio.create_task(
            self._sync_cleanup_loop(),
            name="sync_cleanup"
        )
        
        # Start performance monitoring task
        self.tasks["performance_monitor"] = asyncio.create_task(
            self._performance_monitoring_loop(),
            name="performance_monitor"
        )
        
        # Start health check task
        self.tasks["health_check"] = asyncio.create_task(
            self._health_check_loop(),
            name="health_check"
        )
        
        # Start consistency monitoring task
        self.tasks["consistency_monitor"] = asyncio.create_task(
            self._consistency_monitoring_loop(),
            name="consistency_monitor"
        )
        
        # Start auto-recovery task
        self.tasks["auto_recovery"] = asyncio.create_task(
            self._auto_recovery_loop(),
            name="auto_recovery"
        )
        
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
                # Create a new database session for this cleanup cycle
                async with AsyncSessionLocal() as db_session:
                    # Create services for this cleanup cycle
                    file_service = FileService(db_session)
                    
                    # Initialize embedding service (minimal setup for cleanup)
                    try:
                        from sentence_transformers import SentenceTransformer
                        embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                        embedding_service = EmbeddingService(db_session, embedding_model)
                    except Exception as e:
                        logger.warning(f"Could not initialize embedding service for cleanup: {e}")
                        # Create a minimal embedding service for cleanup
                        embedding_service = EmbeddingService(db_session, None)
                    
                    sync_service = SyncService(db_session, file_service, embedding_service)
                    
                    # Create sync operations manager
                    sync_manager = SyncOperationsManager(
                        db_session=db_session,
                        sync_service=sync_service,
                        config=self._cleanup_config
                    )
                    
                    # Perform cleanup
                    cleanup_count = await sync_manager.cleanup_stuck_operations()
                    
                    if cleanup_count > 0:
                        logger.info(f"Background cleanup: processed {cleanup_count} stuck operations")
                
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
        """Background loop for consistency monitoring"""
        logger.info("Started consistency monitoring background task")
        
        while self.running:
            try:
                # Run consistency checks periodically (every 6 hours)
                async with AsyncSessionLocal() as db_session:
                    consistency_checker = await get_consistency_checker(db_session)
                    
                    # Check all tenants
                    all_results = await consistency_checker.check_all_tenants_consistency()
                    
                    # Log summary of consistency issues
                    total_inconsistencies = 0
                    tenants_with_issues = 0
                    
                    for tenant_id, (stats, inconsistencies) in all_results.items():
                        if inconsistencies:
                            tenants_with_issues += 1
                            total_inconsistencies += len(inconsistencies)
                            
                            # Log critical issues immediately
                            critical_issues = [i for i in inconsistencies if i.severity.value == "critical"]
                            if critical_issues:
                                logger.error(f"Tenant {tenant_id} has {len(critical_issues)} critical consistency issues")
                    
                    if total_inconsistencies > 0:
                        logger.warning(
                            f"Consistency check: {tenants_with_issues} tenants with {total_inconsistencies} total issues"
                        )
                    else:
                        logger.info("Consistency check: All tenants healthy")
                
                # Check every 6 hours
                await asyncio.sleep(21600)
                
            except asyncio.CancelledError:
                logger.info("Consistency monitoring task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in consistency monitoring loop: {e}")
                await asyncio.sleep(1800)  # Wait 30 minutes on error
    
    async def _auto_recovery_loop(self):
        """Background loop for automatic recovery of common issues"""
        logger.info("Started auto-recovery background task")
        
        while self.running:
            try:
                # Run auto-recovery every 2 hours for quick fixes only
                async with AsyncSessionLocal() as db_session:
                    embedding_service = EmbeddingService(db_session, None)  # Minimal setup
                    recovery_service = await get_recovery_service(db_session, embedding_service)
                    
                    # Get all tenant IDs that might need quick fixes
                    from sqlalchemy import select, func
                    from src.backend.models.database import File
                    
                    result = await db_session.execute(
                        select(func.distinct(File.tenant_id))
                    )
                    tenant_ids = [row[0] for row in result.fetchall()]
                    
                    total_fixes = 0
                    
                    # Apply quick fixes to each tenant
                    for tenant_id in tenant_ids:
                        try:
                            results = await recovery_service.quick_fix_tenant(tenant_id)
                            
                            if results["fixes_applied"]:
                                logger.info(f"Auto-recovery for tenant {tenant_id}: {', '.join(results['fixes_applied'])}")
                                total_fixes += len(results["fixes_applied"])
                            
                            if results["errors"]:
                                logger.warning(f"Auto-recovery errors for tenant {tenant_id}: {', '.join(results['errors'])}")
                        
                        except Exception as e:
                            logger.error(f"Auto-recovery failed for tenant {tenant_id}: {e}")
                            continue
                    
                    if total_fixes > 0:
                        logger.info(f"Auto-recovery completed: applied {total_fixes} fixes across {len(tenant_ids)} tenants")
                
                # Run every 2 hours
                await asyncio.sleep(7200)
                
            except asyncio.CancelledError:
                logger.info("Auto-recovery task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in auto-recovery loop: {e}")
                await asyncio.sleep(1800)  # Wait 30 minutes on error

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