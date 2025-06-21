"""
Document processor for the Enterprise RAG Platform.

This module handles document loading, content extraction, and chunking
for PDF, Word, and text files using LlamaIndex and custom processing logic.
Implements fixed-size chunking strategy with configurable overlap.
"""

import os
import hashlib
import mimetypes
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple, Union
from pathlib import Path
import logging
from dataclasses import dataclass

# LlamaIndex imports
from llama_index.core import Document as LlamaDocument
from llama_index.readers.file import (
    PDFReader, 
    DocxReader, 
    UnstructuredReader
)
from llama_index.core.text_splitter import TokenTextSplitter
from llama_index.core.node_parser import SimpleNodeParser

# Local imports
from ..models.document import (
    Document, DocumentChunk, DocumentStatus, DocumentType, ChunkType,
    create_document_from_file, create_document_chunk
)

logger = logging.getLogger(__name__)


@dataclass
class ChunkingConfig:
    """Configuration for document chunking strategy."""
    chunk_size: int = 512  # Target chunk size in tokens
    chunk_overlap: int = 50  # Overlap between chunks in tokens
    min_chunk_size: int = 100  # Minimum chunk size to avoid tiny chunks
    max_chunk_size: int = 1024  # Maximum chunk size
    separator: str = "\n\n"  # Preferred separator for chunks
    preserve_sentences: bool = True  # Try to preserve sentence boundaries
    
    def validate(self):
        """Validate chunking configuration."""
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap cannot be negative")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        if self.min_chunk_size <= 0:
            raise ValueError("min_chunk_size must be positive")
        if self.max_chunk_size <= self.chunk_size:
            raise ValueError("max_chunk_size must be greater than chunk_size")


@dataclass
class ProcessingResult:
    """Result of document processing operation."""
    success: bool
    document: Optional[Document] = None
    chunks: List[DocumentChunk] = None
    error_message: Optional[str] = None
    processing_metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.chunks is None:
            self.chunks = []
        if self.processing_metadata is None:
            self.processing_metadata = {}


