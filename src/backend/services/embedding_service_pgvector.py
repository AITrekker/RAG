"""
PostgreSQL pgvector-based Embedding Service
Simplified, single-database implementation
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID, uuid4  # Still needed for chunk and file IDs
import hashlib
import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, insert, text
from sqlalchemy.sql import func

from src.backend.models.database import File, EmbeddingChunk
from src.backend.config.settings import get_settings
# Document processing factory removed - using SimpleDocumentProcessor directly

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
        
        # self.processor_factory = DocumentProcessorFactory()  # Removed - using SimpleDocumentProcessor directly
    
    def _try_load_model(self):
        """Try to load the embedding model"""
        try:
            from sentence_transformers import SentenceTransformer
            import torch
            
            logger.info(f"🤖 Loading embedding model: {self.model_name}")
            
            # Use GPU if available, otherwise CPU
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            self.embedding_model = SentenceTransformer(self.model_name, device=device)
            
            # Clear any existing CUDA cache
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            self.model_loaded = True
            logger.info(f"✓ Embedding model loaded successfully on {device}")
            
        except Exception as e:
            logger.error(f"❌ Failed to load embedding model: {e}")
            self.model_loaded = False
            self.embedding_model = None
    
    def _extract_text_sync(self, file_path: Path) -> str:
        """Simple synchronous text extraction"""
        try:
            if file_path.suffix.lower() in ['.txt', '.md']:
                return file_path.read_text(encoding='utf-8', errors='ignore')
            else:
                logger.warning(f"Unsupported file type: {file_path.suffix}")
                return ""
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {e}")
            return ""
    
    async def _extract_text_simple(self, file_path: Path) -> str:
        """Simple text extraction in executor"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._extract_text_sync, file_path
        )


    
    async def process_file_to_chunks(
        self, 
        file_path: Path, 
        tenant_slug: str, 
        file_record: File
    ) -> List[DocumentChunk]:
        """
        Process a file into chunks using the document processor
        
        Args:
            file_path: Path to the file to process
            tenant_slug: Tenant ID for the file
            file_record: Database file record
            
        Returns:
            List of DocumentChunk objects
        """
        try:
            # Simple direct text reading
            text_content = file_path.read_text(encoding='utf-8', errors='ignore')
            doc_chunks = []
            if text_content:
                # Simple word-based chunking
                words = text_content.split()
                chunk_index = 0
                start = 0
                
                max_iterations = 1000  # Safety limit
                iteration_count = 0
                
                while start < len(words) and iteration_count < max_iterations:
                    iteration_count += 1
                    end = min(start + self.chunk_size, len(words))
                    chunk_text = " ".join(words[start:end])
                    
                    if chunk_text.strip():  # Only create non-empty chunks
                        chunk = DocumentChunk(
                            content=chunk_text,
                            chunk_index=chunk_index,
                            metadata={
                                'file_id': str(file_record.id),
                                'tenant_slug': tenant_slug,
                                'filename': file_record.filename,
                                'file_path': file_record.file_path,
                                'start_word': start,
                                'end_word': end
                            }
                        )
                        doc_chunks.append(chunk)
                        chunk_index += 1
                    
                    # Ensure we always advance by at least 1 word to prevent infinite loops
                    start = max(start + 1, end - self.chunk_overlap)
                
                if iteration_count >= max_iterations:
                    logger.warning(f"Chunking loop exceeded {max_iterations} iterations")
            
            logger.info(f"✓ Processed '{file_record.filename}' into {len(doc_chunks)} chunks")
            return doc_chunks
            
        except Exception as e:
            logger.error(f"❌ Error processing file {file_path}: {e}")
            return []
    
    async def generate_embeddings(self, chunks: List[DocumentChunk]) -> List[EmbeddingResult]:
        """
        Generate embeddings for a list of chunks
        
        Args:
            chunks: List of DocumentChunk objects
            
        Returns:
            List of EmbeddingResult objects
        """
        if not self.model_loaded or not self.embedding_model:
            raise RuntimeError("Embedding model not loaded")
        
        try:
            # Extract text content from chunks
            texts = [chunk.content for chunk in chunks]
            
            # Generate embeddings using sentence-transformers
            # Run in executor to prevent blocking the event loop
            embeddings = await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: self.embedding_model.encode(texts, normalize_embeddings=True)
            )
            
            # Convert to list format and create results
            results = []
            for i, embedding in enumerate(embeddings):
                result = EmbeddingResult(
                    vector=embedding.tolist(),
                    metadata=chunks[i].metadata
                )
                results.append(result)
            
            logger.info(f"✓ Generated {len(results)} real embeddings using {self.model_name}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Error generating embeddings: {e}")
            raise
    
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
                        (id, file_id, tenant_slug, chunk_index, chunk_content, chunk_hash, 
                         token_count, embedding, embedding_model, processed_at, created_at, updated_at)
                        VALUES 
                        (:id, :file_id, :tenant_slug, :chunk_index, :chunk_content, :chunk_hash,
                         :token_count, (:embedding)::vector, :embedding_model, :processed_at, :created_at, :updated_at)
                    """),
                    {
                        'id': str(chunk_id),
                        'file_id': str(file_record.id),
                        'tenant_slug': file_record.tenant_slug,
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
                    tenant_slug=file_record.tenant_slug,
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
            # Don't rollback - let the caller handle transaction state
            return []
    
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
            # Don't rollback - let the caller handle transaction state
            return 0
    
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
        tenant_slug: str, 
        limit: int = 10
    ) -> List[Tuple[EmbeddingChunk, float]]:
        """
        Search for similar chunks using vector similarity
        
        Args:
            query_embedding: Query vector
            tenant_slug: Tenant ID to filter by
            limit: Maximum number of results
            
        Returns:
            List of (EmbeddingChunk, similarity_score) tuples
        """
        try:
            # Convert query embedding to pgvector format
            query_vector = str(query_embedding)
            
            # Use explicit transaction management to prevent rollbacks
            async with self.db.begin():
                # OPTIMIZED: Separate vector search from file filtering
                # First, get valid file IDs (fast with regular indexes)
                file_result = await self.db.execute(
                    text("""
                        SELECT id FROM files 
                        WHERE tenant_slug = :tenant_slug 
                        AND sync_status = 'synced' 
                        AND deleted_at IS NULL
                    """),
                    {'tenant_slug': tenant_id}
                )
                valid_file_ids = [str(row[0]) for row in file_result.fetchall()]
                
                if not valid_file_ids:
                    return []  # No valid files
                
                # Then, fast vector search (uses vector index efficiently)
                result = await self.db.execute(
                    text("""
                        SELECT ec.*, ec.embedding <=> :query_vector as similarity
                        FROM embedding_chunks ec
                        WHERE ec.tenant_slug = :tenant_slug
                        AND ec.file_id = ANY(:valid_file_ids)
                        ORDER BY similarity ASC
                        LIMIT :limit
                    """),
                    {
                        'query_vector': query_vector,
                        'tenant_slug': tenant_slug,
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
                        tenant_slug=row.tenant_slug,
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
    
    async def get_tenant_chunk_count(self, tenant_slug: str) -> int:
        """Get total number of chunks for a tenant"""
        try:
            # Use explicit transaction management to prevent rollbacks
            async with self.db.begin():
                result = await self.db.execute(
                    select(func.count(EmbeddingChunk.id)).where(EmbeddingChunk.tenant_slug == tenant_slug)
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
        return await self.process_file_to_chunks(file_path, file_record.tenant_slug, file_record)
    
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
                    file_path, file_record.tenant_slug, file_record
                )
            
            if not chunks:
                logger.warning(f"⚠️ No chunks extracted from {file_path}")
                return []
            
            # Step 2: Generate embeddings (now async)
            embeddings = await self.generate_embeddings(chunks)
            
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
        Process file using SimpleDocumentProcessor (hybrid processing removed for simplicity)
        """
        logger.info(f"✓ Processing {file_record.filename} using SimpleDocumentProcessor")
        return await self.process_file_to_chunks(file_path, file_record.tenant_slug, file_record)


# Factory function for dependency injection
async def get_pgvector_embedding_service(
    db_session: AsyncSession, 
    embedding_model=None
) -> PgVectorEmbeddingService:
    """Factory function to create PgVectorEmbeddingService"""
    return PgVectorEmbeddingService(db_session, embedding_model)