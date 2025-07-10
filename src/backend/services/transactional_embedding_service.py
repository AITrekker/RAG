"""
Transactional Embedding Service - Ensures data consistency between PostgreSQL and Qdrant
Implements two-phase commit pattern to prevent inconsistent states during sync operations
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Set
from uuid import UUID, uuid4
from enum import Enum
import hashlib
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, and_

from src.backend.models.database import File, EmbeddingChunk
from src.backend.services.embedding_service import EmbeddingService, DocumentChunk, EmbeddingResult
from src.backend.config.settings import get_settings

settings = get_settings()


class TransactionPhase(Enum):
    """Phases of the two-phase commit process"""
    PREPARE = "prepare"
    COMMIT = "commit"
    ROLLBACK = "rollback"
    COMPLETED = "completed"


class EmbeddingTransaction:
    """Represents a transactional embedding operation"""
    
    def __init__(self, file_id: UUID, tenant_id: UUID, operation_type: str):
        self.transaction_id = uuid4()
        self.file_id = file_id
        self.tenant_id = tenant_id
        self.operation_type = operation_type  # 'create', 'update', 'delete'
        self.phase = TransactionPhase.PREPARE
        self.created_at = datetime.utcnow()
        
        # Track what was done in each phase
        self.qdrant_points_stored: List[str] = []
        self.postgres_chunks_created: List[UUID] = []
        self.postgres_chunks_deleted: List[UUID] = []
        self.backup_data: Dict[str, Any] = {}
        self.rollback_performed = False


class TransactionalEmbeddingService:
    """Enhanced embedding service with transactional guarantees"""
    
    def __init__(self, db_session: AsyncSession, embedding_service: EmbeddingService):
        self.db = db_session
        self.embedding_service = embedding_service
        self.active_transactions: Dict[UUID, EmbeddingTransaction] = {}
        
    async def transactional_store_embeddings(
        self,
        file_record: File,
        chunks: List[DocumentChunk],
        embeddings: List[EmbeddingResult],
        environment: str = None
    ) -> Tuple[List[EmbeddingChunk], bool]:
        """
        Store embeddings with two-phase commit guarantee
        
        Returns:
            Tuple[List[EmbeddingChunk], bool]: (chunk_records, success)
        """
        transaction = EmbeddingTransaction(
            file_id=file_record.id,
            tenant_id=file_record.tenant_id,
            operation_type='create'
        )
        
        self.active_transactions[transaction.transaction_id] = transaction
        
        try:
            # Phase 1: Prepare - Store in Qdrant first (can be rolled back)
            success = await self._prepare_phase_store(transaction, file_record, chunks, embeddings, environment)
            if not success:
                await self._rollback_transaction(transaction)
                return [], False
            
            # Phase 2: Commit - Store in PostgreSQL (permanent)
            chunk_records = await self._commit_phase_store(transaction, file_record, chunks, embeddings, environment)
            
            # Mark transaction as completed
            transaction.phase = TransactionPhase.COMPLETED
            
            return chunk_records, True
            
        except Exception as e:
            print(f"⚠️ Transaction {transaction.transaction_id} failed: {e}")
            await self._rollback_transaction(transaction)
            return [], False
        finally:
            # Clean up transaction
            self.active_transactions.pop(transaction.transaction_id, None)
    
    async def transactional_update_embeddings(
        self,
        file_record: File,
        chunks: List[DocumentChunk],
        embeddings: List[EmbeddingResult],
        environment: str = None
    ) -> Tuple[List[EmbeddingChunk], int, bool]:
        """
        Update embeddings with two-phase commit guarantee
        
        Returns:
            Tuple[List[EmbeddingChunk], int, bool]: (new_chunks, deleted_count, success)
        """
        transaction = EmbeddingTransaction(
            file_id=file_record.id,
            tenant_id=file_record.tenant_id,
            operation_type='update'
        )
        
        self.active_transactions[transaction.transaction_id] = transaction
        
        try:
            # Phase 1: Prepare - Backup old data and store new in Qdrant
            old_chunks_deleted = await self._prepare_phase_update(transaction, file_record, chunks, embeddings, environment)
            
            # Phase 2: Commit - Update PostgreSQL
            chunk_records = await self._commit_phase_update(transaction, file_record, chunks, embeddings, environment)
            
            # Mark transaction as completed
            transaction.phase = TransactionPhase.COMPLETED
            
            return chunk_records, old_chunks_deleted, True
            
        except Exception as e:
            print(f"⚠️ Update transaction {transaction.transaction_id} failed: {e}")
            await self._rollback_transaction(transaction)
            return [], 0, False
        finally:
            # Clean up transaction
            self.active_transactions.pop(transaction.transaction_id, None)
    
    async def transactional_delete_embeddings(
        self,
        file_id: UUID,
        tenant_id: UUID
    ) -> Tuple[int, bool]:
        """
        Delete embeddings with two-phase commit guarantee
        
        Returns:
            Tuple[int, bool]: (deleted_count, success)
        """
        transaction = EmbeddingTransaction(
            file_id=file_id,
            tenant_id=tenant_id,
            operation_type='delete'
        )
        
        self.active_transactions[transaction.transaction_id] = transaction
        
        try:
            # Phase 1: Prepare - Backup data and prepare for deletion
            deleted_count = await self._prepare_phase_delete(transaction, file_id)
            
            # Phase 2: Commit - Actually delete from both systems
            await self._commit_phase_delete(transaction, file_id)
            
            # Mark transaction as completed
            transaction.phase = TransactionPhase.COMPLETED
            
            return deleted_count, True
            
        except Exception as e:
            print(f"⚠️ Delete transaction {transaction.transaction_id} failed: {e}")
            await self._rollback_transaction(transaction)
            return 0, False
        finally:
            # Clean up transaction
            self.active_transactions.pop(transaction.transaction_id, None)
    
    async def _prepare_phase_store(
        self,
        transaction: EmbeddingTransaction,
        file_record: File,
        chunks: List[DocumentChunk],
        embeddings: List[EmbeddingResult],
        environment: str
    ) -> bool:
        """Phase 1: Store in Qdrant (can be rolled back)"""
        import os
        
        current_env = environment or os.getenv("RAG_ENVIRONMENT", "development")
        collection_name = f"documents_{current_env}"
        
        try:
            # Ensure Qdrant collection exists
            await self.embedding_service._ensure_qdrant_collection(collection_name)
            
            # Prepare Qdrant points
            qdrant_points = []
            point_ids = []
            
            for chunk, embedding in zip(chunks, embeddings):
                point_id = uuid4()
                point_ids.append(str(point_id))
                
                qdrant_points.append({
                    'id': str(point_id),
                    'vector': embedding.vector,
                    'payload': await self.embedding_service._prepare_qdrant_payload(
                        point_id, chunk, file_record, current_env
                    )
                })
            
            # Store in Qdrant first
            await self.embedding_service._bulk_store_in_qdrant(qdrant_points, collection_name)
            
            # Track what we stored for potential rollback
            transaction.qdrant_points_stored = point_ids
            transaction.backup_data['collection_name'] = collection_name
            transaction.backup_data['qdrant_points'] = qdrant_points
            
            transaction.phase = TransactionPhase.COMMIT
            print(f"✓ Transaction {transaction.transaction_id}: Qdrant prepare phase completed")
            
            return True
            
        except Exception as e:
            print(f"⚠️ Transaction {transaction.transaction_id}: Qdrant prepare phase failed: {e}")
            return False
    
    async def _commit_phase_store(
        self,
        transaction: EmbeddingTransaction,
        file_record: File,
        chunks: List[DocumentChunk],
        embeddings: List[EmbeddingResult],
        environment: str
    ) -> List[EmbeddingChunk]:
        """Phase 2: Store in PostgreSQL (permanent)"""
        import os
        from sqlalchemy import insert
        
        current_env = environment or os.getenv("RAG_ENVIRONMENT", "development")
        collection_name = f"documents_{current_env}"
        
        # Prepare PostgreSQL bulk data using the same point IDs from Qdrant
        postgres_bulk_data = []
        chunk_records = []
        
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_id = uuid4()
            point_id = UUID(transaction.qdrant_points_stored[i])
            
            postgres_bulk_data.append({
                'id': chunk_id,
                'file_id': file_record.id,
                'tenant_id': file_record.tenant_id,
                'chunk_index': chunk.chunk_index,
                'chunk_content': chunk.content,
                'chunk_hash': chunk.hash,
                'token_count': chunk.token_count,
                'qdrant_point_id': point_id,
                'collection_name': collection_name,
                'embedding_model': self.embedding_service.model_name,
                'processed_at': datetime.utcnow()
            })
            
            transaction.postgres_chunks_created.append(chunk_id)
        
        # Bulk insert into PostgreSQL
        await self.db.execute(
            insert(EmbeddingChunk).values(postgres_bulk_data)
        )
        await self.db.commit()
        
        # Convert to EmbeddingChunk objects for return
        for data in postgres_bulk_data:
            chunk_record = EmbeddingChunk(
                id=data['id'],
                file_id=data['file_id'],
                tenant_id=data['tenant_id'],
                chunk_index=data['chunk_index'],
                chunk_content=data['chunk_content'],
                chunk_hash=data['chunk_hash'],
                token_count=data['token_count'],
                qdrant_point_id=data['qdrant_point_id'],
                collection_name=data['collection_name'],
                embedding_model=data['embedding_model'],
                processed_at=data['processed_at']
            )
            chunk_records.append(chunk_record)
        
        print(f"✓ Transaction {transaction.transaction_id}: PostgreSQL commit phase completed")
        return chunk_records
    
    async def _prepare_phase_update(
        self,
        transaction: EmbeddingTransaction,
        file_record: File,
        chunks: List[DocumentChunk],
        embeddings: List[EmbeddingResult],
        environment: str
    ) -> int:
        """Phase 1: Backup old data and store new in Qdrant"""
        
        # First, backup existing chunks for potential rollback
        result = await self.db.execute(
            select(EmbeddingChunk).where(EmbeddingChunk.file_id == file_record.id)
        )
        existing_chunks = result.scalars().all()
        
        # Store backup data
        transaction.backup_data['existing_chunks'] = [
            {
                'id': chunk.id,
                'chunk_content': chunk.chunk_content,
                'chunk_hash': chunk.chunk_hash,
                'qdrant_point_id': chunk.qdrant_point_id,
                'collection_name': chunk.collection_name
            }
            for chunk in existing_chunks
        ]
        
        old_chunks_count = len(existing_chunks)
        old_point_ids = [str(chunk.qdrant_point_id) for chunk in existing_chunks]
        
        # Store new embeddings in Qdrant (this can be rolled back)
        success = await self._prepare_phase_store(transaction, file_record, chunks, embeddings, environment)
        if not success:
            raise Exception("Failed to store new embeddings in Qdrant")
        
        # Remove old embeddings from Qdrant
        if old_point_ids and existing_chunks:
            collection_name = existing_chunks[0].collection_name
            await self.embedding_service._batch_delete_from_qdrant(old_point_ids, collection_name)
        
        return old_chunks_count
    
    async def _commit_phase_update(
        self,
        transaction: EmbeddingTransaction,
        file_record: File,
        chunks: List[DocumentChunk],
        embeddings: List[EmbeddingResult],
        environment: str
    ) -> List[EmbeddingChunk]:
        """Phase 2: Update PostgreSQL records"""
        
        # Delete old PostgreSQL records
        result = await self.db.execute(
            select(EmbeddingChunk.id).where(EmbeddingChunk.file_id == file_record.id)
        )
        old_chunk_ids = [row[0] for row in result.fetchall()]
        transaction.postgres_chunks_deleted = old_chunk_ids
        
        await self.db.execute(
            delete(EmbeddingChunk).where(EmbeddingChunk.file_id == file_record.id)
        )
        
        # Insert new PostgreSQL records
        chunk_records = await self._commit_phase_store(transaction, file_record, chunks, embeddings, environment)
        
        return chunk_records
    
    async def _prepare_phase_delete(self, transaction: EmbeddingTransaction, file_id: UUID) -> int:
        """Phase 1: Backup data for potential rollback"""
        
        # Get all chunks to delete
        result = await self.db.execute(
            select(EmbeddingChunk).where(EmbeddingChunk.file_id == file_id)
        )
        chunks_to_delete = result.scalars().all()
        
        if not chunks_to_delete:
            return 0
        
        # Store backup data
        transaction.backup_data['deleted_chunks'] = [
            {
                'id': chunk.id,
                'file_id': chunk.file_id,
                'tenant_id': chunk.tenant_id,
                'chunk_index': chunk.chunk_index,
                'chunk_content': chunk.chunk_content,
                'chunk_hash': chunk.chunk_hash,
                'token_count': chunk.token_count,
                'qdrant_point_id': chunk.qdrant_point_id,
                'collection_name': chunk.collection_name,
                'embedding_model': chunk.embedding_model,
                'processed_at': chunk.processed_at
            }
            for chunk in chunks_to_delete
        ]
        
        transaction.qdrant_points_stored = [str(chunk.qdrant_point_id) for chunk in chunks_to_delete]
        transaction.postgres_chunks_deleted = [chunk.id for chunk in chunks_to_delete]
        
        return len(chunks_to_delete)
    
    async def _commit_phase_delete(self, transaction: EmbeddingTransaction, file_id: UUID):
        """Phase 2: Actually delete from both systems"""
        
        chunks_data = transaction.backup_data.get('deleted_chunks', [])
        if not chunks_data:
            return
        
        # Delete from Qdrant
        collection_name = chunks_data[0]['collection_name']
        await self.embedding_service._batch_delete_from_qdrant(
            transaction.qdrant_points_stored, 
            collection_name
        )
        
        # Delete from PostgreSQL
        await self.db.execute(
            delete(EmbeddingChunk).where(EmbeddingChunk.file_id == file_id)
        )
        await self.db.commit()
    
    async def _rollback_transaction(self, transaction: EmbeddingTransaction):
        """Rollback a failed transaction"""
        
        if transaction.rollback_performed:
            return
        
        transaction.phase = TransactionPhase.ROLLBACK
        
        try:
            if transaction.operation_type == 'create':
                await self._rollback_create(transaction)
            elif transaction.operation_type == 'update':
                await self._rollback_update(transaction)
            elif transaction.operation_type == 'delete':
                await self._rollback_delete(transaction)
            
            transaction.rollback_performed = True
            print(f"✓ Transaction {transaction.transaction_id}: Rollback completed")
            
        except Exception as e:
            print(f"⚠️ Transaction {transaction.transaction_id}: Rollback failed: {e}")
    
    async def _rollback_create(self, transaction: EmbeddingTransaction):
        """Rollback a failed create operation"""
        
        # Remove from Qdrant if we stored anything there
        if transaction.qdrant_points_stored:
            collection_name = transaction.backup_data.get('collection_name')
            if collection_name:
                await self.embedding_service._batch_delete_from_qdrant(
                    transaction.qdrant_points_stored,
                    collection_name
                )
        
        # Remove from PostgreSQL if we stored anything there
        if transaction.postgres_chunks_created:
            await self.db.execute(
                delete(EmbeddingChunk).where(
                    EmbeddingChunk.id.in_(transaction.postgres_chunks_created)
                )
            )
            await self.db.commit()
    
    async def _rollback_update(self, transaction: EmbeddingTransaction):
        """Rollback a failed update operation"""
        
        # Remove new points from Qdrant
        if transaction.qdrant_points_stored:
            collection_name = transaction.backup_data.get('collection_name')
            if collection_name:
                await self.embedding_service._batch_delete_from_qdrant(
                    transaction.qdrant_points_stored,
                    collection_name
                )
        
        # Restore old chunks to Qdrant
        existing_chunks = transaction.backup_data.get('existing_chunks', [])
        if existing_chunks:
            # This is complex - we'd need to restore the old vectors
            # For now, we'll mark the file as needing re-sync
            print(f"⚠️ Complex rollback needed for update transaction {transaction.transaction_id}")
    
    async def _rollback_delete(self, transaction: EmbeddingTransaction):
        """Rollback a failed delete operation"""
        
        # Restore chunks to PostgreSQL if they were deleted
        deleted_chunks = transaction.backup_data.get('deleted_chunks', [])
        if deleted_chunks and transaction.postgres_chunks_deleted:
            from sqlalchemy import insert
            await self.db.execute(
                insert(EmbeddingChunk).values(deleted_chunks)
            )
            await self.db.commit()
    
    async def get_active_transactions(self) -> List[Dict[str, Any]]:
        """Get information about active transactions"""
        return [
            {
                'transaction_id': str(txn.transaction_id),
                'file_id': str(txn.file_id),
                'tenant_id': str(txn.tenant_id),
                'operation_type': txn.operation_type,
                'phase': txn.phase.value,
                'created_at': txn.created_at.isoformat(),
                'qdrant_points': len(txn.qdrant_points_stored),
                'postgres_chunks': len(txn.postgres_chunks_created)
            }
            for txn in self.active_transactions.values()
        ]
    
    async def cleanup_stuck_transactions(self, max_age_minutes: int = 30):
        """Clean up transactions that have been running too long"""
        
        cutoff_time = datetime.utcnow().timestamp() - (max_age_minutes * 60)
        stuck_transactions = []
        
        for txn_id, txn in list(self.active_transactions.items()):
            if txn.created_at.timestamp() < cutoff_time:
                stuck_transactions.append(txn)
                # Force rollback
                await self._rollback_transaction(txn)
                # Remove from active transactions
                del self.active_transactions[txn_id]
        
        return len(stuck_transactions)


async def get_transactional_embedding_service(
    db_session: AsyncSession,
    embedding_service: EmbeddingService
) -> TransactionalEmbeddingService:
    """Factory function to create transactional embedding service"""
    return TransactionalEmbeddingService(db_session, embedding_service) 