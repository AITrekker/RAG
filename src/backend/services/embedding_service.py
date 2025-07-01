"""
Embedding Service - Handles document processing and embedding generation
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID, uuid4
import hashlib
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from src.backend.models.database import File, EmbeddingChunk
from src.backend.config.settings import get_settings
from .document_processing.factory import DocumentProcessorFactory

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


class EmbeddingService:
    """Service for document processing and embedding generation"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.model_name = settings.embedding_model
        self.chunk_size = settings.chunk_size
        self.chunk_overlap = settings.chunk_overlap
        
        # TODO: Initialize embedding model when implemented
        self._model = None
        self._tokenizer = None
    
    async def initialize(self):
        """Initialize embedding model and tokenizer"""
        try:
            from sentence_transformers import SentenceTransformer
            
            # Initialize the embedding model
            self._model = SentenceTransformer(self.model_name)
            self._tokenizer = self._model.tokenizer
            
            # Move to appropriate device if specified
            device = getattr(settings, 'embedding_device', 'cpu')
            if device != 'cpu':
                self._model = self._model.to(device)
            
            self._embedding_dimension = self._model.get_sentence_embedding_dimension()
            
            print(f"✓ Embedding model initialized: {self.model_name}")
            print(f"  - Dimension: {self._embedding_dimension}")
            print(f"  - Device: {device}")
            
        except ImportError:
            print("⚠️ sentence-transformers not available, using mock embeddings")
            self._model = None
            self._tokenizer = None
            self._embedding_dimension = 384  # Default dimension for mock
        except Exception as e:
            print(f"⚠️ Failed to load embedding model: {e}")
            print("  Using mock embeddings")
            self._model = None
            self._tokenizer = None
            self._embedding_dimension = 384
    
    async def process_file(self, file_record: File) -> List[DocumentChunk]:
        """
        Process a file into chunks for embedding generation
        
        Args:
            file_record: File database record
            
        Returns:
            List[DocumentChunk]: List of processed chunks
        """
        file_path = f"./data/uploads/{file_record.file_path}"
        
        # Extract text based on file type
        text_content = await self._extract_text(file_path, file_record.mime_type)
        
        # Chunk the text
        chunks = await self._chunk_text(text_content, file_record)
        
        return chunks
    
    async def _extract_text(self, file_path: str, mime_type: Optional[str]) -> str:
        """
        Extract text using new document processor system
        """
        try:
            # Try new document processor system first
            processor = DocumentProcessorFactory.get_processor(file_path)
            if processor:
                return processor.extract_text(file_path)
            
            # Fallback to legacy extraction for unsupported types
            if mime_type == "application/pdf":
                return await self._extract_pdf_text(file_path)
            elif mime_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
                              "application/msword"]:
                return await self._extract_docx_text(file_path)
            elif mime_type and mime_type.startswith("text/"):
                # Plain text files
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                # Try to read as text, fallback to empty
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        return f.read()
                except UnicodeDecodeError:
                    # Binary file or unsupported format
                    return f"[Binary file: {Path(file_path).name}]"
        except Exception as e:
            print(f"Error extracting text from {file_path}: {e}")
            return ""
    
    async def _extract_pdf_text(self, file_path: str) -> str:
        """Extract text from PDF files"""
        try:
            import PyPDF2
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text
        except ImportError:
            print("⚠️ PyPDF2 not available for PDF processing")
            return f"[PDF file: {Path(file_path).name} - PDF processing not available]"
        except Exception as e:
            print(f"Error extracting PDF text: {e}")
            return f"[PDF file: {Path(file_path).name} - extraction failed]"
    
    async def _extract_docx_text(self, file_path: str) -> str:
        """Extract text from DOCX files"""
        try:
            import docx
            doc = docx.Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        except ImportError:
            print("⚠️ python-docx not available for DOCX processing")
            return f"[DOCX file: {Path(file_path).name} - DOCX processing not available]"
        except Exception as e:
            print(f"Error extracting DOCX text: {e}")
            return f"[DOCX file: {Path(file_path).name} - extraction failed]"
    
    async def _chunk_text(
        self, 
        text: str, 
        file_record: File
    ) -> List[DocumentChunk]:
        """
        Split text into chunks for embedding with smart sentence-aware chunking
        """
        chunks = []
        chunk_size = self.chunk_size
        overlap = self.chunk_overlap
        
        # Clean and normalize text
        text = text.strip()
        if not text:
            return chunks
        
        # Try sentence-aware chunking first
        try:
            import os
            import nltk
            
            # Set NLTK data path to writable location
            if '/tmp/nltk_data' not in nltk.data.path:
                nltk.data.path.insert(0, '/tmp/nltk_data')
            
            # Ensure punkt_tab is available (newer NLTK versions)
            try:
                nltk.data.find('tokenizers/punkt_tab')
            except LookupError:
                import tempfile
                os.makedirs('/tmp/nltk_data', exist_ok=True)
                nltk.download('punkt_tab', download_dir='/tmp/nltk_data', quiet=True)
            
            sentences = nltk.sent_tokenize(text)
            
            current_chunk = ""
            current_start = 0
            chunk_index = 0
            
            for sentence in sentences:
                # If adding this sentence would exceed chunk size and we have content
                if len(current_chunk) + len(sentence) > chunk_size and current_chunk:
                    # Save current chunk
                    if current_chunk.strip():
                        chunk = DocumentChunk(
                            content=current_chunk.strip(),
                            chunk_index=chunk_index,
                            metadata={
                                'file_id': str(file_record.id),
                                'filename': file_record.filename,
                                'start_char': current_start,
                                'end_char': current_start + len(current_chunk),
                                'chunking_method': 'sentence-aware'
                            }
                        )
                        chunks.append(chunk)
                        chunk_index += 1
                    
                    # Start new chunk with overlap
                    if overlap > 0 and current_chunk:
                        overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
                        current_chunk = overlap_text + " " + sentence
                        current_start = current_start + len(current_chunk) - len(overlap_text) - len(sentence) - 1
                    else:
                        current_chunk = sentence
                        current_start = current_start + len(current_chunk)
                else:
                    # Add sentence to current chunk
                    current_chunk += " " + sentence if current_chunk else sentence
            
            # Add final chunk
            if current_chunk.strip():
                chunk = DocumentChunk(
                    content=current_chunk.strip(),
                    chunk_index=chunk_index,
                    metadata={
                        'file_id': str(file_record.id),
                        'filename': file_record.filename,
                        'start_char': current_start,
                        'end_char': current_start + len(current_chunk),
                        'chunking_method': 'sentence-aware'
                    }
                )
                chunks.append(chunk)
        
        except ImportError:
            # Fallback to character-based chunking
            print("⚠️ NLTK not available, using character-based chunking")
            chunks = await self._chunk_text_simple(text, file_record)
        
        return chunks
    
    async def _chunk_text_simple(self, text: str, file_record: File) -> List[DocumentChunk]:
        """Simple character-based chunking fallback"""
        chunks = []
        chunk_size = self.chunk_size
        overlap = self.chunk_overlap
        
        start = 0
        chunk_index = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk_text = text[start:end]
            
            if chunk_text.strip():
                chunk = DocumentChunk(
                    content=chunk_text.strip(),
                    chunk_index=chunk_index,
                    metadata={
                        'file_id': str(file_record.id),
                        'filename': file_record.filename,
                        'start_char': start,
                        'end_char': end,
                        'chunking_method': 'character-based'
                    }
                )
                chunks.append(chunk)
                chunk_index += 1
            
            start = end - overlap if end < len(text) else end
        
        return chunks
    
    async def generate_embeddings(self, chunks: List[DocumentChunk]) -> List[EmbeddingResult]:
        """
        Generate embeddings for document chunks
        """
        if not chunks:
            return []
        
        embeddings = []
        
        if self._model is not None:
            # Use real sentence-transformers model
            try:
                # Extract text content from chunks
                texts = [chunk.content for chunk in chunks]
                
                # Generate embeddings in batch for efficiency
                batch_embeddings = self._model.encode(texts, convert_to_tensor=False)
                
                # Create embedding results
                for i, (chunk, embedding) in enumerate(zip(chunks, batch_embeddings)):
                    embeddings.append(EmbeddingResult(
                        vector=embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding),
                        metadata={
                            'chunk_id': chunk.hash,
                            'chunk_index': chunk.chunk_index,
                            'file_id': chunk.metadata.get('file_id'),
                            'filename': chunk.metadata.get('filename'),
                            'content_length': len(chunk.content),
                            'token_count': chunk.token_count,
                            'model_name': self.model_name,
                            'embedding_dimension': self._embedding_dimension
                        }
                    ))
                
                print(f"✓ Generated {len(embeddings)} embeddings using {self.model_name}")
                
            except Exception as e:
                print(f"⚠️ Error generating embeddings: {e}")
                # Fallback to mock embeddings
                embeddings = self._generate_mock_embeddings(chunks)
        else:
            # Use mock embeddings when model is not available
            embeddings = self._generate_mock_embeddings(chunks)
        
        return embeddings
    
    def _generate_mock_embeddings(self, chunks: List[DocumentChunk]) -> List[EmbeddingResult]:
        """Generate mock embeddings for testing when model is not available"""
        import random
        
        embeddings = []
        for chunk in chunks:
            # Generate deterministic but varied mock embeddings based on content hash
            random.seed(hash(chunk.content) % 2147483647)  # Ensure 32-bit
            dummy_vector = [random.uniform(-1, 1) for _ in range(self._embedding_dimension)]
            
            embedding = EmbeddingResult(
                vector=dummy_vector,
                metadata={
                    'chunk_id': chunk.hash,
                    'chunk_index': chunk.chunk_index,
                    'file_id': chunk.metadata.get('file_id'),
                    'filename': chunk.metadata.get('filename'),
                    'content_length': len(chunk.content),
                    'token_count': chunk.token_count,
                    'model_name': 'mock-embeddings',
                    'embedding_dimension': self._embedding_dimension
                }
            )
            embeddings.append(embedding)
        
        print(f"✓ Generated {len(embeddings)} mock embeddings")
        return embeddings
    
    async def store_embeddings(
        self, 
        file_record: File, 
        chunks: List[DocumentChunk], 
        embeddings: List[EmbeddingResult],
        environment: str = None
    ) -> List[EmbeddingChunk]:
        """
        Store embeddings in database and vector store with environment separation
        
        Args:
            file_record: File database record
            chunks: Document chunks
            embeddings: Generated embeddings
            environment: Target environment (defaults to current)
            
        Returns:
            List[EmbeddingChunk]: Database records for chunks
        """
        import os
        
        chunk_records = []
        current_env = environment or os.getenv("RAG_ENVIRONMENT", "development")
        collection_name = f"documents_{current_env}"  # Environment-specific collection
        
        # Initialize Qdrant client if not already done
        await self._ensure_qdrant_collection(collection_name)
        
        for chunk, embedding in zip(chunks, embeddings):
            # Generate unique point ID for Qdrant
            point_id = uuid4()
            
            # Store in Qdrant vector database
            await self._store_in_qdrant(point_id, embedding.vector, chunk, file_record, collection_name)
            
            # Store metadata in PostgreSQL
            chunk_record = EmbeddingChunk(
                file_id=file_record.id,
                tenant_id=file_record.tenant_id,
                chunk_index=chunk.chunk_index,
                chunk_content=chunk.content,
                chunk_hash=chunk.hash,
                token_count=chunk.token_count,
                qdrant_point_id=point_id,
                collection_name=collection_name,
                embedding_model=self.model_name,
                processed_at=datetime.utcnow()
            )
            
            self.db.add(chunk_record)
            chunk_records.append(chunk_record)
        
        await self.db.commit()
        return chunk_records
    
    async def _ensure_qdrant_collection(self, collection_name: str):
        """Ensure Qdrant collection exists for the tenant"""
        if not hasattr(self, '_qdrant_client') or self._qdrant_client is None:
            try:
                from qdrant_client import QdrantClient
                from qdrant_client.models import Distance, VectorParams
                
                self._qdrant_client = QdrantClient(
                    host=settings.qdrant_host,
                    port=settings.qdrant_port
                )
                
                # Check if collection exists, create if not
                collections = self._qdrant_client.get_collections().collections
                collection_names = [col.name for col in collections]
                
                if collection_name not in collection_names:
                    self._qdrant_client.create_collection(
                        collection_name=collection_name,
                        vectors_config=VectorParams(
                            size=self._embedding_dimension,
                            distance=Distance.COSINE
                        )
                    )
                    print(f"✓ Created Qdrant collection: {collection_name}")
                
            except ImportError:
                print("⚠️ qdrant-client not available")
                self._qdrant_client = None
            except Exception as e:
                print(f"⚠️ Failed to setup Qdrant collection: {e}")
                self._qdrant_client = None
    
    async def _store_in_qdrant(
        self, 
        point_id: UUID, 
        vector: List[float], 
        chunk: DocumentChunk, 
        file_record: File,
        collection_name: str
    ):
        """Store embedding in Qdrant vector database"""
        if self._qdrant_client is None:
            print("⚠️ Qdrant client not available, skipping vector storage")
            return
        
        try:
            # Get tenant environment from database
            from src.backend.models.database import Tenant
            tenant_result = await self.db.execute(select(Tenant).where(Tenant.id == file_record.tenant_id))
            tenant = tenant_result.scalar_one_or_none()
            environment = tenant.environment if tenant else 'production'
            
            # Enhanced payload with environment for multitenancy
            payload = {
                "chunk_id": str(point_id),
                "file_id": str(file_record.id),
                "tenant_id": str(file_record.tenant_id),
                "environment": environment,
                "chunk_index": chunk.chunk_index,
                "filename": file_record.filename
            }
            
            # Store in Qdrant
            self._qdrant_client.upsert(
                collection_name=collection_name,
                points=[{
                    "id": str(point_id),
                    "vector": vector,
                    "payload": payload
                }]
            )
            
        except Exception as e:
            print(f"⚠️ Failed to store in Qdrant: {e}")
    
    async def delete_file_embeddings(self, file_id: UUID) -> int:
        """
        Delete all embeddings for a file from both Qdrant and PostgreSQL
        
        Returns:
            int: Number of chunks deleted
        """
        # Get chunk records to get Qdrant point IDs
        result = await self.db.execute(
            select(EmbeddingChunk).where(EmbeddingChunk.file_id == file_id)
        )
        chunks = result.scalars().all()
        
        # Delete from Qdrant first
        for chunk in chunks:
            await self._delete_from_qdrant(chunk.qdrant_point_id, chunk.collection_name)
        
        # Delete from PostgreSQL
        await self.db.execute(
            delete(EmbeddingChunk).where(EmbeddingChunk.file_id == file_id)
        )
        await self.db.commit()
        
        print(f"✓ Deleted {len(chunks)} embedding chunks for file {file_id}")
        return len(chunks)
    
    async def _delete_from_qdrant(self, point_id: UUID, collection_name: str):
        """
        Delete point from Qdrant vector database
        """
        if self._qdrant_client is None:
            print("⚠️ Qdrant client not available, skipping vector deletion")
            return
        
        try:
            from qdrant_client.models import PointIdsList
            
            # Delete the point
            self._qdrant_client.delete(
                collection_name=collection_name,
                points_selector=PointIdsList(
                    points=[str(point_id)]
                )
            )
            
        except Exception as e:
            print(f"⚠️ Failed to delete from Qdrant: {e}")
            # Don't raise exception - this is cleanup, shouldn't fail the whole operation
    
    async def reprocess_file(self, file_record: File) -> List[EmbeddingChunk]:
        """
        Reprocess a file (delete old embeddings and create new ones)
        """
        # Delete existing embeddings
        await self.delete_file_embeddings(file_record.id)
        
        # Process file again
        chunks = await self.process_file(file_record)
        embeddings = await self.generate_embeddings(chunks)
        chunk_records = await self.store_embeddings(file_record, chunks, embeddings)
        
        return chunk_records
    
    async def get_embedding_stats(self, tenant_id: UUID) -> Dict[str, Any]:
        """Get embedding statistics for a tenant"""
        # TODO: Implement embedding statistics
        return {
            'total_files': 0,
            'total_chunks': 0,
            'total_embeddings': 0,
            'model_name': self.model_name,
            'processing_status': {
                'pending': 0,
                'processing': 0,
                'completed': 0,
                'failed': 0
            }
        }
    
    async def batch_process_files(self, file_records: List[File]) -> Dict[str, Any]:
        """
        Process multiple files in batch
        
        TODO: Implement efficient batch processing
        """
        results = {
            'processed': 0,
            'failed': 0,
            'total_chunks': 0
        }
        
        for file_record in file_records:
            try:
                chunks = await self.process_file(file_record)
                embeddings = await self.generate_embeddings(chunks)
                await self.store_embeddings(file_record, chunks, embeddings)
                
                results['processed'] += 1
                results['total_chunks'] += len(chunks)
                
            except Exception as e:
                # TODO: Log error properly
                results['failed'] += 1
        
        return results


# Dependency function for FastAPI
async def get_embedding_service(db_session: AsyncSession) -> EmbeddingService:
    """Dependency to get embedding service with database session"""
    service = EmbeddingService(db_session)
    await service.initialize()
    return service