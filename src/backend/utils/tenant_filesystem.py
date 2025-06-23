"""
Tenant-Specific Filesystem Management for the Enterprise RAG Platform.
"""
import os
import shutil
import uuid
import aiofiles
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import UploadFile
import logging

from ..core.tenant_isolation import get_tenant_isolation_strategy

logger = logging.getLogger(__name__)

class TenantFileSystemManager:
    def __init__(self, base_data_path: str = "data"):
        self.base_path = Path(base_data_path)
        self.isolation_strategy = get_tenant_isolation_strategy()

    def get_tenant_directories(self, tenant_id: str) -> Dict[str, Path]:
        fs_config = self.isolation_strategy.get_filesystem_strategy(tenant_id)
        root = Path(fs_config["tenant_path"])
        return {
            "root": root,
            "documents": Path(fs_config["documents_path"]),
            "uploads": Path(fs_config["uploads_path"]),
        }

    def create_tenant_directories(self, tenant_id: str):
        dirs = self.get_tenant_directories(tenant_id)
        for dir_path in dirs.values():
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {dir_path} for tenant {tenant_id}")

    def delete_tenant_directories(self, tenant_id: str):
        dirs = self.get_tenant_directories(tenant_id)
        root_dir = dirs.get("root")
        if root_dir and root_dir.exists():
            shutil.rmtree(root_dir)
            logger.info(f"Deleted directory tree: {root_dir} for tenant {tenant_id}")

    async def save_uploaded_file(
        self, 
        tenant_id: str, 
        file: UploadFile, 
        document_id: str = None
    ) -> str:
        """
        Save an uploaded file to the tenant's upload directory.
        
        Args:
            tenant_id: The tenant ID
            file: The uploaded file
            document_id: Optional document ID for filename
            
        Returns:
            Path to the saved file
        """
        # Ensure tenant directories exist
        self.create_tenant_directories(tenant_id)
        
        # Get tenant directories
        dirs = self.get_tenant_directories(tenant_id)
        uploads_dir = dirs["uploads"]
        
        # Generate unique filename
        if document_id:
            # Use document ID for filename
            filename = f"{document_id}_{file.filename}"
        else:
            # Generate unique filename
            unique_id = str(uuid.uuid4())
            filename = f"{unique_id}_{file.filename}"
        
        file_path = uploads_dir / filename
        
        # Save file asynchronously
        async with aiofiles.open(file_path, 'wb') as buffer:
            content = await file.read()
            await buffer.write(content)
        
        logger.info(f"Saved uploaded file {file.filename} to {file_path} for tenant {tenant_id}")
        return str(file_path)

    def create_tenant_structure(self, tenant_id: str) -> Dict[str, Path]:
        """Create complete tenant directory structure."""
        self.create_tenant_directories(tenant_id)
        return self.get_tenant_directories(tenant_id)

    def cleanup_tenant_structure(self, tenant_id: str, force: bool = False) -> Dict[str, any]:
        """Clean up tenant directory structure."""
        try:
            self.delete_tenant_directories(tenant_id)
            return {"success": True, "errors": []}
        except Exception as e:
            return {"success": False, "errors": [str(e)]}

    def archive_tenant_data(self, tenant_id: str) -> Dict[str, str]:
        """Archive tenant data before deletion."""
        import tarfile
        from datetime import datetime
        
        dirs = self.get_tenant_directories(tenant_id)
        root_dir = dirs["root"]
        
        if not root_dir.exists():
            return {"archive_path": None, "message": "No data to archive"}
        
        # Create archive
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"tenant_{tenant_id}_backup_{timestamp}.tar.gz"
        archive_path = self.base_path / "backups" / archive_name
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(root_dir, arcname=f"tenant_{tenant_id}")
        
        return {"archive_path": str(archive_path)} 