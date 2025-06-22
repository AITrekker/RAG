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

from sqlalchemy.orm import Session
from sqlalchemy import text

from ..models.document import Document, DocumentStatus
from ..models.audit import SyncEvent
from ..db.session import get_db
from ..config.settings import get_settings
from .document_processor import DocumentProcessor
from .tenant_manager import TenantManager

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
    
    def __init__(self, tenant_manager: TenantManager, document_processor: DocumentProcessor):
        self.tenant_manager = tenant_manager
        self.document_processor = document_processor
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
    
    def get_stored_file_state(self, tenant_id: str, db: Session) -> Dict[str, Dict]:
        """
        Get the current state of files from the database.
        
        Returns:
            Dict mapping file paths to stored metadata
        """
        stored_files = {}
        
        try:
            documents = db.query(Document).filter(
                Document.tenant_id == tenant_id,
                Document.status != DocumentStatus.ARCHIVED
            ).all()
            
            for doc in documents:
                stored_files[doc.file_path] = {
                    'id': doc.id,
                    'hash': doc.file_hash,
                    'size': doc.file_size,
                    'version': doc.version,
                    'status': doc.status,
                    'updated_at': doc.updated_at
                }
                
        except Exception as e:
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
    
    def process_document_change(
        self, 
        change: DocumentChange, 
        tenant_id: str, 
        tenant_path: Path,
        db: Session
    ) -> bool:
        """Process a single document change."""
        try:
            if change.change_type == ChangeType.ADDED:
                return self._process_added_document(change, tenant_id, tenant_path, db)
            elif change.change_type == ChangeType.MODIFIED:
                return self._process_modified_document(change, tenant_id, tenant_path, db)
            elif change.change_type == ChangeType.DELETED:
                return self._process_deleted_document(change, tenant_id, db)
            else:
                self.logger.warning(f"Unsupported change type: {change.change_type}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error processing change {change.file_path}: {e}")
            return False
    
    def _process_added_document(
        self, 
        change: DocumentChange, 
        tenant_id: str, 
        tenant_path: Path,
        db: Session
    ) -> bool:
        """Process a newly added document."""
        full_path = tenant_path / change.file_path
        
        if not change.file_hash:
            change.file_hash = self.calculate_file_hash(full_path)
        
        # Use document processor to ingest the new document
        success = self.document_processor.process_document(
            file_path=str(full_path),
            tenant_id=tenant_id,
            db=db
        )
        
        if success:
            self.logger.info(f"Successfully added document: {change.file_path}")
        else:
            self.logger.error(f"Failed to add document: {change.file_path}")
            
        return success
    
    def _process_modified_document(
        self, 
        change: DocumentChange, 
        tenant_id: str, 
        tenant_path: Path,
        db: Session
    ) -> bool:
        """Process a modified document."""
        full_path = tenant_path / change.file_path
        
        # Archive the old version
        try:
            old_doc = db.query(Document).filter(
                Document.tenant_id == tenant_id,
                Document.file_path == change.file_path,
                Document.status != DocumentStatus.ARCHIVED
            ).first()
            
            if old_doc:
                # Update old document to archived status
                old_doc.status = DocumentStatus.ARCHIVED
                old_doc.updated_at = datetime.now(timezone.utc)
                
                # Process the updated document as a new version
                success = self.document_processor.process_document(
                    file_path=str(full_path),
                    tenant_id=tenant_id,
                    db=db,
                    version=old_doc.version + 1
                )
                
                if success:
                    self.logger.info(f"Successfully updated document: {change.file_path}")
                    db.commit()
                    return True
                else:
                    self.logger.error(f"Failed to update document: {change.file_path}")
                    db.rollback()
                    return False
            else:
                # Document not found in database, treat as new
                return self._process_added_document(change, tenant_id, tenant_path, db)
                
        except Exception as e:
            self.logger.error(f"Error updating document {change.file_path}: {e}")
            db.rollback()
            return False
    
    def _process_deleted_document(self, change: DocumentChange, tenant_id: str, db: Session) -> bool:
        """Process a deleted document."""
        try:
            # Mark document as archived instead of deleting
            docs = db.query(Document).filter(
                Document.tenant_id == tenant_id,
                Document.file_path == change.file_path,
                Document.status != DocumentStatus.ARCHIVED
            ).all()
            
            for doc in docs:
                doc.status = DocumentStatus.ARCHIVED
                doc.updated_at = datetime.now(timezone.utc)
            
            # TODO: Also clean up associated chunks and embeddings
            
            db.commit()
            self.logger.info(f"Successfully archived deleted document: {change.file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error archiving document {change.file_path}: {e}")
            db.rollback()
            return False
    
    def log_sync_event(
        self, 
        sync_run_id: str, 
        tenant_id: str, 
        event_type: str, 
        status: str, 
        message: str = None,
        metadata: Dict = None,
        db: Session = None
    ):
        """Log a synchronization event."""
        if not db:
            db = next(get_db())
        
        try:
            event = SyncEvent(
                sync_run_id=sync_run_id,
                tenant_id=tenant_id,
                event_type=event_type,
                status=status,
                message=message,
                event_metadata=metadata or {}
            )
            
            db.add(event)
            db.commit()
            
        except Exception as e:
            self.logger.error(f"Error logging sync event: {e}")
            db.rollback()
    
    def synchronize_tenant(self, tenant_id: str) -> SyncResult:
        """
        Perform delta synchronization for a specific tenant.
        """
        sync_run_id = f"sync_{tenant_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_time = datetime.now(timezone.utc)
        
        result = SyncResult(
            sync_run_id=sync_run_id,
            tenant_id=tenant_id,
            total_files_scanned=0,
            files_added=0,
            files_modified=0,
            files_deleted=0,
            files_moved=0,
            errors=[],
            start_time=start_time
        )
        
        db = next(get_db())
        
        try:
            # Log sync start
            self.log_sync_event(
                sync_run_id, tenant_id, "SYNC_START", "IN_PROGRESS",
                f"Starting delta sync for tenant {tenant_id}", db=db
            )
            
            # Get tenant documents directory
            tenant_config = self.tenant_manager.get_tenant_config(tenant_id)
            if not tenant_config:
                raise Exception(f"Tenant {tenant_id} not found")
            
            tenant_path = Path(tenant_config.documents_path)
            
            # Scan current files
            current_files = self.scan_directory(tenant_path, tenant_id)
            result.total_files_scanned = len(current_files)
            
            # Get stored file state
            stored_files = self.get_stored_file_state(tenant_id, db)
            
            # Detect changes
            changes = self.detect_changes(current_files, stored_files)
            
            self.logger.info(f"Detected {len(changes)} changes for tenant {tenant_id}")
            
            # Process each change
            for change in changes:
                success = self.process_document_change(change, tenant_id, tenant_path, db)
                
                if success:
                    if change.change_type == ChangeType.ADDED:
                        result.files_added += 1
                    elif change.change_type == ChangeType.MODIFIED:
                        result.files_modified += 1
                    elif change.change_type == ChangeType.DELETED:
                        result.files_deleted += 1
                    elif change.change_type == ChangeType.MOVED:
                        result.files_moved += 1
                else:
                    result.errors.append(f"Failed to process {change.file_path}: {change.change_type}")
            
            result.success = len(result.errors) == 0
            result.end_time = datetime.now(timezone.utc)
            
            # Log sync completion
            self.log_sync_event(
                sync_run_id, tenant_id, "SYNC_COMPLETE", 
                "SUCCESS" if result.success else "PARTIAL_SUCCESS",
                f"Sync completed. Added: {result.files_added}, Modified: {result.files_modified}, "
                f"Deleted: {result.files_deleted}, Errors: {len(result.errors)}",
                metadata={
                    'total_scanned': result.total_files_scanned,
                    'files_added': result.files_added,
                    'files_modified': result.files_modified,
                    'files_deleted': result.files_deleted,
                    'error_count': len(result.errors)
                },
                db=db
            )
            
        except Exception as e:
            result.errors.append(str(e))
            result.success = False
            result.end_time = datetime.now(timezone.utc)
            
            self.logger.error(f"Sync failed for tenant {tenant_id}: {e}")
            
            # Log sync failure
            self.log_sync_event(
                sync_run_id, tenant_id, "SYNC_FAILED", "FAILURE",
                f"Sync failed: {str(e)}", db=db
            )
            
        finally:
            db.close()
        
        return result
    
    def get_sync_history(self, tenant_id: str, limit: int = 50) -> List[Dict]:
        """Get synchronization history for a tenant."""
        db = next(get_db())
        
        try:
            events = db.query(SyncEvent).filter(
                SyncEvent.tenant_id == tenant_id,
                SyncEvent.event_type.in_(["SYNC_START", "SYNC_COMPLETE", "SYNC_FAILED"])
            ).order_by(SyncEvent.timestamp.desc()).limit(limit).all()
            
            return [
                {
                    'sync_run_id': event.sync_run_id,
                    'timestamp': event.timestamp.isoformat(),
                    'event_type': event.event_type,
                    'status': event.status,
                    'message': event.message,
                    'metadata': event.event_metadata
                }
                for event in events
            ]
            
        except Exception as e:
            self.logger.error(f"Error retrieving sync history for tenant {tenant_id}: {e}")
            return []
        finally:
            db.close() 