class DocumentProcessor:
    """
    Main document processor for handling various file types.
    
    Supports PDF, Word documents, and text files with configurable
    chunking strategies and metadata extraction.
    """
    
    def __init__(self, chunking_config: ChunkingConfig = None):
        """Initialize document processor with configuration."""
        self.chunking_config = chunking_config or ChunkingConfig()
        self.chunking_config.validate()
        
        # Initialize LlamaIndex readers
        self.pdf_reader = PDFReader()
        self.docx_reader = DocxReader()
        self.unstructured_reader = UnstructuredReader()
        
        # Initialize text splitter
        self.text_splitter = TokenTextSplitter(
            chunk_size=self.chunking_config.chunk_size,
            chunk_overlap=self.chunking_config.chunk_overlap,
            separator=self.chunking_config.separator
        )
        
        # Supported file extensions
        self.supported_extensions = {
            '.pdf': DocumentType.PDF,
            '.doc': DocumentType.WORD,
            '.docx': DocumentType.WORD,
            '.txt': DocumentType.TEXT,
            '.md': DocumentType.MARKDOWN,
            '.html': DocumentType.HTML,
            '.htm': DocumentType.HTML,
        }
        
        logger.info(f"DocumentProcessor initialized with chunk_size={self.chunking_config.chunk_size}")
    
    def process_file(
        self, 
        file_path: str, 
        tenant_id: str,
        filename: str = None
    ) -> ProcessingResult:
        """
        Process a file and return document with chunks.
        
        Args:
            file_path: Path to the file to process
            tenant_id: Tenant ID for isolation
            filename: Optional custom filename (defaults to file basename)
            
        Returns:
            ProcessingResult containing document and chunks or error information
        """
        try:
            # Validate file path
            if not os.path.exists(file_path):
                return ProcessingResult(
                    success=False,
                    error_message=f"File not found: {file_path}"
                )
            
            # Get file information
            file_info = self._get_file_info(file_path, filename)
            
            # Check if file type is supported
            if file_info['document_type'] == DocumentType.UNKNOWN:
                return ProcessingResult(
                    success=False,
                    error_message=f"Unsupported file type: {file_info['extension']}"
                )
            
            logger.info(f"Processing file: {file_info['filename']} ({file_info['file_size']} bytes)")
            
            # Create document instance
            document = create_document_from_file(
                tenant_id=tenant_id,
                file_path=file_path,
                filename=file_info['filename'],
                file_size=file_info['file_size'],
                file_hash=file_info['file_hash'],
                mime_type=file_info['mime_type'],
                file_modified_at=file_info['modified_at']
            )
            
            # Update document status
            document.status = DocumentStatus.PROCESSING.value
            document.processing_started_at = datetime.now(timezone.utc)
            
            # Extract content based on file type
            content_result = self._extract_content(file_path, file_info['document_type'])
            if not content_result['success']:
                document.status = DocumentStatus.FAILED.value
                document.processing_error = content_result['error']
                return ProcessingResult(
                    success=False,
                    document=document,
                    error_message=content_result['error']
                )
            
            # Update document with extracted content metadata
            document.title = content_result.get('title')
            document.content_preview = content_result['content'][:500] if content_result['content'] else None
            document.word_count = len(content_result['content'].split()) if content_result['content'] else 0
            document.page_count = content_result.get('page_count', 1)
            document.language = content_result.get('language', 'en')
            
            # Create chunks
            chunks_result = self._create_chunks(
                content_result['content'],
                str(document.id),
                tenant_id,
                content_result.get('metadata', {})
            )
            
            if not chunks_result['success']:
                document.status = DocumentStatus.FAILED.value
                document.processing_error = chunks_result['error']
                return ProcessingResult(
                    success=False,
                    document=document,
                    error_message=chunks_result['error']
                )
            
            # Update document with chunk information
            document.total_chunks = len(chunks_result['chunks'])
            document.status = DocumentStatus.COMPLETED.value
            document.processing_completed_at = datetime.now(timezone.utc)
            
            # Create processing metadata
            processing_metadata = {
                'chunking_config': {
                    'chunk_size': self.chunking_config.chunk_size,
                    'chunk_overlap': self.chunking_config.chunk_overlap,
                    'method': 'fixed_size'
                },
                'content_extraction': content_result.get('metadata', {}),
                'processing_time_seconds': (
                    document.processing_completed_at - document.processing_started_at
                ).total_seconds()
            }
            
            logger.info(f"Successfully processed {file_info['filename']}: {len(chunks_result['chunks'])} chunks")
            
            return ProcessingResult(
                success=True,
                document=document,
                chunks=chunks_result['chunks'],
                processing_metadata=processing_metadata
            )
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {str(e)}")
            return ProcessingResult(
                success=False,
                error_message=f"Processing error: {str(e)}"
            )
    
    def _get_file_info(self, file_path: str, filename: str = None) -> Dict[str, Any]:
        """Extract file information and metadata."""
        path_obj = Path(file_path)
        
        # Use provided filename or extract from path
        final_filename = filename or path_obj.name
        
        # Get file stats
        stat = os.stat(file_path)
        file_size = stat.st_size
        modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        
        # Calculate file hash
        file_hash = self._calculate_file_hash(file_path)
        
        # Determine file type
        extension = path_obj.suffix.lower()
        document_type = self.supported_extensions.get(extension, DocumentType.UNKNOWN)
        
        # Get MIME type
        mime_type, _ = mimetypes.guess_type(file_path)
        
        return {
            'filename': final_filename,
            'extension': extension,
            'file_size': file_size,
            'file_hash': file_hash,
            'mime_type': mime_type,
            'document_type': document_type,
            'modified_at': modified_at
        }
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file."""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def _extract_content(self, file_path: str, document_type: DocumentType) -> Dict[str, Any]:
        """Extract content from file based on document type."""
        try:
            if document_type == DocumentType.PDF:
                return self._extract_pdf_content(file_path)
            elif document_type == DocumentType.WORD:
                return self._extract_word_content(file_path)
            elif document_type in [DocumentType.TEXT, DocumentType.MARKDOWN]:
                return self._extract_text_content(file_path)
            elif document_type == DocumentType.HTML:
                return self._extract_html_content(file_path)
            else:
                return {
                    'success': False,
                    'error': f"Unsupported document type: {document_type}"
                }
        except Exception as e:
            logger.error(f"Content extraction error for {file_path}: {str(e)}")
            return {
                'success': False,
                'error': f"Content extraction failed: {str(e)}"
            }
    
    def _extract_pdf_content(self, file_path: str) -> Dict[str, Any]:
        """Extract content from PDF file."""
        try:
            documents = self.pdf_reader.load_data(file=Path(file_path))
            
            if not documents:
                return {
                    'success': False,
                    'error': "No content extracted from PDF"
                }
            
            # Combine all document content
            content = "\n\n".join([doc.text for doc in documents])
            
            # Extract metadata
            metadata = documents[0].metadata if documents else {}
            
            return {
                'success': True,
                'content': content,
                'title': metadata.get('title'),
                'page_count': len(documents),
                'language': metadata.get('language', 'en'),
                'metadata': metadata
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"PDF extraction error: {str(e)}"
            }
    
    def _extract_word_content(self, file_path: str) -> Dict[str, Any]:
        """Extract content from Word document."""
        try:
            documents = self.docx_reader.load_data(file=Path(file_path))
            
            if not documents:
                return {
                    'success': False,
                    'error': "No content extracted from Word document"
                }
            
            # Combine all document content
            content = "\n\n".join([doc.text for doc in documents])
            
            # Extract metadata
            metadata = documents[0].metadata if documents else {}
            
            return {
                'success': True,
                'content': content,
                'title': metadata.get('title'),
                'page_count': 1,  # Word docs don't have clear page boundaries
                'language': metadata.get('language', 'en'),
                'metadata': metadata
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Word document extraction error: {str(e)}"
            }
    
    def _extract_text_content(self, file_path: str) -> Dict[str, Any]:
        """Extract content from plain text file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Try to extract title from first line if it looks like a title
            lines = content.split('\n')
            title = None
            if lines and len(lines[0]) < 100 and not lines[0].startswith(' '):
                title = lines[0].strip()
            
            return {
                'success': True,
                'content': content,
                'title': title,
                'page_count': 1,
                'language': 'en',  # Could use language detection here
                'metadata': {}
            }
            
        except UnicodeDecodeError:
            # Try with different encoding
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    content = f.read()
                return {
                    'success': True,
                    'content': content,
                    'title': None,
                    'page_count': 1,
                    'language': 'en',
                    'metadata': {'encoding': 'latin-1'}
                }
            except Exception as e:
                return {
                    'success': False,
                    'error': f"Text file encoding error: {str(e)}"
                }
        except Exception as e:
            return {
                'success': False,
                'error': f"Text file extraction error: {str(e)}"
            }
    
    def _extract_html_content(self, file_path: str) -> Dict[str, Any]:
        """Extract content from HTML file."""
        try:
            documents = self.unstructured_reader.load_data(file=Path(file_path))
            
            if not documents:
                return {
                    'success': False,
                    'error': "No content extracted from HTML"
                }
            
            # Combine all document content
            content = "\n\n".join([doc.text for doc in documents])
            
            # Extract metadata
            metadata = documents[0].metadata if documents else {}
            
            return {
                'success': True,
                'content': content,
                'title': metadata.get('title'),
                'page_count': 1,
                'language': metadata.get('language', 'en'),
                'metadata': metadata
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"HTML extraction error: {str(e)}"
            }
    
    def _create_chunks(
        self, 
        content: str, 
        document_id: str, 
        tenant_id: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create chunks from document content using fixed-size strategy."""
        try:
            if not content or not content.strip():
                return {
                    'success': False,
                    'error': "No content to chunk"
                }
            
            # Split content into chunks using LlamaIndex text splitter
            text_chunks = self.text_splitter.split_text(content)
            
            if not text_chunks:
                return {
                    'success': False,
                    'error': "Text splitter produced no chunks"
                }
            
            chunks = []
            for i, chunk_content in enumerate(text_chunks):
                # Skip chunks that are too small
                if len(chunk_content.strip()) < self.chunking_config.min_chunk_size:
                    continue
                
                # Determine chunk type (basic heuristics)
                chunk_type = self._determine_chunk_type(chunk_content)
                
                # Create chunk instance
                chunk = create_document_chunk(
                    document_id=document_id,
                    tenant_id=tenant_id,
                    content=chunk_content.strip(),
                    chunk_index=i,
                    chunk_method="fixed_size",
                    chunk_size=self.chunking_config.chunk_size,
                    overlap_size=self.chunking_config.chunk_overlap,
                    chunk_type=chunk_type.value
                )
                
                chunks.append(chunk)
            
            logger.info(f"Created {len(chunks)} chunks from content ({len(content)} characters)")
            
            return {
                'success': True,
                'chunks': chunks,
                'metadata': {
                    'original_content_length': len(content),
                    'total_chunks': len(chunks),
                    'avg_chunk_size': sum(len(c.content) for c in chunks) / len(chunks) if chunks else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Chunking error: {str(e)}")
            return {
                'success': False,
                'error': f"Chunking failed: {str(e)}"
            }
    
    def _determine_chunk_type(self, content: str) -> ChunkType:
        """Determine chunk type based on content analysis."""
        content_lower = content.lower().strip()
        
        # Check for title patterns
        if (len(content) < 100 and 
            ('\n' not in content or content.count('\n') <= 1) and
            not content.endswith('.') and
            content.isupper() or content.istitle()):
            return ChunkType.TITLE
        
        # Check for heading patterns
        if (content.startswith('#') or 
            (len(content) < 200 and content.endswith(':')) or
            content_lower.startswith(('chapter', 'section', 'part'))):
            return ChunkType.HEADING
        
        # Check for list items
        if (content.strip().startswith(('•', '-', '*', '1.', '2.', '3.')) or
            content.count('\n•') > 2 or content.count('\n-') > 2):
            return ChunkType.LIST_ITEM
        
        # Check for code blocks
        if ('```' in content or content.count('    ') > 3 or
            content_lower.count('def ') > 0 or content_lower.count('function') > 0):
            return ChunkType.CODE
        
        # Check for quotes
        if content.strip().startswith('"') and content.strip().endswith('"'):
            return ChunkType.QUOTE
        
        # Default to paragraph
        return ChunkType.PARAGRAPH
    
    def update_chunking_config(self, config: ChunkingConfig):
        """Update chunking configuration."""
        config.validate()
        self.chunking_config = config
        
        # Update text splitter
        self.text_splitter = TokenTextSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            separator=config.separator
        )
        
        logger.info(f"Updated chunking config: chunk_size={config.chunk_size}, overlap={config.chunk_overlap}")
    
    def get_supported_extensions(self) -> List[str]:
        """Get list of supported file extensions."""
        return list(self.supported_extensions.keys())
    
    def is_supported_file(self, file_path: str) -> bool:
        """Check if file type is supported."""
        extension = Path(file_path).suffix.lower()
        return extension in self.supported_extensions


# Utility functions
def create_default_processor() -> DocumentProcessor:
    """Create document processor with default configuration."""
    return DocumentProcessor(ChunkingConfig())


def create_optimized_processor(chunk_size: int = 768, overlap: int = 64) -> DocumentProcessor:
    """Create document processor optimized for embedding models."""
    config = ChunkingConfig(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        min_chunk_size=128,
        max_chunk_size=1024
    )
    return DocumentProcessor(config) 