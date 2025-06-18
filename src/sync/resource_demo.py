#!/usr/bin/env python3
"""
Resource management system demonstration.

This script demonstrates the comprehensive resource management capabilities
including allocation, fair scheduling, monitoring, and optimization.
"""

import asyncio
import logging
import time
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import resource management components
from .resource_manager import (
    ResourceType, ResourceLimits, resource_allocator
)
from .fair_scheduler import (
    TaskPriority, SchedulingPolicy, FairTenantQuota, fair_scheduler
)
from .resource_monitor import (
    AlertSeverity, resource_monitor
)
from .resource_optimizer import (
    OptimizationStrategy, BatchConfiguration, ParallelismConfiguration,
    resource_optimizer
)

async def setup_tenants():
    """Set up multiple tenants with different resource limits."""
    logger.info("Setting up tenant configurations...")
    
    # Tenant configurations
    tenants = {
        'enterprise_corp': {
            'limits': ResourceLimits(
                max_gpu_memory_mb=2048.0,
                max_cpu_cores=8.0,
                max_memory_mb=8192.0,
                max_disk_io_mbps=200.0,
                max_operation_duration=3600.0
            ),
            'quota': FairTenantQuota(
                tenant_id='enterprise_corp',
                max_concurrent_tasks=10,
                max_queued_tasks=50,
                default_priority=TaskPriority.HIGH,
                priority_boost=1,
                fair_share_weight=3.0,
                max_tasks_per_minute=20,
                max_tasks_per_hour=500
            )
        },
        'startup_inc': {
            'limits': ResourceLimits(
                max_gpu_memory_mb=1024.0,
                max_cpu_cores=4.0,
                max_memory_mb=4096.0,
                max_disk_io_mbps=100.0,
                max_operation_duration=1800.0
            ),
            'quota': FairTenantQuota(
                tenant_id='startup_inc',
                max_concurrent_tasks=5,
                max_queued_tasks=25,
                default_priority=TaskPriority.NORMAL,
                priority_boost=0,
                fair_share_weight=1.5,
                max_tasks_per_minute=10,
                max_tasks_per_hour=200
            )
        },
        'research_lab': {
            'limits': ResourceLimits(
                max_gpu_memory_mb=4096.0,
                max_cpu_cores=12.0,
                max_memory_mb=16384.0,
                max_disk_io_mbps=300.0,
                max_operation_duration=7200.0
            ),
            'quota': FairTenantQuota(
                tenant_id='research_lab',
                max_concurrent_tasks=8,
                max_queued_tasks=40,
                default_priority=TaskPriority.HIGH,
                priority_boost=2,
                fair_share_weight=2.5,
                max_tasks_per_minute=15,
                max_tasks_per_hour=300
            )
        }
    }
    
    # Configure tenants
    for tenant_id, config in tenants.items():
        # Set resource limits
        resource_allocator.set_tenant_limits(tenant_id, config['limits'])
        
        # Set scheduling quota
        fair_scheduler.set_tenant_quota(tenant_id, config['quota'])
        
        logger.info(f"Configured tenant: {tenant_id}")
    
    return list(tenants.keys())

async def demo_resource_allocation():
    """Demonstrate resource allocation system."""
    logger.info("\n=== Resource Allocation Demo ===")
    
    tenant_id = "enterprise_corp"
    operation_id = "demo_allocation_001"
    
    # Define resource requirements
    resource_requirements = {
        ResourceType.GPU: 512.0,  # 512MB GPU memory
        ResourceType.CPU: 2.0,    # 2 CPU cores
        ResourceType.MEMORY: 1024.0,  # 1GB memory
        ResourceType.DISK_IO: 50.0    # 50MB/s disk I/O
    }
    
    logger.info(f"Requesting resources for {tenant_id}: {resource_requirements}")
    
    # Allocate resources
    allocations = await resource_allocator.allocate_resources(
        tenant_id=tenant_id,
        operation_id=operation_id,
        resource_requirements=resource_requirements,
        duration_seconds=300.0  # 5 minutes
    )
    
    # Check allocation results
    successful_allocations = {rt: alloc for rt, alloc in allocations.items() if alloc is not None}
    failed_allocations = {rt: alloc for rt, alloc in allocations.items() if alloc is None}
    
    logger.info(f"Successful allocations: {len(successful_allocations)}")
    logger.info(f"Failed allocations: {len(failed_allocations)}")
    
    if successful_allocations:
        # Simulate some work
        logger.info("Simulating work with allocated resources...")
        await asyncio.sleep(2)
        
        # Get system status
        status = resource_allocator.get_system_status()
        logger.info(f"System resource status: {status['allocations']}")
        
        # Release allocations
        for allocation in successful_allocations.values():
            await resource_allocator.release_allocation(allocation.allocation_id)
        
        logger.info("Released all allocations")
    
    return len(successful_allocations) > 0

