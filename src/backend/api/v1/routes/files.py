"""
File Management API Routes - Using the new service architecture
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, status
from typing import List, Optional
from uuid import UUID

from src.backend.dependencies import (
    get_current_tenant_dep,
    get_file_service_dep,
    get_sync_service_dep,
    get_rag_service_dep
)
from src.backend.services.file_service import FileService
from src.backend.services.sync_service import SyncService
from src.backend.models.database import Tenant
from src.backend.models.api_models import (
    FileResponse,
    FileListResponse,
    UploadResponse
)

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    file_service: FileService = Depends(get_file_service_dep)
):
    """Upload a file for the authenticated tenant"""
    try:
        file_record = await file_service.upload_file(
            tenant_id=current_tenant.slug,
            file=file
        )
        
        return UploadResponse(
            file_id=str(file_record.id),
            filename=file_record.filename,
            file_size=file_record.file_size,
            sync_status=file_record.sync_status,
            message="File uploaded successfully"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )


@router.get("/", response_model=FileListResponse)
async def list_files(
    skip: int = 0,
    limit: int = 100,
    sync_status: Optional[str] = None,
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    file_service: FileService = Depends(get_file_service_dep)
):
    """List files for the authenticated tenant"""
    try:
        files = await file_service.list_files(
            tenant_id=current_tenant.slug,
            skip=skip,
            limit=limit,
            sync_status=sync_status
        )
        
        file_responses = [
            FileResponse(
                id=str(file.id),
                filename=file.filename,
                file_size=file.file_size,
                mime_type=file.mime_type,
                sync_status=file.sync_status,
                word_count=file.word_count,
                page_count=file.page_count,
                language=file.language,
                created_at=file.created_at.isoformat(),
                updated_at=file.updated_at.isoformat()
            )
            for file in files
        ]
        
        return FileListResponse(
            files=file_responses,
            total_count=len(file_responses),  # TODO: Get actual total count
            page=skip // limit + 1,
            page_size=limit
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list files: {str(e)}"
        )


@router.get("/{file_id}", response_model=FileResponse)
async def get_file(
    file_id: UUID,
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    file_service: FileService = Depends(get_file_service_dep)
):
    """Get file details"""
    file_record = await file_service.get_file(current_tenant.slug, file_id)
    
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    return FileResponse(
        id=str(file_record.id),
        filename=file_record.filename,
        file_size=file_record.file_size,
        mime_type=file_record.mime_type,
        sync_status=file_record.sync_status,
        word_count=file_record.word_count,
        page_count=file_record.page_count,
        language=file_record.language,
        created_at=file_record.created_at.isoformat(),
        updated_at=file_record.updated_at.isoformat()
    )


@router.delete("/{file_id}")
async def delete_file(
    file_id: UUID,
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    file_service: FileService = Depends(get_file_service_dep)
):
    """Delete a file"""
    success = await file_service.delete_file(current_tenant.slug, file_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    return {"message": "File deleted successfully"}


@router.post("/{file_id}/sync")
async def sync_file(
    file_id: UUID,
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    sync_service: SyncService = Depends(get_sync_service_dep)
):
    """Trigger sync for a specific file"""
    success = await sync_service.trigger_file_sync(file_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to sync file"
        )
    
    return {"message": "File sync triggered successfully"}


@router.get("/{file_id}/chunks")
async def get_file_chunks(
    file_id: UUID,
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    rag_service = Depends(get_rag_service_dep)
):
    """Get all chunks for a file"""
    chunks = await rag_service.get_document_chunks(file_id, current_tenant.slug)
    return {"chunks": chunks}