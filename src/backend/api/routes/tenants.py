"""
Tenant management API endpoints for the Enterprise RAG Platform.

Handles tenant creation, configuration, and management operations.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime
import uuid

from ...core.tenant_manager import TenantManager
from ...models.tenant import Tenant, TenantStatus
from ...middleware.mock_tenant import get_current_tenant_id

logger = logging.getLogger(__name__)

router = APIRouter()

# Request/Response Models
class TenantCreateRequest(BaseModel):
    """Request model for tenant creation."""
    name: str = Field(..., min_length=1, max_length=255, description="Tenant name")
    description: Optional[str] = Field(None, max_length=1000, description="Tenant description")
    contact_email: str = Field(..., description="Primary contact email")
    settings: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Tenant-specific settings")
    
    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('Tenant name cannot be empty')
        return v.strip()
    
    @validator('contact_email')
    def validate_email(cls, v):
        # Basic email validation
        if '@' not in v or '.' not in v.split('@')[-1]:
            raise ValueError('Invalid email format')
        return v.lower().strip()


class TenantUpdateRequest(BaseModel):
    """Request model for tenant updates."""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Tenant name")
    description: Optional[str] = Field(None, max_length=1000, description="Tenant description")
    contact_email: Optional[str] = Field(None, description="Primary contact email")
    settings: Optional[Dict[str, Any]] = Field(None, description="Tenant-specific settings")
    status: Optional[TenantStatus] = Field(None, description="Tenant status")
    
    @validator('name')
    def validate_name(cls, v):
        if v is not None and not v.strip():
            raise ValueError('Tenant name cannot be empty')
        return v.strip() if v else v
    
    @validator('contact_email')
    def validate_email(cls, v):
        if v is not None:
            if '@' not in v or '.' not in v.split('@')[-1]:
                raise ValueError('Invalid email format')
            return v.lower().strip()
        return v


class TenantResponse(BaseModel):
    """Response model for tenant information."""
    id: str = Field(..., description="Unique tenant identifier")
    name: str = Field(..., description="Tenant name")
    description: Optional[str] = Field(None, description="Tenant description")
    contact_email: str = Field(..., description="Primary contact email")
    status: TenantStatus = Field(..., description="Tenant status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Tenant-specific settings")
    document_count: Optional[int] = Field(None, description="Number of documents")
    storage_used: Optional[int] = Field(None, description="Storage used in bytes")


class TenantListResponse(BaseModel):
    """Response model for tenant listing."""
    tenants: List[TenantResponse] = Field(default_factory=list, description="List of tenants")
    total_count: int = Field(..., description="Total number of tenants")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of tenants per page")


class TenantStatsResponse(BaseModel):
    """Response model for tenant statistics."""
    tenant_id: str = Field(..., description="Tenant identifier")
    document_count: int = Field(..., description="Total number of documents")
    chunk_count: int = Field(..., description="Total number of chunks")
    storage_used: int = Field(..., description="Storage used in bytes")
    query_count_today: int = Field(..., description="Queries processed today")
    query_count_total: int = Field(..., description="Total queries processed")
    last_sync: Optional[datetime] = Field(None, description="Last synchronization timestamp")
    avg_query_time: Optional[float] = Field(None, description="Average query processing time")


# Dependency to get tenant manager
async def get_tenant_manager() -> TenantManager:
    """Get tenant manager instance."""
    try:
        return TenantManager()
    except Exception as e:
        logger.error(f"Failed to initialize tenant manager: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to initialize tenant management service"
        )


@router.post("/tenants", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    request: TenantCreateRequest,
    tenant_manager: TenantManager = Depends(get_tenant_manager)
):
    """
    Create a new tenant.
    
    Creates a new tenant with the specified configuration and initializes
    the necessary resources (database, vector store, file system).
    """
    try:
        logger.info(f"Creating new tenant: {request.name}")
        
        # Create tenant
        tenant = await tenant_manager.create_tenant(
            name=request.name,
            description=request.description,
            contact_email=request.contact_email,
            settings=request.settings
        )
        
        # Convert to response format
        response = TenantResponse(
            id=str(tenant.id),
            name=tenant.name,
            description=tenant.description,
            contact_email=tenant.contact_email,
            status=tenant.status,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
            settings=tenant.settings or {},
            document_count=0,
            storage_used=0
        )
        
        logger.info(f"Tenant created successfully: {tenant.id}")
        return response
        
    except ValueError as e:
        logger.warning(f"Invalid tenant creation request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create tenant: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create tenant"
        )


@router.get("/tenants", response_model=TenantListResponse)
async def list_tenants(
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[TenantStatus] = None,
    tenant_manager: TenantManager = Depends(get_tenant_manager)
):
    """
    List all tenants with pagination and filtering.
    
    Returns a paginated list of tenants with optional status filtering.
    """
    try:
        logger.info(f"Listing tenants: page={page}, page_size={page_size}, status={status_filter}")
        
        # Get tenants from manager
        tenants, total_count = await tenant_manager.list_tenants(
            page=page,
            page_size=page_size,
            status_filter=status_filter
        )
        
        # Convert to response format
        tenant_responses = []
        for tenant in tenants:
            # Get additional stats for each tenant
            stats = await tenant_manager.get_tenant_stats(str(tenant.id))
            
            tenant_responses.append(TenantResponse(
                id=str(tenant.id),
                name=tenant.name,
                description=tenant.description,
                contact_email=tenant.contact_email,
                status=tenant.status,
                created_at=tenant.created_at,
                updated_at=tenant.updated_at,
                settings=tenant.settings or {},
                document_count=stats.get('document_count', 0),
                storage_used=stats.get('storage_used', 0)
            ))
        
        return TenantListResponse(
            tenants=tenant_responses,
            total_count=total_count,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"Failed to list tenants: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tenant list"
        )


@router.get("/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    tenant_manager: TenantManager = Depends(get_tenant_manager)
):
    """
    Get detailed information about a specific tenant.
    
    Returns comprehensive tenant information including statistics.
    """
    try:
        logger.info(f"Retrieving tenant: {tenant_id}")
        
        # Validate tenant ID format
        try:
            uuid.UUID(tenant_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid tenant ID format"
            )
        
        # Get tenant information
        tenant = await tenant_manager.get_tenant(tenant_id)
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        # Get tenant statistics
        stats = await tenant_manager.get_tenant_stats(tenant_id)
        
        response = TenantResponse(
            id=str(tenant.id),
            name=tenant.name,
            description=tenant.description,
            contact_email=tenant.contact_email,
            status=tenant.status,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
            settings=tenant.settings or {},
            document_count=stats.get('document_count', 0),
            storage_used=stats.get('storage_used', 0)
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tenant information"
        )


@router.put("/tenants/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: str,
    request: TenantUpdateRequest,
    tenant_manager: TenantManager = Depends(get_tenant_manager)
):
    """
    Update tenant information and settings.
    
    Updates the specified tenant with new information and settings.
    """
    try:
        logger.info(f"Updating tenant: {tenant_id}")
        
        # Validate tenant ID format
        try:
            uuid.UUID(tenant_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid tenant ID format"
            )
        
        # Update tenant
        updated_tenant = await tenant_manager.update_tenant(
            tenant_id=tenant_id,
            name=request.name,
            description=request.description,
            contact_email=request.contact_email,
            settings=request.settings,
            status=request.status
        )
        
        if not updated_tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        # Get updated statistics
        stats = await tenant_manager.get_tenant_stats(tenant_id)
        
        response = TenantResponse(
            id=str(updated_tenant.id),
            name=updated_tenant.name,
            description=updated_tenant.description,
            contact_email=updated_tenant.contact_email,
            status=updated_tenant.status,
            created_at=updated_tenant.created_at,
            updated_at=updated_tenant.updated_at,
            settings=updated_tenant.settings or {},
            document_count=stats.get('document_count', 0),
            storage_used=stats.get('storage_used', 0)
        )
        
        logger.info(f"Tenant updated successfully: {tenant_id}")
        return response
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid tenant update request for {tenant_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update tenant"
        )


@router.delete("/tenants/{tenant_id}")
async def delete_tenant(
    tenant_id: str,
    tenant_manager: TenantManager = Depends(get_tenant_manager)
):
    """
    Delete a tenant and all associated data.
    
    WARNING: This operation is irreversible and will delete all tenant data
    including documents, embeddings, and query history.
    """
    try:
        logger.warning(f"Deleting tenant: {tenant_id}")
        
        # Validate tenant ID format
        try:
            uuid.UUID(tenant_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid tenant ID format"
            )
        
        # Delete tenant
        success = await tenant_manager.delete_tenant(tenant_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        logger.info(f"Tenant deleted successfully: {tenant_id}")
        return {"message": "Tenant deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete tenant"
        )


@router.get("/tenants/{tenant_id}/stats", response_model=TenantStatsResponse)
async def get_tenant_stats(
    tenant_id: str,
    tenant_manager: TenantManager = Depends(get_tenant_manager)
):
    """
    Get detailed statistics for a specific tenant.
    
    Returns comprehensive usage and performance statistics.
    """
    try:
        logger.info(f"Retrieving stats for tenant: {tenant_id}")
        
        # Validate tenant ID format
        try:
            uuid.UUID(tenant_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid tenant ID format"
            )
        
        # Verify tenant exists
        tenant = await tenant_manager.get_tenant(tenant_id)
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        # Get detailed statistics
        stats = await tenant_manager.get_detailed_stats(tenant_id)
        
        response = TenantStatsResponse(
            tenant_id=tenant_id,
            document_count=stats.get('document_count', 0),
            chunk_count=stats.get('chunk_count', 0),
            storage_used=stats.get('storage_used', 0),
            query_count_today=stats.get('query_count_today', 0),
            query_count_total=stats.get('query_count_total', 0),
            last_sync=stats.get('last_sync'),
            avg_query_time=stats.get('avg_query_time')
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve stats for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tenant statistics"
        ) 