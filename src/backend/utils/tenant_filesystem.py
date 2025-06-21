"""
Tenant-Specific Folder Structure Management

Utilities for creating, managing, and maintaining tenant-specific directory structures
with proper isolation, permissions, and cleanup mechanisms.

Author: Enterprise RAG Platform Team
"""

import os
import shutil
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone
import logging
import json

from ..core.tenant_isolation import get_tenant_isolation_strategy, TenantSecurityError

logger = logging.getLogger(__name__)


class TenantFilesystemManager:
    """
    Manages tenant-specific filesystem operations and directory structures
    """
    
    def __init__(self, base_data_path: str = "/data"):
        self.base_data_path = Path(base_data_path)
        self.isolation_strategy = get_tenant_isolation_strategy()
        
        # Ensure base directory exists
        self.base_data_path.mkdir(parents=True, exist_ok=True)
    
    def create_tenant_structure(self, tenant_id: str) -> Dict[str, str]:
        """
        Create complete directory structure for a tenant
        
        Args:
            tenant_id: Unique tenant identifier
            
        Returns:
            Dictionary mapping directory types to their paths
        """
        try:
            # Get filesystem strategy for tenant
            fs_config = self.isolation_strategy.get_filesystem_strategy(tenant_id)
            
            # Define directory structure
            directories = {
                'root': fs_config['tenant_path'],
                'documents': fs_config['documents_path'],
                'uploads': fs_config['uploads_path'],
                'cache': fs_config['cache_path'],
                'logs': fs_config['logs_path'],
                'temp': os.path.join(fs_config['tenant_path'], 'temp'),
                'exports': os.path.join(fs_config['tenant_path'], 'exports'),
                'backups': os.path.join(fs_config['tenant_path'], 'backups'),
                'config': os.path.join(fs_config['tenant_path'], 'config'),
                'metadata': os.path.join(fs_config['tenant_path'], 'metadata')
            }
            
            # Create all directories
            created_dirs = []
            for dir_type, dir_path in directories.items():
                path_obj = Path(dir_path)
                path_obj.mkdir(parents=True, exist_ok=True)
                created_dirs.append(dir_path)
                
                # Set appropriate permissions (Unix-like systems)
                if os.name != 'nt':  # Not Windows
                    os.chmod(dir_path, 0o750)
                
                logger.info(f"Created {dir_type} directory for tenant {tenant_id}: {dir_path}")
            
            # Create tenant metadata file
            self._create_tenant_metadata(tenant_id, directories)
            
            # Create .gitkeep files to preserve empty directories
            self._create_gitkeep_files(directories)
            
            logger.info(f"Successfully created directory structure for tenant {tenant_id}")
            return directories
            
        except Exception as e:
            logger.error(f"Failed to create directory structure for tenant {tenant_id}: {str(e)}")
            # Cleanup partially created structure
            self._cleanup_partial_structure(fs_config.get('tenant_path'))
            raise
    
    def validate_tenant_structure(self, tenant_id: str) -> Dict[str, Any]:
        """
        Validate that tenant directory structure is complete and accessible
        
        Args:
            tenant_id: Unique tenant identifier
            
        Returns:
            Validation results with details about each directory
        """
        fs_config = self.isolation_strategy.get_filesystem_strategy(tenant_id)
        tenant_root = Path(fs_config['tenant_path'])
        
        validation_results = {
            'valid': True,
            'tenant_id': tenant_id,
            'root_path': str(tenant_root),
            'directories': {},
            'issues': [],
            'total_size_mb': 0
        }
        
        expected_dirs = {
            'documents': fs_config['documents_path'],
            'uploads': fs_config['uploads_path'],
            'cache': fs_config['cache_path'],
            'logs': fs_config['logs_path'],
            'temp': os.path.join(fs_config['tenant_path'], 'temp'),
            'exports': os.path.join(fs_config['tenant_path'], 'exports'),
            'backups': os.path.join(fs_config['tenant_path'], 'backups'),
            'config': os.path.join(fs_config['tenant_path'], 'config'),
            'metadata': os.path.join(fs_config['tenant_path'], 'metadata')
        }
        
        for dir_name, dir_path in expected_dirs.items():
            path_obj = Path(dir_path)
            dir_info = {
                'path': str(path_obj),
                'exists': path_obj.exists(),
                'is_directory': path_obj.is_dir() if path_obj.exists() else False,
                'readable': os.access(path_obj, os.R_OK) if path_obj.exists() else False,
                'writable': os.access(path_obj, os.W_OK) if path_obj.exists() else False,
                'size_mb': 0,
                'file_count': 0
            }
            
            if path_obj.exists() and path_obj.is_dir():
                try:
                    # Calculate directory size and file count
                    total_size = 0
                    file_count = 0
                    for root, dirs, files in os.walk(path_obj):
                        for file in files:
                            file_path = os.path.join(root, file)
                            try:
                                total_size += os.path.getsize(file_path)
                                file_count += 1
                            except (OSError, IOError):
                                pass
                    
                    dir_info['size_mb'] = round(total_size / (1024 * 1024), 2)
                    dir_info['file_count'] = file_count
                    validation_results['total_size_mb'] += dir_info['size_mb']
                    
                except Exception as e:
                    validation_results['issues'].append(f"Error calculating size for {dir_name}: {str(e)}")
            
            if not dir_info['exists']:
                validation_results['valid'] = False
                validation_results['issues'].append(f"Missing directory: {dir_name} ({dir_path})")
            elif not dir_info['is_directory']:
                validation_results['valid'] = False
                validation_results['issues'].append(f"Path exists but is not a directory: {dir_name} ({dir_path})")
            elif not (dir_info['readable'] and dir_info['writable']):
                validation_results['valid'] = False
                validation_results['issues'].append(f"Insufficient permissions for directory: {dir_name} ({dir_path})")
            
            validation_results['directories'][dir_name] = dir_info
        
        return validation_results
    
    def cleanup_tenant_structure(self, tenant_id: str, force: bool = False) -> Dict[str, Any]:
        """
        Clean up and remove tenant directory structure
        
        Args:
            tenant_id: Unique tenant identifier
            force: Force removal even if validation fails
            
        Returns:
            Cleanup results
        """
        fs_config = self.isolation_strategy.get_filesystem_strategy(tenant_id)
        tenant_root = Path(fs_config['tenant_path'])
        
        cleanup_results = {
            'success': False,
            'tenant_id': tenant_id,
            'root_path': str(tenant_root),
            'removed_size_mb': 0,
            'removed_files': 0,
            'errors': []
        }
        
        try:
            # Validate tenant access
            if not self.isolation_strategy.validate_tenant_access(tenant_id, tenant_id):
                raise TenantSecurityError(f"Access denied for tenant {tenant_id}")
            
            # Check if structure exists
            if not tenant_root.exists():
                cleanup_results['success'] = True
                cleanup_results['errors'].append("Directory structure does not exist")
                return cleanup_results
            
            # Calculate size before removal
            total_size = 0
            file_count = 0
            try:
                for root, dirs, files in os.walk(tenant_root):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            total_size += os.path.getsize(file_path)
                            file_count += 1
                        except (OSError, IOError):
                            pass
                
                cleanup_results['removed_size_mb'] = round(total_size / (1024 * 1024), 2)
                cleanup_results['removed_files'] = file_count
            except Exception as e:
                cleanup_results['errors'].append(f"Error calculating size: {str(e)}")
            
            # Remove directory structure
            if force or tenant_root.is_dir():
                shutil.rmtree(tenant_root, ignore_errors=force)
                cleanup_results['success'] = True
                logger.info(f"Successfully removed directory structure for tenant {tenant_id}")
            else:
                cleanup_results['errors'].append("Path exists but is not a directory")
                
        except Exception as e:
            cleanup_results['errors'].append(str(e))
            logger.error(f"Failed to cleanup directory structure for tenant {tenant_id}: {str(e)}")
        
        return cleanup_results
    
    def get_tenant_storage_stats(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get detailed storage statistics for a tenant
        
        Args:
            tenant_id: Unique tenant identifier
            
        Returns:
            Storage statistics
        """
        validation_results = self.validate_tenant_structure(tenant_id)
        
        stats = {
            'tenant_id': tenant_id,
            'total_size_mb': validation_results['total_size_mb'],
            'directory_breakdown': {},
            'file_types': {},
            'large_files': [],
            'old_files': [],
            'last_updated': datetime.now(timezone.utc).isoformat()
        }
        
        # Process each directory
        for dir_name, dir_info in validation_results['directories'].items():
            stats['directory_breakdown'][dir_name] = {
                'size_mb': dir_info['size_mb'],
                'file_count': dir_info['file_count'],
                'percentage': round((dir_info['size_mb'] / stats['total_size_mb'] * 100), 1) if stats['total_size_mb'] > 0 else 0
            }
            
            # Analyze file types and sizes in this directory
            if dir_info['exists'] and dir_info['is_directory']:
                self._analyze_directory_contents(Path(dir_info['path']), stats)
        
        return stats
    
    def archive_tenant_data(self, tenant_id: str, archive_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Create an archive of tenant data for backup or migration
        
        Args:
            tenant_id: Unique tenant identifier
            archive_path: Optional custom archive path
            
        Returns:
            Archive creation results
        """
        fs_config = self.isolation_strategy.get_filesystem_strategy(tenant_id)
        tenant_root = Path(fs_config['tenant_path'])
        
        if not archive_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_path = f"{tenant_root.parent}/tenant_{tenant_id}_archive_{timestamp}.tar.gz"
        
        archive_results = {
            'success': False,
            'tenant_id': tenant_id,
            'archive_path': archive_path,
            'archive_size_mb': 0,
            'files_archived': 0,
            'errors': []
        }
        
        try:
            import tarfile
            
            with tarfile.open(archive_path, "w:gz") as tar:
                # Add tenant directory to archive
                tar.add(tenant_root, arcname=f"tenant_{tenant_id}")
                
                # Count files and calculate size
                for root, dirs, files in os.walk(tenant_root):
                    archive_results['files_archived'] += len(files)
            
            # Get archive size
            archive_size = os.path.getsize(archive_path)
            archive_results['archive_size_mb'] = round(archive_size / (1024 * 1024), 2)
            archive_results['success'] = True
            
            logger.info(f"Successfully created archive for tenant {tenant_id}: {archive_path}")
            
        except Exception as e:
            archive_results['errors'].append(str(e))
            logger.error(f"Failed to create archive for tenant {tenant_id}: {str(e)}")
        
        return archive_results
    
    def _create_tenant_metadata(self, tenant_id: str, directories: Dict[str, str]) -> None:
        """Create metadata file for tenant directory structure"""
        metadata = {
            'tenant_id': tenant_id,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'structure_version': '1.0',
            'directories': directories,
            'permissions': {
                'owner': f'tenant_{tenant_id}',
                'group': 'rag_tenants',
                'mode': '0750'
            }
        }
        
        metadata_path = Path(directories['metadata']) / 'structure.json'
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def _create_gitkeep_files(self, directories: Dict[str, str]) -> None:
        """Create .gitkeep files in empty directories"""
        for dir_path in directories.values():
            gitkeep_path = Path(dir_path) / '.gitkeep'
            gitkeep_path.touch()
    
    def _cleanup_partial_structure(self, tenant_path: Optional[str]) -> None:
        """Clean up partially created directory structure"""
        if tenant_path and Path(tenant_path).exists():
            try:
                shutil.rmtree(tenant_path)
                logger.info(f"Cleaned up partial structure: {tenant_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup partial structure {tenant_path}: {str(e)}")
    
    def _analyze_directory_contents(self, directory: Path, stats: Dict[str, Any]) -> None:
        """Analyze contents of a directory for detailed statistics"""
        try:
            for item in directory.rglob('*'):
                if item.is_file():
                    try:
                        file_size = item.stat().st_size
                        file_size_mb = file_size / (1024 * 1024)
                        
                        # Track file types
                        file_ext = item.suffix.lower() or 'no_extension'
                        if file_ext not in stats['file_types']:
                            stats['file_types'][file_ext] = {'count': 0, 'size_mb': 0}
                        stats['file_types'][file_ext]['count'] += 1
                        stats['file_types'][file_ext]['size_mb'] += file_size_mb
                        
                        # Track large files (>10MB)
                        if file_size_mb > 10:
                            stats['large_files'].append({
                                'path': str(item.relative_to(directory.parent)),
                                'size_mb': round(file_size_mb, 2)
                            })
                        
                        # Track old files (>90 days)
                        file_mtime = datetime.fromtimestamp(item.stat().st_mtime, tz=timezone.utc)
                        days_old = (datetime.now(timezone.utc) - file_mtime).days
                        if days_old > 90:
                            stats['old_files'].append({
                                'path': str(item.relative_to(directory.parent)),
                                'days_old': days_old,
                                'size_mb': round(file_size_mb, 2)
                            })
                            
                    except (OSError, IOError):
                        pass
        except Exception as e:
            logger.warning(f"Error analyzing directory {directory}: {str(e)}")


def get_tenant_filesystem_manager() -> TenantFilesystemManager:
    """Get the global tenant filesystem manager instance"""
    return TenantFilesystemManager()


# Utility functions
def ensure_tenant_directory_exists(tenant_id: str, directory_type: str = 'documents') -> str:
    """
    Ensure a specific tenant directory exists and return its path
    
    Args:
        tenant_id: Unique tenant identifier
        directory_type: Type of directory (documents, uploads, cache, etc.)
        
    Returns:
        Path to the directory
    """
    manager = get_tenant_filesystem_manager()
    validation = manager.validate_tenant_structure(tenant_id)
    
    if not validation['valid']:
        # Create structure if it doesn't exist
        directories = manager.create_tenant_structure(tenant_id)
        return directories.get(directory_type, directories['documents'])
    
    return validation['directories'][directory_type]['path']


def calculate_tenant_storage_usage(tenant_id: str) -> float:
    """
    Calculate total storage usage for a tenant in MB
    
    Args:
        tenant_id: Unique tenant identifier
        
    Returns:
        Storage usage in MB
    """
    manager = get_tenant_filesystem_manager()
    stats = manager.get_tenant_storage_stats(tenant_id)
    return stats['total_size_mb']


def cleanup_tenant_temp_files(tenant_id: str, max_age_hours: int = 24) -> int:
    """
    Clean up temporary files older than specified age
    
    Args:
        tenant_id: Unique tenant identifier
        max_age_hours: Maximum age of temp files to keep
        
    Returns:
        Number of files cleaned up
    """
    manager = get_tenant_filesystem_manager()
    validation = manager.validate_tenant_structure(tenant_id)
    
    if not validation['valid']:
        return 0
    
    temp_dir = Path(validation['directories']['temp']['path'])
    if not temp_dir.exists():
        return 0
    
    cleaned_count = 0
    cutoff_time = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)
    
    try:
        for item in temp_dir.rglob('*'):
            if item.is_file() and item.stat().st_mtime < cutoff_time:
                try:
                    item.unlink()
                    cleaned_count += 1
                except (OSError, IOError):
                    pass
    except Exception as e:
        logger.warning(f"Error cleaning temp files for tenant {tenant_id}: {str(e)}")
    
    return cleaned_count 