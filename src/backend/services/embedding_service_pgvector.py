"""
PostgreSQL pgvector-based Embedding Service
Simplified, single-database implementation
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID, uuid4
import hashlib
import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, insert, text
from sqlalchemy.sql import func

from src.backend.models.database import File, EmbeddingChunk
from src.backend.config.settings import get_settings
from .document_processing.factory import DocumentProcessorFactory

logger = logging.getLogger(__name__)
settings = get_settings()


class DocumentChunk:
    """Data class for document chunks"""
    def __init__(
        self, 
        content: str, 
        chunk_index: int, 
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.content = content
        self.chunk_index = chunk_index
        self.metadata = metadata or {}
        self.token_count = len(content.split())  # Simple token count
        self.hash = hashlib.sha256(content.encode()).hexdigest()


class EmbeddingResult:
    """Data class for embedding results"""
    def __init__(self, vector: List[float], metadata: Dict[str, Any]):
        self.vector = vector
        self.metadata = metadata


class PgVectorEmbeddingService:
    """Service for document processing and embedding generation using PostgreSQL + pgvector"""
    
    def __init__(self, db_session: AsyncSession, embedding_model=None):
        self.db = db_session
        self.model_name = settings.embedding_model
        self.chunk_size = settings.chunk_size
        self.chunk_overlap = settings.chunk_overlap
        
        # Use provided model or try to load default
        if embedding_model:
            self.embedding_model = embedding_model
            self.model_loaded = True
        else:
            self.embedding_model = None
            self.model_loaded = False
            self._try_load_model()
        
        self.processor_factory = DocumentProcessorFactory()
    
    def _try_load_model(self):
        """Try to load the embedding model"""
        try:
            from sentence_transformers import SentenceTransformer
            
            # Handle both full paths and short names
            model_name = self.model_name
            if not model_name.startswith('sentence-transformers/'):
                model_name = f"sentence-transformers/{model_name}"
            
            self.embedding_model = SentenceTransformer(model_name)
            self.model_loaded = True
            logger.info(f"✓ Loaded embedding model: {model_name}")
        except Exception as e:
            logger.warning(f"⚠️ Could not load embedding model: {e}")
            self.model_loaded = False
    
    async def process_file_to_chunks(
        self, 
        file_path: Path, 
        tenant_id: UUID, 
        file_record: File
    ) -> List[DocumentChunk]:
        """
        Process a file into chunks using the document processor
        
        Args:
            file_path: Path to the file to process
            tenant_id: Tenant ID for the file
            file_record: Database file record
            
        Returns:
            List of DocumentChunk objects
        """
        try:
            # Get appropriate processor for file type
            processor = self.processor_factory.get_processor(str(file_path))
            
            if processor is None:
                logger.error(f"❌ No processor available for file type: {file_path.suffix}")
                return []
            
            # Process file to get processed document (run sync call in thread pool)
            import asyncio
            processed_doc = await asyncio.get_event_loop().run_in_executor(
                None, processor.process_document, str(file_path), self.chunk_size
            )
            
            # Convert to our DocumentChunk objects
            doc_chunks = []
            for doc_chunk in processed_doc.chunks:
                chunk = DocumentChunk(
                    content=doc_chunk.content,
                    chunk_index=doc_chunk.chunk_index,
                    metadata={
                        'file_id': str(file_record.id),
                        'tenant_id': str(tenant_id),
                        'filename': file_record.filename,
                        'file_path': file_record.file_path,
                        **doc_chunk.metadata  # Include original metadata
                    }
                )
                doc_chunks.append(chunk)
            
            logger.info(f"✓ Processed '{file_record.filename}' into {len(doc_chunks)} chunks")
            return doc_chunks
            
        except Exception as e:
            logger.error(f"❌ Error processing file {file_path}: {e}")
            return []
    
    def generate_embeddings(self, chunks: List[DocumentChunk]) -> List[EmbeddingResult]:
        """
        Generate embeddings for a list of chunks
        
        Args:
            chunks: List of DocumentChunk objects
            
        Returns:
            List of EmbeddingResult objects
        """
        if not self.model_loaded:
            logger.warning("⚠️ No embedding model available, using mock embeddings")
            return [
                EmbeddingResult(
                    vector=[0.0] * 384,  # Mock embedding
                    metadata=chunk.metadata
                ) for chunk in chunks
            ]
        
        try:
            # Extract text content for embedding
            texts = [chunk.content for chunk in chunks]
            
            # Generate embeddings in batch
            embeddings = self.embedding_model.encode(texts, convert_to_tensor=False)
            
            # Convert to EmbeddingResult objects
            results = []
            for chunk, embedding in zip(chunks, embeddings):
                result = EmbeddingResult(
                    vector=embedding.tolist(),
                    metadata=chunk.metadata
                )
                results.append(result)
            
            logger.info(f"✓ Generated {len(results)} embeddings")
            return results
            
        except Exception as e:
            logger.error(f"❌ Error generating embeddings: {e}")
            # Return mock embeddings as fallback
            return [
                EmbeddingResult(
                    vector=[0.0] * 384,
                    metadata=chunk.metadata
                ) for chunk in chunks
            ]
    
    async def store_embeddings(
        self, 
        chunks: List[DocumentChunk], 
        embeddings: List[EmbeddingResult], 
        file_record: File
    ) -> List[EmbeddingChunk]:
        """
        Store chunks and embeddings in PostgreSQL
        
        Args:
            chunks: List of DocumentChunk objects
            embeddings: List of EmbeddingResult objects
            file_record: Database file record
            
        Returns:
            List of created EmbeddingChunk records
        """
        try:
            # Use raw SQL insert to handle pgvector properly
            from uuid import uuid4
            
            chunk_records = []
            
            for chunk, embedding in zip(chunks, embeddings):
                # Convert embedding to pgvector string format
                vector_str = f"[{','.join(map(str, embedding.vector))}]"
                chunk_id = uuid4()
                
                # Use raw SQL to insert with proper vector casting
                await self.db.execute(
                    text("""
                        INSERT INTO embedding_chunks 
                        (id, file_id, tenant_id, chunk_index, chunk_content, chunk_hash, 
                         token_count, embedding, embedding_model, processed_at, created_at, updated_at)
                        VALUES 
                        (:id, :file_id, :tenant_id, :chunk_index, :chunk_content, :chunk_hash,
                         :token_count, (:embedding)::vector, :embedding_model, :processed_at, :created_at, :updated_at)
                    """),
                    {
                        'id': str(chunk_id),
                        'file_id': str(file_record.id),
                        'tenant_id': str(file_record.tenant_id),
                        'chunk_index': chunk.chunk_index,
                        'chunk_content': chunk.content,
                        'chunk_hash': chunk.hash,
                        'token_count': chunk.token_count,
                        'embedding': vector_str,
                        'embedding_model': self.model_name,
                        'processed_at': datetime.utcnow(),
                        'created_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }
                )
                
                # Create record object for return value (without querying back)
                chunk_record = EmbeddingChunk(
                    id=chunk_id,
                    file_id=file_record.id,
                    tenant_id=file_record.tenant_id,
                    chunk_index=chunk.chunk_index,
                    chunk_content=chunk.content,
                    chunk_hash=chunk.hash,
                    token_count=chunk.token_count,
                    embedding=vector_str,
                    embedding_model=self.model_name,
                    processed_at=datetime.utcnow()
                )
                chunk_records.append(chunk_record)
            
            await self.db.commit()
            
            logger.info(f"✓ Stored {len(chunk_records)} chunks with embeddings in PostgreSQL")
            return chunk_records
            
        except Exception as e:
            logger.error(f"❌ Error storing embeddings: {e}")
            await self.db.rollback()
            raise
    
    async def delete_file_embeddings(self, file_id: UUID) -> int:
        """
        Delete all embeddings for a file
        
        Args:
            file_id: ID of the file
            
        Returns:
            Number of chunks deleted
        """
        try:
            # Get existing chunks for counting
            result = await self.db.execute(
                select(func.count(EmbeddingChunk.id)).where(EmbeddingChunk.file_id == file_id)
            )
            count = result.scalar() or 0
            
            # Delete all chunks for the file
            await self.db.execute(
                delete(EmbeddingChunk).where(EmbeddingChunk.file_id == file_id)
            )
            await self.db.commit()
            
            logger.info(f"✓ Deleted {count} embedding chunks for file {file_id}")
            return count
            
        except Exception as e:
            logger.error(f"❌ Error deleting file embeddings: {e}")
            await self.db.rollback()
            raise
    
    async def delete_multiple_files_embeddings(self, file_ids: List[UUID]) -> int:
        """
        Delete embeddings for multiple files in batch
        
        Args:
            file_ids: List of file IDs to delete embeddings for
            
        Returns:
            Total number of chunks deleted
        """
        try:
            # Get total count before deletion
            result = await self.db.execute(
                select(func.count(EmbeddingChunk.id)).where(EmbeddingChunk.file_id.in_(file_ids))
            )
            count = result.scalar() or 0
            
            # Delete all chunks for the files
            await self.db.execute(
                delete(EmbeddingChunk).where(EmbeddingChunk.file_id.in_(file_ids))
            )
            await self.db.commit()
            
            logger.info(f"✓ Deleted {count} embedding chunks for {len(file_ids)} files")
            return count
            
        except Exception as e:
            logger.error(f"❌ Error deleting multiple file embeddings: {e}")
            await self.db.rollback()
            raise
    
    async def search_similar_chunks(
        self, 
        query_embedding: List[float], 
        tenant_id: UUID, 
        limit: int = 10
    ) -> List[Tuple[EmbeddingChunk, float]]:
        """
        Search for similar chunks using vector similarity
        
        Args:
            query_embedding: Query vector
            tenant_id: Tenant ID to filter by
            limit: Maximum number of results
            
        Returns:
            List of (EmbeddingChunk, similarity_score) tuples
        """
        try:
            # Convert query embedding to pgvector format
            query_vector = str(query_embedding)
            
            # OPTIMIZED: Separate vector search from file filtering
            # First, get valid file IDs (fast with regular indexes)
            file_result = await self.db.execute(
                text("""
                    SELECT id FROM files 
                    WHERE tenant_id = :tenant_id 
                    AND sync_status = 'synced' 
                    AND deleted_at IS NULL
                """),
                {'tenant_id': str(tenant_id)}
            )
            valid_file_ids = [str(row[0]) for row in file_result.fetchall()]
            
            if not valid_file_ids:
                return []  # No valid files
            
            # Then, fast vector search (uses vector index efficiently)
            result = await self.db.execute(
                text("""
                    SELECT ec.*, ec.embedding <=> :query_vector as similarity
                    FROM embedding_chunks ec
                    WHERE ec.tenant_id = :tenant_id
                    AND ec.file_id = ANY(:valid_file_ids)
                    ORDER BY similarity ASC
                    LIMIT :limit
                """),
                {
                    'query_vector': query_vector,
                    'tenant_id': str(tenant_id),
                    'valid_file_ids': valid_file_ids,
                    'limit': limit
                }
            )
            
            # Convert results to EmbeddingChunk objects with similarity scores
            chunks_with_scores = []
            for row in result.fetchall():
                chunk = EmbeddingChunk(
                    id=row.id,
                    file_id=row.file_id,
                    tenant_id=row.tenant_id,
                    chunk_index=row.chunk_index,
                    chunk_content=row.chunk_content,
                    chunk_hash=row.chunk_hash,
                    token_count=row.token_count,
                    embedding=row.embedding,
                    embedding_model=row.embedding_model,
                    processed_at=row.processed_at,
                    created_at=row.created_at,
                    updated_at=row.updated_at
                )
                similarity_score = float(row.similarity)
                chunks_with_scores.append((chunk, similarity_score))
            
            logger.info(f"✓ Found {len(chunks_with_scores)} similar chunks")
            return chunks_with_scores
            
        except Exception as e:
            logger.error(f"❌ Error searching similar chunks: {e}")
            return []
    
    async def get_tenant_chunk_count(self, tenant_id: UUID) -> int:
        """Get total number of chunks for a tenant"""
        try:
            result = await self.db.execute(
                select(func.count(EmbeddingChunk.id)).where(EmbeddingChunk.tenant_id == tenant_id)
            )
            return result.scalar() or 0
        except Exception as e:
            logger.error(f"❌ Error getting chunk count: {e}")
            return 0
    
    async def process_file(self, file_record: File) -> List[DocumentChunk]:
        """
        Process a file into chunks for embedding generation (compatibility method)
        
        Args:
            file_record: File database record
            
        Returns:
            List[DocumentChunk]: List of processed chunks
        """
        from src.backend.config.settings import get_settings
        settings = get_settings()
        file_path = Path(settings.documents_path) / file_record.file_path
        return await self.process_file_to_chunks(file_path, file_record.tenant_id, file_record)
    
    async def process_and_store_file(
        self, 
        file_path: Path, 
        file_record: File,
        use_llamaindex: bool = True
    ) -> List[EmbeddingChunk]:
        """
        Complete pipeline: process file, generate embeddings, and store
        Now with optional LlamaIndex integration for complex documents
        
        Args:
            file_path: Path to the file
            file_record: Database file record
            use_llamaindex: Whether to try LlamaIndex for complex documents
            
        Returns:
            List of created EmbeddingChunk records
        """
        try:
            # Step 1: Choose processing method
            if use_llamaindex:
                chunks = await self._process_with_hybrid_approach(file_path, file_record)
            else:
                chunks = await self.process_file_to_chunks(
                    file_path, file_record.tenant_id, file_record
                )
            
            if not chunks:
                logger.warning(f"⚠️ No chunks extracted from {file_path}")
                return []
            
            # Step 2: Generate embeddings (same as before)
            embeddings = self.generate_embeddings(chunks)
            
            # Step 3: Store in PostgreSQL (same as before)
            chunk_records = await self.store_embeddings(chunks, embeddings, file_record)
            
            logger.info(f"✓ Successfully processed and stored file: {file_record.filename}")
            return chunk_records
            
        except Exception as e:
            logger.error(f"❌ Error in complete file processing: {e}")
            await self.db.rollback()
            raise
    
    async def _process_with_hybrid_approach(
        self, 
        file_path: Path, 
        file_record: File
    ) -> List['DocumentChunk']:
        """
        Process file using hybrid approach (LlamaIndex + simple fallback)
        """
        try:
            # Import the hybrid processor
            from .document_processing.llamaindex_adapter import create_hybrid_document_processor
            
            # Create and initialize hybrid processor
            hybrid_processor = await create_hybrid_document_processor(self.db)
            
            # Process the file
            chunks, method = await hybrid_processor.process_file(str(file_path), file_record)
            
            logger.info(f"✓ Processed {file_record.filename} using {method} method")
            return chunks
            
        except ImportError:
            logger.warning("⚠️ LlamaIndex adapter not available, using simple processing")
            return await self.process_file_to_chunks(file_path, file_record.tenant_id, file_record)
        except Exception as e:
            logger.warning(f"⚠️ Hybrid processing failed, falling back to simple: {e}")
            return await self.process_file_to_chunks(file_path, file_record.tenant_id, file_record)


# Factory function for dependency injection
async def get_pgvector_embedding_service(
    db_session: AsyncSession, 
    embedding_model=None
) -> PgVectorEmbeddingService:
    """Factory function to create PgVectorEmbeddingService"""
    return PgVectorEmbeddingService(db_session, embedding_model)