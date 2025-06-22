"""
Tenant-Specific Filesystem Management for the Enterprise RAG Platform.
"""
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional
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