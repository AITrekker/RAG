"""
Conflict resolution system for file synchronization.

This module provides conflict detection, resolution strategies,
and comprehensive conflict logging for sync operations.
"""

import asyncio
import logging
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Callable
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import shutil

logger = logging.getLogger(__name__)

class ConflictType(Enum):
    """Types of sync conflicts."""
    MODIFICATION_CONFLICT = "modification_conflict"  # Both sides modified
    DELETE_MODIFY_CONFLICT = "delete_modify_conflict"  # One deleted, one modified
    MOVE_CONFLICT = "move_conflict"  # File moved to different locations
    NAME_CONFLICT = "name_conflict"  # Different names for same content
    PERMISSION_CONFLICT = "permission_conflict"  # Permission differences
    SIZE_LIMIT_CONFLICT = "size_limit_conflict"  # File exceeds size limits

class ConflictResolutionStrategy(Enum):
    """Conflict resolution strategies."""
    SOURCE_WINS = "source_wins"  # Source always wins
    TARGET_WINS = "target_wins"  # Target always wins
    NEWER_WINS = "newer_wins"  # Newer file wins
    LARGER_WINS = "larger_wins"  # Larger file wins
    MANUAL = "manual"  # Requires manual intervention
    RENAME_BOTH = "rename_both"  # Keep both files with different names
    MERGE_ATTEMPT = "merge_attempt"  # Try to merge content (text files only)

class ConflictStatus(Enum):
    """Status of conflict resolution."""
    PENDING = "pending"
    RESOLVED = "resolved"
    FAILED = "failed"
    REQUIRES_MANUAL = "requires_manual"

@dataclass
class ConflictDetails:
    """Details about a sync conflict."""
    conflict_id: str
    conflict_type: ConflictType
    tenant_id: str
    folder_name: str
    
    source_path: str
    target_path: str
    
    source_mtime: Optional[datetime] = None
    target_mtime: Optional[datetime] = None
    source_size: Optional[int] = None
    target_size: Optional[int] = None
    source_hash: Optional[str] = None
    target_hash: Optional[str] = None
    
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    
    status: ConflictStatus = ConflictStatus.PENDING
    resolution_strategy: Optional[ConflictResolutionStrategy] = None
    resolution_result: Optional[str] = None
    error_message: Optional[str] = None
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'conflict_id': self.conflict_id,
            'conflict_type': self.conflict_type.value,
            'tenant_id': self.tenant_id,
            'folder_name': self.folder_name,
            'source_path': self.source_path,
            'target_path': self.target_path,
            'source_mtime': self.source_mtime.isoformat() if self.source_mtime else None,
            'target_mtime': self.target_mtime.isoformat() if self.target_mtime else None,
            'source_size': self.source_size,
            'target_size': self.target_size,
            'source_hash': self.source_hash,
            'target_hash': self.target_hash,
            'detected_at': self.detected_at.isoformat(),
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'status': self.status.value,
            'resolution_strategy': self.resolution_strategy.value if self.resolution_strategy else None,
            'resolution_result': self.resolution_result,
            'error_message': self.error_message,
            'metadata': self.metadata
        }

