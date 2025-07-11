"""
Tenant API routes for the Enterprise RAG Platform.

This module provides endpoints for tenant management and API key operations.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer
import logging
from datetime import datetime, timedelta

from src.backend.services.tenant_service import TenantService, get_tenant_service
from src.backend.models.api_models import (
    TenantResponse, 
    TenantListResponse, 
    ApiKeyResponse,
    ApiKeyCreateResponse,
    ApiKeyCreateRequest,
    TenantContextResponse,
    TenantSwitchRequest,
    TenantSwitchResponse,
    TenantDocumentListRequest,
    TenantSyncStatusRequest,
    TenantApiKeyManagementRequest,
    DocumentListResponse,
    SyncResponse,
    SyncHistoryResponse
)
from src.backend.middleware.auth import get_current_tenant, get_tenant_context, verify_tenant_access
from src.backend.api.v1.providers import get_document_service  # , get_delta_sync  # Disabled: needs migration from Qdrant to pgvector
from src.backend.core.document_processor import DocumentProcessor

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()

# =============================================================================
# TENANT CONTEXT MANAGEMENT
# =============================================================================

@router.get("/context", response_model=TenantContextResponse)
async def get_tenant_context_info(
    current_tenant: dict = Depends(get_tenant_context),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    Get current tenant context information.
    
    Args:
        current_tenant: Current tenant context (from auth)
        tenant_service: Tenant service
        
    Returns:
        TenantContextResponse: Current tenant context with permissions
    """
    try:
        logger.info(f"Getting tenant context for: {current_tenant.get('id')}")
        
        # Get tenant details
        tenant = tenant_service.get_tenant(current_tenant.get('id'))
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Get tenant's API keys
        api_keys = tenant_service.list_api_keys(current_tenant.get('id'))
        
        return TenantContextResponse(
            tenant_id=tenant.get('id'),
            tenant_name=tenant.get('name'),
            description=tenant.get('description'),
            status=tenant.get('status'),
            permissions=current_tenant.get('permissions', []),
            api_keys=api_keys,
            created_at=tenant.get('created_at'),
            auto_sync=tenant.get('auto_sync', True),
            sync_interval=tenant.get('sync_interval', 60)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tenant context: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get tenant context: {str(e)}"
        )

