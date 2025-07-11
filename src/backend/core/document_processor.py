"""
Stateless Document Processor for the Enterprise RAG Platform.

This module provides a `DocumentProcessor` that handles loading, content
extraction, and chunking for various file types (PDF, Word, text, HTML).
It is designed to be a stateless utility that does not interact with any
database or persistence layer. Its sole responsibility is to convert a file
into a structured representation of its content and metadata.
"""

import hashlib
import mimetypes
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field

# LlamaIndex imports
from llama_index.core.readers.base import BaseReader
from llama_index.readers.file import PDFReader, DocxReader, UnstructuredReader
from llama_index.core.text_splitter import TokenTextSplitter

from ..services.document_processing.processors.html_processor import HTMLProcessor

logger = logging.getLogger(__name__)

@dataclass
class Chunk:
    """A structured representation of a piece of text from a document."""
    id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ProcessedDocument:
    """The structured output of processing a single file."""
    doc_id: str
    filename: str
    metadata: Dict[str, Any]
    chunks: List[Chunk]

class DocumentProcessor:
    """
    A stateless utility to process files into structured documents and chunks.
    """
    
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ):
        """
        Initializes the DocumentProcessor with a chunking strategy.
        """
        self.text_splitter = TokenTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        self.html_processor = HTMLProcessor()
        self.file_readers: Dict[str, BaseReader] = {
            ".pdf": PDFReader(),
            ".docx": DocxReader(),
            ".doc": UnstructuredReader(),
            ".txt": UnstructuredReader(),
            ".md": UnstructuredReader(),
        }
        logger.info(f"DocumentProcessor initialized with chunk_size={chunk_size}")

    def process_file(self, file_path: Path) -> ProcessedDocument:
        """
        Loads a file, extracts its content, and splits it into chunks.

        Args:
            file_path: The path to the file to be processed.

        Returns:
            A ProcessedDocument containing the file's metadata and a list of chunks.
            
        Raises:
            ValueError: If the file type is not supported.
        """
        if not file_path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        file_extension = file_path.suffix.lower()
        
        # Handle HTML separately
        if file_extension in [".html", ".htm"]:
            raw_text = self.html_processor.extract_text(file_path.read_text(encoding='utf-8'))
        else:
            reader = self.file_readers.get(file_extension)
            if not reader:
                raise ValueError(f"Unsupported file type: {file_extension}")
            # LlamaIndex readers return a list of Document objects
            llama_docs = reader.load_data(file=file_path)
            raw_text = "\n\n".join([doc.get_content() for doc in llama_docs])

        # Split the text into chunks
        text_chunks = self.text_splitter.split_text(raw_text)
        
        # Create metadata
        doc_id, file_metadata = self._create_file_metadata(file_path)

        # Create structured Chunk objects
        chunks = []
        for i, text_chunk in enumerate(text_chunks):
            chunk_id = f"{doc_id}_chunk_{i}"
            chunk_metadata = {
                "doc_id": doc_id,
                "filename": file_path.name,
                "chunk_index": i
            }
            chunks.append(Chunk(id=chunk_id, text=text_chunk, metadata=chunk_metadata))

        logger.info(f"Processed '{file_path.name}' into {len(chunks)} chunks.")
        
        return ProcessedDocument(
            doc_id=doc_id,
            filename=file_path.name,
            metadata=file_metadata,
            chunks=chunks
        )

    def _create_file_metadata(self, file_path: Path) -> tuple[str, Dict[str, Any]]:
        """Creates a unique ID and extracts metadata from a file."""
        file_hash = self._calculate_file_hash(file_path)
        doc_id = str(file_hash) # Use hash for a stable ID
        
        file_stat = file_path.stat()
        mime_type, _ = mimetypes.guess_type(file_path)
        
        metadata = {
            "source": file_path.name,
            "file_path": str(file_path),
            "file_size": file_stat.st_size,
            "file_hash": file_hash,
            "mime_type": mime_type,
            "created_at": file_stat.st_ctime,
            "modified_at": file_stat.st_mtime,
        }
        return doc_id, metadata

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculates the SHA-256 hash of a file."""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()

def create_default_processor() -> DocumentProcessor:
    """Factory function to create a default DocumentProcessor."""
    return DocumentProcessor() 