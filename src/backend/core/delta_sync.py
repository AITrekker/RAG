"""
Delta Synchronization System for Enterprise RAG Platform

This module implements intelligent document synchronization that processes only
changed documents, reducing computational overhead and improving efficiency.
"""

import os
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum
import uuid

# from sqlalchemy.orm import Session
# from sqlalchemy import text

# from ..models.document import Document, DocumentStatus
# from ..models.audit import SyncEvent
# from ..db.session import get_db
from ..config.settings import get_settings
from .document_processor import DocumentProcessor
# from .tenant_manager import TenantManager # Obsolete
from .auditing import audit_logger
from ..utils.vector_store import get_vector_store_manager
from qdrant_client import models

logger = logging.getLogger(__name__)
settings = get_settings()


class ChangeType(Enum):
    """Types of document changes."""
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    MOVED = "moved"


@dataclass
class DocumentChange:
    """Represents a change to a document."""
    file_path: str
    change_type: ChangeType
    file_hash: Optional[str] = None
    file_size: Optional[int] = None
    old_path: Optional[str] = None  # For moved files
    modification_time: Optional[datetime] = None


@dataclass
class SyncResult:
    """Results from a synchronization run."""
    sync_run_id: str
    tenant_id: str
    total_files_scanned: int
    files_added: int
    files_modified: int
    files_deleted: int
    files_moved: int
    errors: List[str]
    start_time: datetime
    end_time: Optional[datetime] = None
    success: bool = False