class ConflictDetector:
    """Detects various types of sync conflicts."""
    
    def __init__(self):
        self.supported_extensions = {
            '.pdf', '.docx', '.doc', '.pptx', '.ppt', '.txt', '.md',
            '.xlsx', '.xls', '.csv'
        }
    
    async def detect_conflicts(
        self, 
        source_files: Dict[str, Dict[str, Any]], 
        target_files: Dict[str, Dict[str, Any]],
        tenant_id: str,
        folder_name: str
    ) -> List[ConflictDetails]:
        """Detect conflicts between source and target file sets."""
        conflicts = []
        conflict_counter = 0
        
        # Find files that exist in both source and target
        common_files = set(source_files.keys()) & set(target_files.keys())
        
        for relative_path in common_files:
            source_info = source_files[relative_path]
            target_info = target_files[relative_path]
            
            conflict = await self._check_file_conflict(
                relative_path, source_info, target_info, tenant_id, folder_name
            )
            
            if conflict:
                conflict_counter += 1
                conflict.conflict_id = f"conflict_{tenant_id}_{conflict_counter:06d}"
                conflicts.append(conflict)
        
        # Check for delete-modify conflicts
        conflicts.extend(await self._detect_delete_modify_conflicts(
            source_files, target_files, tenant_id, folder_name, conflict_counter
        ))
        
        logger.info(f"Detected {len(conflicts)} conflicts for tenant {tenant_id} in folder {folder_name}")
        return conflicts
    
    async def _check_file_conflict(
        self,
        relative_path: str,
        source_info: Dict[str, Any],
        target_info: Dict[str, Any],
        tenant_id: str,
        folder_name: str
    ) -> Optional[ConflictDetails]:
        """Check if a specific file has conflicts."""
        
        # Check if files are identical
        if self._files_identical(source_info, target_info):
            return None
        
        # Determine conflict type
        source_mtime = datetime.fromtimestamp(source_info['mtime'], timezone.utc)
        target_mtime = datetime.fromtimestamp(target_info['mtime'], timezone.utc)
        
        # Both files have been modified (most common conflict)
        if abs((source_mtime - target_mtime).total_seconds()) > 60:  # More than 1 minute difference
            conflict_type = ConflictType.MODIFICATION_CONFLICT
        else:
            # Files modified around same time but different content
            conflict_type = ConflictType.MODIFICATION_CONFLICT
        
        # Check for size limit conflicts
        max_size = 100 * 1024 * 1024  # 100MB limit
        if source_info['size'] > max_size or target_info['size'] > max_size:
            conflict_type = ConflictType.SIZE_LIMIT_CONFLICT
        
        return ConflictDetails(
            conflict_id="",  # Will be set by caller
            conflict_type=conflict_type,
            tenant_id=tenant_id,
            folder_name=folder_name,
            source_path=relative_path,
            target_path=relative_path,
            source_mtime=source_mtime,
            target_mtime=target_mtime,
            source_size=source_info['size'],
            target_size=target_info['size'],
            source_hash=source_info.get('hash'),
            target_hash=target_info.get('hash')
        )
    
    async def _detect_delete_modify_conflicts(
        self,
        source_files: Dict[str, Dict[str, Any]], 
        target_files: Dict[str, Dict[str, Any]],
        tenant_id: str,
        folder_name: str,
        conflict_counter: int
    ) -> List[ConflictDetails]:
        """Detect delete-modify conflicts."""
        conflicts = []
        
        # Files deleted from source but modified in target
        for relative_path in target_files.keys():
            if relative_path not in source_files:
                conflict_counter += 1
                target_info = target_files[relative_path]
                
                conflicts.append(ConflictDetails(
                    conflict_id=f"conflict_{tenant_id}_{conflict_counter:06d}",
                    conflict_type=ConflictType.DELETE_MODIFY_CONFLICT,
                    tenant_id=tenant_id,
                    folder_name=folder_name,
                    source_path=relative_path,
                    target_path=relative_path,
                    target_mtime=datetime.fromtimestamp(target_info['mtime'], timezone.utc),
                    target_size=target_info['size'],
                    target_hash=target_info.get('hash'),
                    metadata={'deleted_from': 'source', 'modified_in': 'target'}
                ))
        
        # Files deleted from target but modified in source
        for relative_path in source_files.keys():
            if relative_path not in target_files:
                conflict_counter += 1
                source_info = source_files[relative_path]
                
                conflicts.append(ConflictDetails(
                    conflict_id=f"conflict_{tenant_id}_{conflict_counter:06d}",
                    conflict_type=ConflictType.DELETE_MODIFY_CONFLICT,
                    tenant_id=tenant_id,
                    folder_name=folder_name,
                    source_path=relative_path,
                    target_path=relative_path,
                    source_mtime=datetime.fromtimestamp(source_info['mtime'], timezone.utc),
                    source_size=source_info['size'],
                    source_hash=source_info.get('hash'),
                    metadata={'deleted_from': 'target', 'modified_in': 'source'}
                ))
        
        return conflicts
    
    def _files_identical(self, source_info: Dict[str, Any], target_info: Dict[str, Any]) -> bool:
        """Check if two files are identical."""
        # Compare by hash if available
        if source_info.get('hash') and target_info.get('hash'):
            return source_info['hash'] == target_info['hash']
        
        # Fall back to size and mtime
        return (source_info['size'] == target_info['size'] and 
                abs(source_info['mtime'] - target_info['mtime']) <= 1.0)

