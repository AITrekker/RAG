"""
Comprehensive demo of the complete sync system.

This script demonstrates the integration of all sync components:
- Sync scheduling with tenant quotas
- Delta synchronization
- Conflict resolution
- Comprehensive logging and metrics
"""

import asyncio
import logging
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
import shutil
import time

from .sync_scheduler import (
    sync_scheduler, 
    SyncPriority, 
    TenantQuota,
    ConflictResolutionStrategy
)
from .delta_sync import delta_sync_manager, SyncDirection
from .conflict_resolver import conflict_manager
from .sync_logger import sync_logger, SyncEventType, AlertLevel

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SyncDemo:
    """Demonstrates the complete sync system functionality."""
    
    def __init__(self):
        self.demo_dir = None
        self.tenant_dirs = {}
        self.target_dirs = {}
    
    async def setup_demo_environment(self) -> None:
        """Set up demo directories and files."""
        # Create temporary directory for demo
        self.demo_dir = Path(tempfile.mkdtemp(prefix="sync_demo_"))
        logger.info(f"Created demo directory: {self.demo_dir}")
        
        # Create tenant directories
        tenants = ["tenant_alpha", "tenant_beta", "tenant_gamma"]
        
        for tenant_id in tenants:
            # Source directory
            source_dir = self.demo_dir / "sources" / tenant_id
            source_dir.mkdir(parents=True, exist_ok=True)
            self.tenant_dirs[tenant_id] = str(source_dir)
            
            # Target directory
            target_dir = self.demo_dir / "targets" / tenant_id
            target_dir.mkdir(parents=True, exist_ok=True)
            self.target_dirs[tenant_id] = str(target_dir)
            
            # Create some initial files
            await self._create_demo_files(source_dir, tenant_id)
        
        logger.info(f"Created demo environment for {len(tenants)} tenants")
    
    async def _create_demo_files(self, base_dir: Path, tenant_id: str) -> None:
        """Create demo files for a tenant."""
        files = [
            ("policies/hr_policy.txt", f"HR Policy for {tenant_id}\n\nThis is the employee handbook..."),
            ("reports/quarterly_report.md", f"# Q1 Report - {tenant_id}\n\n## Summary\nExcellent performance..."),
            ("documents/employee_guide.docx", f"Employee Guide Content for {tenant_id}"),
            ("training/safety_manual.pdf", f"Safety Manual PDF content for {tenant_id}"),
        ]
        
        for file_path, content in files:
            full_path = base_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
    
    async def demonstrate_sync_scheduling(self) -> None:
        """Demonstrate sync scheduling with tenant quotas."""
        logger.info("\n=== SYNC SCHEDULING DEMO ===")
        
        # Configure tenant quotas
        for tenant_id, source_dir in self.tenant_dirs.items():
            quota = TenantQuota(
                tenant_id=tenant_id,
                max_concurrent_operations=2,
                max_daily_operations=10,
                max_hourly_operations=5,
                priority_boost=1 if tenant_id == "tenant_alpha" else 0  # Give alpha priority
            )
            sync_scheduler.set_tenant_quota(tenant_id, quota)
        
        # Register operation handlers
        sync_scheduler.register_operation_handler("delta_sync", self._handle_delta_sync)
        sync_scheduler.register_operation_handler("full_sync", self._handle_full_sync)
        
        # Start scheduler
        await sync_scheduler.start_scheduler()
        await sync_logger.start_background_tasks()
        
        # Schedule various operations
        operations = []
        for tenant_id, source_dir in self.tenant_dirs.items():
            # Schedule delta sync (normal priority)
            op_id = await sync_scheduler.schedule_operation(
                tenant_id=tenant_id,
                source_folder=source_dir,
                operation_type="delta_sync",
                priority=SyncPriority.NORMAL,
                metadata={"target_folder": self.target_dirs[tenant_id]}
            )
            operations.append(op_id)
            
            # Schedule full sync (high priority)
            op_id = await sync_scheduler.schedule_operation(
                tenant_id=tenant_id,
                source_folder=source_dir,
                operation_type="full_sync",
                priority=SyncPriority.HIGH,
                metadata={"target_folder": self.target_dirs[tenant_id]}
            )
            operations.append(op_id)
        
        # Wait for operations to process
        logger.info("Waiting for scheduled operations to complete...")
        await asyncio.sleep(10)
        
        # Show scheduler stats
        stats = sync_scheduler.get_scheduler_stats()
        logger.info(f"Scheduler processed {stats['scheduler']['operations_completed']} operations")
        
        # Show operation statuses
        for op_id in operations[:3]:  # Show first 3
            status = sync_scheduler.get_operation_status(op_id)
            if status:
                logger.info(f"Operation {op_id}: {status['status']} in {status.get('actual_duration', 0):.2f}s")
    
    async def _handle_delta_sync(self, operation) -> None:
        """Handler for delta sync operations."""
        tenant_id = operation.tenant_id
        source_folder = operation.source_folder
        target_folder = operation.metadata.get("target_folder")
        
        logger.info(f"Executing delta sync for {tenant_id}: {source_folder} -> {target_folder}")
        
        # Log sync start
        sync_logger.log_event(
            event_type=SyncEventType.SYNC_STARTED,
            tenant_id=tenant_id,
            folder_name=Path(source_folder).name,
            message="Delta sync started",
            operation_id=operation.operation_id
        )
        
        try:
            # Register folder and perform sync
            engine = await delta_sync_manager.get_engine(tenant_id)
            engine.register_folder(Path(source_folder).name, source_folder)
            
            # Create baseline if not exists
            await engine.create_baseline_snapshot(Path(source_folder).name)
            
            # Perform sync
            result = await engine.sync_folder(
                Path(source_folder).name, 
                target_folder,
                dry_run=False
            )
            
            # Log completion
            sync_logger.log_event(
                event_type=SyncEventType.SYNC_COMPLETED,
                tenant_id=tenant_id,
                folder_name=Path(source_folder).name,
                message=f"Delta sync completed: {result.operations_count} operations",
                operation_id=operation.operation_id,
                duration=result.duration,
                bytes_processed=result.bytes_transferred
            )
            
            logger.info(f"Delta sync completed for {tenant_id}: {result.operations_count} operations, {result.bytes_transferred} bytes")
            
        except Exception as e:
            sync_logger.log_event(
                event_type=SyncEventType.SYNC_FAILED,
                tenant_id=tenant_id,
                folder_name=Path(source_folder).name,
                message=f"Delta sync failed: {str(e)}",
                operation_id=operation.operation_id,
                alert_level=AlertLevel.ERROR
            )
            raise
    
    async def _handle_full_sync(self, operation) -> None:
        """Handler for full sync operations."""
        tenant_id = operation.tenant_id
        source_folder = operation.source_folder
        target_folder = operation.metadata.get("target_folder")
        
        logger.info(f"Executing full sync for {tenant_id}: {source_folder} -> {target_folder}")
        
        # Simulate full sync (copy all files)
        start_time = time.time()
        bytes_copied = 0
        
        try:
            source_path = Path(source_folder)
            target_path = Path(target_folder)
            
            for file_path in source_path.rglob('*'):
                if file_path.is_file():
                    rel_path = file_path.relative_to(source_path)
                    target_file = target_path / rel_path
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    shutil.copy2(file_path, target_file)
                    bytes_copied += file_path.stat().st_size
            
            duration = time.time() - start_time
            
            sync_logger.log_event(
                event_type=SyncEventType.SYNC_COMPLETED,
                tenant_id=tenant_id,
                folder_name=Path(source_folder).name,
                message=f"Full sync completed",
                operation_id=operation.operation_id,
                duration=duration,
                bytes_processed=bytes_copied
            )
            
            logger.info(f"Full sync completed for {tenant_id}: {bytes_copied} bytes in {duration:.2f}s")
            
        except Exception as e:
            sync_logger.log_event(
                event_type=SyncEventType.SYNC_FAILED,
                tenant_id=tenant_id,
                folder_name=Path(source_folder).name,
                message=f"Full sync failed: {str(e)}",
                operation_id=operation.operation_id,
                alert_level=AlertLevel.ERROR
            )
            raise
    
    async def demonstrate_conflict_resolution(self) -> None:
        """Demonstrate conflict detection and resolution."""
        logger.info("\n=== CONFLICT RESOLUTION DEMO ===")
        
        # Create conflicting files
        tenant_id = "tenant_alpha"
        source_dir = Path(self.tenant_dirs[tenant_id])
        target_dir = Path(self.target_dirs[tenant_id])
        
        # Create different versions of the same file
        conflict_file = "policies/conflict_policy.txt"
        
        # Source version
        source_file = source_dir / conflict_file
        source_file.parent.mkdir(parents=True, exist_ok=True)
        with open(source_file, 'w') as f:
            f.write("Source version of policy\nUpdated: " + datetime.now().isoformat())
        
        # Target version (different content, simulate external modification)
        target_file = target_dir / conflict_file  
        target_file.parent.mkdir(parents=True, exist_ok=True)
        with open(target_file, 'w') as f:
            f.write("Target version of policy\nModified externally: " + datetime.now().isoformat())
        
        # Wait a bit to ensure different timestamps
        await asyncio.sleep(1)
        
        # Create file snapshots for conflict detection
        from .delta_sync import FolderSnapshot
        source_snapshot = FolderSnapshot(str(source_dir))
        source_snapshot.create_snapshot()
        
        target_snapshot = FolderSnapshot(str(target_dir))
        target_snapshot.create_snapshot()
        
        # Detect conflicts
        conflicts = await conflict_manager.detect_and_resolve_conflicts(
            source_snapshot.files,
            target_snapshot.files,
            tenant_id,
            "policies",
            str(source_dir),
            str(target_dir),
            auto_resolve=False  # Don't auto-resolve, show manual resolution
        )
        
        logger.info(f"Detected {len(conflicts)} conflicts")
        
        for conflict in conflicts:
            logger.info(f"Conflict: {conflict.conflict_type.value} in {conflict.source_path}")
            
            # Log conflict
            sync_logger.log_event(
                event_type=SyncEventType.CONFLICT_DETECTED,
                tenant_id=tenant_id,
                folder_name="policies",
                message=f"Conflict detected: {conflict.conflict_type.value}",
                details=conflict.to_dict()
            )
        
        # Manually resolve first conflict using "newer wins" strategy
        if conflicts:
            conflict = conflicts[0]
            success = await conflict_manager.resolve_conflict_manually(
                conflict.conflict_id,
                ConflictResolutionStrategy.NEWER_WINS,
                str(source_dir),
                str(target_dir)
            )
            
            if success:
                logger.info(f"Resolved conflict {conflict.conflict_id} using newer_wins strategy")
                sync_logger.log_event(
                    event_type=SyncEventType.CONFLICT_RESOLVED,
                    tenant_id=tenant_id,
                    folder_name="policies",
                    message=f"Conflict resolved using newer_wins strategy",
                    details={'conflict_id': conflict.conflict_id}
                )
    
    async def demonstrate_metrics_and_logging(self) -> None:
        """Demonstrate comprehensive logging and metrics."""
        logger.info("\n=== METRICS AND LOGGING DEMO ===")
        
        # Generate some activity for metrics
        for tenant_id in self.tenant_dirs.keys():
            # Log various events
            sync_logger.log_event(
                event_type=SyncEventType.FILE_PROCESSED,
                tenant_id=tenant_id,
                folder_name="documents",
                message="Processed employee guide",
                file_path="documents/employee_guide.docx",
                bytes_processed=1024,
                details={'operation_type': 'update'}
            )
            
            sync_logger.log_event(
                event_type=SyncEventType.FILE_PROCESSED,
                tenant_id=tenant_id,
                folder_name="policies",
                message="Created new policy file",
                file_path="policies/new_policy.txt",
                bytes_processed=512,
                details={'operation_type': 'create'}
            )
        
        # Wait for metrics to be processed
        await asyncio.sleep(2)
        
        # Show folder status for each tenant
        for tenant_id in self.tenant_dirs.keys():
            status = sync_logger.get_folder_status(tenant_id, "documents")
            logger.info(f"Folder status for {tenant_id}/documents: {status['status']}")
            
            # Show tenant summary
            summary = sync_logger.get_tenant_summary(tenant_id)
            logger.info(f"Tenant {tenant_id} summary: {summary['total_syncs']} syncs, {summary['files_processed']} files processed")
        
        # Show recent events
        recent_events = sync_logger.get_recent_events(limit=5)
        logger.info(f"Recent events ({len(recent_events)}):")
        for event in recent_events:
            logger.info(f"  {event['timestamp']}: {event['event_type']} - {event['message']}")
    
    async def cleanup_demo_environment(self) -> None:
        """Clean up demo environment."""
        if self.demo_dir and self.demo_dir.exists():
            shutil.rmtree(self.demo_dir)
            logger.info(f"Cleaned up demo directory: {self.demo_dir}")
        
        # Stop background services
        await sync_scheduler.stop_scheduler()
        await sync_logger.stop_background_tasks()
    
    async def run_complete_demo(self) -> None:
        """Run the complete sync system demonstration."""
        try:
            logger.info("Starting comprehensive sync system demo...")
            
            # Setup
            await self.setup_demo_environment()
            
            # Demonstrate each component
            await self.demonstrate_sync_scheduling()
            await self.demonstrate_conflict_resolution()
            await self.demonstrate_metrics_and_logging()
            
            logger.info("\n=== DEMO SUMMARY ===")
            
            # Final stats
            scheduler_stats = sync_scheduler.get_scheduler_stats()
            logger.info(f"Scheduler processed {scheduler_stats['scheduler']['operations_completed']} operations")
            
            conflict_stats = conflict_manager.get_conflict_stats()
            logger.info(f"Conflicts: {conflict_stats['total_conflicts']} total, {conflict_stats['resolved']} resolved")
            
            logger.info("Demo completed successfully!")
            
        except Exception as e:
            logger.error(f"Demo failed: {e}")
            raise
        finally:
            await self.cleanup_demo_environment()

async def main():
    """Main demo function."""
    demo = SyncDemo()
    await demo.run_complete_demo()

if __name__ == "__main__":
    asyncio.run(main()) 