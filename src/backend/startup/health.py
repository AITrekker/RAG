"""
Health checks for backend startup.

Provides health check functionality that can be used during
startup and by monitoring systems.
"""

import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)


async def check_database_health() -> Tuple[bool, str]:
    """Check if database connection is healthy."""
    try:
        from src.backend.database import check_database_health as async_check_db_health
        
        # Run the async health check
        is_healthy = await async_check_db_health()
        
        if is_healthy:
            return True, "Database connection healthy"
        else:
            return False, "Database connection failed"
            
    except Exception as e:
        return False, f"Database health check error: {e}"


# Qdrant health check removed - using PostgreSQL + pgvector instead


async def check_services_health() -> Tuple[bool, str]:
    """Check if core services can be initialized."""
    try:
        # Try to import and instantiate core services
        from src.backend.database import get_async_db
        from src.backend.services.tenant_service import TenantService
        
        async for db in get_async_db():
            # Test tenant service
            tenant_service = TenantService(db)
            await tenant_service.list_tenants()
            break  # Only need to test with first session
            
        return True, "Core services healthy"
        
    except Exception as e:
        return False, f"Services health check error: {e}"


async def run_health_checks() -> Tuple[bool, Dict[str, Any]]:
    """
    Run comprehensive health checks.
    
    Returns:
        Tuple[bool, Dict[str, Any]]: (overall_success, detailed_results)
    """
    logger.info("🏥 Running health checks...")
    
    checks = {
        "database": check_database_health,
        "services": check_services_health
    }
    
    results = {}
    overall_success = True
    
    for check_name, check_func in checks.items():
        logger.info(f"Running {check_name} health check...")
        
        try:
            # Check if function is async
            import asyncio
            if asyncio.iscoroutinefunction(check_func):
                success, message = await check_func()
            else:
                success, message = check_func()
                
            results[check_name] = {
                "success": success,
                "message": message
            }
            
            if success:
                logger.info(f"✅ {check_name}: {message}")
            else:
                logger.error(f"❌ {check_name}: {message}")
                overall_success = False
                
        except Exception as e:
            error_msg = f"Health check failed with exception: {e}"
            results[check_name] = {
                "success": False,
                "message": error_msg
            }
            logger.error(f"❌ {check_name}: {error_msg}")
            overall_success = False
    
    if overall_success:
        logger.info("✅ All health checks passed!")
    else:
        logger.error("❌ Some health checks failed!")
    
    return overall_success, results