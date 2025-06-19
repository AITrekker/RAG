"""
Sync module for Enterprise RAG pipeline.

This module provides comprehensive file synchronization capabilities including:
- File system monitoring and change detection
- Event handling and processing
- Sync scheduling with tenant quotas
- Delta synchronization
- Conflict resolution
- Comprehensive logging and metrics
- Resource management and allocation
- Fair scheduling and optimization
"""

# File monitoring and change detection
from .file_watcher import TenantFileWatcher as FileWatcher, FileEvent, FileEventType
from .change_detector import ChangeDetector, FileSnapshot, ChangeType
from .event_handler import (
    FileEventHandler as EventHandler, 
    EventPriority
)
from .monitoring import (
    FileSystemMonitor as SystemMonitor, 
    HealthStatus,
    MonitoringMetrics as SystemMetrics
)

# Sync scheduling and management
from .sync_scheduler import (
    SyncScheduler,
    SyncOperation,
    SyncPriority,
    SyncStatus,
    TenantQuota,
    TenantUsageTracker,
    sync_scheduler
)

# Delta synchronization
from .delta_sync import (
    DeltaSyncEngine,
    DeltaSyncManager,
    DeltaOperation,
    DeltaOperationType,
    SyncDirection,
    SyncResult,
    FolderSnapshot,
    delta_sync_manager
)

# Conflict resolution
from .conflict_resolver import (
    ConflictManager,
    ConflictResolver,
    ConflictDetector,
    ConflictLogger,
    ConflictDetails,
    ConflictType,
    ConflictResolutionStrategy,
    ConflictStatus,
    conflict_manager
)

# Sync logging and metrics
from .sync_logger import (
    SyncLogger,
    SyncEvent as LogSyncEvent,
    SyncEventType,
    SyncMetrics,
    AlertLevel,
    AlertManager,
    sync_logger
)

# Integration layer
from .integration import FileMonitoringSystem as SyncIntegration

# Resource management
from .resource_manager import (
    ResourceAllocationSystem, ResourceType, ResourceLimits, 
    ResourceUsage, ResourceAllocation, AllocationStatus,
    GPUManager, CPUManager, MemoryManager, DiskIOManager, 
    resource_allocator
)

# Fair scheduling
from .fair_scheduler import (
    FairScheduler, ScheduledTask, TenantQuota as FairTenantQuota,
    TaskPriority, TaskStatus, SchedulingPolicy, TenantUsageTracker as FairUsageTracker,
    RoundRobinScheduler, PriorityScheduler, FairShareScheduler,
    fair_scheduler
)

# Resource monitoring
from .resource_monitor import (
    ResourceMonitor, MetricPoint, Alert, AlertSeverity, MetricType,
    MetricsDatabase, ResourceUsageTracker, AlertManager as ResourceAlertManager,
    resource_monitor
)

# Resource optimization
from .resource_optimizer import (
    ResourceOptimizer, BatchOptimizer, ParallelismOptimizer, CacheManager,
    OptimizationStrategy, CacheEvictionPolicy, BatchConfiguration, ParallelismConfiguration,
    resource_optimizer
)

# Global instances - Import existing global instances
from .file_watcher import file_watcher_manager as file_watcher
from .change_detector import tenant_change_tracker as change_detector  
from .event_handler import file_event_handler as event_handler
from .monitoring import file_system_monitor as system_monitor
from .integration import FileMonitoringSystem
sync_integration = FileMonitoringSystem()

__all__ = [
    # File monitoring
    'FileWatcher',
    'FileEvent',
    'FileEventType', 
    'ChangeDetector', 
    'FileSnapshot',
    'ChangeType',
    'EventHandler',
    'EventPriority',
    'SystemMonitor',
    'HealthStatus',
    'SystemMetrics',
    
    # Sync scheduling
    'SyncScheduler',
    'SyncOperation',
    'SyncPriority',
    'SyncStatus',
    'TenantQuota',
    'TenantUsageTracker',
    'sync_scheduler',
    
    # Delta sync
    'DeltaSyncEngine',
    'DeltaSyncManager',
    'DeltaOperation',
    'DeltaOperationType',
    'SyncDirection',
    'SyncResult',
    'FolderSnapshot',
    'delta_sync_manager',
    
    # Conflict resolution
    'ConflictManager',
    'ConflictResolver',
    'ConflictDetector',
    'ConflictLogger',
    'ConflictDetails',
    'ConflictType',
    'ConflictResolutionStrategy',
    'ConflictStatus',
    'conflict_manager',
    
    # Logging and metrics
    'SyncLogger',
    'LogSyncEvent',
    'SyncEventType',
    'SyncMetrics',
    'AlertLevel',
    'AlertManager',
    'sync_logger',
    
    # Integration
    'SyncIntegration',
    
    # Resource management
    'ResourceAllocationSystem',
    'ResourceType',
    'ResourceLimits',
    'ResourceUsage',
    'ResourceAllocation',
    'AllocationStatus',
    'GPUManager',
    'CPUManager',
    'MemoryManager',
    'DiskIOManager',
    'resource_allocator',
    
    # Fair scheduling
    'FairScheduler',
    'ScheduledTask',
    'FairTenantQuota',
    'TaskPriority',
    'TaskStatus',
    'SchedulingPolicy',
    'FairUsageTracker',
    'RoundRobinScheduler',
    'PriorityScheduler',
    'FairShareScheduler',
    'fair_scheduler',
    
    # Resource monitoring
    'ResourceMonitor',
    'MetricPoint',
    'Alert',
    'AlertSeverity',
    'MetricType',
    'MetricsDatabase',
    'ResourceUsageTracker',
    'ResourceAlertManager',
    'resource_monitor',
    
    # Resource optimization
    'ResourceOptimizer',
    'BatchOptimizer',
    'ParallelismOptimizer',
    'CacheManager',
    'OptimizationStrategy',
    'CacheEvictionPolicy',
    'BatchConfiguration',
    'ParallelismConfiguration',
    'resource_optimizer',
    
    # Global instances
    'file_watcher',
    'change_detector',
    'event_handler',
    'system_monitor',
    'sync_integration'
] 