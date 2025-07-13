"""
Synchronous Embedding Service with Rich Progress Tracking
Eliminates async/sync mixing issues and provides detailed progress updates
"""

import time
import psutil
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Callable
from uuid import UUID, uuid4
import hashlib
import logging
from pathlib import Path

from sqlalchemy import create_engine, select, delete, text
from sqlalchemy.orm import sessionmaker, Session

from src.backend.models.database import File, EmbeddingChunk, SyncOperation
from src.backend.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class SyncDocumentChunk:
    """Data class for document chunks with metadata"""
    def __init__(
        self, 
        content: str, 
        chunk_index: int, 
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.content = content
        self.chunk_index = chunk_index
        self.metadata = metadata or {}
        self.token_count = len(content.split())
        self.word_count = len(content.split())
        self.char_count = len(content)
        self.hash = hashlib.sha256(content.encode()).hexdigest()


class ProgressCallback:
    """Callback for progress updates"""
    def __init__(self, sync_op_id: UUID, db_session: Session):
        self.sync_op_id = sync_op_id
        self.db_session = db_session
        self.start_time = time.time()
        self.last_update = time.time()
        
    def update(self, **kwargs):
        """Update progress with interesting data points"""
        current_time = time.time()
        
        # Calculate processing speeds
        elapsed_time = current_time - self.start_time
        elapsed_minutes = elapsed_time / 60.0
        
        update_data = {
            'heartbeat_at': datetime.utcnow(),
            'memory_usage_mb': int(psutil.Process().memory_info().rss / 1024 / 1024)
        }
        
        # Add all provided metrics
        update_data.update(kwargs)
        
        # Only update database every 2 seconds to avoid too much I/O
        if current_time - self.last_update >= 2.0:
            self.db_session.execute(
                text("""
                    UPDATE sync_operations 
                    SET heartbeat_at = :heartbeat_at,
                        memory_usage_mb = :memory_usage_mb,
                        progress_stage = :progress_stage,
                        progress_percentage = :progress_percentage,
                        current_file_name = :current_file_name,
                        current_file_size = :current_file_size,
                        current_file_type = :current_file_type,
                        current_file_index = :current_file_index,
                        files_processed = :files_processed,
                        chunks_created = :chunks_created,
                        processing_speed_files_per_min = :processing_speed_files_per_min,
                        processing_speed_chunks_per_min = :processing_speed_chunks_per_min,
                        extraction_method = :extraction_method
                    WHERE id = :sync_op_id
                """),
                {
                    'sync_op_id': self.sync_op_id,
                    'heartbeat_at': update_data.get('heartbeat_at'),
                    'memory_usage_mb': update_data.get('memory_usage_mb'),
                    'progress_stage': update_data.get('progress_stage'),
                    'progress_percentage': update_data.get('progress_percentage', 0),
                    'current_file_name': update_data.get('current_file_name'),
                    'current_file_size': update_data.get('current_file_size'),
                    'current_file_type': update_data.get('current_file_type'),
                    'current_file_index': update_data.get('current_file_index'),
                    'files_processed': update_data.get('files_processed'),
                    'chunks_created': update_data.get('chunks_created'),
                    'processing_speed_files_per_min': update_data.get('processing_speed_files_per_min'),
                    'processing_speed_chunks_per_min': update_data.get('processing_speed_chunks_per_min'),
                    'extraction_method': update_data.get('extraction_method')
                }
            )
            self.db_session.commit()
            self.last_update = current_time


class SyncEmbeddingService:
    """Synchronous embedding service with detailed progress tracking"""
    
    def __init__(self, embedding_model=None):
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
        
        # Create synchronous database engine and session factory
        from src.backend.database import get_environment_database_url
        db_url = get_environment_database_url().replace("postgresql://", "postgresql://", 1)
        self.sync_engine = create_engine(
            db_url,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            echo=False
        )
        self.SessionLocal = sessionmaker(bind=self.sync_engine, autoflush=False, autocommit=False)
    
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
    
    def extract_text_from_file(self, file_path: Path) -> Tuple[str, str]:
        """Extract text from file and return content + extraction method"""
        file_ext = file_path.suffix.lower()
        
        try:
            if file_ext in ['.txt', '.md']:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                return content, "text_read"
            elif file_ext == '.pdf':
                try:
                    import PyPDF2
                    with open(file_path, 'rb') as file:
                        reader = PyPDF2.PdfReader(file)
                        text = ""
                        for page in reader.pages:
                            text += page.extract_text() + "\n"
                    return text, "pypdf2"
                except ImportError:
                    logger.warning("PyPDF2 not available, treating as text file")
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    return content, "text_fallback"
            else:
                logger.warning(f"Unsupported file type: {file_ext}")
                return "", "unsupported"
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {e}")
            return "", "error"
    
    def chunk_text(self, text: str) -> List[SyncDocumentChunk]:
        """Split text into chunks with overlap - fixed to prevent infinite loops"""
        if not text.strip():
            return []
        
        words = text.split()
        chunks = []
        start = 0
        max_iterations = 1000  # Safety limit
        iteration_count = 0
        
        while start < len(words) and iteration_count < max_iterations:
            iteration_count += 1
            end = min(start + self.chunk_size, len(words))
            chunk_text = " ".join(words[start:end])
            
            if chunk_text.strip():  # Only add non-empty chunks
                chunks.append(SyncDocumentChunk(
                    content=chunk_text,
                    chunk_index=len(chunks),
                    metadata={"start_word": start, "end_word": end}
                ))
            
            # Ensure we always advance by at least 1 word to prevent infinite loops
            start = max(start + 1, end - self.chunk_overlap)
            
            # Break if we're not making progress
            if start >= end:
                start = end
        
        if iteration_count >= max_iterations:
            logger.warning(f"⚠️ Chunking hit iteration limit of {max_iterations}")
        
        logger.info(f"📝 Created {len(chunks)} chunks from {len(words)} words")
        return chunks
    
    def generate_embeddings_sync(self, chunks: List[SyncDocumentChunk]) -> List[List[float]]:
        """Generate embeddings synchronously"""
        if not self.model_loaded or not chunks:
            return []
        
        try:
            # Extract text from chunks
            texts = [chunk.content for chunk in chunks]
            
            # Generate embeddings (this is CPU/GPU intensive but synchronous)
            embeddings = self.embedding_model.encode(texts, show_progress_bar=True)
            
            # Convert to list of lists
            return [embedding.tolist() for embedding in embeddings]
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return []
    
    def process_files_with_progress(
        self, 
        files: List[File], 
        tenant_slug: str, 
        sync_op_id: UUID
    ) -> Dict[str, Any]:
        """Process multiple files with detailed progress tracking"""
        
        with self.SessionLocal() as db_session:
            progress = ProgressCallback(sync_op_id, db_session)
            
            total_files = len(files)
            total_chunks_created = 0
            total_files_processed = 0
            
            start_time = time.time()
            
            # Update initial progress
            progress.update(
                progress_stage="initializing",
                progress_percentage=0,
                total_files_to_process=total_files
            )
            
            for file_index, file_record in enumerate(files):
                file_start_time = time.time()
                
                # Update progress for current file
                progress.update(
                    progress_stage="extracting_text",
                    current_file_index=file_index + 1,
                    current_file_name=file_record.filename,
                    current_file_size=file_record.file_size,
                    current_file_type=Path(file_record.filename).suffix.upper().replace('.', ''),
                    progress_percentage=(file_index / total_files) * 100
                )
                
                try:
                    # Extract text
                    file_path = Path(settings.upload_directory) / str(tenant_slug) / file_record.filename
                    text_content, extraction_method = self.extract_text_from_file(file_path)
                    
                    progress.update(
                        progress_stage="chunking_text",
                        extraction_method=extraction_method
                    )
                    
                    # Create chunks
                    chunks = self.chunk_text(text_content)
                    
                    if chunks:
                        progress.update(
                            progress_stage="generating_embeddings",
                            extraction_method=extraction_method
                        )
                        
                        # Generate embeddings
                        embeddings = self.generate_embeddings_sync(chunks)
                        
                        progress.update(
                            progress_stage="storing_embeddings"
                        )
                        
                        # Store embeddings in database
                        for chunk, embedding in zip(chunks, embeddings):
                            embedding_chunk = EmbeddingChunk(
                                id=uuid4(),
                                tenant_id=tenant_id,
                                file_id=file_record.id,
                                chunk_index=chunk.chunk_index,
                                content=chunk.content,
                                metadata=chunk.metadata,
                                token_count=chunk.token_count,
                                embedding=embedding
                            )
                            db_session.add(embedding_chunk)
                        
                        db_session.commit()
                        total_chunks_created += len(chunks)
                    
                    total_files_processed += 1
                    
                    # Calculate processing speeds
                    elapsed_time = time.time() - start_time
                    elapsed_minutes = elapsed_time / 60.0
                    files_per_min = total_files_processed / elapsed_minutes if elapsed_minutes > 0 else 0
                    chunks_per_min = total_chunks_created / elapsed_minutes if elapsed_minutes > 0 else 0
                    
                    # Update progress with speeds
                    progress.update(
                        progress_stage="file_completed",
                        files_processed=total_files_processed,
                        chunks_created=total_chunks_created,
                        processing_speed_files_per_min=round(files_per_min, 2),
                        processing_speed_chunks_per_min=round(chunks_per_min, 2),
                        progress_percentage=((file_index + 1) / total_files) * 100
                    )
                    
                    logger.info(f"✅ Processed {file_record.filename}: {len(chunks)} chunks, {round(time.time() - file_start_time, 2)}s")
                    
                except Exception as e:
                    logger.error(f"❌ Error processing {file_record.filename}: {e}")
                    # Continue with next file
                    continue
            
            # Final progress update
            progress.update(
                progress_stage="completed",
                progress_percentage=100,
                files_processed=total_files_processed,
                chunks_created=total_chunks_created
            )
            
            return {
                "files_processed": total_files_processed,
                "chunks_created": total_chunks_created,
                "total_time_seconds": time.time() - start_time,
                "success": True
            }