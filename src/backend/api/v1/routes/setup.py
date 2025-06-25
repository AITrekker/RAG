"""
Setup and initialization API endpoints.

This module provides endpoints for:
- Checking system initialization status
- Initializing the system with admin tenant
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
import os
import json
from datetime import datetime

from ...models.api_models import (
    SetupCheckResponse,
    SetupInitializeRequest,
    SetupInitializeResponse,
    ErrorResponse
)
from ...core.tenant_service import TenantService
from ...core.embedding_manager import EmbeddingManager
from ...middleware.auth import get_current_tenant
from ...config.settings import get_settings

router = APIRouter(prefix="/setup", tags=["Setup & Initialization"])

@router.get("/status", response_model=SetupCheckResponse)
async def check_setup_status():
    """
    Check if the system is properly initialized.
    
    Returns:
        SetupCheckResponse: Current initialization status
    """
    try:
        settings = get_settings()
        tenant_service = TenantService()
        
        # Check if admin tenant exists
        admin_tenant = await tenant_service.get_tenant_by_name("admin")
        admin_tenant_exists = admin_tenant is not None
        
        # Count total tenants
        all_tenants = await tenant_service.list_tenants()
        total_tenants = len(all_tenants)
        
        # Determine initialization status
        if admin_tenant_exists:
            return SetupCheckResponse(
                initialized=True,
                message="System is initialized and ready",
                admin_tenant_exists=True,
                total_tenants=total_tenants
            )
        else:
            return SetupCheckResponse(
                initialized=False,
                message="System not initialized. Admin tenant not found.",
                admin_tenant_exists=False,
                total_tenants=total_tenants
            )
            
    except Exception as e:
        return SetupCheckResponse(
            initialized=False,
            message=f"Error checking setup status: {str(e)}",
            admin_tenant_exists=False,
            total_tenants=0
        )

@router.post("/initialize", response_model=SetupInitializeResponse)
async def initialize_system(request: SetupInitializeRequest):
    """
    Initialize the system with admin tenant and basic configuration.
    
    This endpoint:
    1. Creates the admin tenant
    2. Generates admin API key
    3. Sets up initial configuration
    4. Creates necessary collections in Qdrant
    
    Args:
        request: SetupInitializeRequest containing admin tenant details
        
    Returns:
        SetupInitializeResponse: Initialization results with admin credentials
    """
    try:
        settings = get_settings()
        tenant_service = TenantService()
        
        # Check if already initialized
        existing_admin = await tenant_service.get_tenant_by_name("admin")
        if existing_admin:
            raise HTTPException(
                status_code=400,
                detail="System already initialized. Admin tenant exists."
            )
        
        # Create admin tenant
        admin_tenant_id = await tenant_service.create_tenant(
            name="admin",
            description=request.admin_tenant_description or "System administrator tenant",
            auto_sync=True,
            sync_interval=60
        )
        
        # Create admin API key
        admin_api_key = await tenant_service.create_api_key(
            tenant_id=admin_tenant_id,
            name="Admin API Key",
            description="Default admin API key"
        )
        
        # Initialize embedding manager for admin tenant
        embedding_manager = EmbeddingManager(tenant_id=admin_tenant_id)
        await embedding_manager.initialize_collections()
        
        # Write admin credentials to .env file if it doesn't exist
        config_written = False
        env_file = ".env"
        if not os.path.exists(env_file):
            try:
                with open(env_file, "w") as f:
                    f.write(f"# RAG Platform Configuration\n")
                    f.write(f"# Generated on {datetime.utcnow().isoformat()}\n\n")
                    f.write(f"ADMIN_TENANT_ID={admin_tenant_id}\n")
                    f.write(f"ADMIN_API_KEY={admin_api_key}\n")
                    f.write(f"# Add other configuration as needed\n")
                config_written = True
            except Exception as e:
                # Log but don't fail initialization
                print(f"Warning: Could not write to .env file: {e}")
        
        return SetupInitializeResponse(
            success=True,
            admin_tenant_id=admin_tenant_id,
            admin_api_key=admin_api_key,
            message="System initialized successfully",
            config_written=config_written
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize system: {str(e)}"
        ) 