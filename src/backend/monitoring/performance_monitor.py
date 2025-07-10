"""
Performance monitoring and metrics collection for RAG system
"""

import asyncio
import time
import psutil
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from uuid import UUID
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics snapshot"""
    timestamp: datetime
    tenant_id: Optional[UUID]
    operation: str
    duration_ms: float
    memory_usage_mb: float
    cpu_usage_percent: float
    gpu_usage_percent: float
    gpu_memory_mb: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    database_queries: int
    vector_operations: int
    embedding_batch_size: int
    chunks_processed: int
    files_processed: int
    error_count: int
    metadata: Dict[str, Any]
    
    # Sync-specific metrics
    sync_id: Optional[UUID] = None
    sync_stage: Optional[str] = None
    progress_percentage: Optional[float] = None


@dataclass
class SystemResources:
    """System resource snapshot"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_available_gb: float
    disk_usage_percent: float
    disk_free_gb: float
    gpu_percent: float
    gpu_memory_used_gb: float
    gpu_memory_total_gb: float
    gpu_temperature: float
    network_sent_mb: float
    network_recv_mb: float


class PerformanceMonitor:
    """Performance monitoring and metrics collection"""
    
    def __init__(self, db_session: Optional[AsyncSession] = None):
        self.db = db_session
        self.metrics_buffer: List[PerformanceMetrics] = []
        self.system_snapshots: List[SystemResources] = []
        self.active_operations: Dict[str, dict] = {}
        self.buffer_size = 1000
        self.flush_interval = 60  # seconds
        self._last_flush = time.time()
        
        # GPU monitoring
        self._gpu_available = False
        self._gpu_device_count = 0
        self._init_gpu_monitoring()
        
        # System monitoring
        self._last_network_stats = psutil.net_io_counters()
        self._last_disk_stats = psutil.disk_io_counters()
        
    def _init_gpu_monitoring(self):
        """Initialize GPU monitoring if available"""
        try:
            import torch
            if torch.cuda.is_available():
                self._gpu_available = True
                self._gpu_device_count = torch.cuda.device_count()
                logger.info(f"GPU monitoring enabled: {self._gpu_device_count} devices")
            else:
                logger.info("GPU monitoring disabled: CUDA not available")
        except ImportError:
            logger.info("GPU monitoring disabled: PyTorch not available")
    
    @asynccontextmanager
    async def track_operation(
        self, 
        operation: str, 
        tenant_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Context manager for tracking operation performance"""
        operation_id = f"{operation}_{time.time()}"
        start_time = time.time()
        start_metrics = self._get_system_snapshot()
        
        # Track operation start
        self.active_operations[operation_id] = {
            'operation': operation,
            'tenant_id': tenant_id,
            'start_time': start_time,
            'start_metrics': start_metrics,
            'metadata': metadata or {}
        }
        
        try:
            yield operation_id
        except Exception as e:
            # Track error
            self.active_operations[operation_id]['error'] = str(e)
            raise
        finally:
            # Track operation completion
            await self._complete_operation(operation_id)
    
    async def _complete_operation(self, operation_id: str):
        """Complete operation tracking and record metrics"""
        if operation_id not in self.active_operations:
            return
        
        op_data = self.active_operations.pop(operation_id)
        end_time = time.time()
        duration_ms = (end_time - op_data['start_time']) * 1000
        
        # Get end metrics
        end_metrics = self._get_system_snapshot()
        
        # Calculate resource deltas
        cpu_delta = end_metrics.cpu_percent - op_data['start_metrics'].cpu_percent
        memory_delta = end_metrics.memory_percent - op_data['start_metrics'].memory_percent
        
        # Create performance metrics
        metrics = PerformanceMetrics(
            timestamp=datetime.utcnow(),
            tenant_id=op_data['tenant_id'],
            operation=op_data['operation'],
            duration_ms=duration_ms,
            memory_usage_mb=psutil.virtual_memory().used / (1024 * 1024),
            cpu_usage_percent=end_metrics.cpu_percent,
            gpu_usage_percent=end_metrics.gpu_percent,
            gpu_memory_mb=end_metrics.gpu_memory_used_gb * 1024,
            disk_io_read_mb=0,  # Will be calculated properly
            disk_io_write_mb=0,
            database_queries=op_data['metadata'].get('database_queries', 0),
            vector_operations=op_data['metadata'].get('vector_operations', 0),
            embedding_batch_size=op_data['metadata'].get('embedding_batch_size', 0),
            chunks_processed=op_data['metadata'].get('chunks_processed', 0),
            files_processed=op_data['metadata'].get('files_processed', 0),
            error_count=1 if 'error' in op_data else 0,
            metadata=op_data['metadata']
        )
        
        # Add to buffer
        self.metrics_buffer.append(metrics)
        
        # Check if buffer needs flushing
        if len(self.metrics_buffer) >= self.buffer_size or \
           (time.time() - self._last_flush) > self.flush_interval:
            await self._flush_metrics()
    
    def _get_system_snapshot(self) -> SystemResources:
        """Get current system resource snapshot"""
        # CPU and Memory
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        # Disk
        disk = psutil.disk_usage('/')
        
        # Network
        net_stats = psutil.net_io_counters()
        
        # GPU
        gpu_percent = 0
        gpu_memory_used = 0
        gpu_memory_total = 0
        gpu_temperature = 0
        
        if self._gpu_available:
            try:
                import torch
                if torch.cuda.is_available():
                    # Get GPU utilization
                    import nvidia_ml_py3 as nvml
                    nvml.nvmlInit()
                    handle = nvml.nvmlDeviceGetHandleByIndex(0)
                    
                    # GPU utilization
                    util = nvml.nvmlDeviceGetUtilizationRates(handle)
                    gpu_percent = util.gpu
                    
                    # GPU memory
                    mem_info = nvml.nvmlDeviceGetMemoryInfo(handle)
                    gpu_memory_used = mem_info.used / (1024 ** 3)  # GB
                    gpu_memory_total = mem_info.total / (1024 ** 3)  # GB
                    
                    # GPU temperature
                    gpu_temperature = nvml.nvmlDeviceGetTemperature(handle, nvml.NVML_TEMPERATURE_GPU)
                    
            except Exception as e:
                logger.warning(f"GPU monitoring failed: {e}")
        
        return SystemResources(
            timestamp=datetime.utcnow(),
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_available_gb=memory.available / (1024 ** 3),
            disk_usage_percent=disk.percent,
            disk_free_gb=disk.free / (1024 ** 3),
            gpu_percent=gpu_percent,
            gpu_memory_used_gb=gpu_memory_used,
            gpu_memory_total_gb=gpu_memory_total,
            gpu_temperature=gpu_temperature,
            network_sent_mb=net_stats.bytes_sent / (1024 ** 2),
            network_recv_mb=net_stats.bytes_recv / (1024 ** 2)
        )
    
    async def _flush_metrics(self):
        """Flush metrics buffer to storage"""
        if not self.metrics_buffer:
            return
        
        try:
            # For now, just log metrics - in production, store in database
            logger.info(f"Flushing {len(self.metrics_buffer)} performance metrics")
            
            # Log summary statistics
            operations = {}
            for metric in self.metrics_buffer:
                if metric.operation not in operations:
                    operations[metric.operation] = []
                operations[metric.operation].append(metric.duration_ms)
            
            for operation, durations in operations.items():
                avg_duration = sum(durations) / len(durations)
                max_duration = max(durations)
                min_duration = min(durations)
                
                logger.info(f"Operation {operation}: avg={avg_duration:.2f}ms, "
                           f"max={max_duration:.2f}ms, min={min_duration:.2f}ms, "
                           f"count={len(durations)}")
            
            # Clear buffer
            self.metrics_buffer.clear()
            self._last_flush = time.time()
            
        except Exception as e:
            logger.error(f"Failed to flush metrics: {e}")
    
    async def get_performance_report(
        self, 
        tenant_id: Optional[UUID] = None,
        operation: Optional[str] = None,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Generate performance report"""
        # Filter metrics based on criteria
        filtered_metrics = []
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        for metric in self.metrics_buffer:
            if metric.timestamp < cutoff_time:
                continue
            if tenant_id and metric.tenant_id != tenant_id:
                continue
            if operation and metric.operation != operation:
                continue
            filtered_metrics.append(metric)
        
        if not filtered_metrics:
            return {
                'report_generated': datetime.utcnow().isoformat(),
                'metrics_found': 0,
                'message': 'No metrics found for the specified criteria'
            }
        
        # Calculate statistics
        durations = [m.duration_ms for m in filtered_metrics]
        cpu_usages = [m.cpu_usage_percent for m in filtered_metrics]
        memory_usages = [m.memory_usage_mb for m in filtered_metrics]
        gpu_usages = [m.gpu_usage_percent for m in filtered_metrics]
        
        operations_summary = {}
        for metric in filtered_metrics:
            if metric.operation not in operations_summary:
                operations_summary[metric.operation] = {
                    'count': 0,
                    'total_duration': 0,
                    'total_chunks': 0,
                    'total_files': 0,
                    'errors': 0
                }
            
            summary = operations_summary[metric.operation]
            summary['count'] += 1
            summary['total_duration'] += metric.duration_ms
            summary['total_chunks'] += metric.chunks_processed
            summary['total_files'] += metric.files_processed
            summary['errors'] += metric.error_count
        
        # Calculate averages
        for op, summary in operations_summary.items():
            if summary['count'] > 0:
                summary['avg_duration'] = summary['total_duration'] / summary['count']
                summary['avg_chunks_per_operation'] = summary['total_chunks'] / summary['count']
                summary['error_rate'] = summary['errors'] / summary['count']
        
        return {
            'report_generated': datetime.utcnow().isoformat(),
            'tenant_id': str(tenant_id) if tenant_id else None,
            'operation_filter': operation,
            'time_range_hours': hours,
            'metrics_analyzed': len(filtered_metrics),
            'performance_summary': {
                'avg_duration_ms': sum(durations) / len(durations),
                'max_duration_ms': max(durations),
                'min_duration_ms': min(durations),
                'avg_cpu_percent': sum(cpu_usages) / len(cpu_usages),
                'avg_memory_mb': sum(memory_usages) / len(memory_usages),
                'avg_gpu_percent': sum(gpu_usages) / len(gpu_usages) if gpu_usages else 0,
                'total_chunks_processed': sum(m.chunks_processed for m in filtered_metrics),
                'total_files_processed': sum(m.files_processed for m in filtered_metrics),
                'total_errors': sum(m.error_count for m in filtered_metrics)
            },
            'operations_breakdown': operations_summary
        }
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get current system health status"""
        current_snapshot = self._get_system_snapshot()
        
        # Define health thresholds
        cpu_warning = 80
        memory_warning = 85
        disk_warning = 90
        gpu_warning = 90
        gpu_temp_warning = 80
        
        # Determine health status
        health_status = "healthy"
        warnings = []
        
        if current_snapshot.cpu_percent > cpu_warning:
            health_status = "warning"
            warnings.append(f"High CPU usage: {current_snapshot.cpu_percent:.1f}%")
        
        if current_snapshot.memory_percent > memory_warning:
            health_status = "warning"
            warnings.append(f"High memory usage: {current_snapshot.memory_percent:.1f}%")
        
        if current_snapshot.disk_usage_percent > disk_warning:
            health_status = "warning"
            warnings.append(f"High disk usage: {current_snapshot.disk_usage_percent:.1f}%")
        
        if current_snapshot.gpu_percent > gpu_warning:
            health_status = "warning"
            warnings.append(f"High GPU usage: {current_snapshot.gpu_percent:.1f}%")
        
        if current_snapshot.gpu_temperature > gpu_temp_warning:
            health_status = "warning"
            warnings.append(f"High GPU temperature: {current_snapshot.gpu_temperature:.1f}°C")
        
        return {
            'timestamp': current_snapshot.timestamp.isoformat(),
            'health_status': health_status,
            'warnings': warnings,
            'system_resources': asdict(current_snapshot),
            'active_operations': len(self.active_operations),
            'metrics_buffer_size': len(self.metrics_buffer),
            'gpu_available': self._gpu_available,
            'gpu_device_count': self._gpu_device_count
        }
    
    def update_operation_metadata(self, operation_id: str, metadata: Dict[str, Any]):
        """Update metadata for an active operation"""
        if operation_id in self.active_operations:
            self.active_operations[operation_id]['metadata'].update(metadata)
    
    async def start_background_monitoring(self):
        """Start background system monitoring"""
        async def monitor_loop():
            while True:
                try:
                    # Take system snapshot
                    snapshot = self._get_system_snapshot()
                    self.system_snapshots.append(snapshot)
                    
                    # Keep only last 1000 snapshots
                    if len(self.system_snapshots) > 1000:
                        self.system_snapshots = self.system_snapshots[-1000:]
                    
                    # Sleep for 30 seconds
                    await asyncio.sleep(30)
                    
                except Exception as e:
                    logger.error(f"Background monitoring error: {e}")
                    await asyncio.sleep(60)  # Wait longer on error
        
        # Start monitoring task
        asyncio.create_task(monitor_loop())
        logger.info("Background performance monitoring started")


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


# Convenience functions
async def track_operation(operation: str, tenant_id: Optional[UUID] = None, metadata: Optional[Dict[str, Any]] = None):
    """Convenience function for tracking operations"""
    return performance_monitor.track_operation(operation, tenant_id, metadata)


async def get_performance_report(**kwargs) -> Dict[str, Any]:
    """Convenience function for getting performance reports"""
    return await performance_monitor.get_performance_report(**kwargs)


async def get_system_health() -> Dict[str, Any]:
    """Convenience function for getting system health"""
    return await performance_monitor.get_system_health()