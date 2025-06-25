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

from ...models.api_models import (
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
    SyncEventResponse
)
from ...core.tenant_service import TenantService
from ...core.embedding_manager import EmbeddingManager
from ...middleware.auth import get_current_tenant, require_admin
from ...config.settings import get_settings
from src.backend.core.auditing import AuditLogger, get_audit_logger

router = APIRouter(prefix="/admin", tags=["Admin Operations"])

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
    current_tenant: dict = Depends(require_admin)
):
    """
    List all tenants (Admin only).
    
    Args:
        page: Page number for pagination
        page_size: Number of tenants per page
        current_tenant: Admin tenant (from auth)
        
    Returns:
        TenantListResponse: List of tenants with pagination
    """
    try:
        tenant_service = TenantService()
        tenants = await tenant_service.list_tenants()
        
        # Simple pagination
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
        tenant = await tenant_service.get_tenant(tenant_id)
        
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
        existing_tenant = await tenant_service.get_tenant(tenant_id)
        if not existing_tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Update tenant
        updated_tenant = await tenant_service.update_tenant(
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
        existing_tenant = await tenant_service.get_tenant(tenant_id)
        if not existing_tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Prevent admin tenant deletion
        if existing_tenant.name == "admin":
            raise HTTPException(
                status_code=400,
                detail="Cannot delete admin tenant"
            )
        
        # Delete tenant
        await tenant_service.delete_tenant(tenant_id)
        
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
        existing_tenant = await tenant_service.get_tenant(tenant_id)
        if not existing_tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Create API key
        api_key = await tenant_service.create_api_key(
            tenant_id=tenant_id,
            name=request.name,
            expires_at=request.expires_at
        )
        
        # Get key info
        key_info = await tenant_service.get_api_key_info(tenant_id, api_key)
        
        return ApiKeyCreateResponse(
            api_key=api_key,
            key_info=key_info
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
        existing_tenant = await tenant_service.get_tenant(tenant_id)
        if not existing_tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Get API keys
        api_keys = await tenant_service.list_api_keys(tenant_id)
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
        existing_tenant = await tenant_service.get_tenant(tenant_id)
        if not existing_tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Delete API key
        await tenant_service.delete_api_key(tenant_id, key_id)
        
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
        tenants = await tenant_service.list_tenants()
        total_tenants = len(tenants)
        
        # Calculate total documents (simplified)
        total_documents = 0
        for tenant in tenants:
            embedding_manager = EmbeddingManager(tenant_id=tenant.id)
            try:
                collection_info = await embedding_manager.get_collection_info()
                total_documents += collection_info.get("points_count", 0)
            except:
                pass
        
        # Check component statuses
        components = {}
        
        # Qdrant status
        try:
            embedding_manager = EmbeddingManager(tenant_id="status_check")
            await embedding_manager.check_connection()
            components["qdrant"] = {"status": "healthy"}
        except Exception as e:
            components["qdrant"] = {"status": "unhealthy", "error": str(e)}
        
        # Tenant service status
        try:
            await tenant_service.list_tenants()
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

@router.post("/system/clear-embeddings-stats")
async def clear_embedding_statistics(
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

@router.post("/system/clear-llm-stats")
async def clear_llm_statistics(
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

@router.post("/system/clear-llm-cache")
async def clear_llm_cache(
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

@router.post("/system/maintenance")
async def trigger_maintenance_mode(
    current_tenant: dict = Depends(require_admin)
):
    """
    Trigger system maintenance mode (Admin only).
    
    Args:
        current_tenant: Admin tenant (from auth)
        
    Returns:
        dict: Maintenance mode status
    """
    try:
        # This would implement actual maintenance mode logic
        return {
            "message": "Maintenance mode triggered",
            "status": "maintenance",
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