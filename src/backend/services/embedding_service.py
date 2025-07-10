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
    
    def __init__(self, db_session: AsyncSession, embedding_model=None, qdrant_client=None):
        self.db = db_session
        self.model_name = settings.embedding_model
        self.chunk_size = settings.chunk_size
        self.chunk_overlap = settings.chunk_overlap
        
        # Use provided model or fallback to None for mock mode
        self._model = embedding_model
        self._tokenizer = None
        
        # Use injected Qdrant client
        self._qdrant_client = qdrant_client
        
        if self._model:
            try:
                self._embedding_dimension = self._model.get_sentence_embedding_dimension()
                print(f"✓ Using singleton embedding model: {self.model_name}")
                print(f"  - Dimension: {self._embedding_dimension}")
                print(f"  - Device: {self._model.device}")
            except Exception as e:
                print(f"⚠️ Error getting model dimensions, using default: {e}")
                self._embedding_dimension = 384  # Default for all-MiniLM-L6-v2
        else:
            print("⚠️ No embedding model provided, using mock embeddings")
            self._embedding_dimension = 384  # Default for all-MiniLM-L6-v2
    
    async def initialize(self):
        """Initialize embedding model and tokenizer (deprecated - use dependency injection)"""
        # This method is now deprecated since model is injected via constructor
        if self._model is None:
            print("⚠️ No embedding model available, using mock embeddings")
        # No-op since model is now provided via dependency injection
    
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
        Split text into chunks for embedding with LlamaIndex semantic chunking
        """
        chunks = []
        
        # Clean and normalize text
        text = text.strip()
        if not text:
            return chunks
        
        # Try LlamaIndex semantic chunking first
        try:
            from .document_processing.llamaindex_chunker import create_tenant_chunker
            
            # Create tenant-isolated chunker
            chunker = await create_tenant_chunker(file_record.tenant_id)
            
            # Use LlamaIndex semantic chunking with tenant isolation
            llamaindex_chunks = await chunker.chunk_text(
                text=text,
                file_id=file_record.id,
                filename=file_record.filename,
                metadata={
                    'file_path': file_record.file_path,
                    'mime_type': file_record.mime_type,
                    'file_size': file_record.file_size
                }
            )
            
            # Convert LlamaIndex chunks to our DocumentChunk format
            for llamaindex_chunk in llamaindex_chunks:
                chunk = DocumentChunk(
                    content=llamaindex_chunk.content,
                    chunk_index=llamaindex_chunk.chunk_index,
                    metadata=llamaindex_chunk.metadata
                )
                chunks.append(chunk)
            
            print(f"✓ LlamaIndex semantic chunking: {len(chunks)} chunks generated")
            return chunks
            
        except Exception as e:
            print(f"⚠️ LlamaIndex chunking failed: {e}, falling back to sentence-aware chunking")
        
        # Fallback to sentence-aware chunking
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
                if len(current_chunk) + len(sentence) > self.chunk_size and current_chunk:
                    # Save current chunk
                    if current_chunk.strip():
                        chunk = DocumentChunk(
                            content=current_chunk.strip(),
                            chunk_index=chunk_index,
                            metadata={
                                'file_id': str(file_record.id),
                                'filename': file_record.filename,
                                'tenant_id': str(file_record.tenant_id),
                                'start_char': current_start,
                                'end_char': current_start + len(current_chunk),
                                'chunking_method': 'sentence-aware'
                            }
                        )
                        chunks.append(chunk)
                        chunk_index += 1
                    
                    # Start new chunk with overlap
                    if self.chunk_overlap > 0 and current_chunk:
                        overlap_text = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else current_chunk
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
                        'tenant_id': str(file_record.tenant_id),
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
        Generate embeddings for document chunks with optimized GPU batch processing
        """
        if not chunks:
            return []
        
        embeddings = []
        
        if self._model is not None:
            # Use real sentence-transformers model with optimized batch processing
            try:
                import torch
                
                # Extract text content from chunks
                texts = [chunk.content for chunk in chunks]
                
                # Optimize batch size based on GPU memory and text length
                batch_size = self._calculate_optimal_batch_size(texts)
                all_embeddings = []
                
                print(f"🚀 Processing {len(texts)} chunks in batches of {batch_size}")
                
                # Process all batches in parallel where possible
                batch_tasks = []
                for i in range(0, len(texts), batch_size):
                    batch_texts = texts[i:i + batch_size]
                    batch_tasks.append(self._process_embedding_batch(batch_texts, i // batch_size))
                
                # Execute batches with controlled concurrency
                max_concurrent_batches = 2  # Limit concurrent GPU operations
                for i in range(0, len(batch_tasks), max_concurrent_batches):
                    concurrent_batch = batch_tasks[i:i + max_concurrent_batches]
                    batch_results = await asyncio.gather(*concurrent_batch, return_exceptions=True)
                    
                    for result in batch_results:
                        if isinstance(result, Exception):
                            print(f"⚠️ Batch processing failed: {result}")
                            continue
                        all_embeddings.extend(result)
                    
                    # Clear GPU cache between concurrent batches
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                
                # Create embedding results
                for i, (chunk, embedding) in enumerate(zip(chunks, all_embeddings)):
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
                
                # Final cleanup
                del all_embeddings
                del texts
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                
                print(f"✓ Generated {len(embeddings)} embeddings using {self.model_name} with optimized batching")
                
            except Exception as e:
                print(f"⚠️ Error generating embeddings: {e}")
                # Fallback to mock embeddings
                embeddings = self._generate_mock_embeddings(chunks)
        else:
            # Use mock embeddings when model is not available
            embeddings = self._generate_mock_embeddings(chunks)
        
        return embeddings
    
    def _calculate_optimal_batch_size(self, texts: List[str]) -> int:
        """
        Calculate optimal batch size based on GPU memory and text characteristics
        """
        try:
            import torch
            
            # Base batch size from environment config
            env_batch_size = int(settings.batch_size) if hasattr(settings, 'batch_size') else 32
            
            # Adjust based on GPU memory if available
            if torch.cuda.is_available():
                gpu_memory_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                
                # Calculate average text length
                avg_text_length = sum(len(text) for text in texts) / len(texts) if texts else 512
                
                # Adjust batch size based on GPU memory and text length
                if gpu_memory_gb >= 16:  # High-end GPU
                    if avg_text_length <= 256:
                        batch_size = min(128, env_batch_size * 4)
                    elif avg_text_length <= 512:
                        batch_size = min(64, env_batch_size * 2)
                    else:
                        batch_size = min(32, env_batch_size)
                elif gpu_memory_gb >= 8:  # Mid-range GPU
                    if avg_text_length <= 256:
                        batch_size = min(64, env_batch_size * 2)
                    elif avg_text_length <= 512:
                        batch_size = min(32, env_batch_size)
                    else:
                        batch_size = min(16, env_batch_size // 2)
                else:  # Low-end GPU
                    batch_size = min(16, env_batch_size // 2)
                
                print(f"🎯 Optimized batch size: {batch_size} (GPU: {gpu_memory_gb:.1f}GB, avg_text_len: {avg_text_length:.0f})")
                return batch_size
            else:
                # CPU fallback
                return min(16, env_batch_size // 2)
                
        except Exception as e:
            print(f"⚠️ Error calculating batch size: {e}, using default")
            return 32

    def _get_current_collection_name(self) -> str:
        """Get the current environment collection name (ignores stored collection_name)"""
        import os
        current_env = os.getenv("RAG_ENVIRONMENT", "development")
        return f"documents_{current_env}"
    
    async def _process_embedding_batch(self, batch_texts: List[str], batch_index: int) -> List:
        """
        Process a single batch of embeddings asynchronously
        """
        try:
            import torch
            
            # Run embedding generation in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            
            def generate_batch():
                with torch.no_grad():  # Disable gradient computation for inference
                    # Enable mixed precision for RTX 5070 if available
                    if torch.cuda.is_available() and hasattr(torch.cuda, 'amp'):
                        with torch.cuda.amp.autocast():
                            return self._model.encode(
                                batch_texts, 
                                convert_to_tensor=False,
                                show_progress_bar=False,
                                batch_size=len(batch_texts)  # Process entire batch at once
                            )
                    else:
                        return self._model.encode(
                            batch_texts, 
                            convert_to_tensor=False,
                            show_progress_bar=False,
                            batch_size=len(batch_texts)
                        )
            
            batch_embeddings = await loop.run_in_executor(None, generate_batch)
            print(f"  ✓ Batch {batch_index + 1}: {len(batch_texts)} embeddings")
            
            return batch_embeddings
            
        except Exception as e:
            print(f"⚠️ Error processing batch {batch_index + 1}: {e}")
            raise
    
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
        Store embeddings in database and vector store with optimized bulk operations
        
        Args:
            file_record: File database record
            chunks: Document chunks
            embeddings: Generated embeddings
            environment: Target environment (defaults to current)
            
        Returns:
            List[EmbeddingChunk]: Database records for chunks
        """
        import os
        from sqlalchemy import insert
        
        chunk_records = []
        current_env = environment or os.getenv("RAG_ENVIRONMENT", "development")
        collection_name = f"documents_{current_env}"  # Environment-specific collection
        
        # Initialize Qdrant client if not already done
        await self._ensure_qdrant_collection(collection_name)
        
        # Prepare bulk data for both PostgreSQL and Qdrant
        postgres_bulk_data = []
        qdrant_points = []
        
        for chunk, embedding in zip(chunks, embeddings):
            # Generate unique point ID for Qdrant
            point_id = uuid4()
            
            # Prepare PostgreSQL bulk insert data
            postgres_bulk_data.append({
                'id': uuid4(),
                'file_id': file_record.id,
                'tenant_id': file_record.tenant_id,
                'chunk_index': chunk.chunk_index,
                'chunk_content': chunk.content,
                'chunk_hash': chunk.hash,
                'token_count': chunk.token_count,
                'qdrant_point_id': point_id,
                'collection_name': collection_name,
                'embedding_model': self.model_name,
                'processed_at': datetime.utcnow()
            })
            
            # Prepare Qdrant bulk upsert data
            qdrant_points.append({
                'id': str(point_id),
                'vector': embedding.vector,
                'payload': await self._prepare_qdrant_payload(point_id, chunk, file_record, current_env)
            })
        
        # Bulk insert into PostgreSQL
        try:
            await self.db.execute(
                insert(EmbeddingChunk).values(postgres_bulk_data)
            )
            await self.db.commit()
            
            # Convert bulk data to EmbeddingChunk objects for return
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
            
            print(f"✓ Bulk inserted {len(postgres_bulk_data)} chunks into PostgreSQL")
            
        except Exception as e:
            print(f"⚠️ Bulk PostgreSQL insert failed: {e}")
            await self.db.rollback()
            # Fallback to individual inserts
            for chunk, embedding in zip(chunks, embeddings):
                point_id = uuid4()
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
        
        # Bulk upsert into Qdrant
        await self._bulk_store_in_qdrant(qdrant_points, collection_name)
        
        return chunk_records
    
    async def _ensure_qdrant_collection(self, collection_name: str):
        """Ensure Qdrant collection exists for the tenant"""
        if self._qdrant_client is None:
            print("⚠️ Qdrant client not available")
            return
        
        try:
            from qdrant_client.models import Distance, VectorParams
            
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
            
        except Exception as e:
            print(f"⚠️ Failed to setup Qdrant collection: {e}")
    
    async def _prepare_qdrant_payload(
        self, 
        point_id: UUID, 
        chunk: DocumentChunk, 
        file_record: File,
        environment: str
    ) -> Dict[str, Any]:
        """Prepare standardized payload for Qdrant storage with consistent tenant isolation"""
        return {
            # Core identifiers for filtering
            "chunk_id": str(point_id),
            "file_id": str(file_record.id),
            "tenant_id": str(file_record.tenant_id),
            "environment": environment,
            
            # Chunk-specific data
            "chunk_index": chunk.chunk_index,
            "chunk_hash": chunk.hash,
            "token_count": chunk.token_count,
            
            # File metadata for search and filtering
            "filename": file_record.filename,
            "file_path": file_record.file_path,
            "file_size": file_record.file_size,
            "mime_type": file_record.mime_type,
            
            # Processing metadata
            "embedding_model": self.model_name,
            "processed_at": datetime.utcnow().isoformat(),
            
            # Nested metadata for backward compatibility
            "metadata": {
                "file_path": file_record.file_path,
                "filename": file_record.filename,
                "chunk_index": chunk.chunk_index,
                "file_id": str(file_record.id),
                "tenant_id": str(file_record.tenant_id)
            }
        }
    
    async def _bulk_store_in_qdrant(
        self, 
        qdrant_points: List[Dict[str, Any]], 
        collection_name: str
    ):
        """Store embeddings in Qdrant vector database using bulk operations"""
        if self._qdrant_client is None:
            print("⚠️ Qdrant client not available, skipping vector storage")
            return
        
        if not qdrant_points:
            return
        
        try:
            # Process in batches to avoid memory issues and API limits
            batch_size = 100  # Qdrant recommended batch size
            total_stored = 0
            
            for i in range(0, len(qdrant_points), batch_size):
                batch = qdrant_points[i:i + batch_size]
                
                # Bulk upsert batch
                self._qdrant_client.upsert(
                    collection_name=collection_name,
                    points=batch
                )
                
                total_stored += len(batch)
                print(f"  ✓ Bulk stored batch {i//batch_size + 1}: {len(batch)} points to Qdrant")
            
            print(f"✓ Successfully bulk stored {total_stored} points to Qdrant collection: {collection_name}")
            
        except Exception as e:
            print(f"⚠️ Failed to bulk store in Qdrant: {e}")
            # Fallback to individual storage
            for point in qdrant_points:
                try:
                    self._qdrant_client.upsert(
                        collection_name=collection_name,
                        points=[point]
                    )
                except Exception as e2:
                    print(f"⚠️ Failed to store individual point: {e2}")
    
    async def _store_in_qdrant(
        self, 
        point_id: UUID, 
        vector: List[float], 
        chunk: DocumentChunk, 
        file_record: File,
        collection_name: str
    ):
        """Store embedding in Qdrant vector database (legacy method for individual storage)"""
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
        
        if not chunks:
            return 0
        
        # Group chunks by collection for efficient batch deletion
        chunks_by_collection = {}
        current_collection = self._get_current_collection_name()
        chunks_by_collection[current_collection] = chunks
        
        # Batch delete from Qdrant by collection
        total_deleted = 0
        for collection_name, collection_chunks in chunks_by_collection.items():
            await self._ensure_qdrant_collection(collection_name)
            
            # Extract point IDs for batch deletion
            point_ids = [str(chunk.qdrant_point_id) for chunk in collection_chunks]
            
            try:
                deleted_count = await self._batch_delete_from_qdrant(point_ids, collection_name)
                total_deleted += deleted_count
                print(f"✓ Batch deleted {deleted_count} points from collection {collection_name}")
            except Exception as e:
                print(f"⚠️ Failed to batch delete from Qdrant collection {collection_name}: {e}")
                # Fallback to individual deletion
                for chunk in collection_chunks:
                    try:
                        await self._delete_from_qdrant(chunk.qdrant_point_id, collection_name)
                        total_deleted += 1
                    except Exception as e2:
                        print(f"⚠️ Failed to delete point {chunk.qdrant_point_id}: {e2}")
        
        # Delete from PostgreSQL in one query
        await self.db.execute(
            delete(EmbeddingChunk).where(EmbeddingChunk.file_id == file_id)
        )
        await self.db.commit()
        
        print(f"✓ Deleted {len(chunks)} embedding chunks for file {file_id}")
        return len(chunks)
    
    async def delete_multiple_files_embeddings(self, file_ids: List[UUID]) -> int:
        """
        Delete all embeddings for multiple files in batch - much more efficient
        
        Args:
            file_ids: List of file IDs to delete embeddings for
            
        Returns:
            int: Total number of chunks deleted
        """
        if not file_ids:
            return 0
        
        # Get all chunks for all files in one query
        result = await self.db.execute(
            select(EmbeddingChunk).where(EmbeddingChunk.file_id.in_(file_ids))
        )
        chunks = result.scalars().all()
        
        if not chunks:
            return 0
        
        print(f"🗞️ Bulk deleting {len(chunks)} chunks for {len(file_ids)} files")
        
        # Group chunks by collection for efficient batch deletion
        chunks_by_collection = {}
        current_collection = self._get_current_collection_name()
        chunks_by_collection[current_collection] = chunks
        
        # Batch delete from Qdrant by collection
        total_deleted = 0
        for collection_name, collection_chunks in chunks_by_collection.items():
            await self._ensure_qdrant_collection(collection_name)
            
            # Extract point IDs for batch deletion
            point_ids = [str(chunk.qdrant_point_id) for chunk in collection_chunks]
            
            try:
                deleted_count = await self._batch_delete_from_qdrant(point_ids, collection_name)
                total_deleted += deleted_count
                print(f"✓ Batch deleted {deleted_count} points from collection {collection_name}")
            except Exception as e:
                print(f"⚠️ Failed to batch delete from Qdrant collection {collection_name}: {e}")
                # Continue with other collections even if one fails
        
        # Delete from PostgreSQL in one query for all files
        await self.db.execute(
            delete(EmbeddingChunk).where(EmbeddingChunk.file_id.in_(file_ids))
        )
        await self.db.commit()
        
        print(f"✓ Bulk deleted {len(chunks)} embedding chunks for {len(file_ids)} files")
        return len(chunks)
    
    async def _batch_delete_from_qdrant(self, point_ids: List[str], collection_name: str) -> int:
        """
        Batch delete multiple points from Qdrant vector database
        
        Args:
            point_ids: List of point IDs to delete
            collection_name: Name of the collection
            
        Returns:
            int: Number of points successfully deleted
        """
        if self._qdrant_client is None:
            print("⚠️ Qdrant client not available, skipping vector deletion")
            return 0
        
        if not point_ids:
            return 0
        
        try:
            from qdrant_client.models import PointIdsList
            
            # Batch delete up to 100 points at a time (Qdrant limit)
            batch_size = 100
            total_deleted = 0
            
            for i in range(0, len(point_ids), batch_size):
                batch = point_ids[i:i + batch_size]
                
                self._qdrant_client.delete(
                    collection_name=collection_name,
                    points_selector=PointIdsList(points=batch)
                )
                
                total_deleted += len(batch)
                print(f"  Deleted batch of {len(batch)} points from {collection_name}")
            
            return total_deleted
            
        except Exception as e:
            print(f"⚠️ Failed to batch delete from Qdrant: {e}")
            raise
    
    async def _delete_from_qdrant(self, point_id: UUID, collection_name: str):
        """
        Delete single point from Qdrant vector database (fallback method)
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