async def demo_fair_scheduling():
    """Demonstrate fair scheduling system."""
    logger.info("\n=== Fair Scheduling Demo ===")
    
    # Set scheduling policy
    fair_scheduler.set_scheduling_policy(SchedulingPolicy.FAIR_SHARE)
    
    # Define sample tasks
    async def sample_task(tenant_id: str, task_num: int, duration: float):
        """Sample task that simulates work."""
        logger.info(f"Task {task_num} for {tenant_id} started")
        await asyncio.sleep(duration)
        logger.info(f"Task {task_num} for {tenant_id} completed")
    
    # Submit tasks for different tenants
    tenants = ['enterprise_corp', 'startup_inc', 'research_lab']
    task_ids = []
    
    for i in range(15):  # Submit 15 tasks
        tenant_id = random.choice(tenants)
        priority = random.choice(list(TaskPriority))
        duration = random.uniform(1.0, 5.0)
        
        # Resource requirements for the task
        resource_requirements = {
            ResourceType.CPU: random.uniform(0.5, 2.0),
            ResourceType.MEMORY: random.uniform(256.0, 1024.0)
        }
        
        try:
            task_id = await fair_scheduler.submit_task(
                tenant_id=tenant_id,
                task_function=sample_task,
                resource_requirements=resource_requirements,
                priority=priority,
                estimated_duration=duration,
                tenant_id,  # task args
                i + 1,
                duration
            )
            
            task_ids.append(task_id)
            logger.info(f"Submitted task {task_id} for {tenant_id} with priority {priority.name}")
            
        except ValueError as e:
            logger.warning(f"Failed to submit task for {tenant_id}: {e}")
    
    # Start the scheduler
    await fair_scheduler.start_scheduler()
    
    # Let tasks run for a while
    logger.info("Letting tasks run...")
    await asyncio.sleep(10)
    
    # Get scheduler statistics
    stats = fair_scheduler.get_scheduler_stats()
    logger.info(f"Scheduler stats: {stats['running_tasks']} running, {stats['completed_tasks']} completed")
    
    # Show tenant statistics
    for tenant_id in tenants:
        tenant_stats = stats['tenant_stats'].get(tenant_id, {})
        logger.info(f"Tenant {tenant_id}: {tenant_stats}")
    
    # Stop the scheduler
    await fair_scheduler.stop_scheduler()
    
    return len(task_ids)

async def demo_resource_monitoring():
    """Demonstrate resource monitoring system."""
    logger.info("\n=== Resource Monitoring Demo ===")
    
    # Set up resource monitor with allocator
    resource_monitor.set_resource_allocator(resource_allocator)
    
    # Start monitoring
    await resource_monitor.start_monitoring()
    
    # Let monitoring collect some data
    logger.info("Collecting monitoring data...")
    await asyncio.sleep(5)
    
    # Get monitoring status
    status = resource_monitor.get_monitoring_status()
    logger.info(f"Monitoring status: {status}")
    
    # Collect some metrics manually
    system_metrics = await resource_monitor.collect_system_metrics()
    logger.info(f"Collected {len(system_metrics)} system metrics")
    
    allocation_metrics = await resource_monitor.collect_resource_allocation_metrics()
    logger.info(f"Collected {len(allocation_metrics)} allocation metrics")
    
    # Add a custom alert handler
    async def custom_alert_handler(alert):
        logger.warning(f"CUSTOM ALERT: {alert.message} (severity: {alert.severity.value})")
    
    resource_monitor.alert_manager.add_alert_handler(custom_alert_handler)
    
    # Trigger a test alert by adding a rule with low threshold
    resource_monitor.alert_manager.add_alert_rule(
        "test_alert",
        "cpu_utilization_percent",
        1.0,  # Very low threshold to trigger easily
        "greater",
        AlertSeverity.INFO
    )
    
    # Wait for potential alerts
    await asyncio.sleep(3)
    
    # Get active alerts
    active_alerts = resource_monitor.alert_manager.get_active_alerts()
    logger.info(f"Active alerts: {len(active_alerts)}")
    
    # Generate a usage report
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=10)
    
    report = resource_monitor.generate_usage_report(start_time, end_time)
    logger.info(f"Usage report generated for {report['report_period']}")
    
    # Stop monitoring
    await resource_monitor.stop_monitoring()
    
    return len(system_metrics) + len(allocation_metrics)

