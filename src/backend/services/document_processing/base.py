"""Base classes for document processing."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dataclasses import dataclass
from pathlib import Path

@dataclass
class DocumentChunk:
    """Represents a processed document chunk."""
    content: str
    chunk_index: int
    metadata: Dict[str, Any]
    chunk_type: str = "text"

@dataclass  
class ProcessedDocument:
    """Represents a fully processed document."""
    chunks: List[DocumentChunk]
    metadata: Dict[str, Any]
    total_chunks: int
    processing_stats: Dict[str, Any]

class DocumentProcessor(ABC):
    """Abstract base class for document processors."""
    
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """Return list of supported file extensions."""
        pass
    
    @abstractmethod
    def extract_text(self, file_path: str) -> str:
        """Extract raw text from document."""
        pass
    
    @abstractmethod
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract document metadata."""
        pass
    
    def process_document(self, file_path: str, chunk_size: int = 1000) -> ProcessedDocument:
        """Process document into chunks with metadata."""
        try:
            # Extract text and metadata
            text = self.extract_text(file_path)
            metadata = self.extract_metadata(file_path)
            
            # Create chunks
            chunks = self._create_chunks(text, chunk_size)
            
            # Processing stats
            stats = {
                "original_length": len(text),
                "chunk_size": chunk_size,
                "processing_method": self.__class__.__name__
            }
            
            return ProcessedDocument(
                chunks=chunks,
                metadata=metadata,
                total_chunks=len(chunks),
                processing_stats=stats
            )
            
        except Exception as e:
            raise ValueError(f"Error processing document {file_path}: {e}")
    
    def _create_chunks(self, text: str, chunk_size: int) -> List[DocumentChunk]:
        """Create text chunks from content."""
        if not text.strip():
            return []
        
        chunks = []
        # Simple chunking for now - can be enhanced with NLTK later
        words = text.split()
        
        current_chunk = []
        current_size = 0
        chunk_index = 0
        
        for word in words:
            word_size = len(word) + 1  # +1 for space
            
            if current_size + word_size > chunk_size and current_chunk:
                # Create chunk
                chunk_content = ' '.join(current_chunk)
                chunk = DocumentChunk(
                    content=chunk_content,
                    chunk_index=chunk_index,
                    metadata={"word_count": len(current_chunk)},
                    chunk_type="text"
                )
                chunks.append(chunk)
                
                # Reset for next chunk
                current_chunk = [word]
                current_size = word_size
                chunk_index += 1
            else:
                current_chunk.append(word)
                current_size += word_size
        
        # Add final chunk
        if current_chunk:
            chunk_content = ' '.join(current_chunk)
            chunk = DocumentChunk(
                content=chunk_content,
                chunk_index=chunk_index,
                metadata={"word_count": len(current_chunk)},
                chunk_type="text"
            )
            chunks.append(chunk)
        
        return chunks