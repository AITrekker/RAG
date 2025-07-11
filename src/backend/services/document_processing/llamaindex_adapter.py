"""
LlamaIndex adapter for pgvector integration
Bridges LlamaIndex document processing with our simplified pgvector architecture
"""

from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID, uuid4
from dataclasses import dataclass
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from src.backend.models.database import File, EmbeddingChunk
from src.backend.config.settings import get_settings

settings = get_settings()


@dataclass
class ProcessedDocument:
    """Document processed by LlamaIndex but adapted for our schema"""
    chunks: List['DocumentChunk']
    metadata: Dict[str, Any]
    processing_stats: Dict[str, Any]


@dataclass
class DocumentChunk:
    """Chunk format compatible with our pgvector system"""
    content: str
    chunk_index: int
    metadata: Dict[str, Any]
    token_count: int
    
    @property
    def hash(self) -> str:
        import hashlib
        return hashlib.sha256(self.content.encode()).hexdigest()


class LlamaIndexPgVectorAdapter:
    """
    Adapter that uses LlamaIndex for document processing but stores in pgvector
    
    Strategy:
    1. Use LlamaIndex ONLY for document parsing/chunking
    2. Extract the processed chunks 
    3. Store directly in our pgvector schema
    4. Bypass LlamaIndex's vector store abstractions entirely
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self._node_parser = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize LlamaIndex components for document processing only"""
        try:
            # Import only what we need from LlamaIndex
            from llama_index.core.node_parser import SimpleNodeParser
            from llama_index.core.text_splitter import SentenceSplitter
            
            # Create text splitter with our settings
            text_splitter = SentenceSplitter(
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
                separator=" ",
                backup_separators=["\n", "\n\n", ".", "!", "?"]
            )
            
            # Create node parser (this is where LlamaIndex shines)
            self._node_parser = SimpleNodeParser(
                text_splitter=text_splitter,
                include_metadata=True,
                include_prev_next_rel=False  # We don't need relationships
            )
            
            # Try to initialize readers - these might not be available
            try:
                from llama_index.readers.file import PDFReader
                self._pdf_reader = PDFReader()
                print("✓ LlamaIndex PDF reader available")
            except ImportError:
                print("⚠️ LlamaIndex PDF reader not available - will use pypdf2 fallback")
                self._pdf_reader = None
            
            try:
                from llama_index.readers.file import DocxReader
                self._docx_reader = DocxReader()
                print("✓ LlamaIndex DOCX reader available")
            except ImportError:
                print("⚠️ LlamaIndex DOCX reader not available - will use fallback")
                self._docx_reader = None
            
            self._initialized = True
            print("✓ LlamaIndex adapter initialized (document processing only)")
            
        except ImportError as e:
            print(f"⚠️ LlamaIndex not available, falling back to simple processing: {e}")
            self._initialized = False
        except Exception as e:
            print(f"⚠️ Error initializing LlamaIndex adapter: {e}")
            self._initialized = False
    
    async def process_document(
        self, 
        file_path: str, 
        file_record: File
    ) -> Optional[ProcessedDocument]:
        """
        Process document using LlamaIndex but return in our format
        
        Key insight: We use LlamaIndex for parsing, NOT for vector storage
        """
        if not self._initialized:
            return None
        
        try:
            # Step 1: Use LlamaIndex to load and parse the document
            documents = await self._load_document(file_path)
            if not documents:
                return None
            
            # Step 2: Use LlamaIndex to create nodes (chunks)
            nodes = self._node_parser.get_nodes_from_documents(documents)
            
            # Step 3: Convert LlamaIndex nodes to our DocumentChunk format
            chunks = []
            for i, node in enumerate(nodes):
                chunk = DocumentChunk(
                    content=node.text,
                    chunk_index=i,
                    metadata={
                        'file_id': str(file_record.id),
                        'tenant_id': str(file_record.tenant_id),
                        'filename': file_record.filename,
                        'file_path': file_record.file_path,
                        # Include LlamaIndex metadata
                        'llamaindex_node_id': node.id_,
                        'source_metadata': dict(node.metadata),
                        'start_char_idx': getattr(node, 'start_char_idx', None),
                        'end_char_idx': getattr(node, 'end_char_idx', None),
                    },
                    token_count=len(node.text.split())  # Simple token count
                )
                chunks.append(chunk)
            
            # Step 4: Return processed document in our format
            return ProcessedDocument(
                chunks=chunks,
                metadata={
                    'processing_method': 'llamaindex',
                    'node_count': len(nodes),
                    'source_documents': len(documents),
                    'total_chars': sum(len(chunk.content) for chunk in chunks)
                },
                processing_stats={
                    'chunks_created': len(chunks),
                    'avg_chunk_size': sum(len(chunk.content) for chunk in chunks) / len(chunks) if chunks else 0
                }
            )
            
        except Exception as e:
            print(f"❌ Error processing document with LlamaIndex: {e}")
            return None
    
    async def _load_document(self, file_path: str) -> List:
        """Load document using appropriate LlamaIndex reader"""
        try:
            file_extension = file_path.lower().split('.')[-1]
            
            if file_extension == 'pdf' and self._pdf_reader:
                # Use LlamaIndex PDF reader (much better than pypdf)
                return self._pdf_reader.load_data(file_path)
            elif file_extension in ['docx', 'doc'] and self._docx_reader:
                # Use LlamaIndex DOCX reader
                return self._docx_reader.load_data(file_path)
            else:
                # Fallback to simple text reading
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Create a simple LlamaIndex document
                from llama_index.core.schema import Document
                return [Document(text=content, metadata={'source': file_path})]
                
        except Exception as e:
            print(f"❌ Error loading document {file_path}: {e}")
            return []
    
    async def store_chunks_in_pgvector(
        self,
        chunks: List[DocumentChunk],
        embeddings: List[List[float]],
        file_record: File
    ) -> List[EmbeddingChunk]:
        """
        Store processed chunks directly in pgvector
        
        This bypasses LlamaIndex's vector store entirely
        """
        try:
            chunk_records = []
            
            for chunk, embedding in zip(chunks, embeddings):
                # Convert embedding to pgvector string format
                vector_str = f"[{','.join(map(str, embedding))}]"
                chunk_id = uuid4()
                
                # Store directly in our pgvector schema
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
                        'embedding_model': settings.embedding_model,
                        'processed_at': 'NOW()',
                        'created_at': 'NOW()',
                        'updated_at': 'NOW()'
                    }
                )
                
                # Create record object for return
                chunk_record = EmbeddingChunk(
                    id=chunk_id,
                    file_id=file_record.id,
                    tenant_id=file_record.tenant_id,
                    chunk_index=chunk.chunk_index,
                    chunk_content=chunk.content,
                    chunk_hash=chunk.hash,
                    token_count=chunk.token_count,
                    embedding=vector_str,
                    embedding_model=settings.embedding_model
                )
                chunk_records.append(chunk_record)
            
            await self.db.commit()
            print(f"✓ Stored {len(chunk_records)} LlamaIndex-processed chunks in pgvector")
            return chunk_records
            
        except Exception as e:
            print(f"❌ Error storing chunks in pgvector: {e}")
            await self.db.rollback()
            raise