async def demo_resource_optimization():
    """Demonstrate resource optimization system."""
    logger.info("\n=== Resource Optimization Demo ===")
    
    # Set optimization strategy
    resource_optimizer.set_optimization_strategy(OptimizationStrategy.BALANCED)
    
    # Configure batch optimization
    batch_config = BatchConfiguration(
        min_batch_size=5,
        max_batch_size=50,
        target_batch_size=20,
        batch_timeout_seconds=30.0,
        adaptive_sizing=True
    )
    
    resource_optimizer.batch_optimizer.set_configuration("document_processing", batch_config)
    
    # Configure parallelism optimization
    parallel_config = ParallelismConfiguration(
        min_workers=2,
        max_workers=8,
        target_workers=4,
        adaptive_scaling=True,
        scale_up_threshold=0.7,
        scale_down_threshold=0.3
    )
    
    resource_optimizer.parallelism_optimizer.set_configuration("document_processing", parallel_config)
    
    # Start optimization
    await resource_optimizer.start_optimization()
    
    # Simulate some batch processing performance data
    operation_type = "document_processing"
    
    for i in range(10):
        batch_size = random.randint(10, 30)
        processing_time = random.uniform(1.0, 10.0)
        success_count = batch_size - random.randint(0, 2)
        error_count = batch_size - success_count
        
        resource_optimizer.batch_optimizer.record_batch_performance(
            operation_type, batch_size, processing_time, success_count, error_count
        )
        
        # Simulate utilization data
        worker_count = random.randint(3, 6)
        queue_size = random.randint(5, 20)
        active_workers = random.randint(1, worker_count)
        
        resource_optimizer.parallelism_optimizer.record_utilization(
            operation_type, worker_count, queue_size, active_workers
        )
    
    # Get optimization statistics
    batch_stats = resource_optimizer.batch_optimizer.get_performance_stats(operation_type)
    logger.info(f"Batch optimization stats: {batch_stats}")
    
    parallel_stats = resource_optimizer.parallelism_optimizer.get_utilization_stats(operation_type)
    logger.info(f"Parallelism optimization stats: {parallel_stats}")
    
    # Test cache management
    cache = resource_optimizer.cache_manager
    
    # Put some test data in cache
    for i in range(20):
        key = f"test_key_{i}"
        value = f"test_value_{i}" * 100  # Make it somewhat large
        cache.put(key, value, ttl_seconds=60.0)
    
    cache_stats = cache.get_cache_stats()
    logger.info(f"Cache stats: {cache_stats}")
    
    # Test cache retrieval
    retrieved_value = cache.get("test_key_5")
    logger.info(f"Retrieved from cache: {retrieved_value is not None}")
    
    # Optimize configurations
    optimized_batch = await resource_optimizer.optimize_batch_configuration(operation_type)
    logger.info(f"Optimized batch config: {optimized_batch.to_dict()}")
    
    optimized_parallel = await resource_optimizer.optimize_parallelism_configuration(operation_type)
    logger.info(f"Optimized parallelism config: {optimized_parallel.to_dict()}")
    
    # Perform resource cleanup
    await resource_optimizer.cleanup_resources()
    
    # Get overall optimization stats
    opt_stats = resource_optimizer.get_optimization_stats()
    logger.info(f"Optimization system stats: {opt_stats}")
    
    # Stop optimization
    await resource_optimizer.stop_optimization()
    
    return True

