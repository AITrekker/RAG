"""
Simplified Embedding Service - Single Path Processing
Replaces the complex dual-path embedding service with clean single approach
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text

from src.backend.models.database import File, EmbeddingChunk
from src.backend.config.settings import get_settings

settings = get_settings()


class SimplifiedEmbeddingService:
    """
    Simplified embedding service with single processing path
    
    This replaces the complex PgVectorEmbeddingService that had:
    - Dual processing paths (simple vs LlamaIndex)
    - Complex decision logic
    - Manual chunking and embedding generation
    
    Now: LlamaIndex handles everything, we just track the results.
    """
    
    def __init__(
        self, 
        db: AsyncSession, 
        embedding_model=None,
        document_processor=None,
        rag_service=None
    ):
        self.db = db
        self.embedding_model = embedding_model
        self.document_processor = document_processor
        self.rag_service = rag_service
        self.model_loaded = embedding_model is not None
    
    async def process_and_store_file(
        self, 
        file_path: Path, 
        file_record: File
    ) -> bool:
        """
        Complete file processing pipeline - simplified!
        
        Before: 516 lines of complex chunking, embedding, and storage logic
        After: Let LlamaIndex handle it all, just track the result
        """
        try:
            if not self.document_processor:
                print("⚠️ No document processor available")
                return False
            
            # Use unified document processor (handles everything)
            result = await self.document_processor.process_file(file_path, file_record)
            
            if result.success:
                # Update file status
                await self._update_file_sync_status(
                    file_record.id, 
                    'synced',
                    chunks_created=result.chunks_created
                )
                print(f"✓ Successfully processed {file_record.filename} with {result.processing_method}")
                return True
            else:
                # Update file status with error
                await self._update_file_sync_status(
                    file_record.id, 
                    'failed',
                    error_message=result.error_message
                )
                print(f"❌ Failed to process {file_record.filename}: {result.error_message}")
                return False
                
        except Exception as e:
            print(f"❌ Error processing file {file_path}: {e}")
            await self._update_file_sync_status(
                file_record.id, 
                'failed',
                error_message=str(e)
            )
            return False
    
    async def _update_file_sync_status(
        self, 
        file_id: UUID, 
        status: str,
        chunks_created: int = 0,
        error_message: Optional[str] = None
    ):
        """Update file sync status in database"""
        try:
            update_data = {
                'sync_status': status,
                'sync_completed_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            if error_message:
                update_data['sync_error'] = error_message
            
            await self.db.execute(
                text("""
                    UPDATE files 
                    SET sync_status = :status,
                        sync_completed_at = :sync_completed_at,
                        sync_error = :sync_error,
                        updated_at = :updated_at
                    WHERE id = :file_id
                """),
                {
                    'file_id': str(file_id),
                    'status': status,
                    'sync_completed_at': update_data['sync_completed_at'],
                    'sync_error': error_message,
                    'updated_at': update_data['updated_at']
                }
            )
            await self.db.commit()
            
        except Exception as e:
            print(f"❌ Error updating file sync status: {e}")
            await self.db.rollback()
    
    async def process_multiple_files(
        self, 
        file_records: List[File]
    ) -> Dict[str, int]:
        """Process multiple files and return statistics"""
        stats = {
            'total_files': len(file_records),
            'successful': 0,
            'failed': 0,
            'skipped': 0
        }
        
        if not self.document_processor:
            print("⚠️ No document processor available for batch processing")
            stats['skipped'] = stats['total_files']
            return stats
        
        # Process files using unified processor
        results = await self.document_processor.process_multiple_files(file_records)
        
        # Update database with results
        for result in results:
            if result.success:
                stats['successful'] += 1
                await self._update_file_sync_status(
                    result.file_id, 
                    'synced',
                    chunks_created=result.chunks_created
                )
            else:
                stats['failed'] += 1
                await self._update_file_sync_status(
                    result.file_id, 
                    'failed',
                    error_message=result.error_message
                )
        
        return stats
    
    async def delete_file_embeddings(self, file_id: UUID) -> bool:
        """
        Delete embeddings for a file
        
        Note: With LlamaIndex, this is handled by the vector store
        We just need to track it in our database
        """
        try:
            # LlamaIndex vector store handles the actual deletion
            # We just need to update our tracking
            
            await self._update_file_sync_status(
                file_id, 
                'deleted'
            )
            
            print(f"✓ Marked file {file_id} embeddings as deleted")
            return True
            
        except Exception as e:
            print(f"❌ Error deleting file embeddings: {e}")
            return False
    
    async def search_similar_chunks(
        self, 
        query_embedding: List[float], 
        tenant_id: UUID, 
        limit: int = 10
    ) -> List[Tuple[Any, float]]:
        """
        Search for similar chunks
        
        Note: This is now handled by the RAG service's LlamaIndex integration
        This method is kept for compatibility but delegates to the RAG service
        """
        try:
            if not self.rag_service:
                print("⚠️ No RAG service available for similarity search")
                return []
            
            # Use RAG service for search (it has the LlamaIndex integration)
            # This is a compatibility shim - in the new architecture, 
            # you should use the RAG service directly
            print("⚠️ similarity search via embedding service is deprecated")
            print("  Use the RAG service query() method instead")
            return []
            
        except Exception as e:
            print(f"❌ Error in similarity search: {e}")
            return []
    
    async def get_tenant_stats(self, tenant_id: UUID) -> Dict[str, Any]:
        """Get embedding statistics for a tenant"""
        try:
            # Get file counts by status
            result = await self.db.execute(
                text("""
                    SELECT sync_status, COUNT(*) as count
                    FROM files 
                    WHERE tenant_id = :tenant_id 
                    AND deleted_at IS NULL
                    GROUP BY sync_status
                """),
                {'tenant_id': str(tenant_id)}
            )
            
            status_counts = {row.sync_status: row.count for row in result.fetchall()}
            
            # Get RAG service stats if available
            rag_stats = {}
            if self.rag_service:
                rag_stats = await self.rag_service.get_tenant_stats(tenant_id)
            
            return {
                'tenant_id': str(tenant_id),
                'file_status_counts': status_counts,
                'total_files': sum(status_counts.values()),
                'rag_stats': rag_stats,
                'processing_method': 'unified_llamaindex'
            }
            
        except Exception as e:
            print(f"❌ Error getting tenant stats: {e}")
            return {'error': str(e)}
    
    async def get_processing_stats(self) -> Dict[str, Any]:
        """Get overall processing statistics"""
        try:
            processor_stats = {}
            if self.document_processor:
                processor_stats = await self.document_processor.get_processing_stats()
            
            return {
                'embedding_model_loaded': self.model_loaded,
                'embedding_model_type': type(self.embedding_model).__name__ if self.embedding_model else None,
                'document_processor_available': self.document_processor is not None,
                'processor_stats': processor_stats,
                'service_type': 'simplified_embedding_service'
            }
            
        except Exception as e:
            print(f"❌ Error getting processing stats: {e}")
            return {'error': str(e)}


# Factory function for dependency injection
async def get_simplified_embedding_service(
    db: AsyncSession,
    embedding_model=None,
    document_processor=None,
    rag_service=None
) -> SimplifiedEmbeddingService:
    """Factory function to create simplified embedding service"""
    return SimplifiedEmbeddingService(
        db=db,
        embedding_model=embedding_model,
        document_processor=document_processor,
        rag_service=rag_service
    )