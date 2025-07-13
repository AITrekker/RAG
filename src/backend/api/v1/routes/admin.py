"""
Simple Admin Routes - Just Core Tenant Management
Replaces complex admin.py with teaching-focused simplicity
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Dict, Any

from src.backend.database import get_async_db
from src.backend.middleware.api_key_auth import get_current_tenant
from src.backend.models.database import Tenant

router = APIRouter()


@router.get("/tenants")
async def list_tenants(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """List all tenants - admin only"""
    
    if current_tenant.slug != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        # Simple SQL query to get tenants
        result = await db.execute(text("""
            SELECT slug, name, created_at, updated_at
            FROM tenants 
            ORDER BY created_at
        """))
        
        tenants = []
        for row in result:
            tenants.append({
                "slug": row.slug,
                "name": row.name,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat()
            })
        
        return {
            "tenants": tenants,
            "total": len(tenants)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list tenants: {str(e)}")


@router.get("/stats")
async def get_system_stats(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """Get simple system statistics - admin only"""
    
    if current_tenant.slug != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        # Get tenant count
        tenant_result = await db.execute(text("SELECT COUNT(*) FROM tenants"))
        tenant_count = tenant_result.scalar()
        
        # Get file count
        file_result = await db.execute(text("SELECT COUNT(*) FROM files"))
        file_count = file_result.scalar()
        
        # Get embedding count
        embedding_result = await db.execute(text("SELECT COUNT(*) FROM embedding_chunks"))
        embedding_count = embedding_result.scalar()
        
        return {
            "tenants": tenant_count,
            "files": file_count,
            "embeddings": embedding_count
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/health")
async def health_check():
    """Simple health check"""
    return {"status": "healthy", "service": "admin"}