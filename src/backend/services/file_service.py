"""
File Service - Handles file CRUD operations and metadata management
"""

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, BinaryIO
from uuid import UUID

from fastapi import UploadFile, HTTPException
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.models.database import File, Tenant
from src.backend.config.settings import get_settings

settings = get_settings()


class FileService:
    """Service for file operations and metadata management"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def upload_file(
        self, 
        tenant_id: UUID, 
        uploaded_by: UUID, 
        file: UploadFile
    ) -> File:
        """
        Upload a file for a tenant
        
        Args:
            tenant_id: Tenant ID
            uploaded_by: User ID who uploaded the file
            file: FastAPI UploadFile object
            
        Returns:
            File: Created file record
        """
        # Validate file
        if file.size and file.size > 100 * 1024 * 1024:  # 100MB limit
            raise HTTPException(400, "File too large")
        
        # Create tenant upload directory
        tenant_upload_dir = Path(f"./data/uploads/{tenant_id}")
        tenant_upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename to avoid conflicts
        file_path = tenant_upload_dir / file.filename
        counter = 1
        while file_path.exists():
            name, ext = os.path.splitext(file.filename)
            file_path = tenant_upload_dir / f"{name}_{counter}{ext}"
            counter += 1
        
        # Save file to disk
        content = await file.read()
        file_path.write_bytes(content)
        
        # Calculate file hash
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Create file record
        file_record = File(
            tenant_id=tenant_id,
            uploaded_by=uploaded_by,
            filename=file.filename,
            file_path=str(file_path.relative_to("./data/uploads/")),
            file_size=len(content),
            mime_type=file.content_type,
            file_hash=file_hash,
            sync_status='pending'
        )
        
        self.db.add(file_record)
        await self.db.commit()
        await self.db.refresh(file_record)
        
        return file_record
    
    async def get_file(self, tenant_id: UUID, file_id: UUID) -> Optional[File]:
        """Get file by ID with tenant isolation"""
        result = await self.db.execute(
            select(File).where(
                File.id == file_id,
                File.tenant_id == tenant_id,
                File.deleted_at.is_(None)
            )
        )
        return result.scalar_one_or_none()
    
    async def list_files(
        self, 
        tenant_id: UUID, 
        skip: int = 0, 
        limit: int = 100,
        sync_status: Optional[str] = None
    ) -> List[File]:
        """List files for a tenant with pagination"""
        query = select(File).where(
            File.tenant_id == tenant_id,
            File.deleted_at.is_(None)
        )
        
        if sync_status:
            query = query.where(File.sync_status == sync_status)
        
        query = query.offset(skip).limit(limit).order_by(File.created_at.desc())
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def update_file_metadata(
        self, 
        file_id: UUID, 
        tenant_id: UUID, 
        metadata: Dict[str, Any]
    ) -> Optional[File]:
        """Update file metadata"""
        # First check if file exists and belongs to tenant
        file_record = await self.get_file(tenant_id, file_id)
        if not file_record:
            return None
        
        # Update allowed metadata fields
        update_data = {}
        if 'word_count' in metadata:
            update_data['word_count'] = metadata['word_count']
        if 'page_count' in metadata:
            update_data['page_count'] = metadata['page_count']
        if 'language' in metadata:
            update_data['language'] = metadata['language']
        if 'extraction_method' in metadata:
            update_data['extraction_method'] = metadata['extraction_method']
        
        if update_data:
            await self.db.execute(
                update(File)
                .where(File.id == file_id)
                .values(**update_data)
            )
            await self.db.commit()
            await self.db.refresh(file_record)
        
        return file_record
    
    async def update_sync_status(
        self, 
        file_id: UUID, 
        status: str, 
        error: Optional[str] = None
    ) -> None:
        """Update file sync status"""
        update_data = {
            'sync_status': status,
            'sync_started_at': datetime.utcnow() if status == 'processing' else None,
            'sync_completed_at': datetime.utcnow() if status in ['synced', 'failed'] else None,
            'sync_error': error
        }
        
        await self.db.execute(
            update(File)
            .where(File.id == file_id)
            .values(**update_data)
        )
        await self.db.commit()
    
    async def delete_file(self, tenant_id: UUID, file_id: UUID) -> bool:
        """Soft delete a file"""
        file_record = await self.get_file(tenant_id, file_id)
        if not file_record:
            return False
        
        # Soft delete
        await self.db.execute(
            update(File)
            .where(File.id == file_id)
            .values(
                deleted_at=datetime.utcnow(),
                sync_status='deleted'
            )
        )
        await self.db.commit()
        
        # TODO: Schedule physical file deletion and embedding cleanup
        return True
    
    async def calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of a file"""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    async def scan_tenant_files(self, tenant_id: UUID) -> List[Dict[str, Any]]:
        """
        Scan filesystem for tenant files and return file info
        Used by sync service for delta detection
        """
        tenant_upload_dir = Path(f"./data/uploads/{tenant_id}")
        if not tenant_upload_dir.exists():
            return []
        
        files = []
        for file_path in tenant_upload_dir.rglob("*"):
            if file_path.is_file():
                stat = file_path.stat()
                files.append({
                    'path': str(file_path.relative_to("./data/uploads/")),
                    'size': stat.st_size,
                    'modified_time': datetime.fromtimestamp(stat.st_mtime),
                    'hash': await self.calculate_file_hash(str(file_path))
                })
        
        return files
    
    async def get_files_by_sync_status(
        self, 
        tenant_id: UUID, 
        status: str
    ) -> List[File]:
        """Get files by sync status for processing"""
        result = await self.db.execute(
            select(File).where(
                File.tenant_id == tenant_id,
                File.sync_status == status,
                File.deleted_at.is_(None)
            )
        )
        return result.scalars().all()
    
    async def get_tenant_storage_usage(self, tenant_id: UUID) -> Dict[str, Any]:
        """Get storage usage statistics for a tenant"""
        # TODO: Implement storage usage calculation
        return {
            'total_files': 0,
            'total_size_bytes': 0,
            'storage_limit_bytes': 0,
            'usage_percentage': 0.0
        }


# Dependency function for FastAPI
async def get_file_service(db_session: AsyncSession) -> FileService:
    """Dependency to get file service with database session"""
    return FileService(db_session)