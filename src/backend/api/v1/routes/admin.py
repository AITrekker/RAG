"""
Admin API endpoints for system administration.

This module provides admin-only endpoints for:
- Tenant management (CRUD operations)
- API key management
- System monitoring and metrics
- System-wide operations

All endpoints require admin authentication.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from uuid import UUID
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
    SuccessResponse,
    DemoSetupRequest,
    DemoSetupResponse,
    DemoTenantInfo,
    DemoCleanupResponse,
    SyncEventResponse
)
from src.backend.services.tenant_service import TenantService, get_tenant_service
from src.backend.core.embedding_manager import EmbeddingManager
from src.backend.core.llm_service import get_llm_service
from src.backend.middleware.api_key_auth import get_current_tenant
from src.backend.config.settings import get_settings
from src.backend.core.auditing import AuditLogger, get_audit_logger
from src.backend.utils.error_handling import (
    handle_exception,
    not_found_error,
    validation_error,
    internal_error,
    ResourceNotFoundError,
    ValidationError as RAGValidationError
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Admin Operations"])

# =============================================================================
# TENANT MANAGEMENT
# =============================================================================

@router.post("/tenants", response_model=TenantResponse)
async def create_tenant(
    request: TenantCreateRequest,
    current_tenant: dict = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    Create a new tenant (Admin only).
    
    Args:
        request: Tenant creation details
        current_tenant: Admin tenant (from auth)
        tenant_service: Tenant service
        
    Returns:
        TenantResponse: Created tenant information
    """
    try:
        # Verify admin access
        if current_tenant.name != "admin" and current_tenant.slug != "system_admin":
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )
        
        # Create tenant
        result = await tenant_service.create_tenant(
            name=request.name,
            description=request.description,
            auto_sync=request.auto_sync,
            sync_interval=request.sync_interval
        )
        
        # Get created tenant details
        tenant = await tenant_service.get_tenant_by_id(UUID(result["id"]))
        if not tenant:
            raise HTTPException(status_code=500, detail="Failed to retrieve created tenant")
            
        # Include the API key from the creation result
        api_keys = []
        if result.get("api_key"):
            api_keys = [ApiKeyResponse(
                id=f"key_{tenant.id}",
                name="Default Key",
                key_prefix=result["api_key"][:8] + "..." + result["api_key"][-8:] if len(result["api_key"]) > 16 else result["api_key"],
                is_active=True,
                created_at=tenant.created_at,
                expires_at=None
            )]
            
        return TenantResponse(
            id=str(tenant.id),
            name=tenant.name,
            description=tenant.description,
            status=tenant.status or "active",
            created_at=tenant.created_at,
            auto_sync=tenant.auto_sync,
            sync_interval=tenant.sync_interval,
            api_keys=api_keys,
            document_count=0,
            storage_used_mb=0.0,
            api_key=result.get("api_key")  # Add the full API key for demo setup
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, endpoint="create_tenant")

@router.get("/tenants", response_model=TenantListResponse)
async def list_tenants(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    include_api_keys: bool = Query(False, description="Include API keys in response"),
    demo_only: bool = Query(False, description="Show only demo tenants"),
    current_tenant: dict = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    List all tenants (Admin only).
    
    Args:
        page: Page number for pagination
        page_size: Number of tenants per page
        include_api_keys: Include API keys in response
        demo_only: Show only demo tenants
        current_tenant: Admin tenant (from auth)
        tenant_service: Tenant service
        
    Returns:
        TenantListResponse: List of tenants with pagination
    """
    try:
        # Verify admin access
        if current_tenant.name != "admin" and current_tenant.slug != "system_admin":
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )
        
        tenants = await tenant_service.list_tenants()
        
        # Convert to response format
        tenant_responses = []
        for tenant in tenants:
            tenant_response = TenantResponse(
                id=str(tenant.id),
                name=tenant.name,
                description=tenant.description,
                status=tenant.status or "active",
                created_at=tenant.created_at,
                auto_sync=tenant.auto_sync,
                sync_interval=tenant.sync_interval,
                api_keys=[],
                document_count=0,
                storage_used_mb=0.0
            )
            
            # Add API keys if requested
            if include_api_keys:
                api_keys = await tenant_service.list_api_keys(tenant.id)
                tenant_response.api_keys = [
                    ApiKeyResponse(
                        id=key.get("id", ""),
                        name=key.get("name", ""),
                        key_prefix=key.get("key_prefix", ""),
                        is_active=key.get("is_active", True),
                        created_at=key.get("created_at"),
                        expires_at=key.get("expires_at")
                    ) for key in api_keys
                ]
            
            tenant_responses.append(tenant_response)
        
        # Filter for demo tenants if requested
        if demo_only:
            tenant_responses = [
                t for t in tenant_responses 
                if "demo" in t.name.lower() or "test" in t.name.lower()
            ]
        
        # Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_tenants = tenant_responses[start_idx:end_idx]
        
        return TenantListResponse(
            tenants=paginated_tenants,
            total_count=len(tenant_responses)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, endpoint="list_tenants")

@router.get("/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    current_tenant: dict = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    Get tenant details (Admin only).
    
    Args:
        tenant_id: Tenant ID
        current_tenant: Admin tenant (from auth)
        tenant_service: Tenant service
        
    Returns:
        TenantResponse: Tenant information
    """
    try:
        # Verify admin access
        if current_tenant.name != "admin" and current_tenant.slug != "system_admin":
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )
        
        tenant = await tenant_service.get_tenant_by_id(UUID(tenant_id))
        
        if not tenant:
            raise not_found_error("Tenant", tenant_id)
            
        return TenantResponse(
            id=str(tenant.id),
            name=tenant.name,
            description=tenant.description,
            status=tenant.status or "active",
            created_at=tenant.created_at,
            auto_sync=tenant.auto_sync,
            sync_interval=tenant.sync_interval,
            api_keys=[],
            document_count=0,
            storage_used_mb=0.0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, endpoint="get_tenant")

