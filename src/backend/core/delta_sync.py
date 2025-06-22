"""
Delta Synchronization Service for the Enterprise RAG Platform.

This service is responsible for comparing a source directory (e.g., an
'uploads' folder) with a target directory (the source-of-truth 'documents'
folder for a tenant) and applying the necessary changes.

The delta sync process involves three main operations:
1.  **Inclusion**: Adding new files that exist in the source but not the target.
2.  **Update**: Updating files in the target that have been modified in the source.
3.  **Deletion**: Removing files from the target that are no longer in the source.

This service orchestrates the file operations and triggers the necessary
processing pipelines (e.g., document ingestion, embedding removal).
"""

import logging
from pathlib import Path
from typing import Dict, List, Tuple, Set
import hashlib
import os
import shutil
from .document_ingestion import DocumentIngestionPipeline
from sqlalchemy.orm import Session
from .auditing import AuditLogger

logger = logging.getLogger(__name__)


class DeltaSyncService:
    """
    Manages the delta synchronization between a source and target directory.
    """

    def __init__(self, tenant_id: str, db: Session, ingestion_pipeline: DocumentIngestionPipeline, sync_run_id: str, audit_logger: AuditLogger):
        self.tenant_id = tenant_id
        self.db = db
        self.ingestion_pipeline = ingestion_pipeline
        self.sync_run_id = sync_run_id
        self.audit_logger = audit_logger
        # Placeholder for directory paths; these will be determined dynamically.
        self.source_dir = Path(f"/data/tenants/{tenant_id}/uploads")
        self.target_dir = Path(f"/data/tenants/{tenant_id}/documents")
        logger.info(f"Initialized DeltaSyncService for tenant '{self.tenant_id}'")

    def run_sync(self):
        """
        Executes the full delta synchronization process.
        """
        logger.info(f"Starting delta sync for tenant '{self.tenant_id}'...")
        
        # 1. Detect changes
        new_files, updated_files, deleted_files = self._detect_changes()
        
        # 2. Process changes
        self._process_inclusions(new_files)
        self._process_updates(updated_files)
        self._process_deletions(deleted_files)
        
        logger.info(f"Delta sync completed for tenant '{self.tenant_id}'.")

    def _detect_changes(self) -> Tuple[List[Path], List[Path], List[Path]]:
        """
        Compares the source and target directories to find differences.
        
        Returns:
            A tuple containing lists of new, updated, and deleted file paths relative to the source dir.
        """
        logger.info(f"Detecting changes between {self.source_dir} and {self.target_dir}")
        
        source_files = {p.relative_to(self.source_dir): self._get_file_hash(p) for p in self.source_dir.rglob('*') if p.is_file()}
        target_files = {p.relative_to(self.target_dir): self._get_file_hash(p) for p in self.target_dir.rglob('*') if p.is_file()}

        new_files = [self.source_dir / f for f in source_files if f not in target_files]
        deleted_files = [self.target_dir / f for f in target_files if f not in source_files]
        
        updated_files = []
        potential_updates = [f for f in source_files if f in target_files]

        for file_rel_path in potential_updates:
            source_hash = source_files[file_rel_path]
            target_hash = target_files[file_rel_path]
            if source_hash != target_hash:
                updated_files.append(self.source_dir / file_rel_path)

        logger.info(f"Found {len(new_files)} new, {len(updated_files)} updated, {len(deleted_files)} deleted files.")
        return new_files, updated_files, deleted_files
        
    def _get_file_hash(self, file_path: Path) -> str:
        """Calculates the SHA256 hash of a file."""
        sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except IOError:
            logger.warning(f"Could not read file for hashing: {file_path}", exc_info=True)
            return ""

    def _process_inclusions(self, files: List[Path]):
        """Processes new files to be added."""
        if not files:
            return
        logger.info(f"Processing {len(files)} new files...")
        for src_path in files:
            relative_path = src_path.relative_to(self.source_dir)
            target_path = self.target_dir / relative_path
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                shutil.copy2(src_path, target_path)
                logger.info(f"Copied new file from {src_path} to {target_path}")

                # Now, ingest the document from its new source-of-truth location
                _, __ = self.ingestion_pipeline.ingest_document(self.db, target_path)
                
                self.audit_logger.log_sync_event(
                    self.db, self.sync_run_id, self.tenant_id, "FILE_ADDED", "SUCCESS",
                    f"Successfully ingested new file: {relative_path}",
                    metadata={"filename": str(relative_path), "path": str(target_path)}
                )

            except Exception as e:
                logger.error(f"Failed to process new file {src_path}: {e}", exc_info=True)
                self.audit_logger.log_sync_event(
                    self.db, self.sync_run_id, self.tenant_id, "FILE_ADDED", "FAILURE",
                    f"Failed to ingest new file: {relative_path}",
                    metadata={"filename": str(relative_path), "error": str(e)}
                )
        
    def _process_updates(self, files: List[Path]):
        """Processes modified files to be updated."""
        if not files:
            return
        logger.info(f"Processing {len(files)} updated files...")
        for src_path in files:
            relative_path = src_path.relative_to(self.source_dir)
            target_path = self.target_dir / relative_path
            try:
                # Overwrite the existing file
                shutil.copy2(src_path, target_path)
                logger.info(f"Copied updated file from {src_path} to {target_path}")

                # The ingestion pipeline handles versioning internally.
                _, __ = self.ingestion_pipeline.ingest_document(self.db, target_path)
                
                self.audit_logger.log_sync_event(
                    self.db, self.sync_run_id, self.tenant_id, "FILE_UPDATED", "SUCCESS",
                    f"Successfully ingested updated file: {relative_path}",
                    metadata={"filename": str(relative_path), "path": str(target_path)}
                )

            except Exception as e:
                logger.error(f"Failed to process updated file {src_path}: {e}", exc_info=True)
                self.audit_logger.log_sync_event(
                    self.db, self.sync_run_id, self.tenant_id, "FILE_UPDATED", "FAILURE",
                    f"Failed to ingest updated file: {relative_path}",
                    metadata={"filename": str(relative_path), "error": str(e)}
                )
        
    def _process_deletions(self, files: List[Path]):
        """
        Processes files to be deleted from the target directory and all associated data.
        """
        if not files:
            return
        logger.info(f"Processing {len(files)} deleted files...")
        
        from ..models.document import Document # Local import to avoid circular dependency issues at module level

        for target_path in files:
            relative_path = target_path.relative_to(self.target_dir)
            try:
                filename = target_path.name
                
                doc_to_delete = self.db.query(Document).filter(
                    Document.tenant_id == self.tenant_id,
                    Document.filename == filename,
                    Document.is_current_version == True
                ).first()

                if not doc_to_delete:
                    logger.warning(f"Could not find DB record for deleted file: {filename}. It might have been deleted manually.")
                    # Still remove the file from the target directory if it exists
                    if target_path.exists():
                        target_path.unlink()
                        logger.info(f"Removed orphaned file from target: {target_path}")
                    continue

                # Use the pipeline to delete all associated data (DB records, vector embeddings)
                self.ingestion_pipeline.delete_document(self.db, doc_to_delete.id)
                
                # Finally, delete the file from the source-of-truth directory
                if target_path.exists():
                    target_path.unlink()
                    logger.info(f"Deleted file from target directory: {target_path}")
                
                self.audit_logger.log_sync_event(
                    self.db, self.sync_run_id, self.tenant_id, "FILE_DELETED", "SUCCESS",
                    f"Successfully deleted file: {relative_path}",
                    metadata={"filename": str(relative_path)}
                )

            except Exception as e:
                logger.error(f"Failed to process deleted file {target_path}: {e}", exc_info=True)
                self.audit_logger.log_sync_event(
                    self.db, self.sync_run_id, self.tenant_id, "FILE_DELETED", "FAILURE",
                    f"Failed to delete file: {relative_path}",
                    metadata={"filename": str(relative_path), "error": str(e)}
                ) 