class DeltaSync:
    """
    Delta synchronization manager that efficiently processes document changes.
    """
    
    def __init__(self, document_processor: DocumentProcessor):
        self.document_processor = document_processor
        self.vector_store_manager = get_vector_store_manager()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of a file."""
        hasher = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.hexdigest()
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            self.logger.error(f"Error calculating hash for {file_path}: {e}")
            return None
    
    def scan_directory(self, directory: Path, tenant_id: str) -> Dict[str, Dict]:
        """
        Scan directory and build current file state map.
        
        Returns:
            Dict mapping file paths to file metadata
        """
        current_files = {}
        
        if not directory.exists():
            self.logger.warning(f"Directory does not exist: {directory}")
            return current_files
        
        try:
            # Get supported file extensions
            supported_extensions = set(settings.supported_file_types)
            
            for file_path in directory.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                    try:
                        relative_path = str(file_path.relative_to(directory))
                        stat = file_path.stat()
                        
                        current_files[relative_path] = {
                            'full_path': str(file_path),
                            'size': stat.st_size,
                            'mtime': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                            'hash': None  # Will be calculated only if needed
                        }
                        
                    except Exception as e:
                        self.logger.error(f"Error processing file {file_path}: {e}")
                        
        except Exception as e:
            self.logger.error(f"Error scanning directory {directory}: {e}")
            
        return current_files
    
    def get_stored_file_state(self, tenant_id: str) -> Dict[str, Dict]:
        """
        Get the current state of files from the Qdrant vector store.
        
        Returns:
            Dict mapping file paths to stored metadata from point payloads.
        """
        stored_files = {}
        collection_name = self.vector_store_manager.get_collection_name_for_tenant(tenant_id)
        
        try:
            # Scroll through all points in the collection to fetch metadata
            # We only need the payload, not the vectors.
            all_points, _ = self.vector_store_manager.client.scroll(
                collection_name=collection_name,
                limit=10000, # Assuming a large limit to get all points, pagination would be needed for larger sets
                with_payload=True,
                with_vectors=False
            )
            
            for point in all_points:
                payload = point.payload
                # We need a unique identifier for each *file*, but many points belong to one file.
                # The 'file_path' in the payload is what we group by.
                file_path = payload.get("metadata", {}).get("file_path")
                if file_path and file_path not in stored_files:
                    stored_files[file_path] = {
                        'hash': payload.get("metadata", {}).get("file_hash"),
                        'updated_at': datetime.fromtimestamp(payload.get("metadata", {}).get("modified_at", 0), tz=timezone.utc)
                    }
                
        except Exception as e:
            # It's not an error if the collection doesn't exist yet
            if "not found" in str(e).lower():
                self.logger.info(f"Collection {collection_name} not found for tenant {tenant_id}. Assuming no stored files.")
            else:
                self.logger.error(f"Error retrieving stored file state for tenant {tenant_id}: {e}")
            
        return stored_files
    
    def detect_changes(
        self, 
        current_files: Dict[str, Dict], 
        stored_files: Dict[str, Dict]
    ) -> List[DocumentChange]:
        """
        Detect changes between current and stored file states.
        """
        changes = []
        current_paths = set(current_files.keys())
        stored_paths = set(stored_files.keys())
        
        # Find added files
        for path in current_paths - stored_paths:
            file_info = current_files[path]
            changes.append(DocumentChange(
                file_path=path,
                change_type=ChangeType.ADDED,
                file_size=file_info['size'],
                modification_time=file_info['mtime']
            ))
        
        # Find deleted files
        for path in stored_paths - current_paths:
            changes.append(DocumentChange(
                file_path=path,
                change_type=ChangeType.DELETED
            ))
        
        # Find potentially modified files
        for path in current_paths & stored_paths:
            current_info = current_files[path]
            stored_info = stored_files[path]
            
            # Check if file size or modification time changed
            if (current_info['size'] != stored_info['size'] or
                current_info['mtime'] > stored_info['updated_at']):
                
                # Calculate hash to confirm actual content change
                current_hash = self.calculate_file_hash(Path(current_info['full_path']))
                if current_hash and current_hash != stored_info['hash']:
                    changes.append(DocumentChange(
                        file_path=path,
                        change_type=ChangeType.MODIFIED,
                        file_hash=current_hash,
                        file_size=current_info['size'],
                        modification_time=current_info['mtime']
                    ))
        
        return changes
    
    def _process_document_change(
        self, 
        change: DocumentChange, 
        tenant_id: str, 
        tenant_uploads_path: Path,
        sync_run_id: str
    ) -> bool:
        """Process a single document change against Qdrant."""
        try:
            full_path = tenant_uploads_path / change.file_path

            if change.change_type == ChangeType.ADDED or change.change_type == ChangeType.MODIFIED:
                self.logger.info(f"Processing {change.change_type.value} file: {full_path}")
                processed_doc = self.document_processor.process_file(full_path)
                
                # Prepare points for upsert
                points_to_upsert = []
                for chunk in processed_doc.chunks:
                    point = models.PointStruct(
                        id=chunk.id,
                        payload={
                            "text": chunk.text,
                            "metadata": chunk.metadata
                        },
                        vector=[] # Vector will be added by the manager
                    )
                    points_to_upsert.append(point)
                
                # Upsert points into vector store
                self.vector_store_manager.upsert_points(tenant_id, points_to_upsert)
                audit_logger.log_sync_event(tenant_id, sync_run_id, change.change_type.value.upper(), "SUCCESS", f"Processed file: {change.file_path}")
                return True

            elif change.change_type == ChangeType.DELETED:
                self.logger.info(f"Processing deleted file: {change.file_path}")
                # We need to find all point IDs associated with this file path to delete them.
                # This requires a way to filter points by file_path in the metadata.
                self.vector_store_manager.delete_documents_by_path(tenant_id, change.file_path)
                audit_logger.log_sync_event(tenant_id, sync_run_id, "DELETED", "SUCCESS", f"Deleted file: {change.file_path}")
                return True

            else:
                self.logger.warning(f"Unsupported change type: {change.change_type}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error processing change for {change.file_path}: {e}", exc_info=True)
            audit_logger.log_sync_event(tenant_id, sync_run_id, change.change_type.value.upper(), "FAILURE", f"Failed to process file {change.file_path}: {e}")
            return False
    
    def synchronize_tenant(self, tenant_id: str) -> SyncResult:
        """Synchronize documents for a single tenant using Qdrant."""
        sync_run_id = f"sync_{tenant_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        start_time = datetime.now(timezone.utc)
        
        result = SyncResult(
            sync_run_id=sync_run_id,
            tenant_id=tenant_id,
            total_files_scanned=0,
            files_added=0,
            files_modified=0,
            files_deleted=0,
            files_moved=0, # Move detection not implemented yet
            errors=[],
            start_time=start_time
        )
        
        audit_logger.log_sync_event(tenant_id, sync_run_id, "SYNC_START", "IN_PROGRESS")

        try:
            # This needs to be refactored to not get path from tenant manager
            tenant_uploads_path = Path(f"data/tenants/{tenant_id}/uploads")
            
            # 1. Scan filesystem for current state
            current_files = self.scan_directory(tenant_uploads_path, tenant_id)
            result.total_files_scanned = len(current_files)
            
            # 2. Get stored state from Qdrant
            stored_files = self.get_stored_file_state(tenant_id)
            
            # 3. Detect changes
            changes = self.detect_changes(current_files, stored_files)
            self.logger.info(f"Detected {len(changes)} changes for tenant {tenant_id}")

            # 4. Process changes
            for change in changes:
                success = self._process_document_change(change, tenant_id, tenant_uploads_path, sync_run_id)
                if success:
                    if change.change_type == ChangeType.ADDED:
                        result.files_added += 1
                    elif change.change_type == ChangeType.MODIFIED:
                        result.files_modified += 1
                    elif change.change_type == ChangeType.DELETED:
                        result.files_deleted += 1
                else:
                    result.errors.append(f"Failed to process {change.file_path}")
            
            result.success = not result.errors
            result.end_time = datetime.now(timezone.utc)
            audit_logger.log_sync_event(tenant_id, sync_run_id, "SYNC_COMPLETE", "SUCCESS" if result.success else "FAILURE", f"Sync finished for tenant {tenant_id}.")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Critical error during tenant synchronization {tenant_id}: {e}", exc_info=True)
            result.errors.append(str(e))
            result.success = False
            result.end_time = datetime.now(timezone.utc)
            audit_logger.log_sync_event(tenant_id, sync_run_id, "SYNC_FAILED", "FAILURE", message=str(e))
            return result
    
    # These methods are no longer needed as they were for the old DB-based history
    # def get_sync_history(self, tenant_id: str, limit: int = 50) -> List[Dict]:
    #     return []
    
    # def get_sync_status(self, tenant_id: str) -> Dict:
    #     return {} 