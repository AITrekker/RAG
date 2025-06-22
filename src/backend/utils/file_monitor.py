"""
Real-time file system monitoring for document synchronization.

This module provides intelligent file system monitoring that detects changes
and triggers delta synchronization processes automatically.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Callable, Set
from dataclasses import dataclass
from threading import Thread, Event
import schedule
import requests
import json

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = None

from ..config.settings import get_settings
from ..core.delta_sync import DeltaSync, SyncResult
from ..core.tenant_manager import TenantManager
from ..core.document_processor import DocumentProcessor
from ..db.session import get_db

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class WebhookConfig:
    """Configuration for webhook notifications."""
    url: str
    secret: Optional[str] = None
    events: List[str] = None  # List of events to send: ['sync_start', 'sync_complete', 'sync_failed']
    timeout: int = 30
    retry_count: int = 3


@dataclass
class MonitorConfig:
    """Configuration for file monitoring."""
    tenant_id: str
    documents_path: str
    sync_interval_minutes: int = 1440  # 24 hours default
    auto_sync_enabled: bool = True
    webhooks: List[WebhookConfig] = None
    ignore_patterns: Set[str] = None


class DocumentChangeHandler(FileSystemEventHandler):
    """Handles file system events for document changes."""
    
    def __init__(self, monitor: 'FileMonitor', tenant_id: str):
        super().__init__()
        self.monitor = monitor
        self.tenant_id = tenant_id
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Debounce settings to avoid excessive syncs
        self.last_event_time = {}
        self.debounce_seconds = 5
    
    def should_process_event(self, event: FileSystemEvent) -> bool:
        """Determine if an event should trigger processing."""
        if event.is_directory:
            return False
        
        # Check file extension
        file_path = Path(event.src_path)
        if file_path.suffix.lower() not in settings.supported_file_types:
            return False
        
        # Check ignore patterns
        config = self.monitor.get_tenant_config(self.tenant_id)
        if config and config.ignore_patterns:
            for pattern in config.ignore_patterns:
                if pattern in str(file_path):
                    return False
        
        # Debounce rapid events
        now = time.time()
        last_time = self.last_event_time.get(event.src_path, 0)
        
        if now - last_time < self.debounce_seconds:
            return False
        
        self.last_event_time[event.src_path] = now
        return True
    
    def on_created(self, event: FileSystemEvent):
        """Handle file creation events."""
        if self.should_process_event(event):
            self.logger.info(f"File created: {event.src_path}")
            self.monitor.queue_sync(self.tenant_id, "file_created", event.src_path)
    
    def on_modified(self, event: FileSystemEvent):
        """Handle file modification events."""
        if self.should_process_event(event):
            self.logger.info(f"File modified: {event.src_path}")
            self.monitor.queue_sync(self.tenant_id, "file_modified", event.src_path)
    
    def on_deleted(self, event: FileSystemEvent):
        """Handle file deletion events."""
        if self.should_process_event(event):
            self.logger.info(f"File deleted: {event.src_path}")
            self.monitor.queue_sync(self.tenant_id, "file_deleted", event.src_path)
    
    def on_moved(self, event: FileSystemEvent):
        """Handle file move events."""
        if self.should_process_event(event):
            self.logger.info(f"File moved: {event.src_path} -> {event.dest_path}")
            self.monitor.queue_sync(self.tenant_id, "file_moved", f"{event.src_path} -> {event.dest_path}")


class WebhookNotifier:
    """Handles webhook notifications for sync events."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    async def send_webhook(self, webhook: WebhookConfig, event_data: Dict) -> bool:
        """Send a webhook notification."""
        try:
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'RAG-Platform-Webhook/1.0'
            }
            
            # Add signature if secret is configured
            if webhook.secret:
                import hmac
                import hashlib
                
                payload = json.dumps(event_data)
                signature = hmac.new(
                    webhook.secret.encode('utf-8'),
                    payload.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                headers['X-RAG-Signature'] = f"sha256={signature}"
            
            for attempt in range(webhook.retry_count):
                try:
                    response = requests.post(
                        webhook.url,
                        json=event_data,
                        headers=headers,
                        timeout=webhook.timeout
                    )
                    
                    if response.status_code < 400:
                        self.logger.info(f"Webhook sent successfully to {webhook.url}")
                        return True
                    else:
                        self.logger.warning(f"Webhook failed with status {response.status_code}: {webhook.url}")
                        
                except requests.RequestException as e:
                    self.logger.warning(f"Webhook attempt {attempt + 1} failed: {e}")
                    if attempt < webhook.retry_count - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error sending webhook to {webhook.url}: {e}")
            return False
    
    async def notify_sync_event(self, config: MonitorConfig, event_type: str, sync_result: SyncResult):
        """Send webhook notifications for sync events."""
        if not config.webhooks:
            return
        
        event_data = {
            'event_type': event_type,
            'tenant_id': config.tenant_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'sync_result': {
                'sync_run_id': sync_result.sync_run_id,
                'success': sync_result.success,
                'files_added': sync_result.files_added,
                'files_modified': sync_result.files_modified,
                'files_deleted': sync_result.files_deleted,
                'total_files_scanned': sync_result.total_files_scanned,
                'error_count': len(sync_result.errors),
                'duration_seconds': (
                    sync_result.end_time - sync_result.start_time
                ).total_seconds() if sync_result.end_time else None
            }
        }
        
        # Send webhooks for relevant events
        for webhook in config.webhooks:
            if not webhook.events or event_type in webhook.events:
                await self.send_webhook(webhook, event_data)


class FileMonitor:
    """
    Comprehensive file monitoring system with real-time change detection
    and automated synchronization scheduling.
    """
    
    def __init__(self, tenant_manager: TenantManager, document_processor: DocumentProcessor):
        self.tenant_manager = tenant_manager
        self.document_processor = document_processor
        self.delta_sync = DeltaSync(tenant_manager, document_processor)
        self.webhook_notifier = WebhookNotifier()
        
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Monitoring state
        self.tenant_configs: Dict[str, MonitorConfig] = {}
        self.observers: Dict[str, Observer] = {}
        self.sync_queue: asyncio.Queue = asyncio.Queue()
        self.scheduled_syncs: Dict[str, bool] = {}
        
        # Control events
        self.shutdown_event = Event()
        self.scheduler_thread: Optional[Thread] = None
        self.sync_processor_task: Optional[asyncio.Task] = None
        
        if not WATCHDOG_AVAILABLE:
            self.logger.warning("Watchdog not available. File monitoring will be limited.")
    
    def add_tenant_monitoring(self, config: MonitorConfig):
        """Add monitoring for a tenant's documents directory."""
        self.tenant_configs[config.tenant_id] = config
        
        if WATCHDOG_AVAILABLE and config.auto_sync_enabled:
            self._start_file_watcher(config)
        
        if config.auto_sync_enabled:
            self._schedule_periodic_sync(config)
        
        self.logger.info(f"Added monitoring for tenant {config.tenant_id}")
    
    def remove_tenant_monitoring(self, tenant_id: str):
        """Remove monitoring for a tenant."""
        if tenant_id in self.observers:
            self.observers[tenant_id].stop()
            self.observers[tenant_id].join()
            del self.observers[tenant_id]
        
        if tenant_id in self.tenant_configs:
            del self.tenant_configs[tenant_id]
        
        if tenant_id in self.scheduled_syncs:
            del self.scheduled_syncs[tenant_id]
        
        self.logger.info(f"Removed monitoring for tenant {tenant_id}")
    
    def _start_file_watcher(self, config: MonitorConfig):
        """Start real-time file system monitoring for a tenant."""
        if not WATCHDOG_AVAILABLE:
            return
        
        documents_path = Path(config.documents_path)
        if not documents_path.exists():
            self.logger.warning(f"Documents path does not exist: {documents_path}")
            return
        
        event_handler = DocumentChangeHandler(self, config.tenant_id)
        observer = Observer()
        observer.schedule(event_handler, str(documents_path), recursive=True)
        observer.start()
        
        self.observers[config.tenant_id] = observer
        self.logger.info(f"Started file watcher for tenant {config.tenant_id}")
    
    def _schedule_periodic_sync(self, config: MonitorConfig):
        """Schedule periodic synchronization for a tenant."""
        def sync_job():
            self.queue_sync(config.tenant_id, "scheduled_sync")
        
        # Schedule based on interval
        if config.sync_interval_minutes >= 1440:  # Daily
            schedule.every().day.at("02:00").do(sync_job).tag(config.tenant_id)
        elif config.sync_interval_minutes >= 60:  # Hourly
            schedule.every(config.sync_interval_minutes // 60).hours.do(sync_job).tag(config.tenant_id)
        else:  # Minutes
            schedule.every(config.sync_interval_minutes).minutes.do(sync_job).tag(config.tenant_id)
        
        self.scheduled_syncs[config.tenant_id] = True
        self.logger.info(f"Scheduled periodic sync for tenant {config.tenant_id} every {config.sync_interval_minutes} minutes")
    
    def queue_sync(self, tenant_id: str, trigger_reason: str, file_path: str = None):
        """Queue a synchronization request."""
        try:
            sync_request = {
                'tenant_id': tenant_id,
                'trigger_reason': trigger_reason,
                'file_path': file_path,
                'timestamp': datetime.now(timezone.utc)
            }
            
            # Use asyncio-safe method to add to queue
            asyncio.create_task(self.sync_queue.put(sync_request))
            
        except Exception as e:
            self.logger.error(f"Error queuing sync for tenant {tenant_id}: {e}")
    
    async def process_sync_queue(self):
        """Process synchronization requests from the queue."""
        while not self.shutdown_event.is_set():
            try:
                # Wait for sync request with timeout
                sync_request = await asyncio.wait_for(
                    self.sync_queue.get(),
                    timeout=1.0
                )
                
                tenant_id = sync_request['tenant_id']
                config = self.tenant_configs.get(tenant_id)
                
                if not config:
                    self.logger.warning(f"No config found for tenant {tenant_id}")
                    continue
                
                self.logger.info(f"Processing sync for tenant {tenant_id}, trigger: {sync_request['trigger_reason']}")
                
                # Send webhook notification for sync start
                await self.webhook_notifier.notify_sync_event(
                    config, 'sync_start', 
                    SyncResult(
                        sync_run_id=f"temp_{tenant_id}",
                        tenant_id=tenant_id,
                        total_files_scanned=0,
                        files_added=0,
                        files_modified=0,
                        files_deleted=0,
                        files_moved=0,
                        errors=[],
                        start_time=datetime.now(timezone.utc)
                    )
                )
                
                # Perform synchronization
                sync_result = self.delta_sync.synchronize_tenant(tenant_id)
                
                # Send webhook notification for sync completion
                event_type = 'sync_complete' if sync_result.success else 'sync_failed'
                await self.webhook_notifier.notify_sync_event(config, event_type, sync_result)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Error processing sync queue: {e}")
    
    def start_scheduler(self):
        """Start the background scheduler for periodic syncs."""
        def run_scheduler():
            while not self.shutdown_event.is_set():
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        
        self.scheduler_thread = Thread(target=run_scheduler, daemon=True)
        self.scheduler_thread.start()
        self.logger.info("Started sync scheduler")
    
    async def start_monitoring(self):
        """Start the file monitoring system."""
        self.start_scheduler()
        
        # Start sync queue processor
        self.sync_processor_task = asyncio.create_task(self.process_sync_queue())
        
        self.logger.info("File monitoring system started")
    
    def stop_monitoring(self):
        """Stop the file monitoring system."""
        self.shutdown_event.set()
        
        # Stop all file observers
        for observer in self.observers.values():
            observer.stop()
            observer.join()
        
        # Cancel scheduled jobs
        for tenant_id in list(self.scheduled_syncs.keys()):
            schedule.clear(tenant_id)
        
        # Stop scheduler thread
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)
        
        # Cancel sync processor
        if self.sync_processor_task and not self.sync_processor_task.done():
            self.sync_processor_task.cancel()
        
        self.logger.info("File monitoring system stopped")
    
    def get_tenant_config(self, tenant_id: str) -> Optional[MonitorConfig]:
        """Get monitoring configuration for a tenant."""
        return self.tenant_configs.get(tenant_id)
    
    def trigger_manual_sync(self, tenant_id: str) -> bool:
        """Manually trigger synchronization for a tenant."""
        try:
            self.queue_sync(tenant_id, "manual_trigger")
            return True
        except Exception as e:
            self.logger.error(f"Error triggering manual sync for tenant {tenant_id}: {e}")
            return False
    
    def get_monitoring_status(self) -> Dict[str, Dict]:
        """Get current monitoring status for all tenants."""
        status = {}
        
        for tenant_id, config in self.tenant_configs.items():
            status[tenant_id] = {
                'auto_sync_enabled': config.auto_sync_enabled,
                'sync_interval_minutes': config.sync_interval_minutes,
                'file_watcher_active': tenant_id in self.observers,
                'scheduled_sync_active': tenant_id in self.scheduled_syncs,
                'documents_path': config.documents_path,
                'webhook_count': len(config.webhooks) if config.webhooks else 0
            }
        
        return status


# Global instance for use across the application
file_monitor: Optional[FileMonitor] = None


def get_file_monitor() -> FileMonitor:
    """Get the global file monitor instance."""
    global file_monitor
    if file_monitor is None:
        from ..core.tenant_manager import TenantManager
        from ..core.document_processor import DocumentProcessor
        
        tenant_manager = TenantManager()
        document_processor = DocumentProcessor()
        file_monitor = FileMonitor(tenant_manager, document_processor)
    
    return file_monitor


def initialize_monitoring_for_tenant(tenant_id: str, config: Dict) -> bool:
    """Initialize monitoring for a tenant with the given configuration."""
    try:
        monitor = get_file_monitor()
        
        # Create webhook configs
        webhooks = []
        if config.get('webhooks'):
            for webhook_data in config['webhooks']:
                webhooks.append(WebhookConfig(
                    url=webhook_data['url'],
                    secret=webhook_data.get('secret'),
                    events=webhook_data.get('events'),
                    timeout=webhook_data.get('timeout', 30),
                    retry_count=webhook_data.get('retry_count', 3)
                ))
        
        monitor_config = MonitorConfig(
            tenant_id=tenant_id,
            documents_path=config['documents_path'],
            sync_interval_minutes=config.get('sync_interval_minutes', 1440),
            auto_sync_enabled=config.get('auto_sync_enabled', True),
            webhooks=webhooks,
            ignore_patterns=set(config.get('ignore_patterns', []))
        )
        
        monitor.add_tenant_monitoring(monitor_config)
        return True
        
    except Exception as e:
        logger.error(f"Error initializing monitoring for tenant {tenant_id}: {e}")
        return False 