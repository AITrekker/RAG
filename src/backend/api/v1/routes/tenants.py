from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from src.backend.models.api_models import TenantResponse, CreateApiKeyRequest, CreateApiKeyResponse
from src.backend.core.tenant_service import TenantService, get_tenant_service

router = APIRouter()

@router.get("", response_model=List[TenantResponse])
def get_tenants(tenant_service: TenantService = Depends(get_tenant_service)):
    """
    Get all tenants.
    """
    tenants = tenant_service.list_tenants()
    return tenants

@router.post("/api-key", response_model=CreateApiKeyResponse)
def create_api_key(
    request: CreateApiKeyRequest,
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """
    Create an API key for a tenant.
    """
    try:
        api_key = tenant_service.create_api_key(request.tenant_id)
        return CreateApiKeyResponse(api_key=api_key)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) 