class HybridDocumentProcessor:
    """
    Processor that intelligently chooses between LlamaIndex and simple processing
    
    Strategy:
    - Use LlamaIndex for complex documents (PDF, DOCX)
    - Use simple processing for basic documents (TXT)
    - Always store in our pgvector schema
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.llamaindex_adapter = LlamaIndexPgVectorAdapter(db_session)
        
        # Import our simple processor
        from .factory import DocumentProcessorFactory
        self.simple_factory = DocumentProcessorFactory()
    
    async def initialize(self):
        """Initialize both processing methods"""
        await self.llamaindex_adapter.initialize()
        print("✓ Hybrid document processor initialized")
    
    def should_use_llamaindex(self, file_path: str) -> bool:
        """Decide whether to use LlamaIndex for this file"""
        if not self.llamaindex_adapter._initialized:
            return False
        
        file_extension = file_path.lower().split('.')[-1]
        
        # Use LlamaIndex for complex document types, but only if readers are available
        if file_extension == 'pdf' and self.llamaindex_adapter._pdf_reader:
            return True
        elif file_extension in ['docx', 'doc'] and self.llamaindex_adapter._docx_reader:
            return True
        elif file_extension in ['html', 'htm']:
            return True  # HTML can use simple text reader
        
        return False
    
    async def process_file(
        self, 
        file_path: str, 
        file_record: File
    ) -> Tuple[List[DocumentChunk], str]:
        """
        Process file using the most appropriate method
        
        Returns: (chunks, processing_method)
        """
        if self.should_use_llamaindex(file_path):
            # Use LlamaIndex for complex documents
            processed = await self.llamaindex_adapter.process_document(file_path, file_record)
            if processed:
                return processed.chunks, "llamaindex"
        
        # Fallback to simple processing
        processor = self.simple_factory.get_processor(file_path)
        if processor:
            # Use our simple document processor
            processed_doc = processor.process_document(file_path, settings.chunk_size)
            
            # Convert to our chunk format
            chunks = []
            for doc_chunk in processed_doc.chunks:
                chunk = DocumentChunk(
                    content=doc_chunk.content,
                    chunk_index=doc_chunk.chunk_index,
                    metadata={
                        'file_id': str(file_record.id),
                        'tenant_id': str(file_record.tenant_id),
                        'filename': file_record.filename,
                        'file_path': file_record.file_path,
                        **doc_chunk.metadata
                    },
                    token_count=len(doc_chunk.content.split())
                )
                chunks.append(chunk)
            
            return chunks, "simple"
        
        # No processor available
        return [], "none"


# Factory function for dependency injection
async def create_hybrid_document_processor(db_session: AsyncSession) -> HybridDocumentProcessor:
    """Factory function to create and initialize hybrid processor"""
    processor = HybridDocumentProcessor(db_session)
    await processor.initialize()
    return processor