async def demo_integrated_workflow():
    """Demonstrate integrated workflow with all systems."""
    logger.info("\n=== Integrated Workflow Demo ===")
    
    # Start all systems
    await resource_monitor.start_monitoring()
    await fair_scheduler.start_scheduler()
    await resource_optimizer.start_optimization()
    
    # Simulate a complex workflow
    workflow_tasks = []
    
    async def complex_task(tenant_id: str, task_type: str, complexity: str):
        """Complex task that uses multiple resources."""
        
        # Define resource requirements based on complexity
        if complexity == "light":
            requirements = {
                ResourceType.CPU: 1.0,
                ResourceType.MEMORY: 512.0
            }
        elif complexity == "medium":
            requirements = {
                ResourceType.CPU: 2.0,
                ResourceType.MEMORY: 1024.0,
                ResourceType.DISK_IO: 25.0
            }
        else:  # heavy
            requirements = {
                ResourceType.GPU: 256.0,
                ResourceType.CPU: 4.0,
                ResourceType.MEMORY: 2048.0,
                ResourceType.DISK_IO: 50.0
            }
        
        # Use managed allocation context
        async with resource_allocator.managed_allocation(
            tenant_id, f"{task_type}_task", requirements, 120.0
        ) as allocations:
            
            if any(alloc is None for alloc in allocations.values()):
                logger.warning(f"Task {task_type} couldn't get all required resources")
                return False
            
            # Simulate work
            work_duration = random.uniform(2.0, 8.0)
            logger.info(f"Executing {complexity} {task_type} task for {tenant_id} ({work_duration:.1f}s)")
            await asyncio.sleep(work_duration)
            
            return True
    
    # Submit various types of tasks
    tenants = ['enterprise_corp', 'startup_inc', 'research_lab']
    task_types = ['document_processing', 'data_analysis', 'ml_training', 'report_generation']
    complexities = ['light', 'medium', 'heavy']
    
    for i in range(20):
        tenant_id = random.choice(tenants)
        task_type = random.choice(task_types)
        complexity = random.choice(complexities)
        priority = TaskPriority.HIGH if complexity == 'heavy' else TaskPriority.NORMAL
        
        # Resource requirements for scheduling
        if complexity == "light":
            requirements = {ResourceType.CPU: 1.0, ResourceType.MEMORY: 512.0}
        elif complexity == "medium":
            requirements = {ResourceType.CPU: 2.0, ResourceType.MEMORY: 1024.0, ResourceType.DISK_IO: 25.0}
        else:
            requirements = {ResourceType.GPU: 256.0, ResourceType.CPU: 4.0, ResourceType.MEMORY: 2048.0, ResourceType.DISK_IO: 50.0}
        
        try:
            task_id = await fair_scheduler.submit_task(
                tenant_id=tenant_id,
                task_function=complex_task,
                resource_requirements=requirements,
                priority=priority,
                estimated_duration=random.uniform(5.0, 15.0),
                tenant_id,
                task_type,
                complexity
            )
            
            workflow_tasks.append(task_id)
            logger.info(f"Submitted {complexity} {task_type} task for {tenant_id}")
            
        except ValueError as e:
            logger.warning(f"Failed to submit task: {e}")
        
        # Small delay between submissions
        await asyncio.sleep(0.5)
    
    # Let the workflow run
    logger.info(f"Running integrated workflow with {len(workflow_tasks)} tasks...")
    await asyncio.sleep(30)
    
    # Get comprehensive statistics
    scheduler_stats = fair_scheduler.get_scheduler_stats()
    monitor_status = resource_monitor.get_monitoring_status()
    optimizer_stats = resource_optimizer.get_optimization_stats()
    
    logger.info(f"Workflow Results:")
    logger.info(f"  - Tasks completed: {scheduler_stats['completed_tasks']}")
    logger.info(f"  - Tasks running: {scheduler_stats['running_tasks']}")
    logger.info(f"  - Active alerts: {monitor_status['active_alerts']}")
    logger.info(f"  - Cache utilization: {optimizer_stats['cache_stats']['utilization_percent']:.1f}%")
    
    # Generate final report
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=5)
    
    final_report = resource_monitor.generate_usage_report(start_time, end_time)
    logger.info(f"Final system report: {final_report['system_metrics']}")
    
    # Clean shutdown
    await fair_scheduler.stop_scheduler()
    await resource_monitor.stop_monitoring()
    await resource_optimizer.stop_optimization()
    
    return len(workflow_tasks)

async def main():
    """Main demonstration function."""
    logger.info("Starting Resource Management System Demo")
    logger.info("=" * 60)
    
    try:
        # Setup
        tenants = await setup_tenants()
        logger.info(f"Set up {len(tenants)} tenants")
        
        # Individual component demos
        allocation_success = await demo_resource_allocation()
        tasks_scheduled = await demo_fair_scheduling()
        metrics_collected = await demo_resource_monitoring()
        optimization_success = await demo_resource_optimization()
        
        # Integrated workflow demo
        workflow_tasks = await demo_integrated_workflow()
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("DEMO SUMMARY")
        logger.info("=" * 60)
        logger.info(f"✓ Resource allocation: {'Success' if allocation_success else 'Failed'}")
        logger.info(f"✓ Fair scheduling: {tasks_scheduled} tasks submitted")
        logger.info(f"✓ Resource monitoring: {metrics_collected} metrics collected")
        logger.info(f"✓ Resource optimization: {'Success' if optimization_success else 'Failed'}")
        logger.info(f"✓ Integrated workflow: {workflow_tasks} tasks in workflow")
        logger.info("\nAll resource management components demonstrated successfully!")
        
    except Exception as e:
        logger.error(f"Demo failed with error: {e}")
        raise

if __name__ == "__main__":
    # Run the demo
    asyncio.run(main()) 