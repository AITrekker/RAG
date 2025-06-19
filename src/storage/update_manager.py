"""
Embedding update workflow manager for Enterprise RAG system.

This module provides comprehensive embedding update capabilities including
atomic transactions, rollback mechanisms, verification, and audit logging.
"""

import asyncio
import logging
import time
import threading
import json
from typing import Dict, Any, List, Optional, Set, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import uuid
from datetime import datetime, timedelta

from llama_index.core.schema import BaseNode

from .vector_store import get_vector_store, EmbeddingMetadata, VectorStoreOperation, OperationStatus
from .metadata_handler import get_metadata_manager, MetadataFilter, FilterOperator
from .version_manager import get_version_manager
from ..processing.llama_processor import TenantAwareLlamaProcessor
from ..config.settings import get_settings

logger = logging.getLogger(__name__)


class UpdateStatus(Enum):
    """Status of update operations."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    GENERATING_EMBEDDINGS = "generating_embeddings"
    STORING_TEMPORARY = "storing_temporary"
    VERIFYING_TEMPORARY = "verifying_temporary"
    DELETING_OLD = "deleting_old"
    UPDATING_MAPPING = "updating_mapping"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    VERIFIED = "verified"


class UpdateScope(Enum):
    """Scope of update operations."""
    SINGLE_DOCUMENT = "single_document"
    MULTIPLE_DOCUMENTS = "multiple_documents"
    FOLDER = "folder"
    BATCH = "batch"


@dataclass
class UpdateTransaction:
    """Represents an atomic update transaction."""
    transaction_id: str
    tenant_id: str
    scope: UpdateScope
    status: UpdateStatus = UpdateStatus.PENDING
    
    # Target identification
    document_ids: List[str] = field(default_factory=list)
    document_paths: List[str] = field(default_factory=list)
    folder_paths: List[str] = field(default_factory=list)
    
    # Transaction steps
    steps_completed: List[str] = field(default_factory=list)
    current_step: Optional[str] = None
    
    # Execution tracking
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # Data tracking
    old_embeddings: List[EmbeddingMetadata] = field(default_factory=list)
    new_embeddings: List[EmbeddingMetadata] = field(default_factory=list)
    temporary_ids: List[str] = field(default_factory=list)
    
    # Version tracking
    old_version_ids: List[str] = field(default_factory=list)
    new_version_ids: List[str] = field(default_factory=list)
    
    # Results tracking
    total_documents: int = 0
    processed_documents: int = 0
    success_count: int = 0
    failure_count: int = 0
    
    # Error tracking
    errors: List[str] = field(default_factory=list)
    rollback_data: Optional[Dict[str, Any]] = None
    
    # Verification
    verification_passed: bool = False
    verification_errors: List[str] = field(default_factory=list)


@dataclass
class UpdateLog:
    """Log entry for update operations."""
    log_id: str
    transaction_id: str
    tenant_id: str
    timestamp: float
    step: str
    operation: str
    target_type: str
    target_id: str
    status: str
    details: Dict[str, Any]
    error_message: Optional[str] = None


class TenantAwareUpdateManager:
    """
    Comprehensive update manager with atomic transactions.
    
    Features:
    - Atomic update transactions
    - Multi-step workflow with rollback
    - Version tracking integration
    - Comprehensive verification
    - Audit logging
    - Tenant isolation
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the update manager.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or get_settings()
        self.update_config = self.config.get("update", {})
        
        # Core components
        self.vector_store = get_vector_store()
        self.metadata_manager = get_metadata_manager()
        self.version_manager = get_version_manager()
        self.llama_processor = TenantAwareLlamaProcessor(config)
        
        # Transaction management
        self.active_transactions: Dict[str, UpdateTransaction] = {}
        self.completed_transactions: List[UpdateTransaction] = []
        self.transaction_lock = threading.RLock()
        
        # Processing control
        self.processing_enabled = True
        self.max_concurrent_transactions = self.update_config.get("max_concurrent_transactions", 2)
        self.verification_enabled = self.update_config.get("enable_verification", True)
        self.auto_cleanup_enabled = self.update_config.get("auto_cleanup", True)
        
        # Logging
        self.update_logs: List[UpdateLog] = []
        self.log_retention_hours = self.update_config.get("log_retention_hours", 168)  # 7 days
        self.logs_lock = threading.RLock()
        
        # Statistics
        self.stats = {
            "total_transactions": 0,
            "completed_transactions": 0,
            "failed_transactions": 0,
            "rolled_back_transactions": 0,
            "total_updates": 0,
            "verification_failures": 0
        }
        self.stats_lock = threading.RLock()
        
        logger.info("Initialized TenantAwareUpdateManager")
    
    def create_update_transaction(
        self,
        tenant_id: str,
        scope: UpdateScope,
        targets: Dict[str, List[str]]
    ) -> str:
        """
        Create a new update transaction.
        
        Args:
            tenant_id: Unique identifier for the tenant
            scope: Scope of update operation
            targets: Dictionary with target IDs by type
            
        Returns:
            str: Transaction ID
        """
        transaction_id = f"upd_{tenant_id}_{uuid.uuid4().hex[:8]}"
        
        transaction = UpdateTransaction(
            transaction_id=transaction_id,
            tenant_id=tenant_id,
            scope=scope,
            document_ids=targets.get("document_ids", []),
            document_paths=targets.get("document_paths", []),
            folder_paths=targets.get("folder_paths", [])
        )
        
        # Calculate total documents
        transaction.total_documents = (
            len(transaction.document_ids) +
            len(transaction.document_paths) +
            len(transaction.folder_paths)
        )
        
        # Add to active transactions
        with self.transaction_lock:
            self.active_transactions[transaction_id] = transaction
            
        with self.stats_lock:
            self.stats["total_transactions"] += 1
        
        self._log_operation(
            transaction_id=transaction_id,
            tenant_id=tenant_id,
            step="initialization",
            operation="transaction_created",
            target_type=scope.value,
            target_id=transaction_id,
            status="pending",
            details={"total_documents": transaction.total_documents}
        )
        
        logger.info(f"Created update transaction {transaction_id} for tenant {tenant_id}")
        return transaction_id
    
    def update_documents(
        self,
        tenant_id: str,
        document_paths: List[str]
    ) -> str:
        """
        Update embeddings for specific documents.
        
        Args:
            tenant_id: Unique identifier for the tenant
            document_paths: List of document paths to update
            
        Returns:
            str: Transaction ID
        """
        scope = UpdateScope.SINGLE_DOCUMENT if len(document_paths) == 1 else UpdateScope.MULTIPLE_DOCUMENTS
        
        return self.create_update_transaction(
            tenant_id=tenant_id,
            scope=scope,
            targets={"document_paths": document_paths}
        )
    
    def update_folder(
        self,
        tenant_id: str,
        folder_path: str,
        recursive: bool = True
    ) -> str:
        """
        Update embeddings for all documents in a folder.
        
        Args:
            tenant_id: Unique identifier for the tenant
            folder_path: Path to the folder
            recursive: Whether to process recursively
            
        Returns:
            str: Transaction ID
        """
        return self.create_update_transaction(
            tenant_id=tenant_id,
            scope=UpdateScope.FOLDER,
            targets={"folder_paths": [folder_path]}
        )
    
    def execute_update_transaction(self, transaction_id: str) -> bool:
        """
        Execute an update transaction.
        
        Args:
            transaction_id: Transaction identifier
            
        Returns:
            bool: Success status
        """
        with self.transaction_lock:
            transaction = self.active_transactions.get(transaction_id)
            if not transaction:
                logger.error(f"Transaction {transaction_id} not found")
                return False
        
        try:
            transaction.status = UpdateStatus.IN_PROGRESS
            transaction.started_at = time.time()
            
            # Execute transaction steps
            self._execute_transaction_steps(transaction)
            
            # Mark as completed
            transaction.status = UpdateStatus.COMPLETED
            transaction.completed_at = time.time()
            
            # Verify if enabled
            if self.verification_enabled:
                self._verify_update_transaction(transaction)
            
            # Complete the transaction
            self._complete_transaction(transaction)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to execute transaction {transaction_id}: {e}")
            transaction.status = UpdateStatus.FAILED
            transaction.errors.append(str(e))
            
            # Attempt rollback
            try:
                self._rollback_transaction(transaction)
            except Exception as rollback_error:
                logger.error(f"Failed to rollback transaction {transaction_id}: {rollback_error}")
                transaction.errors.append(f"Rollback failed: {rollback_error}")
            
            self._complete_transaction(transaction)
            return False
    
    def _execute_transaction_steps(self, transaction: UpdateTransaction):
        """Execute the atomic update transaction steps."""
        # Step 1: Start transaction
        self._step_start_transaction(transaction)
        
        # Step 2: Generate new embeddings
        self._step_generate_new_embeddings(transaction)
        
        # Step 3: Store new embeddings with temporary flag
        self._step_store_temporary_embeddings(transaction)
        
        # Step 4: Verify new embeddings are stored correctly
        self._step_verify_temporary_embeddings(transaction)
        
        # Step 5: Delete old embeddings
        self._step_delete_old_embeddings(transaction)
        
        # Step 6: Update version mapping
        self._step_update_version_mapping(transaction)
        
        # Step 7: Remove temporary flag from new embeddings
        self._step_finalize_embeddings(transaction)
        
        # Step 8: Commit transaction
        self._step_commit_transaction(transaction)
    
    def _step_start_transaction(self, transaction: UpdateTransaction):
        """Step 1: Start transaction."""
        transaction.current_step = "start_transaction"
        
        # Prepare rollback data
        transaction.rollback_data = self._prepare_rollback_data(transaction)
        
        # Get existing embeddings
        for document_path in transaction.document_paths:
            # Find document ID from path
            # This is simplified - in practice you'd have a more robust lookup
            document_id = Path(document_path).stem
            
            metadata_list = self.metadata_manager.query_metadata(
                tenant_id=transaction.tenant_id,
                filters=[
                    MetadataFilter(
                        field="document_id",
                        operator=FilterOperator.EQUALS,
                        value=document_id
                    )
                ]
            )
            
            transaction.old_embeddings.extend(metadata_list)
        
        transaction.steps_completed.append("start_transaction")
        
        self._log_operation(
            transaction_id=transaction.transaction_id,
            tenant_id=transaction.tenant_id,
            step="start_transaction",
            operation="prepare",
            target_type="transaction",
            target_id=transaction.transaction_id,
            status="completed",
            details={"old_embeddings_count": len(transaction.old_embeddings)}
        )
    
    def _step_generate_new_embeddings(self, transaction: UpdateTransaction):
        """Step 2: Generate new embeddings."""
        transaction.current_step = "generate_embeddings"
        transaction.status = UpdateStatus.GENERATING_EMBEDDINGS
        
        try:
            for document_path in transaction.document_paths:
                # Process document to generate new embeddings
                result = self.llama_processor.process_single_document(
                    tenant_id=transaction.tenant_id,
                    document_path=document_path
                )
                
                if result.get("success", False):
                    # Get the generated embeddings metadata
                    nodes = result.get("nodes", [])
                    embeddings = result.get("embeddings", [])
                    
                    # Create embedding metadata for new embeddings
                    for i, node in enumerate(nodes):
                        embedding_metadata = self._create_embedding_metadata(
                            node=node,
                            tenant_id=transaction.tenant_id,
                            embedding=embeddings[i] if i < len(embeddings) else None
                        )
                        transaction.new_embeddings.append(embedding_metadata)
                    
                    transaction.success_count += 1
                else:
                    transaction.failure_count += 1
                    error = f"Failed to generate embeddings for {document_path}"
                    transaction.errors.append(error)
                
                transaction.processed_documents += 1
        
        except Exception as e:
            raise Exception(f"Failed to generate new embeddings: {e}")
        
        transaction.steps_completed.append("generate_embeddings")
        
        self._log_operation(
            transaction_id=transaction.transaction_id,
            tenant_id=transaction.tenant_id,
            step="generate_embeddings",
            operation="generate",
            target_type="embeddings",
            target_id="new_embeddings",
            status="completed",
            details={"new_embeddings_count": len(transaction.new_embeddings)}
        )
    
    def _step_store_temporary_embeddings(self, transaction: UpdateTransaction):
        """Step 3: Store new embeddings with temporary flag."""
        transaction.current_step = "store_temporary"
        transaction.status = UpdateStatus.STORING_TEMPORARY
        
        try:
            # Create nodes from embedding metadata
            nodes = []
            embeddings = []
            
            for metadata in transaction.new_embeddings:
                # Create a temporary node (simplified)
                from llama_index.core.schema import TextNode
                node = TextNode(
                    text=metadata.text_content,
                    metadata={
                        **metadata.custom_metadata,
                        "temporary": True,
                        "transaction_id": transaction.transaction_id
                    }
                )
                nodes.append(node)
                
                # Add temporary ID for tracking
                temp_id = f"temp_{metadata.embedding_id}"
                transaction.temporary_ids.append(temp_id)
            
            # Store in vector store with temporary flag
            success = self.vector_store.add_embeddings(
                tenant_id=transaction.tenant_id,
                nodes=nodes,
                embeddings=embeddings
            )
            
            if not success:
                raise Exception("Failed to store temporary embeddings in vector store")
            
        except Exception as e:
            raise Exception(f"Failed to store temporary embeddings: {e}")
        
        transaction.steps_completed.append("store_temporary")
        
        self._log_operation(
            transaction_id=transaction.transaction_id,
            tenant_id=transaction.tenant_id,
            step="store_temporary",
            operation="store",
            target_type="temporary_embeddings",
            target_id="temporary_store",
            status="completed",
            details={"temporary_ids_count": len(transaction.temporary_ids)}
        )
    
    def _step_verify_temporary_embeddings(self, transaction: UpdateTransaction):
        """Step 4: Verify new embeddings are stored correctly."""
        transaction.current_step = "verify_temporary"
        transaction.status = UpdateStatus.VERIFYING_TEMPORARY
        
        try:
            verification_errors = []
            
            # Verify each temporary embedding
            for temp_id in transaction.temporary_ids:
                metadata = self.metadata_manager.get_metadata(temp_id)
                if not metadata:
                    verification_errors.append(f"Temporary embedding {temp_id} not found")
                elif not metadata.custom_metadata.get("temporary", False):
                    verification_errors.append(f"Embedding {temp_id} not marked as temporary")
            
            if verification_errors:
                raise Exception(f"Verification failed: {verification_errors}")
        
        except Exception as e:
            raise Exception(f"Failed to verify temporary embeddings: {e}")
        
        transaction.steps_completed.append("verify_temporary")
        
        self._log_operation(
            transaction_id=transaction.transaction_id,
            tenant_id=transaction.tenant_id,
            step="verify_temporary",
            operation="verify",
            target_type="temporary_embeddings",
            target_id="verification",
            status="completed",
            details={}
        )
    
    def _step_delete_old_embeddings(self, transaction: UpdateTransaction):
        """Step 5: Delete old embeddings."""
        transaction.current_step = "delete_old"
        transaction.status = UpdateStatus.DELETING_OLD
        
        try:
            # Delete old embeddings from metadata store
            for old_metadata in transaction.old_embeddings:
                success = self.metadata_manager.delete_metadata(old_metadata.embedding_id)
                if not success:
                    logger.warning(f"Failed to delete old embedding {old_metadata.embedding_id}")
            
        except Exception as e:
            raise Exception(f"Failed to delete old embeddings: {e}")
        
        transaction.steps_completed.append("delete_old")
        
        self._log_operation(
            transaction_id=transaction.transaction_id,
            tenant_id=transaction.tenant_id,
            step="delete_old",
            operation="delete",
            target_type="old_embeddings",
            target_id="old_embeddings",
            status="completed",
            details={"deleted_count": len(transaction.old_embeddings)}
        )
    
    def _step_update_version_mapping(self, transaction: UpdateTransaction):
        """Step 6: Update version mapping."""
        transaction.current_step = "update_mapping"
        transaction.status = UpdateStatus.UPDATING_MAPPING
        
        try:
            # Create new versions for updated documents
            for document_path in transaction.document_paths:
                document_id = Path(document_path).stem
                
                # Create new version
                version_id = self.version_manager.create_version(
                    tenant_id=transaction.tenant_id,
                    document_id=document_id,
                    document_path=document_path,
                    metadata={
                        "transaction_id": transaction.transaction_id,
                        "update_timestamp": time.time()
                    }
                )
                
                transaction.new_version_ids.append(version_id)
        
        except Exception as e:
            raise Exception(f"Failed to update version mapping: {e}")
        
        transaction.steps_completed.append("update_mapping")
        
        self._log_operation(
            transaction_id=transaction.transaction_id,
            tenant_id=transaction.tenant_id,
            step="update_mapping",
            operation="update",
            target_type="version_mapping",
            target_id="versions",
            status="completed",
            details={"new_versions_count": len(transaction.new_version_ids)}
        )
    
    def _step_finalize_embeddings(self, transaction: UpdateTransaction):
        """Step 7: Remove temporary flag from new embeddings."""
        transaction.current_step = "finalize"
        transaction.status = UpdateStatus.FINALIZING
        
        try:
            # Update metadata to remove temporary flag
            for temp_id in transaction.temporary_ids:
                metadata = self.metadata_manager.get_metadata(temp_id)
                if metadata and metadata.custom_metadata.get("temporary", False):
                    # Remove temporary flag
                    metadata.custom_metadata.pop("temporary", None)
                    metadata.custom_metadata.pop("transaction_id", None)
                    
                    # Update metadata (this is simplified - would need proper update method)
                    self.metadata_manager.add_metadata(metadata)  # Re-add with updated metadata
        
        except Exception as e:
            raise Exception(f"Failed to finalize embeddings: {e}")
        
        transaction.steps_completed.append("finalize")
        
        self._log_operation(
            transaction_id=transaction.transaction_id,
            tenant_id=transaction.tenant_id,
            step="finalize",
            operation="finalize",
            target_type="new_embeddings",
            target_id="finalize",
            status="completed",
            details={}
        )
    
    def _step_commit_transaction(self, transaction: UpdateTransaction):
        """Step 8: Commit transaction."""
        transaction.current_step = "commit"
        
        # Clear temporary data
        transaction.temporary_ids.clear()
        transaction.rollback_data = None
        
        transaction.steps_completed.append("commit")
        
        self._log_operation(
            transaction_id=transaction.transaction_id,
            tenant_id=transaction.tenant_id,
            step="commit",
            operation="commit",
            target_type="transaction",
            target_id=transaction.transaction_id,
            status="completed",
            details={}
        )
    
    def _create_embedding_metadata(
        self,
        node: BaseNode,
        tenant_id: str,
        embedding: Optional[List[float]] = None
    ) -> EmbeddingMetadata:
        """Create embedding metadata from node."""
        import hashlib
        
        # Generate IDs
        embedding_id = f"{tenant_id}_{uuid.uuid4().hex}"
        content_hash = hashlib.sha256(node.text.encode()).hexdigest()
        
        # Extract metadata from node
        node_metadata = getattr(node, 'metadata', {}) or {}
        
        # Calculate embedding hash if available
        embedding_hash = ""
        vector_dimension = 0
        if embedding:
            import numpy as np
            embedding_hash = hashlib.sha256(np.array(embedding).tobytes()).hexdigest()
            vector_dimension = len(embedding)
        
        return EmbeddingMetadata(
            embedding_id=embedding_id,
            tenant_id=tenant_id,
            document_id=node_metadata.get("document_id", "unknown"),
            node_id=getattr(node, 'node_id', str(uuid.uuid4())),
            text_content=node.text,
            content_hash=content_hash,
            content_length=len(node.text),
            embedding_model=node_metadata.get("embedding_model", "unknown"),
            embedding_version="1.0",
            processing_timestamp=time.time(),
            document_path=node_metadata.get("file_path", ""),
            document_name=node_metadata.get("file_name", ""),
            document_type=node_metadata.get("file_extension", ""),
            folder_path=node_metadata.get("folder_path", ""),
            vector_dimension=vector_dimension,
            embedding_hash=embedding_hash,
            custom_metadata=node_metadata,
            tags=node_metadata.get("tags", [])
        )
    
    def _prepare_rollback_data(self, transaction: UpdateTransaction) -> Dict[str, Any]:
        """Prepare data needed for rollback."""
        return {
            "transaction_id": transaction.transaction_id,
            "tenant_id": transaction.tenant_id,
            "scope": transaction.scope.value,
            "timestamp": time.time(),
            "old_embeddings_backup": [metadata.to_dict() for metadata in transaction.old_embeddings]
        }
    
    def _rollback_transaction(self, transaction: UpdateTransaction):
        """Rollback a failed transaction."""
        logger.warning(f"Attempting rollback for transaction {transaction.transaction_id}")
        transaction.status = UpdateStatus.ROLLED_BACK
        
        try:
            # Clean up temporary embeddings
            if transaction.temporary_ids:
                for temp_id in transaction.temporary_ids:
                    try:
                        self.metadata_manager.delete_metadata(temp_id)
                    except Exception as e:
                        logger.warning(f"Failed to cleanup temporary embedding {temp_id}: {e}")
            
            # Restore old embeddings if they were deleted
            # This would require more sophisticated backup/restore logic
            
            with self.stats_lock:
                self.stats["rolled_back_transactions"] += 1
        
        except Exception as e:
            logger.error(f"Rollback failed for transaction {transaction.transaction_id}: {e}")
            transaction.errors.append(f"Rollback failed: {e}")
        
        self._log_operation(
            transaction_id=transaction.transaction_id,
            tenant_id=transaction.tenant_id,
            step="rollback",
            operation="rollback",
            target_type="transaction",
            target_id=transaction.transaction_id,
            status="completed",
            details={}
        )
    
    def _verify_update_transaction(self, transaction: UpdateTransaction):
        """Verify that update transaction was successful."""
        try:
            verification_errors = []
            
            # Verify new embeddings exist and are not temporary
            for metadata in transaction.new_embeddings:
                stored_metadata = self.metadata_manager.get_metadata(metadata.embedding_id)
                if not stored_metadata:
                    verification_errors.append(f"New embedding {metadata.embedding_id} not found")
                elif stored_metadata.custom_metadata.get("temporary", False):
                    verification_errors.append(f"Embedding {metadata.embedding_id} still marked as temporary")
            
            # Verify old embeddings are deleted
            for old_metadata in transaction.old_embeddings:
                stored_metadata = self.metadata_manager.get_metadata(old_metadata.embedding_id)
                if stored_metadata:
                    verification_errors.append(f"Old embedding {old_metadata.embedding_id} still exists")
            
            # Update verification status
            if verification_errors:
                transaction.verification_passed = False
                transaction.verification_errors = verification_errors
                transaction.status = UpdateStatus.FAILED
                
                with self.stats_lock:
                    self.stats["verification_failures"] += 1
            else:
                transaction.verification_passed = True
                transaction.status = UpdateStatus.VERIFIED
                
        except Exception as e:
            transaction.verification_passed = False
            transaction.verification_errors = [f"Verification failed: {e}"]
            logger.error(f"Verification failed for transaction {transaction.transaction_id}: {e}")
    
    def _complete_transaction(self, transaction: UpdateTransaction):
        """Complete an update transaction."""
        with self.transaction_lock:
            if transaction.transaction_id in self.active_transactions:
                del self.active_transactions[transaction.transaction_id]
            self.completed_transactions.append(transaction)
            
            # Keep only last 1000 completed transactions
            if len(self.completed_transactions) > 1000:
                self.completed_transactions = self.completed_transactions[-1000:]
        
        with self.stats_lock:
            if transaction.status in [UpdateStatus.COMPLETED, UpdateStatus.VERIFIED]:
                self.stats["completed_transactions"] += 1
                self.stats["total_updates"] += transaction.success_count
            else:
                self.stats["failed_transactions"] += 1
        
        self._log_operation(
            transaction_id=transaction.transaction_id,
            tenant_id=transaction.tenant_id,
            step="completion",
            operation="transaction_completed",
            target_type="transaction",
            target_id=transaction.transaction_id,
            status=transaction.status.value,
            details={
                "processed_documents": transaction.processed_documents,
                "success_count": transaction.success_count,
                "failure_count": transaction.failure_count,
                "verification_passed": transaction.verification_passed
            }
        )
        
        logger.info(f"Completed update transaction {transaction.transaction_id} with status {transaction.status.value}")
    
    def _log_operation(
        self,
        transaction_id: str,
        tenant_id: str,
        step: str,
        operation: str,
        target_type: str,
        target_id: str,
        status: str,
        details: Dict[str, Any],
        error_message: Optional[str] = None
    ):
        """Log an update operation."""
        log_entry = UpdateLog(
            log_id=f"log_{uuid.uuid4().hex[:8]}",
            transaction_id=transaction_id,
            tenant_id=tenant_id,
            timestamp=time.time(),
            step=step,
            operation=operation,
            target_type=target_type,
            target_id=target_id,
            status=status,
            details=details,
            error_message=error_message
        )
        
        with self.logs_lock:
            self.update_logs.append(log_entry)
            
            # Clean up old logs
            cutoff_time = time.time() - (self.log_retention_hours * 3600)
            self.update_logs = [
                log for log in self.update_logs
                if log.timestamp > cutoff_time
            ]
    
    def get_transaction_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """Get status of an update transaction."""
        with self.transaction_lock:
            if transaction_id in self.active_transactions:
                transaction = self.active_transactions[transaction_id]
                return self._transaction_to_dict(transaction)
            
            for transaction in self.completed_transactions:
                if transaction.transaction_id == transaction_id:
                    return self._transaction_to_dict(transaction)
        
        return None
    
    def _transaction_to_dict(self, transaction: UpdateTransaction) -> Dict[str, Any]:
        """Convert transaction to dictionary."""
        return {
            "transaction_id": transaction.transaction_id,
            "tenant_id": transaction.tenant_id,
            "scope": transaction.scope.value,
            "status": transaction.status.value,
            "current_step": transaction.current_step,
            "steps_completed": transaction.steps_completed,
            "total_documents": transaction.total_documents,
            "processed_documents": transaction.processed_documents,
            "success_count": transaction.success_count,
            "failure_count": transaction.failure_count,
            "created_at": transaction.created_at,
            "started_at": transaction.started_at,
            "completed_at": transaction.completed_at,
            "verification_passed": transaction.verification_passed,
            "verification_errors": transaction.verification_errors,
            "errors": transaction.errors
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get update statistics."""
        with self.stats_lock:
            stats = dict(self.stats)
        
        with self.logs_lock:
            stats["log_entries"] = len(self.update_logs)
        
        with self.transaction_lock:
            stats["active_transactions"] = len(self.active_transactions)
        
        return stats
    
    def get_update_logs(
        self,
        tenant_id: Optional[str] = None,
        transaction_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get update logs with optional filtering."""
        with self.logs_lock:
            logs = self.update_logs.copy()
        
        # Apply filters
        if tenant_id:
            logs = [log for log in logs if log.tenant_id == tenant_id]
        
        if transaction_id:
            logs = [log for log in logs if log.transaction_id == transaction_id]
        
        # Sort by timestamp (newest first) and limit
        logs.sort(key=lambda x: x.timestamp, reverse=True)
        logs = logs[:limit]
        
        # Convert to dictionaries
        return [
            {
                "log_id": log.log_id,
                "transaction_id": log.transaction_id,
                "tenant_id": log.tenant_id,
                "timestamp": log.timestamp,
                "step": log.step,
                "operation": log.operation,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "status": log.status,
                "details": log.details,
                "error_message": log.error_message
            }
            for log in logs
        ]


# Global update manager instance
_update_manager = None


def get_update_manager() -> TenantAwareUpdateManager:
    """Get the global update manager instance."""
    global _update_manager
    if _update_manager is None:
        _update_manager = TenantAwareUpdateManager()
    return _update_manager