@router.put("/tenants/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: str,
    request: TenantUpdateRequest,
    current_tenant: dict = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    Update tenant details (Admin only).
    
    Args:
        tenant_id: Tenant ID
        request: Update details
        current_tenant: Admin tenant (from auth)
        tenant_service: Tenant service
        
    Returns:
        TenantResponse: Updated tenant information
    """
    try:
        # Verify admin access
        if current_tenant.name != "admin" and current_tenant.slug != "system_admin":
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )
        
        tenant = await tenant_service.get_tenant_by_id(UUID(tenant_id))
        
        if not tenant:
            raise not_found_error("Tenant", tenant_id)
        
        updated_tenant = await tenant_service.update_tenant(
            tenant_id=UUID(tenant_id),
            name=request.name,
            description=request.description,
            status=request.status,
            auto_sync=request.auto_sync,
            sync_interval=request.sync_interval
        )
        
        return TenantResponse(
            id=str(updated_tenant.id),
            name=updated_tenant.name,
            description=updated_tenant.description,
            status=updated_tenant.status or "active",
            created_at=updated_tenant.created_at,
            auto_sync=updated_tenant.auto_sync,
            sync_interval=updated_tenant.sync_interval,
            api_keys=[],
            document_count=0,
            storage_used_mb=0.0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, endpoint="update_tenant")

@router.delete("/tenants/{tenant_id}", response_model=SuccessResponse)
async def delete_tenant(
    tenant_id: str,
    current_tenant: dict = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    Delete a tenant (Admin only).
    
    Args:
        tenant_id: Tenant ID
        current_tenant: Admin tenant (from auth)
        tenant_service: Tenant service
        
    Returns:
        dict: Deletion confirmation
    """
    try:
        # Verify admin access
        if current_tenant.name != "admin" and current_tenant.slug != "system_admin":
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )
        
        tenant = await tenant_service.get_tenant_by_id(UUID(tenant_id))
        
        if not tenant:
            raise not_found_error("Tenant", tenant_id)
        
        # Prevent admin tenant deletion
        if tenant.name == "admin":
            raise validation_error(
                "Cannot delete admin tenant",
                {"tenant_id": tenant_id, "tenant_name": "admin"}
            )
        
        await tenant_service.delete_tenant(UUID(tenant_id))
        
        return SuccessResponse(message=f"Tenant {tenant_id} deleted successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, endpoint="delete_tenant")

# =============================================================================
# API KEY MANAGEMENT
# =============================================================================

@router.post("/tenants/{tenant_id}/api-keys", response_model=ApiKeyCreateResponse)
async def create_api_key(
    tenant_id: str,
    request: ApiKeyCreateRequest,
    current_tenant: dict = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    Create API key for a tenant (Admin only).
    
    Args:
        tenant_id: Tenant ID
        request: API key details
        current_tenant: Admin tenant (from auth)
        tenant_service: Tenant service
        
    Returns:
        ApiKeyCreateResponse: Created API key
    """
    try:
        # Verify admin access
        if current_tenant.name != "admin" and current_tenant.slug != "system_admin":
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )
        
        tenant = await tenant_service.get_tenant_by_id(UUID(tenant_id))
        
        if not tenant:
            raise not_found_error("Tenant", tenant_id)
        
        api_key = await tenant_service.create_api_key(UUID(tenant_id), request.name)
        
        return ApiKeyCreateResponse(
            tenant_id=tenant_id,
            api_key=api_key,
            key_name=request.name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, endpoint="create_api_key")

@router.get("/tenants/{tenant_id}/api-keys", response_model=List[ApiKeyResponse])
async def list_api_keys(
    tenant_id: str,
    current_tenant: dict = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    List API keys for a tenant (Admin only).
    
    Args:
        tenant_id: Tenant ID
        current_tenant: Admin tenant (from auth)
        tenant_service: Tenant service
        
    Returns:
        List[ApiKeyResponse]: List of API keys
    """
    try:
        # Verify admin access
        if current_tenant.name != "admin" and current_tenant.slug != "system_admin":
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )
        
        tenant = await tenant_service.get_tenant_by_id(UUID(tenant_id))
        
        if not tenant:
            raise not_found_error("Tenant", tenant_id)
        
        api_keys = await tenant_service.list_api_keys(UUID(tenant_id))
        return api_keys
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, endpoint="list_api_keys")

