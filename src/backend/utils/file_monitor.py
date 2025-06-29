"""
Real-time file system monitoring for document synchronization.

This module provides intelligent file system monitoring that detects changes
and triggers delta synchronization processes automatically.
"""

import logging
import time
from threading import Thread, Event
import schedule

from ..core.delta_sync import DeltaSync
from ..core.document_processor import DocumentProcessor
from ..services.tenant_service import get_tenant_service

logger = logging.getLogger(__name__)

class FileMonitor:
    """A simple, scheduled monitor to trigger global tenant synchronization."""

    def __init__(self):
        self.document_processor = DocumentProcessor()
        self.delta_sync = DeltaSync(self.document_processor)
        self.tenant_service = get_tenant_service()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.shutdown_event = Event()
        self.scheduler_thread = None

    def run_global_sync(self):
        """
        Fetches all tenants and runs DeltaSync for each.
        """
        self.logger.info("Starting global synchronization run...")
        try:
            # This is a placeholder as get_all_tenants doesn't exist yet in TenantService.
            # In a real implementation, you would get all tenant IDs from the tenant service.
            all_tenant_ids = ["default"] 
            self.logger.info(f"Found {len(all_tenant_ids)} tenants to sync.")
            
            for tenant_id in all_tenant_ids:
                try:
                    self.logger.info(f"Synchronizing tenant: {tenant_id}")
                    self.delta_sync.synchronize_tenant(tenant_id)
                except Exception as e:
                    self.logger.error(f"Failed to synchronize tenant {tenant_id}: {e}", exc_info=True)
        except Exception as e:
            self.logger.error(f"A critical error occurred during the global sync run: {e}", exc_info=True)
        self.logger.info("Global synchronization run finished.")

    def start(self, interval_minutes: int = 60):
        """Starts the scheduler in a background thread."""
        self.logger.info(f"Scheduling global sync to run every {interval_minutes} minutes.")
        schedule.every(interval_minutes).minutes.do(self.run_global_sync)

        def run_scheduler():
            while not self.shutdown_event.is_set():
                schedule.run_pending()
                time.sleep(60)

        self.scheduler_thread = Thread(target=run_scheduler, daemon=True)
        self.scheduler_thread.start()
        self.logger.info("File monitor scheduler started.")

    def stop(self):
        """Stops the scheduler."""
        self.shutdown_event.set()
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)
        self.logger.info("File monitor scheduler stopped.")

_file_monitor_instance = None

def get_file_monitor() -> "FileMonitor":
    """Gets the singleton instance of the FileMonitor."""
    global _file_monitor_instance
    if _file_monitor_instance is None:
        _file_monitor_instance = FileMonitor()
    return _file_monitor_instance 