@router.post("/switch", response_model=TenantSwitchResponse)
async def switch_tenant_context(
    request: TenantSwitchRequest,
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    Switch to different tenant context.
    
    Args:
        request: Tenant switch request with target tenant and API key
        tenant_service: Tenant service
        
    Returns:
        TenantSwitchResponse: New tenant context after switch
    """
    try:
        logger.info(f"Switching tenant context to: {request.tenant_id}")
        
        # Validate the provided API key for the target tenant
        tenant_info = tenant_service.validate_api_key(request.api_key)
        if not tenant_info or tenant_info.get('id') != request.tenant_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key for target tenant"
            )
        
        # Get target tenant details
        tenant = tenant_service.get_tenant(request.tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Target tenant not found")
        
        # Get target tenant's API keys
        api_keys = tenant_service.list_api_keys(request.tenant_id)
        
        # Determine permissions for target tenant
        permissions = []
        if tenant.get('name') == 'admin':
            permissions = ["admin", "tenant_management", "system_management"]
        else:
            permissions = ["tenant_operations", "document_access", "query_access"]
        
        tenant_context = TenantContextResponse(
            tenant_id=tenant.get('id'),
            tenant_name=tenant.get('name'),
            description=tenant.get('description'),
            status=tenant.get('status'),
            permissions=permissions,
            api_keys=api_keys,
            created_at=tenant.get('created_at'),
            auto_sync=tenant.get('auto_sync', True),
            sync_interval=tenant.get('sync_interval', 60)
        )
        
        return TenantSwitchResponse(
            success=True,
            tenant_context=tenant_context,
            message=f"Successfully switched to tenant: {tenant.get('name')}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to switch tenant context: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to switch tenant context: {str(e)}"
        )

# =============================================================================
# ENHANCED TENANT OPERATIONS
# =============================================================================

@router.get("/{tenant_id}/documents", response_model=DocumentListResponse)
async def list_tenant_documents(
    tenant_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Page size"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    status: Optional[str] = Query(None, description="Filter by document status"),
    current_tenant: dict = Depends(get_current_tenant),
    document_service = Depends(get_document_service)
):
    """
    List documents for current tenant (scoped access).
    
    Args:
        tenant_id: Target tenant ID
        page: Page number for pagination
        page_size: Number of documents per page
        document_type: Filter by document type
        status: Filter by document status
        current_tenant: Current tenant (from auth)
        document_service: Document service
        
    Returns:
        DocumentListResponse: List of documents with pagination
    """
    try:
        # Verify tenant has access to target tenant
        verified_tenant_id = verify_tenant_access(tenant_id, current_tenant)
        
        logger.info(f"Listing documents for tenant: {verified_tenant_id}")
        
        # Get documents for the tenant - this would need to be implemented in DocumentService
        # For now, return empty list
        documents = {
            "documents": [],
            "total_count": 0
        }
        
        return DocumentListResponse(
            documents=documents.get('documents', []),
            total_count=documents.get('total_count', 0),
            page=page,
            page_size=page_size
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list tenant documents: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list tenant documents: {str(e)}"
        )

@router.get("/{tenant_id}/sync/status", response_model=SyncResponse)
async def get_tenant_sync_status(
    tenant_id: str,
    include_history: bool = Query(False, description="Include sync history"),
    limit: int = Query(10, ge=1, le=50, description="Number of history entries"),
    current_tenant: dict = Depends(get_current_tenant)
    # delta_sync = Depends(get_delta_sync)  # Disabled: needs migration from Qdrant to pgvector
):
    """
    Get sync status for current tenant.
    
    Args:
        tenant_id: Target tenant ID
        include_history: Include sync history
        limit: Number of history entries
        current_tenant: Current tenant (from auth)
        delta_sync: Delta sync service
        
    Returns:
        SyncResponse: Current sync status
    """
    try:
        # Verify tenant has access to target tenant
        verified_tenant_id = verify_tenant_access(tenant_id, current_tenant)
        
        logger.info(f"Getting sync status for tenant: {verified_tenant_id}")
        
        # Get current sync status - this would need to be implemented in DeltaSync
        # For now, return a basic status
        sync_status = {
            "sync_id": f"status_{verified_tenant_id}",
            "tenant_id": verified_tenant_id,
            "status": "completed",
            "started_at": datetime.utcnow(),
            "completed_at": datetime.utcnow(),
            "progress": {"message": "Sync status retrieved"},
            "error_message": None
        }
        
        if include_history:
            # Get sync history - this would need to be implemented in DeltaSync
            sync_status['history'] = []
        
        return SyncResponse(**sync_status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tenant sync status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get tenant sync status: {str(e)}"
        )

@router.post("/{tenant_id}/api-keys", response_model=ApiKeyCreateResponse)
async def create_tenant_api_key(
    tenant_id: str,
    request: TenantApiKeyManagementRequest,
    current_tenant: dict = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    Create a new API key for tenant (self-service).
    
    Args:
        tenant_id: Target tenant ID
        request: API key creation request
        current_tenant: Current tenant (from auth)
        tenant_service: Tenant service
        
    Returns:
        ApiKeyCreateResponse: Created API key details
    """
    try:
        # Verify tenant has access to target tenant
        verified_tenant_id = verify_tenant_access(tenant_id, current_tenant)
        
        logger.info(f"Creating API key for tenant: {verified_tenant_id}")
        
        # Verify tenant exists
        tenant = tenant_service.get_tenant(verified_tenant_id)
        if not tenant:
            raise HTTPException(
                status_code=404,
                detail=f"Tenant {verified_tenant_id} not found"
            )
        
        # Create API key
        api_key_string = tenant_service.create_api_key(
            tenant_id=verified_tenant_id,
            name=request.key_name,
            description=request.description or "",
            expires_at=request.expires_at
        )
        
        return ApiKeyCreateResponse(
            api_key=api_key_string,
            key_info=ApiKeyResponse(
                id=f"{api_key_string[:8]}_new",
                name=request.key_name,
                key_prefix=api_key_string[:8],
                is_active=True,
                created_at=datetime.utcnow(),
                expires_at=request.expires_at
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create tenant API key: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create API key: {str(e)}"
        )

# =============================================================================
# EXISTING TENANT OPERATIONS (Enhanced)
# =============================================================================

@router.get("/", response_model=TenantListResponse)
async def list_tenants(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Number of tenants per page"),
    _: str = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    List all tenants with pagination.
    
    Args:
        page: Page number for pagination
        page_size: Number of tenants per page
        _: API key verification (required)
        tenant_service: Tenant service
        
    Returns:
        TenantListResponse: List of tenants with pagination
        
    Raises:
        HTTPException: If there's an error listing tenants
    """
    try:
        logger.info(f"Listing tenants (page {page}, size {page_size})")
        tenants = tenant_service.list_tenants()
        
        # Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_tenants = tenants[start_idx:end_idx]
        
        return TenantListResponse(
            tenants=paginated_tenants,
            total_count=len(tenants)
        )
        
    except Exception as e:
        logger.error(f"Failed to list tenants: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list tenants: {str(e)}"
        )

@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    _: str = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    Get tenant details by ID.
    
    Args:
        tenant_id: The unique identifier of the tenant
        _: API key verification (required)
        tenant_service: Tenant service
        
    Returns:
        TenantResponse: Tenant details
        
    Raises:
        HTTPException: If tenant not found or error occurs
    """
    try:
        logger.info(f"Getting tenant details: {tenant_id}")
        tenant = tenant_service.get_tenant(tenant_id)
        
        if not tenant:
            raise HTTPException(
                status_code=404,
                detail=f"Tenant {tenant_id} not found"
            )
        
        return TenantResponse(**tenant)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tenant {tenant_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get tenant: {str(e)}"
        )

@router.get("/{tenant_id}/api-keys", response_model=List[ApiKeyResponse])
async def list_api_keys(
    tenant_id: str,
    _: str = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    List API keys for a tenant.
    
    Args:
        tenant_id: The unique identifier of the tenant
        _: API key verification (required)
        tenant_service: Tenant service
        
    Returns:
        List[ApiKeyResponse]: List of API keys
        
    Raises:
        HTTPException: If tenant not found or error occurs
    """
    try:
        logger.info(f"Listing API keys for tenant: {tenant_id}")
        
        # Verify tenant exists
        tenant = tenant_service.get_tenant(tenant_id)
        if not tenant:
            raise HTTPException(
                status_code=404,
                detail=f"Tenant {tenant_id} not found"
            )
        
        api_keys = tenant_service.list_api_keys(tenant_id)
        return [ApiKeyResponse(**key) for key in api_keys]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list API keys for tenant {tenant_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list API keys: {str(e)}"
        )

@router.post("/{tenant_id}/api-keys", response_model=ApiKeyCreateResponse)
async def create_api_key(
    tenant_id: str,
    request: ApiKeyCreateRequest,
    _: str = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    Create a new API key for a tenant.
    
    Args:
        tenant_id: The unique identifier of the tenant
        request: API key creation request
        _: API key verification (required)
        tenant_service: Tenant service
        
    Returns:
        ApiKeyCreateResponse: Created API key details
        
    Raises:
        HTTPException: If tenant not found or error occurs
    """
    try:
        logger.info(f"Creating API key for tenant: {tenant_id}")
        
        # Verify tenant exists
        tenant = tenant_service.get_tenant(tenant_id)
        if not tenant:
            raise HTTPException(
                status_code=404,
                detail=f"Tenant {tenant_id} not found"
            )
        
        api_key_string = tenant_service.create_api_key(
            tenant_id=tenant_id,
            name=request.name,
            description="",
            expires_at=request.expires_at
        )
        
        return ApiKeyCreateResponse(
            api_key=api_key_string,
            key_info=ApiKeyResponse(
                id=f"{api_key_string[:8]}_new",
                name=request.name,
                key_prefix=api_key_string[:8],
                is_active=True,
                created_at=datetime.utcnow(),
                expires_at=request.expires_at
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create API key for tenant {tenant_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create API key: {str(e)}"
        )

@router.delete("/{tenant_id}/api-keys/{key_id}")
async def delete_api_key(
    tenant_id: str,
    key_id: str,
    _: str = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    Delete an API key for a tenant.
    
    Args:
        tenant_id: The unique identifier of the tenant
        key_id: The unique identifier of the API key
        _: API key verification (required)
        tenant_service: Tenant service
        
    Returns:
        dict: Success message
        
    Raises:
        HTTPException: If tenant or key not found or error occurs
    """
    try:
        logger.info(f"Deleting API key {key_id} for tenant: {tenant_id}")
        
        # Verify tenant exists
        tenant = tenant_service.get_tenant(tenant_id)
        if not tenant:
            raise HTTPException(
                status_code=404,
                detail=f"Tenant {tenant_id} not found"
            )
        
        success = tenant_service.delete_api_key(tenant_id, key_id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"API key {key_id} not found for tenant {tenant_id}"
            )
        
        return {"message": f"API key {key_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete API key {key_id} for tenant {tenant_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete API key: {str(e)}"
        ) 