@router.delete("/tenants/{tenant_id}/api-keys/{key_id}", response_model=SuccessResponse)
async def delete_api_key(
    tenant_id: str,
    key_id: str,
    current_tenant: dict = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    Delete an API key (Admin only).
    
    Args:
        tenant_id: Tenant ID
        key_id: API key ID
        current_tenant: Admin tenant (from auth)
        tenant_service: Tenant service
        
    Returns:
        dict: Deletion confirmation
    """
    try:
        # Verify admin access
        if current_tenant.name != "admin" and current_tenant.slug != "system_admin":
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )
        
        tenant = await tenant_service.get_tenant_by_id(UUID(tenant_id))
        
        if not tenant:
            raise not_found_error("Tenant", tenant_id)
        
        await tenant_service.delete_api_key(UUID(tenant_id), key_id)
        
        return SuccessResponse(message=f"API key {key_id} deleted successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, endpoint="delete_api_key")

# =============================================================================
# SYSTEM MONITORING
# =============================================================================

@router.get("/system/status", response_model=SystemStatusResponse)
async def get_system_status(
    current_tenant: dict = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    Get comprehensive system status (Admin only).
    
    Args:
        current_tenant: Admin tenant (from auth)
        tenant_service: Tenant service
        
    Returns:
        SystemStatusResponse: System status information
    """
    try:
        # Verify admin access
        if current_tenant.name != "admin" and current_tenant.slug != "system_admin":
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )
        
        # Get basic system info
        start_time = datetime.utcnow()  # This should be actual start time
        uptime = (datetime.utcnow() - start_time).total_seconds()
        
        # Get tenant and document counts
        tenants = await tenant_service.list_tenants()
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
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, endpoint="get_system_status")

@router.get("/system/metrics", response_model=SystemMetricsResponse)
async def get_system_metrics(
    current_tenant: dict = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    Get system performance metrics (Admin only).
    
    Args:
        current_tenant: Admin tenant (from auth)
        tenant_service: Tenant service
        
    Returns:
        SystemMetricsResponse: System metrics
    """
    try:
        # Verify admin access
        if current_tenant.name != "admin" and current_tenant.slug != "system_admin":
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )
        
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
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_exception(e, endpoint="get_system_metrics")

# =============================================================================
# SYSTEM MAINTENANCE
# =============================================================================

@router.delete("/system/embeddings/stats", response_model=SuccessResponse)
async def delete_embedding_statistics(
    current_tenant: dict = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    Clear embedding generation statistics (Admin only).
    
    Args:
        current_tenant: Admin tenant (from auth)
        tenant_service: Tenant service
        
    Returns:
        dict: Clear operation confirmation
    """
    try:
        # Verify admin access
        if current_tenant.name != "admin" and current_tenant.slug != "system_admin":
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )
        
        embedding_manager = EmbeddingManager()
        embedding_manager.clear_stats()
        
        return SuccessResponse(message="Embedding statistics cleared successfully")
    except Exception as e:
        raise handle_exception(e, endpoint="delete_embedding_statistics")