class ConflictResolver:
    """Resolves sync conflicts using various strategies."""
    
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.backup_path = self.base_path / "conflict_backups"
        self.backup_path.mkdir(parents=True, exist_ok=True)
    
    async def resolve_conflict(
        self, 
        conflict: ConflictDetails, 
        strategy: ConflictResolutionStrategy,
        source_base_path: str,
        target_base_path: str
    ) -> bool:
        """Resolve a specific conflict using the given strategy."""
        
        conflict.resolution_strategy = strategy
        
        try:
            source_full_path = Path(source_base_path) / conflict.source_path
            target_full_path = Path(target_base_path) / conflict.target_path
            
            if strategy == ConflictResolutionStrategy.SOURCE_WINS:
                success = await self._resolve_source_wins(
                    conflict, source_full_path, target_full_path
                )
                
            elif strategy == ConflictResolutionStrategy.TARGET_WINS:
                success = await self._resolve_target_wins(
                    conflict, source_full_path, target_full_path
                )
                
            elif strategy == ConflictResolutionStrategy.NEWER_WINS:
                success = await self._resolve_newer_wins(
                    conflict, source_full_path, target_full_path
                )
                
            elif strategy == ConflictResolutionStrategy.LARGER_WINS:
                success = await self._resolve_larger_wins(
                    conflict, source_full_path, target_full_path
                )
                
            elif strategy == ConflictResolutionStrategy.RENAME_BOTH:
                success = await self._resolve_rename_both(
                    conflict, source_full_path, target_full_path
                )
                
            elif strategy == ConflictResolutionStrategy.MERGE_ATTEMPT:
                success = await self._resolve_merge_attempt(
                    conflict, source_full_path, target_full_path
                )
                
            elif strategy == ConflictResolutionStrategy.MANUAL:
                success = await self._resolve_manual(conflict)
                
            else:
                conflict.error_message = f"Unknown resolution strategy: {strategy}"
                success = False
            
            if success:
                conflict.status = ConflictStatus.RESOLVED
                conflict.resolved_at = datetime.now(timezone.utc)
            else:
                conflict.status = ConflictStatus.FAILED
            
            return success
            
        except Exception as e:
            conflict.status = ConflictStatus.FAILED
            conflict.error_message = str(e)
            logger.error(f"Failed to resolve conflict {conflict.conflict_id}: {e}")
            return False
    
    async def _resolve_source_wins(
        self, 
        conflict: ConflictDetails, 
        source_path: Path, 
        target_path: Path
    ) -> bool:
        """Resolve conflict by making source win."""
        if not source_path.exists():
            # Source deleted, delete target too
            if target_path.exists():
                await self._backup_file(target_path, conflict.conflict_id)
                target_path.unlink()
            conflict.resolution_result = "Source deleted, target deleted"
        else:
            # Copy source to target
            if target_path.exists():
                await self._backup_file(target_path, conflict.conflict_id)
            
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)
            conflict.resolution_result = "Source copied to target"
        
        return True
    
    async def _resolve_target_wins(
        self, 
        conflict: ConflictDetails, 
        source_path: Path, 
        target_path: Path
    ) -> bool:
        """Resolve conflict by making target win."""
        if not target_path.exists():
            # Target deleted, delete source too
            if source_path.exists():
                await self._backup_file(source_path, conflict.conflict_id)
                source_path.unlink()
            conflict.resolution_result = "Target deleted, source deleted"
        else:
            # Target wins, no action needed (or copy target to source if needed)
            conflict.resolution_result = "Target kept as-is"
        
        return True
    
    async def _resolve_newer_wins(
        self, 
        conflict: ConflictDetails, 
        source_path: Path, 
        target_path: Path
    ) -> bool:
        """Resolve conflict by keeping the newer file."""
        
        # Compare modification times
        source_newer = False
        if conflict.source_mtime and conflict.target_mtime:
            source_newer = conflict.source_mtime > conflict.target_mtime
        elif source_path.exists() and target_path.exists():
            source_mtime = datetime.fromtimestamp(source_path.stat().st_mtime, timezone.utc)
            target_mtime = datetime.fromtimestamp(target_path.stat().st_mtime, timezone.utc)
            source_newer = source_mtime > target_mtime
        
        if source_newer:
            return await self._resolve_source_wins(conflict, source_path, target_path)
        else:
            return await self._resolve_target_wins(conflict, source_path, target_path)
    
    async def _resolve_larger_wins(
        self, 
        conflict: ConflictDetails, 
        source_path: Path, 
        target_path: Path
    ) -> bool:
        """Resolve conflict by keeping the larger file."""
        
        source_larger = False
        if conflict.source_size is not None and conflict.target_size is not None:
            source_larger = conflict.source_size > conflict.target_size
        elif source_path.exists() and target_path.exists():
            source_larger = source_path.stat().st_size > target_path.stat().st_size
        
        if source_larger:
            return await self._resolve_source_wins(conflict, source_path, target_path)
        else:
            return await self._resolve_target_wins(conflict, source_path, target_path)
    
    async def _resolve_rename_both(
        self, 
        conflict: ConflictDetails, 
        source_path: Path, 
        target_path: Path
    ) -> bool:
        """Resolve conflict by keeping both files with different names."""
        
        if not source_path.exists() or not target_path.exists():
            # Can't rename both if one doesn't exist
            return False
        
        # Create backup of target
        await self._backup_file(target_path, conflict.conflict_id)
        
        # Create unique names
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        source_name = f"{source_path.stem}_source_{timestamp}{source_path.suffix}"
        target_name = f"{target_path.stem}_target_{timestamp}{target_path.suffix}"
        
        # Rename files
        source_new_path = target_path.parent / source_name
        target_new_path = target_path.parent / target_name
        
        shutil.copy2(source_path, source_new_path)
        target_path.rename(target_new_path)
        
        conflict.resolution_result = f"Both files kept: {source_name}, {target_name}"
        return True
    
    async def _resolve_merge_attempt(
        self, 
        conflict: ConflictDetails, 
        source_path: Path, 
        target_path: Path
    ) -> bool:
        """Attempt to merge text files (basic implementation)."""
        
        # Only try to merge text files
        if source_path.suffix.lower() not in {'.txt', '.md'}:
            conflict.error_message = "Merge not supported for this file type"
            return False
        
        if not source_path.exists() or not target_path.exists():
            return False
        
        try:
            # Read both files
            with open(source_path, 'r', encoding='utf-8') as f:
                source_content = f.read()
            
            with open(target_path, 'r', encoding='utf-8') as f:
                target_content = f.read()
            
            # Simple merge: combine content with separator
            merged_content = f"""# Merged file - {datetime.now(timezone.utc).isoformat()}
# Source version:
{source_content}

# ===== MERGE SEPARATOR =====

# Target version:
{target_content}
"""
            
            # Backup original target
            await self._backup_file(target_path, conflict.conflict_id)
            
            # Write merged content
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(merged_content)
            
            conflict.resolution_result = "Files merged with separator"
            return True
            
        except Exception as e:
            conflict.error_message = f"Merge failed: {e}"
            return False
    
    async def _resolve_manual(self, conflict: ConflictDetails) -> bool:
        """Mark conflict for manual resolution."""
        conflict.status = ConflictStatus.REQUIRES_MANUAL
        conflict.resolution_result = "Marked for manual resolution"
        return False  # Not actually resolved
    
    async def _backup_file(self, file_path: Path, conflict_id: str) -> None:
        """Create a backup of a file before resolving conflict."""
        if not file_path.exists():
            return
        
        backup_name = f"{conflict_id}_{file_path.name}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        backup_file = self.backup_path / backup_name
        
        shutil.copy2(file_path, backup_file)
        logger.debug(f"Created backup: {backup_file}")

