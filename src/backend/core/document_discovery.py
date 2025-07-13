"""
Document Discovery - Filesystem vs Database Comparison
Simple functions to detect what files need syncing
"""

import hashlib
from pathlib import Path
from typing import List, Dict, Set, Optional
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.backend.models.database import File


@dataclass
class FileInfo:
    """Basic file information"""
    path: str
    name: str
    size: int
    hash: str


@dataclass
class SyncPlan:
    """What needs to be synced"""
    new_files: List[FileInfo]
    updated_files: List[tuple[File, FileInfo]]  # (db_record, fs_info)
    deleted_files: List[File]
    
    @property
    def total_changes(self) -> int:
        return len(self.new_files) + len(self.updated_files) + len(self.deleted_files)


def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of file content"""
    hash_sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception:
        return ""


def scan_filesystem(tenant_slug: str, upload_dir: str = "./data/uploads") -> List[FileInfo]:
    """Scan filesystem for tenant files"""
    tenant_dir = Path(upload_dir) / tenant_slug
    files = []
    
    if not tenant_dir.exists():
        return files
    
    for file_path in tenant_dir.rglob("*"):
        if file_path.is_file():
            try:
                relative_path = str(file_path.relative_to(upload_dir))
                file_hash = calculate_file_hash(file_path)
                
                files.append(FileInfo(
                    path=relative_path,
                    name=file_path.name,
                    size=file_path.stat().st_size,
                    hash=file_hash
                ))
            except Exception:
                # Skip files we can't read
                continue
    
    return files


async def get_database_files(db: AsyncSession, tenant_slug: str) -> List[File]:
    """Get all files for tenant from database"""
    result = await db.execute(
        select(File).where(File.tenant_slug == tenant_slug)
    )
    return result.scalars().all()


async def create_sync_plan(
    db: AsyncSession, 
    tenant_slug: str, 
    force_full_sync: bool = False
) -> SyncPlan:
    """Compare filesystem vs database and create sync plan"""
    
    # Get current state
    fs_files = scan_filesystem(tenant_slug)
    db_files = await get_database_files(db, tenant_slug)
    
    # Create lookup maps
    fs_map = {f.path: f for f in fs_files}
    db_map = {f.file_path: f for f in db_files}
    
    # Find changes
    new_files = []
    updated_files = []
    deleted_files = []
    
    # Check filesystem files against database
    for fs_file in fs_files:
        db_file = db_map.get(fs_file.path)
        
        if not db_file:
            # New file
            new_files.append(fs_file)
        elif db_file.file_hash != fs_file.hash or force_full_sync:
            # Updated file or force sync
            updated_files.append((db_file, fs_file))
    
    # Check for deleted files (in database but not on filesystem)
    fs_paths = set(f.path for f in fs_files)
    deleted_files = [
        db_file for db_file in db_files 
        if db_file.file_path not in fs_paths
    ]
    
    return SyncPlan(
        new_files=new_files,
        updated_files=updated_files,
        deleted_files=deleted_files
    )


def get_sync_summary(plan: SyncPlan) -> Dict[str, any]:
    """Get human-readable sync summary"""
    return {
        "total_changes": plan.total_changes,
        "new_files": len(plan.new_files),
        "updated_files": len(plan.updated_files),
        "deleted_files": len(plan.deleted_files),
        "new_file_names": [f.name for f in plan.new_files],
        "updated_file_names": [fs_info.name for _, fs_info in plan.updated_files],
        "deleted_file_names": [f.filename for f in plan.deleted_files]
    }