@router.delete("/system/llm/stats", response_model=SuccessResponse)
async def delete_llm_statistics(
    current_tenant: dict = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    Clear LLM service statistics (Admin only).
    
    Args:
        current_tenant: Admin tenant (from auth)
        tenant_service: Tenant service
        
    Returns:
        dict: Clear operation confirmation
    """
    try:
        # Verify admin access
        if current_tenant.name != "admin" and current_tenant.slug != "system_admin":
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )
        
        llm_service = get_llm_service()
        llm_service.clear_stats()
        
        return SuccessResponse(message="LLM statistics cleared successfully")
    except Exception as e:
        raise handle_exception(e, endpoint="delete_llm_statistics")

@router.delete("/system/llm/cache", response_model=SuccessResponse)
async def delete_llm_cache(
    current_tenant: dict = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    Clear LLM service cache (Admin only).
    
    Args:
        current_tenant: Admin tenant (from auth)
        tenant_service: Tenant service
        
    Returns:
        dict: Clear operation confirmation
    """
    try:
        # Verify admin access
        if current_tenant.name != "admin" and current_tenant.slug != "system_admin":
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )
        
        llm_service = get_llm_service()
        llm_service.clear_cache()
        
        return SuccessResponse(message="LLM cache cleared successfully")
    except Exception as e:
        raise handle_exception(e, endpoint="delete_llm_cache")

