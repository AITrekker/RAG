"""
Demo script for file system monitoring.

This script demonstrates how to use the file monitoring system
with tenant-aware file watching, change detection, and event handling.
"""

import asyncio
import logging
from pathlib import Path
from datetime import datetime
import tempfile
import shutil

from .integration import file_monitoring_system
from .file_watcher import FileEvent

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def demo_file_monitoring():
    """Demonstrate the file monitoring system."""
    
    # Create temporary directories for demo
    temp_dir = Path(tempfile.mkdtemp(prefix="rag_demo_"))
    tenant1_dir = temp_dir / "tenant1"
    tenant2_dir = temp_dir / "tenant2"
    
    try:
        logger.info("=== File Monitoring System Demo ===")
        
        # Custom event handler for demo
        def demo_event_handler(event: FileEvent):
            logger.info(f"DEMO EVENT: {event.event_type.value} - {event.file_path}")
        
        # Add tenants to monitoring system
        logger.info("Adding tenants to monitoring system...")
        
        success1 = await file_monitoring_system.add_tenant(
            tenant_id="tenant1",
            source_folders=[str(tenant1_dir)],
            event_handlers=[demo_event_handler]
        )
        
        success2 = await file_monitoring_system.add_tenant(
            tenant_id="tenant2", 
            source_folders=[str(tenant2_dir)]
        )
        
        if not (success1 and success2):
            logger.error("Failed to add tenants")
            return
        
        # Start monitoring system
        logger.info("Starting monitoring system...")
        await file_monitoring_system.start_monitoring()
        
        # Give system time to initialize
        await asyncio.sleep(2)
        
        logger.info("System status:")
        status = file_monitoring_system.get_system_status()
        logger.info(f"Running: {status['is_running']}")
        logger.info(f"Tenants: {file_monitoring_system.get_tenant_list()}")
        
        # Simulate file operations
        logger.info("\n=== Simulating File Operations ===")
        
        # Create some files
        logger.info("Creating test files...")
        test_file1 = tenant1_dir / "document1.pdf"
        test_file2 = tenant1_dir / "report.docx"
        test_file3 = tenant2_dir / "data.xlsx"
        
        test_file1.write_text("PDF content")
        test_file2.write_text("DOCX content")
        test_file3.write_text("XLSX content")
        
        # Wait for events to be processed
        await asyncio.sleep(3)
        
        # Modify files
        logger.info("Modifying files...")
        test_file1.write_text("Modified PDF content")
        test_file2.write_text("Modified DOCX content")
        
        # Wait for events to be processed
        await asyncio.sleep(3)
        
        # Perform manual change scan
        logger.info("Performing manual change scan...")
        changes = await file_monitoring_system.perform_change_scan()
        
        for tenant_id, tenant_changes in changes.items():
            logger.info(f"Tenant {tenant_id}: {len(tenant_changes)} changes detected")
            for change in tenant_changes[:3]:  # Show first 3 changes
                logger.info(f"  - {change.change_type.value}: {change.file_path}")
        
        # Get tenant information
        logger.info("\n=== Tenant Information ===")
        for tenant_id in ["tenant1", "tenant2"]:
            info = file_monitoring_system.get_tenant_info(tenant_id)
            if info:
                logger.info(f"Tenant {tenant_id}:")
                logger.info(f"  - Active: {info['is_active']}")
                logger.info(f"  - Files watched: {info['watcher_stats']['files_watched']}")
                logger.info(f"  - Events processed: {info['watcher_stats']['events_processed']}")
                logger.info(f"  - Changes tracked: {info['change_count']}")
        
        # Delete a file
        logger.info("Deleting a file...")
        test_file3.unlink()
        
        # Wait for deletion event
        await asyncio.sleep(2)
        
        logger.info("\n=== Final System Status ===")
        final_status = file_monitoring_system.get_system_status()
        components = final_status['components']
        
        logger.info(f"Event Handler Queue Size: {components['event_handler']['handler']['queue_size']}")
        logger.info(f"Total Events Processed: {components['event_handler']['handler']['processed_events']}")
        
        if 'monitoring' in final_status:
            monitoring = final_status['monitoring']
            logger.info(f"System Health: {'Healthy' if monitoring['is_healthy'] else 'Unhealthy'}")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        
    finally:
        # Clean up
        logger.info("Stopping monitoring system...")
        await file_monitoring_system.stop_monitoring()
        
        # Remove tenants
        await file_monitoring_system.remove_tenant("tenant1")
        await file_monitoring_system.remove_tenant("tenant2")
        
        # Clean up temporary directory
        try:
            shutil.rmtree(temp_dir)
            logger.info("Cleaned up temporary files")
        except Exception as e:
            logger.warning(f"Failed to clean up temp directory: {e}")
        
        logger.info("Demo completed!")

if __name__ == "__main__":
    asyncio.run(demo_file_monitoring()) 