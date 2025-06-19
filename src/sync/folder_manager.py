"""
Master/sync folder management system.

This module manages the master and sync folder structure with tenant isolation,
ensuring proper file organization and access control.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
import asyncio
import json

logger = logging.getLogger(__name__)

@dataclass
class FolderConfig:
    """Configuration for master/sync folders."""
    tenant_id: str
    master_root: Path
    sync_root: Path
    supported_extensions: Set[str] = field(default_factory=lambda: {
        '.pdf', '.docx', '.doc', '.pptx', '.ppt', '.txt', '.md',
        '.xlsx', '.xls', '.csv'
    })
    max_file_size: int = 100 * 1024 * 1024  # 100MB default
    metadata: Dict[str, Any] = field(default_factory=dict)

class FolderManager:
    """Manages master and sync folder structure for tenants."""
    
    def __init__(self, base_path: str):
        """Initialize folder manager.
        
        Args:
            base_path: Base directory for all tenant folders
        """
        self.base_path = Path(base_path).resolve()
        self.tenant_configs: Dict[str, FolderConfig] = {}
        
        # Create base directories
        self.base_path.mkdir(parents=True, exist_ok=True)
        (self.base_path / 'master').mkdir(exist_ok=True)
        (self.base_path / 'sync').mkdir(exist_ok=True)
        
        logger.info(f"Initialized folder manager at {self.base_path}")
    
    def add_tenant(
        self,
        tenant_id: str,
        supported_extensions: Optional[Set[str]] = None,
        max_file_size: Optional[int] = None
    ) -> FolderConfig:
        """Add a new tenant with isolated folders.
        
        Args:
            tenant_id: Unique tenant identifier
            supported_extensions: Set of allowed file extensions
            max_file_size: Maximum allowed file size in bytes
            
        Returns:
            FolderConfig for the tenant
        """
        # Create tenant directories
        master_root = self.base_path / 'master' / tenant_id
        sync_root = self.base_path / 'sync' / tenant_id
        
        master_root.mkdir(parents=True, exist_ok=True)
        sync_root.mkdir(parents=True, exist_ok=True)
        
        # Create config
        config = FolderConfig(
            tenant_id=tenant_id,
            master_root=master_root,
            sync_root=sync_root,
            supported_extensions=supported_extensions or FolderConfig.supported_extensions,
            max_file_size=max_file_size or FolderConfig.max_file_size
        )
        
        self.tenant_configs[tenant_id] = config
        logger.info(f"Added tenant {tenant_id} folders at {master_root} and {sync_root}")
        
        return config
    
    def remove_tenant(self, tenant_id: str, delete_files: bool = False) -> bool:
        """Remove a tenant's folder configuration.
        
        Args:
            tenant_id: Tenant identifier
            delete_files: If True, delete all tenant files
            
        Returns:
            True if tenant was removed
        """
        if tenant_id not in self.tenant_configs:
            logger.warning(f"Tenant {tenant_id} not found")
            return False
        
        config = self.tenant_configs[tenant_id]
        
        if delete_files:
            # Delete tenant directories
            shutil.rmtree(config.master_root, ignore_errors=True)
            shutil.rmtree(config.sync_root, ignore_errors=True)
            logger.info(f"Deleted tenant {tenant_id} folders")
        
        del self.tenant_configs[tenant_id]
        return True
    
    def validate_file(self, tenant_id: str, file_path: str) -> tuple[bool, Optional[str]]:
        """Validate if a file meets tenant requirements.
        
        Args:
            tenant_id: Tenant identifier
            file_path: Path to file to validate
            
        Returns:
            (is_valid, error_message) tuple
        """
        if tenant_id not in self.tenant_configs:
            return False, "Tenant not found"
        
        config = self.tenant_configs[tenant_id]
        path = Path(file_path)
        
        # Check extension
        if path.suffix.lower() not in config.supported_extensions:
            return False, f"Unsupported file extension: {path.suffix}"
        
        # Check size
        try:
            size = path.stat().st_size
            if size > config.max_file_size:
                return False, f"File too large: {size} bytes"
        except OSError:
            return False, "Cannot access file"
        
        return True, None
    
    async def copy_to_sync(
        self,
        tenant_id: str,
        source_path: str,
        preserve_structure: bool = True
    ) -> Optional[str]:
        """Copy a file from master to sync folder.
        
        Args:
            tenant_id: Tenant identifier
            source_path: Path to source file in master folder
            preserve_structure: Preserve folder structure in sync folder
            
        Returns:
            Path to copied file in sync folder, or None on failure
        """
        if tenant_id not in self.tenant_configs:
            logger.error(f"Tenant {tenant_id} not found")
            return None
        
        config = self.tenant_configs[tenant_id]
        source = Path(source_path)
        
        # Validate source path is in master folder
        if not str(source).startswith(str(config.master_root)):
            logger.error(f"Source file {source} not in master folder")
            return None
        
        try:
            # Calculate relative path from master root
            rel_path = source.relative_to(config.master_root)
            target = config.sync_root / rel_path if preserve_structure else config.sync_root / source.name
            
            # Create target directory
            target.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file with metadata preservation
            shutil.copy2(source, target)
            logger.info(f"Copied {source} to {target}")
            
            return str(target)
            
        except Exception as e:
            logger.error(f"Failed to copy {source} to sync folder: {e}")
            return None
    
    def get_tenant_folders(self, tenant_id: str) -> Optional[FolderConfig]:
        """Get folder configuration for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            FolderConfig if tenant exists, None otherwise
        """
        return self.tenant_configs.get(tenant_id)
    
    def list_master_files(self, tenant_id: str) -> List[str]:
        """List all files in tenant's master folder.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            List of file paths relative to master folder
        """
        if tenant_id not in self.tenant_configs:
            return []
        
        config = self.tenant_configs[tenant_id]
        files = []
        
        try:
            for file_path in config.master_root.rglob('*'):
                if file_path.is_file():
                    rel_path = file_path.relative_to(config.master_root)
                    files.append(str(rel_path))
        except Exception as e:
            logger.error(f"Failed to list master files for tenant {tenant_id}: {e}")
        
        return files
    
    def list_sync_files(self, tenant_id: str) -> List[str]:
        """List all files in tenant's sync folder.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            List of file paths relative to sync folder
        """
        if tenant_id not in self.tenant_configs:
            return []
        
        config = self.tenant_configs[tenant_id]
        files = []
        
        try:
            for file_path in config.sync_root.rglob('*'):
                if file_path.is_file():
                    rel_path = file_path.relative_to(config.sync_root)
                    files.append(str(rel_path))
        except Exception as e:
            logger.error(f"Failed to list sync files for tenant {tenant_id}: {e}")
        
        return files 