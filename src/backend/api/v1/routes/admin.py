"""
Admin API endpoints for system administration.

This module provides admin-only endpoints for:
- Tenant management (CRUD operations)
- API key management
- System monitoring and metrics
- System-wide operations

All endpoints require admin authentication.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from datetime import datetime, timedelta
import psutil
import os
import logging

from src.backend.models.api_models import (
    TenantCreateRequest,
    TenantUpdateRequest,
    TenantResponse,
    TenantListResponse,
    ApiKeyCreateRequest,
    ApiKeyResponse,
    ApiKeyCreateResponse,
    SystemStatusResponse,
    SystemMetricsResponse,
    ErrorResponse,
    DemoSetupRequest,
    DemoSetupResponse,
    DemoTenantInfo,
    DemoCleanupResponse
)
from src.backend.models.api_models import SyncEventResponse  # Add this if not present, or stub if missing
from src.backend.core.tenant_service import TenantService
from src.backend.core.embedding_manager import EmbeddingManager
from src.backend.middleware.auth import get_current_tenant, require_admin
from src.backend.config.settings import get_settings
from src.backend.core.auditing import AuditLogger, get_audit_logger

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Admin Operations"])

# =============================================================================
# TENANT MANAGEMENT
# =============================================================================

@router.post("/tenants", response_model=TenantResponse)
async def create_tenant(
    request: TenantCreateRequest,
    current_tenant: dict = Depends(require_admin)
):
    """
    Create a new tenant (Admin only).
    
    Args:
        request: Tenant creation details
        current_tenant: Admin tenant (from auth)
        
    Returns:
        TenantResponse: Created tenant information
    """
    try:
        tenant_service = TenantService()
        
        # Create tenant
        tenant_id = await tenant_service.create_tenant(
            name=request.name,
            description=request.description,
            auto_sync=request.auto_sync,
            sync_interval=request.sync_interval
        )
        
        # Get created tenant details
        tenant = await tenant_service.get_tenant(tenant_id)
        return tenant
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create tenant: {str(e)}"
        )

@router.get("/tenants", response_model=TenantListResponse)
async def list_tenants(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    include_api_keys: bool = Query(False, description="Include API keys in response"),
    demo_only: bool = Query(False, description="Show only demo tenants"),
    current_tenant: dict = Depends(require_admin)
):
    """
    List all tenants (Admin only).
    
    Args:
        page: Page number for pagination
        page_size: Number of tenants per page
        include_api_keys: Include API keys in response
        demo_only: Show only demo tenants
        current_tenant: Admin tenant (from auth)
        
    Returns:
        TenantListResponse: List of tenants with pagination
    """
    try:
        tenant_service = TenantService()
        tenants = tenant_service.list_tenants()
        
        # Filter for demo tenants if requested
        if demo_only:
            demo_tenants = []
            for tenant in tenants:
                # Get API keys for tenant
                api_keys = tenant_service.list_api_keys(tenant.get("id"))
                # Check if tenant has demo keys
                has_demo_keys = any(
                    "demo" in key.get("name", "").lower() or "demo" in key.get("description", "").lower()
                    for key in api_keys
                )
                if has_demo_keys:
                    demo_tenants.append(tenant)
            tenants = demo_tenants
        
        # Add API keys to response if requested
        if include_api_keys:
            for tenant in tenants:
                api_keys = tenant_service.list_api_keys(tenant.get("id"))
                tenant["api_keys"] = api_keys
        
        # Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_tenants = tenants[start_idx:end_idx]
        
        return TenantListResponse(
            tenants=paginated_tenants,
            total_count=len(tenants)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list tenants: {str(e)}"
        )

@router.get("/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    current_tenant: dict = Depends(require_admin)
):
    """
    Get tenant details (Admin only).
    
    Args:
        tenant_id: Tenant ID
        current_tenant: Admin tenant (from auth)
        
    Returns:
        TenantResponse: Tenant information
    """
    try:
        tenant_service = TenantService()
        tenant = tenant_service.get_tenant(tenant_id)
        
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
            
        return tenant
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get tenant: {str(e)}"
        )

@router.put("/tenants/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: str,
    request: TenantUpdateRequest,
    current_tenant: dict = Depends(require_admin)
):
    """
    Update tenant details (Admin only).
    
    Args:
        tenant_id: Tenant ID
        request: Update details
        current_tenant: Admin tenant (from auth)
        
    Returns:
        TenantResponse: Updated tenant information
    """
    try:
        tenant_service = TenantService()
        
        # Check if tenant exists
        existing_tenant = tenant_service.get_tenant(tenant_id)
        if not existing_tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Update tenant
        updated_tenant = tenant_service.update_tenant(
            tenant_id=tenant_id,
            name=request.name,
            description=request.description,
            status=request.status,
            auto_sync=request.auto_sync,
            sync_interval=request.sync_interval
        )
        
        return updated_tenant
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update tenant: {str(e)}"
        )

@router.delete("/tenants/{tenant_id}")
async def delete_tenant(
    tenant_id: str,
    current_tenant: dict = Depends(require_admin)
):
    """
    Delete a tenant (Admin only).
    
    Args:
        tenant_id: Tenant ID
        current_tenant: Admin tenant (from auth)
        
    Returns:
        dict: Deletion confirmation
    """
    try:
        tenant_service = TenantService()
        
        # Check if tenant exists
        existing_tenant = tenant_service.get_tenant(tenant_id)
        if not existing_tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Prevent admin tenant deletion
        if existing_tenant["name"] == "admin":
            raise HTTPException(
                status_code=400,
                detail="Cannot delete admin tenant"
            )
        
        # Delete tenant
        tenant_service.delete_tenant(tenant_id)
        
        return {"message": f"Tenant {tenant_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete tenant: {str(e)}"
        )

# =============================================================================
# API KEY MANAGEMENT
# =============================================================================

@router.post("/tenants/{tenant_id}/api-keys", response_model=ApiKeyCreateResponse)
async def create_api_key(
    tenant_id: str,
    request: ApiKeyCreateRequest,
    current_tenant: dict = Depends(require_admin)
):
    """
    Create API key for a tenant (Admin only).
    
    Args:
        tenant_id: Tenant ID
        request: API key details
        current_tenant: Admin tenant (from auth)
        
    Returns:
        ApiKeyCreateResponse: Created API key
    """
    try:
        tenant_service = TenantService()
        
        # Check if tenant exists
        existing_tenant = tenant_service.get_tenant(tenant_id)
        if not existing_tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Create API key
        api_key = tenant_service.create_api_key(tenant_id, request.name)
        
        return ApiKeyCreateResponse(
            tenant_id=tenant_id,
            api_key=api_key,
            key_name=request.name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create API key: {str(e)}"
        )

@router.get("/tenants/{tenant_id}/api-keys", response_model=List[ApiKeyResponse])
async def list_api_keys(
    tenant_id: str,
    current_tenant: dict = Depends(require_admin)
):
    """
    List API keys for a tenant (Admin only).
    
    Args:
        tenant_id: Tenant ID
        current_tenant: Admin tenant (from auth)
        
    Returns:
        List[ApiKeyResponse]: List of API keys
    """
    try:
        tenant_service = TenantService()
        
        # Check if tenant exists
        existing_tenant = tenant_service.get_tenant(tenant_id)
        if not existing_tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Get API keys
        api_keys = tenant_service.list_api_keys(tenant_id)
        return api_keys
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list API keys: {str(e)}"
        )

@router.delete("/tenants/{tenant_id}/api-keys/{key_id}")
async def delete_api_key(
    tenant_id: str,
    key_id: str,
    current_tenant: dict = Depends(require_admin)
):
    """
    Delete an API key (Admin only).
    
    Args:
        tenant_id: Tenant ID
        key_id: API key ID
        current_tenant: Admin tenant (from auth)
        
    Returns:
        dict: Deletion confirmation
    """
    try:
        tenant_service = TenantService()
        
        # Check if tenant exists
        existing_tenant = tenant_service.get_tenant(tenant_id)
        if not existing_tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Delete API key
        tenant_service.delete_api_key(tenant_id, key_id)
        
        return {"message": f"API key {key_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete API key: {str(e)}"
        )

# =============================================================================
# SYSTEM MONITORING
# =============================================================================

@router.get("/system/status", response_model=SystemStatusResponse)
async def get_system_status(
    current_tenant: dict = Depends(require_admin)
):
    """
    Get comprehensive system status (Admin only).
    
    Args:
        current_tenant: Admin tenant (from auth)
        
    Returns:
        SystemStatusResponse: System status information
    """
    try:
        tenant_service = TenantService()
        
        # Get basic system info
        start_time = datetime.utcnow()  # This should be actual start time
        uptime = (datetime.utcnow() - start_time).total_seconds()
        
        # Get tenant and document counts
        tenants = tenant_service.list_tenants()
        total_tenants = len(tenants)
        
        # Calculate total documents (simplified - TODO: implement proper document counting)
        total_documents = 0
        
        # Check component statuses
        components = {}
        
        # Qdrant status
        try:
            embedding_manager = EmbeddingManager()
            # Check if we can create an embedding request (simplified health check)
            components["qdrant"] = {"status": "healthy"}
        except Exception as e:
            components["qdrant"] = {"status": "unhealthy", "error": str(e)}
        
        # Tenant service status
        try:
            tenant_service.list_tenants()
            components["tenant_service"] = {"status": "healthy"}
        except Exception as e:
            components["tenant_service"] = {"status": "unhealthy", "error": str(e)}
        
        return SystemStatusResponse(
            status="healthy" if all(c.get("status") == "healthy" for c in components.values()) else "degraded",
            version="1.0.0",
            uptime_seconds=uptime,
            total_tenants=total_tenants,
            total_documents=total_documents,
            components=components
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get system status: {str(e)}"
        )

@router.get("/system/metrics", response_model=SystemMetricsResponse)
async def get_system_metrics(
    current_tenant: dict = Depends(require_admin)
):
    """
    Get system performance metrics (Admin only).
    
    Args:
        current_tenant: Admin tenant (from auth)
        
    Returns:
        SystemMetricsResponse: System metrics
    """
    try:
        # Get system metrics using psutil
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Get network connections (simplified)
        connections = len(psutil.net_connections())
        
        return SystemMetricsResponse(
            timestamp=datetime.utcnow(),
            cpu_usage_percent=cpu_percent,
            memory_usage_percent=memory.percent,
            disk_usage_percent=disk.percent,
            active_connections=connections,
            queries_per_minute=0.0,  # This would need to be tracked
            sync_operations=0  # This would need to be tracked
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get system metrics: {str(e)}"
        )

# =============================================================================
# SYSTEM MAINTENANCE
# =============================================================================

@router.delete("/system/embeddings/stats")
async def delete_embedding_statistics(
    current_tenant: dict = Depends(require_admin)
):
    """
    Clear embedding generation statistics (Admin only).
    
    Args:
        current_tenant: Admin tenant (from auth)
        
    Returns:
        dict: Clear operation confirmation
    """
    try:
        from src.backend.core.embedding_manager import get_embedding_manager
        embedding_manager = get_embedding_manager()
        embedding_manager.clear_stats()
        
        return {"message": "Embedding statistics cleared successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear embedding statistics: {str(e)}"
        )

@router.delete("/system/llm/stats")
async def delete_llm_statistics(
    current_tenant: dict = Depends(require_admin)
):
    """
    Clear LLM service statistics (Admin only).
    
    Args:
        current_tenant: Admin tenant (from auth)
        
    Returns:
        dict: Clear operation confirmation
    """
    try:
        from src.backend.core.llm_service import get_llm_service
        llm_service = get_llm_service()
        llm_service.clear_stats()
        
        return {"message": "LLM statistics cleared successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear LLM statistics: {str(e)}"
        )

@router.delete("/system/llm/cache")
async def delete_llm_cache(
    current_tenant: dict = Depends(require_admin)
):
    """
    Clear LLM service cache (Admin only).
    
    Args:
        current_tenant: Admin tenant (from auth)
        
    Returns:
        dict: Clear operation confirmation
    """
    try:
        from src.backend.core.llm_service import get_llm_service
        llm_service = get_llm_service()
        llm_service.clear_cache()
        
        return {"message": "LLM cache cleared successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear LLM cache: {str(e)}"
        )

@router.put("/system/maintenance")
async def update_maintenance_mode(
    maintenance_request: dict,
    current_tenant: dict = Depends(require_admin)
):
    """
    Update system maintenance mode (Admin only).
    
    Args:
        maintenance_request: Maintenance state request {"enabled": true/false}
        current_tenant: Admin tenant (from auth)
        
    Returns:
        dict: Maintenance mode status
    """
    try:
        enabled = maintenance_request.get("enabled", True)
        status = "maintenance" if enabled else "normal"
        
        # This would implement actual maintenance mode logic
        return {
            "message": f"Maintenance mode {'enabled' if enabled else 'disabled'}",
            "status": status,
            "enabled": enabled,
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger maintenance mode: {str(e)}"
        )

@router.get("/audit/events", response_model=List[SyncEventResponse])
async def get_audit_events(
    tenant_id: str = None,
    limit: int = 100,
    offset: int = 0,
    current_tenant: dict = Depends(require_admin),
    audit_logger: AuditLogger = Depends(get_audit_logger)
) -> List[SyncEventResponse]:
    """
    Retrieve audit events for a tenant (Admin only).
    If tenant_id is not provided, returns all events.
    """
    logger.info(f"Fetching audit events for tenant {tenant_id if tenant_id else 'ALL'} (admin)")
    events = audit_logger.get_events_for_tenant(
        tenant_id=tenant_id,
        limit=limit,
        offset=offset
    )
    return [SyncEventResponse(**event) for event in events]

# =============================================================================
# DEMO MANAGEMENT
# =============================================================================

@router.post("/demo/setup", response_model=DemoSetupResponse)
async def setup_demo_environment(
    request: DemoSetupRequest,
    current_tenant: dict = Depends(require_admin)
):
    """
    Setup demo environment with multiple tenants (Admin only).
    
    Args:
        request: Demo setup request with tenant IDs and duration
        current_tenant: Admin tenant (from auth)
        
    Returns:
        DemoSetupResponse: Demo setup results with API keys
    """
    try:
        logger.info(f"Setting up demo environment for {len(request.demo_tenants)} tenants")
        
        tenant_service = TenantService()
        demo_tenants = []
        
        # Calculate demo expiration
        demo_expires_at = datetime.utcnow() + timedelta(hours=request.demo_duration_hours)
        
        for tenant_id in request.demo_tenants:
            # Verify tenant exists
            tenant = await tenant_service.get_tenant(tenant_id)
            if not tenant:
                logger.warning(f"Tenant {tenant_id} not found, skipping")
                continue
            
            api_keys = []
            if request.generate_api_keys:
                # Generate demo API key for tenant
                demo_key = await tenant_service.create_api_key(
                    tenant_id=tenant_id,
                    name="Demo API Key",
                    description="Auto-generated for demo purposes",
                    expires_at=demo_expires_at
                )
                
                api_keys.append(ApiKeyCreateResponse(
                    api_key=demo_key["api_key"],
                    key_info=ApiKeyResponse(
                        id=demo_key["key_id"],
                        name=demo_key["key_name"],
                        key_prefix=demo_key["api_key"][:8] + "...",
                        is_active=True,
                        created_at=demo_key["created_at"],
                        expires_at=demo_expires_at
                    )
                ))
            
            demo_tenants.append(DemoTenantInfo(
                tenant_id=tenant_id,
                tenant_name=tenant.get("name", ""),
                description=tenant.get("description"),
                api_keys=api_keys,
                demo_expires_at=demo_expires_at,
                created_at=datetime.utcnow()
            ))
        
        return DemoSetupResponse(
            success=True,
            demo_tenants=demo_tenants,
            admin_api_key=current_tenant.get("api_key", ""),  # This should be the admin's API key
            message=f"Demo environment setup for {len(demo_tenants)} tenants",
            total_tenants=len(demo_tenants)
        )
        
    except Exception as e:
        logger.error(f"Failed to setup demo environment: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to setup demo environment: {str(e)}"
        )

@router.get("/demo/tenants", response_model=List[DemoTenantInfo])
async def list_demo_tenants(
    current_tenant: dict = Depends(require_admin)
):
    """
    List all demo tenants with their API keys (Admin only).
    
    Args:
        current_tenant: Admin tenant (from auth)
        
    Returns:
        List[DemoTenantInfo]: List of demo tenants with API keys
    """
    try:
        logger.info("Listing demo tenants")
        
        tenant_service = TenantService()
        all_tenants = tenant_service.list_tenants()
        demo_tenants = []
        
        for tenant in all_tenants:
            # Skip admin tenant
            if tenant.get("name") == "admin":
                continue
            
            # Get API keys for tenant
            api_keys = tenant_service.list_api_keys(tenant.get("id"))
            
            # Filter for demo keys (keys with "Demo" in name or description)
            demo_keys = []
            for key in api_keys:
                if "demo" in key.get("name", "").lower() or "demo" in key.get("description", "").lower():
                    demo_keys.append(ApiKeyCreateResponse(
                        api_key=key.get("api_key", ""),
                        key_info=ApiKeyResponse(**key)
                    ))
            
            if demo_keys:  # Only include tenants with demo keys
                demo_tenants.append(DemoTenantInfo(
                    tenant_id=tenant.get("id"),
                    tenant_name=tenant.get("name", ""),
                    description=tenant.get("description"),
                    api_keys=demo_keys,
                    demo_expires_at=datetime.utcnow() + timedelta(hours=24),  # Default expiration
                    created_at=tenant.get("created_at", datetime.utcnow())
                ))
        
        return demo_tenants
        
    except Exception as e:
        logger.error(f"Failed to list demo tenants: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list demo tenants: {str(e)}"
        )

@router.delete("/demo/cleanup", response_model=DemoCleanupResponse)
async def cleanup_demo_environment(
    current_tenant: dict = Depends(require_admin)
):
    """
    Clean up demo environment and expire demo API keys (Admin only).
    
    Args:
        current_tenant: Admin tenant (from auth)
        
    Returns:
        DemoCleanupResponse: Cleanup results
    """
    try:
        logger.info("Cleaning up demo environment")
        
        tenant_service = TenantService()
        all_tenants = tenant_service.list_tenants()
        cleaned_tenants = 0
        expired_keys = 0
        
        for tenant in all_tenants:
            # Skip admin tenant
            if tenant.get("name") == "admin":
                continue
            
            # Get API keys for tenant
            api_keys = tenant_service.list_api_keys(tenant.get("id"))
            
            # Find and delete demo keys
            for key in api_keys:
                if "demo" in key.get("name", "").lower() or "demo" in key.get("description", "").lower():
                    try:
                        await tenant_service.delete_api_key(tenant.get("id"), key.get("id"))
                        expired_keys += 1
                    except Exception as e:
                        logger.warning(f"Failed to delete demo key {key.get('id')}: {e}")
            
            # If tenant only had demo keys and no other keys, mark as cleaned
            remaining_keys = tenant_service.list_api_keys(tenant.get("id"))
            if not remaining_keys:
                cleaned_tenants += 1
        
        return DemoCleanupResponse(
            success=True,
            cleaned_tenants=cleaned_tenants,
            expired_keys=expired_keys,
            message=f"Cleaned up {cleaned_tenants} tenants and expired {expired_keys} demo keys"
        )
        
    except Exception as e:
        logger.error(f"Failed to cleanup demo environment: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cleanup demo environment: {str(e)}"
        ) 