class ConflictLogger:
    """Logs and tracks conflict resolution activities."""
    
    def __init__(self, log_directory: str):
        self.log_directory = Path(log_directory)
        self.log_directory.mkdir(parents=True, exist_ok=True)
        self.conflicts: Dict[str, ConflictDetails] = {}
    
    def log_conflict(self, conflict: ConflictDetails) -> None:
        """Log a detected conflict."""
        self.conflicts[conflict.conflict_id] = conflict
        
        # Write to daily log file
        log_file = self.log_directory / f"conflicts_{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
        
        try:
            # Load existing data
            conflicts_data = []
            if log_file.exists():
                with open(log_file, 'r') as f:
                    conflicts_data = json.load(f)
            
            # Add new conflict
            conflicts_data.append(conflict.to_dict())
            
            # Write back
            with open(log_file, 'w') as f:
                json.dump(conflicts_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to log conflict {conflict.conflict_id}: {e}")
    
    def update_conflict(self, conflict: ConflictDetails) -> None:
        """Update an existing conflict log."""
        self.conflicts[conflict.conflict_id] = conflict
        
        # Update in daily log file
        log_file = self.log_directory / f"conflicts_{conflict.detected_at.strftime('%Y%m%d')}.json"
        
        try:
            if log_file.exists():
                with open(log_file, 'r') as f:
                    conflicts_data = json.load(f)
                
                # Find and update the conflict
                for i, data in enumerate(conflicts_data):
                    if data['conflict_id'] == conflict.conflict_id:
                        conflicts_data[i] = conflict.to_dict()
                        break
                
                # Write back
                with open(log_file, 'w') as f:
                    json.dump(conflicts_data, f, indent=2)
                    
        except Exception as e:
            logger.error(f"Failed to update conflict {conflict.conflict_id}: {e}")
    
    def get_conflicts_by_tenant(self, tenant_id: str) -> List[ConflictDetails]:
        """Get all conflicts for a specific tenant."""
        return [
            conflict for conflict in self.conflicts.values() 
            if conflict.tenant_id == tenant_id
        ]
    
    def get_pending_conflicts(self) -> List[ConflictDetails]:
        """Get all pending conflicts that need resolution."""
        return [
            conflict for conflict in self.conflicts.values() 
            if conflict.status in [ConflictStatus.PENDING, ConflictStatus.REQUIRES_MANUAL]
        ]
    
    def get_conflict_stats(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get conflict statistics."""
        conflicts = list(self.conflicts.values())
        if tenant_id:
            conflicts = [c for c in conflicts if c.tenant_id == tenant_id]
        
        stats = {
            'total_conflicts': len(conflicts),
            'pending': len([c for c in conflicts if c.status == ConflictStatus.PENDING]),
            'resolved': len([c for c in conflicts if c.status == ConflictStatus.RESOLVED]),
            'failed': len([c for c in conflicts if c.status == ConflictStatus.FAILED]),
            'requires_manual': len([c for c in conflicts if c.status == ConflictStatus.REQUIRES_MANUAL]),
            'by_type': {}
        }
        
        # Count by conflict type
        for conflict in conflicts:
            conflict_type = conflict.conflict_type.value
            stats['by_type'][conflict_type] = stats['by_type'].get(conflict_type, 0) + 1
        
        return stats

class ConflictManager:
    """Main manager for conflict detection and resolution."""
    
    def __init__(self, base_path: str = "./data/conflicts"):
        self.base_path = Path(base_path)
        self.detector = ConflictDetector()
        self.resolver = ConflictResolver(str(self.base_path))
        self.logger = ConflictLogger(str(self.base_path / "logs"))
        
        # Default resolution strategies by conflict type
        self.default_strategies = {
            ConflictType.MODIFICATION_CONFLICT: ConflictResolutionStrategy.NEWER_WINS,
            ConflictType.DELETE_MODIFY_CONFLICT: ConflictResolutionStrategy.MANUAL,
            ConflictType.MOVE_CONFLICT: ConflictResolutionStrategy.MANUAL,
            ConflictType.NAME_CONFLICT: ConflictResolutionStrategy.RENAME_BOTH,
            ConflictType.PERMISSION_CONFLICT: ConflictResolutionStrategy.SOURCE_WINS,
            ConflictType.SIZE_LIMIT_CONFLICT: ConflictResolutionStrategy.MANUAL
        }
    
    async def detect_and_resolve_conflicts(
        self,
        source_files: Dict[str, Dict[str, Any]], 
        target_files: Dict[str, Dict[str, Any]],
        tenant_id: str,
        folder_name: str,
        source_base_path: str,
        target_base_path: str,
        auto_resolve: bool = True
    ) -> List[ConflictDetails]:
        """Detect conflicts and optionally auto-resolve them."""
        
        # Detect conflicts
        conflicts = await self.detector.detect_conflicts(
            source_files, target_files, tenant_id, folder_name
        )
        
        # Log all conflicts
        for conflict in conflicts:
            self.logger.log_conflict(conflict)
        
        if not auto_resolve:
            return conflicts
        
        # Auto-resolve conflicts using default strategies
        for conflict in conflicts:
            if conflict.status == ConflictStatus.PENDING:
                strategy = self.default_strategies.get(
                    conflict.conflict_type, 
                    ConflictResolutionStrategy.MANUAL
                )
                
                if strategy != ConflictResolutionStrategy.MANUAL:
                    success = await self.resolver.resolve_conflict(
                        conflict, strategy, source_base_path, target_base_path
                    )
                    
                    # Update log
                    self.logger.update_conflict(conflict)
                    
                    if success:
                        logger.info(f"Auto-resolved conflict {conflict.conflict_id} using {strategy.value}")
                    else:
                        logger.warning(f"Failed to auto-resolve conflict {conflict.conflict_id}")
        
        return conflicts
    
    async def resolve_conflict_manually(
        self,
        conflict_id: str,
        strategy: ConflictResolutionStrategy,
        source_base_path: str,
        target_base_path: str
    ) -> bool:
        """Manually resolve a specific conflict."""
        
        conflict = self.logger.conflicts.get(conflict_id)
        if not conflict:
            logger.error(f"Conflict {conflict_id} not found")
            return False
        
        success = await self.resolver.resolve_conflict(
            conflict, strategy, source_base_path, target_base_path
        )
        
        # Update log
        self.logger.update_conflict(conflict)
        
        return success
    
    def get_tenant_conflicts(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get all conflicts for a tenant."""
        conflicts = self.logger.get_conflicts_by_tenant(tenant_id)
        return [conflict.to_dict() for conflict in conflicts]
    
    def get_pending_conflicts(self) -> List[Dict[str, Any]]:
        """Get all conflicts that need manual resolution."""
        conflicts = self.logger.get_pending_conflicts()
        return [conflict.to_dict() for conflict in conflicts]
    
    def get_conflict_stats(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get conflict statistics."""
        return self.logger.get_conflict_stats(tenant_id)

# Global conflict manager
conflict_manager = ConflictManager() 