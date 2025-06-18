"""
Integration module for file system monitoring.

This module provides a unified interface for all file monitoring components,
integrating file watching, change detection, event handling, and monitoring.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from datetime import datetime, timezone

from .file_watcher import FileWatcherManager, FileEvent, file_watcher_manager
from .change_detector import TenantChangeTracker, FileChange, tenant_change_tracker
from .event_handler import FileEventHandler, file_event_handler
from .monitoring import FileSystemMonitor, file_system_monitor

logger = logging.getLogger(__name__)

class FileMonitoringSystem:
    """Unified file monitoring system integrating all components."""
    
    def __init__(self):
        self.watcher_manager = file_watcher_manager
        self.change_tracker = tenant_change_tracker
        self.event_handler = file_event_handler
        self.monitor = file_system_monitor
        
        self.is_initialized = False
        self.is_running = False
        
        # Connect components
        self._setup_integrations()
    
    def _setup_integrations(self) -> None:
        """Set up integration between components."""
        # Connect file watcher to event handler
        self.watcher_manager.add_global_event_handler(self._handle_file_event)
        
        # Add default event handlers
        self.event_handler.add_global_handler(None, self._log_event)
        
        # Register monitoring components
        self.monitor.health_checker.register_check("event_handler", self._check_event_handler_health)
        self.monitor.health_checker.register_check("change_tracker", self._check_change_tracker_health)
    
    def _handle_file_event(self, event: FileEvent) -> None:
        """Handle file events from watchers."""
        # Enqueue event for processing
        asyncio.create_task(self.event_handler.enqueue_event(event))
    
    def _log_event(self, event: FileEvent) -> None:
        """Log file events for debugging."""
        logger.info(f"File event: {event.event_type.value} - {event.file_path} (tenant: {event.tenant_id})")
    
    def _check_event_handler_health(self) -> Dict[str, Any]:
        """Health check for event handler."""
        stats = self.event_handler.get_stats()
        handler_stats = stats.get('handler', {})
        
        is_healthy = (
            handler_stats.get('is_running', False) and
            handler_stats.get('queue_size', 0) < 500  # Alert if queue too full
        )
        
        return {
            'is_healthy': is_healthy,
            'message': f"Event handler running: {handler_stats.get('is_running', False)}, queue size: {handler_stats.get('queue_size', 0)}",
            'details': handler_stats
        }
    
    def _check_change_tracker_health(self) -> Dict[str, Any]:
        """Health check for change tracker."""
        stats = self.change_tracker.get_all_stats()
        
        total_tenants = len(stats)
        is_healthy = total_tenants > 0
        
        return {
            'is_healthy': is_healthy,
            'message': f"Change tracker monitoring {total_tenants} tenants",
            'details': {'tenant_count': total_tenants, 'stats': stats}
        }
    
    async def add_tenant(
        self,
        tenant_id: str,
        source_folders: List[str],
        supported_extensions: Optional[set] = None,
        event_handlers: Optional[List[Callable]] = None
    ) -> bool:
        """Add a tenant to the monitoring system."""
        try:
            # Validate source folders
            validated_folders = []
            for folder in source_folders:
                folder_path = Path(folder)
                if not folder_path.exists():
                    folder_path.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created folder for tenant {tenant_id}: {folder_path}")
                validated_folders.append(str(folder_path))
            
            if not validated_folders:
                logger.error(f"No valid source folders for tenant {tenant_id}")
                return False
            
            # Add to file watcher
            watcher = self.watcher_manager.add_tenant_watcher(
                tenant_id=tenant_id,
                source_folders=validated_folders,
                supported_extensions=supported_extensions
            )
            
            # Add to change tracker
            change_detector = self.change_tracker.add_tenant(
                tenant_id=tenant_id,
                source_folders=validated_folders
            )
            
            # Create baseline snapshot
            await change_detector.create_baseline_snapshot()
            
            # Add custom event handlers if provided
            if event_handlers:
                for handler in event_handlers:
                    self.event_handler.add_tenant_handler(tenant_id, None, handler)
            
            # Register with monitor
            self.monitor.register_tenant_watcher(tenant_id, watcher)
            
            # Start watcher if system is running
            if self.is_running:
                await watcher.start_watching()
            
            logger.info(f"Successfully added tenant {tenant_id} to monitoring system")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add tenant {tenant_id}: {e}")
            return False
    
    async def remove_tenant(self, tenant_id: str) -> bool:
        """Remove a tenant from the monitoring system."""
        try:
            # Stop and remove from watcher manager
            watcher_removed = self.watcher_manager.remove_tenant_watcher(tenant_id)
            
            # Remove from change tracker
            tracker_removed = self.change_tracker.remove_tenant(tenant_id)
            
            # Unregister from monitor
            monitor_removed = self.monitor.unregister_tenant_watcher(tenant_id)
            
            success = watcher_removed and tracker_removed
            
            if success:
                logger.info(f"Successfully removed tenant {tenant_id} from monitoring system")
            else:
                logger.warning(f"Partial removal of tenant {tenant_id} (watcher: {watcher_removed}, tracker: {tracker_removed})")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to remove tenant {tenant_id}: {e}")
            return False
    
    async def start_monitoring(self) -> None:
        """Start the complete monitoring system."""
        if self.is_running:
            logger.warning("Monitoring system is already running")
            return
        
        try:
            # Start event processing
            await self.event_handler.start_processing()
            
            # Start file watchers
            await self.watcher_manager.start_all_watchers()
            
            # Start system monitoring
            await self.monitor.start_monitoring()
            
            self.is_running = True
            logger.info("File monitoring system started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start monitoring system: {e}")
            await self.stop_monitoring()  # Clean up on failure
            raise
    
    async def stop_monitoring(self) -> None:
        """Stop the complete monitoring system."""
        if not self.is_running:
            logger.warning("Monitoring system is not running")
            return
        
        try:
            # Stop file watchers
            await self.watcher_manager.stop_all_watchers()
            
            # Stop event processing
            await self.event_handler.stop_processing()
            
            # Stop system monitoring
            await self.monitor.stop_monitoring()
            
            self.is_running = False
            logger.info("File monitoring system stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping monitoring system: {e}")
    
    async def perform_change_scan(self) -> Dict[str, List[FileChange]]:
        """Perform a manual change detection scan for all tenants."""
        logger.info("Starting manual change detection scan")
        
        try:
            changes = await self.change_tracker.detect_all_changes()
            
            total_changes = sum(len(tenant_changes) for tenant_changes in changes.values())
            logger.info(f"Change scan completed: {total_changes} changes detected across {len(changes)} tenants")
            
            return changes
            
        except Exception as e:
            logger.error(f"Change scan failed: {e}")
            return {}
    
    def get_tenant_info(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive information about a tenant."""
        watcher = self.watcher_manager.get_tenant_watcher(tenant_id)
        if not watcher:
            return None
        
        # Get recent changes
        recent_changes = self.change_tracker.get_tenant_changes(
            tenant_id=tenant_id,
            limit=10
        )
        
        return {
            'tenant_id': tenant_id,
            'watcher_stats': watcher.get_stats(),
            'recent_changes': [change.to_dict() for change in recent_changes],
            'change_count': len(self.change_tracker.get_tenant_changes(tenant_id)),
            'is_active': watcher.is_active
        }
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        # Get basic status
        status = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'is_running': self.is_running,
            'components': {
                'watcher_manager': {
                    'is_running': self.watcher_manager.is_running,
                    'tenant_count': len(self.watcher_manager.watchers),
                    'stats': self.watcher_manager.get_all_stats()
                },
                'event_handler': self.event_handler.get_stats(),
                'change_tracker': {
                    'tenant_count': len(self.change_tracker.detectors),
                    'stats': self.change_tracker.get_all_stats()
                }
            }
        }
        
        # Add monitoring status
        if self.monitor.is_running:
            status['monitoring'] = self.monitor.get_comprehensive_status()
        
        return status
    
    def add_global_event_handler(self, handler: Callable[[FileEvent], None]) -> None:
        """Add a global event handler."""
        self.event_handler.add_global_handler(None, handler)
    
    def get_tenant_list(self) -> List[str]:
        """Get list of all monitored tenants."""
        return list(self.watcher_manager.watchers.keys())

# Global file monitoring system instance
file_monitoring_system = FileMonitoringSystem() 