@router.put("/system/maintenance", response_model=Dict[str, Any])
async def update_maintenance_mode(
    maintenance_request: dict,
    current_tenant: dict = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    Update system maintenance mode (Admin only).
    
    Args:
        maintenance_request: Maintenance state request {"enabled": true/false}
        current_tenant: Admin tenant (from auth)
        tenant_service: Tenant service
        
    Returns:
        dict: Maintenance mode status
    """
    try:
        # Verify admin access
        if current_tenant.name != "admin" and current_tenant.slug != "system_admin":
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )
        
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
        raise handle_exception(e, endpoint="update_maintenance_mode")

@router.get("/audit/events", response_model=List[SyncEventResponse])
async def get_audit_events(
    tenant_id: str = None,
    limit: int = 100,
    offset: int = 0,
    current_tenant: dict = Depends(get_current_tenant),
    audit_logger: AuditLogger = Depends(get_audit_logger),
    tenant_service: TenantService = Depends(get_tenant_service)
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
# SYNC MANAGEMENT (ADMIN)
# =============================================================================


# =============================================================================
# DEMO MANAGEMENT
# =============================================================================

@router.post("/demo/setup", response_model=DemoSetupResponse)
async def setup_demo_environment(
    request: DemoSetupRequest,
    current_tenant: dict = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    Setup demo environment with multiple tenants (Admin only).
    
    Args:
        request: Demo setup request with tenant IDs and duration
        current_tenant: Admin tenant (from auth)
        tenant_service: Tenant service
        
    Returns:
        DemoSetupResponse: Demo setup results with API keys
    """
    try:
        logger.info(f"Setting up demo environment for {len(request.demo_tenants)} tenants")
        
        # Verify admin access
        if current_tenant.name != "admin" and current_tenant.slug != "system_admin":
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )
        
        demo_tenants = []
        
        # Calculate demo expiration
        demo_expires_at = datetime.now(timezone.utc) + timedelta(hours=request.demo_duration_hours)
        
        for tenant_id in request.demo_tenants:
            # Verify tenant exists
            tenant = await tenant_service.get_tenant_by_id(UUID(tenant_id))
            if not tenant:
                logger.warning(f"Tenant {tenant_id} not found, skipping")
                continue
            
            api_keys = []
            if request.generate_api_keys:
                # Generate demo API key for tenant
                demo_api_key = await tenant_service.create_api_key(
                    tenant_id=UUID(tenant_id),
                    name="Demo API Key",
                    description="Auto-generated for demo purposes",
                    expires_at=demo_expires_at
                )
                
                api_keys.append(ApiKeyCreateResponse(
                    api_key=demo_api_key,
                    key_info=ApiKeyResponse(
                        id=f"demo_{tenant_id}",
                        name="Demo API Key",
                        key_prefix=demo_api_key[:8],
                        is_active=True,
                        created_at=datetime.utcnow(),
                        expires_at=demo_expires_at
                    )
                ))
            
            demo_tenants.append(DemoTenantInfo(
                tenant_id=tenant_id,
                tenant_name=tenant.name,
                description=tenant.description,
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
        raise handle_exception(e, endpoint="setup_demo_environment")

@router.get("/demo/tenants", response_model=List[DemoTenantInfo])
async def list_demo_tenants(
    current_tenant: dict = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    List all demo tenants with their API keys (Admin only).
    
    Args:
        current_tenant: Admin tenant (from auth)
        tenant_service: Tenant service
        
    Returns:
        List[DemoTenantInfo]: List of demo tenants with API keys
    """
    try:
        logger.info("Listing demo tenants")
        
        # Verify admin access
        if current_tenant.name != "admin" and current_tenant.slug != "system_admin":
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )
        
        all_tenants = await tenant_service.list_tenants()
        demo_tenants = []
        
        for tenant in all_tenants:
            # Skip admin tenant
            if tenant.name == "admin":
                continue
            
            # Get API keys for tenant
            api_keys = await tenant_service.list_api_keys(tenant.id)
            
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
                    tenant_id=tenant.id,
                    tenant_name=tenant.name,
                    description=tenant.description,
                    api_keys=demo_keys,
                    demo_expires_at=datetime.utcnow() + timedelta(hours=24),  # Default expiration
                    created_at=tenant.created_at
                ))
        
        return demo_tenants
        
    except Exception as e:
        logger.error(f"Failed to list demo tenants: {e}", exc_info=True)
        raise handle_exception(e, endpoint="list_demo_tenants")

@router.delete("/demo/cleanup", response_model=DemoCleanupResponse)
async def cleanup_demo_environment(
    current_tenant: dict = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    Clean up demo environment and expire demo API keys (Admin only).
    
    Args:
        current_tenant: Admin tenant (from auth)
        tenant_service: Tenant service
        
    Returns:
        DemoCleanupResponse: Cleanup results
    """
    try:
        logger.info("Cleaning up demo environment")
        
        # Verify admin access
        if current_tenant.name != "admin" and current_tenant.slug != "system_admin":
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )
        
        all_tenants = await tenant_service.list_tenants()
        cleaned_tenants = 0
        expired_keys = 0
        
        for tenant in all_tenants:
            # Skip admin tenant
            if tenant.name == "admin":
                continue
            
            # Get API keys for tenant
            api_keys = await tenant_service.list_api_keys(tenant.id)
            
            # Find and delete demo keys
            for key in api_keys:
                if "demo" in key.get("name", "").lower() or "demo" in key.get("description", "").lower():
                    try:
                        await tenant_service.delete_api_key(tenant.id, key.get("id"))
                        expired_keys += 1
                    except Exception as e:
                        logger.warning(f"Failed to delete demo key {key.get('id')}: {e}")
            
            # If tenant only had demo keys and no other keys, mark as cleaned
            remaining_keys = await tenant_service.list_api_keys(tenant.id)
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
        raise handle_exception(e, endpoint="cleanup_demo_environment")


@router.post("/system/init-database", response_model=SuccessResponse)
async def initialize_database_schema(
    request: Request,
    environment: Optional[str] = Query(None, description="Target environment for initialization"),
    current_tenant: dict = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service),
    audit_logger: AuditLogger = Depends(get_audit_logger)
):
    """
    Initialize database schema for a specific environment (Admin only).
    
    Creates database tables if they don't exist in the target environment.
    This is useful for setting up new environments or ensuring schema consistency.
    
    Args:
        environment: Target environment (development, test, staging, production)
        
    Returns:
        SuccessResponse: Confirmation of database initialization
        
    Raises:
        HTTPException: If initialization fails
    """
    try:
        logger.info(f"Initializing database schema for environment: {environment}")
        
        # Import database functions
        from src.backend.database import create_tables
        
        # Set up environment-specific database connection if specified
        if environment:
            import os
            current_env = os.getenv("RAG_ENVIRONMENT", "development")
            postgres_user = os.getenv("POSTGRES_USER")
            postgres_password = os.getenv("POSTGRES_PASSWORD")
            
            # Temporarily set DATABASE_URL for the target environment
            original_db_url = os.getenv("DATABASE_URL")
            env_db_url = f"postgresql://{postgres_user}:{postgres_password}@postgres:5432/rag_db_{environment}"
            os.environ["DATABASE_URL"] = env_db_url
            
            try:
                # Create tables in target environment
                create_tables()
                logger.info(f"Database tables created/verified for {environment} environment")
            finally:
                # Restore original DATABASE_URL
                if original_db_url:
                    os.environ["DATABASE_URL"] = original_db_url
        else:
            # Use current environment
            create_tables()
            logger.info("Database tables created/verified for current environment")
        
        # Log the action (skip for now to avoid UUID serialization issues)
        # await audit_logger.log_action(
        #     tenant_id=None,
        #     user_id=None,
        #     action="database_init",
        #     resource_type="system",
        #     resource_id=f"env_{environment or 'current'}",
        #     details={"environment": environment or "current"}
        # )
        
        return SuccessResponse(
            success=True,
            message=f"Database schema initialized successfully for {environment or 'current'} environment"
        )
        
    except Exception as e:
        logger.error(f"Failed to initialize database schema: {e}", exc_info=True)
        raise handle_exception(e, endpoint="initialize_database_schema") 