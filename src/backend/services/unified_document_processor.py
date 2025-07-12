"""
Unified Document Processor - Single LlamaIndex Path
Replaces the dual processing complexity with clean LlamaIndex-only approach
"""

import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.models.database import File
from src.backend.config.settings import get_settings

settings = get_settings()


@dataclass
class ProcessedDocument:
    """Result of document processing"""
    file_id: UUID
    chunks_created: int
    processing_method: str
    success: bool
    error_message: Optional[str] = None


class UnifiedDocumentProcessor:
    """
    Single document processor using LlamaIndex for all file types
    
    This replaces:
    - DocumentProcessorFactory with multiple processors
    - Hybrid processing decisions
    - Dual processing paths in embedding service
    
    LlamaIndex can handle ALL document types we need.
    """
    
    def __init__(self, db: AsyncSession, multitenant_rag_service):
        self.db = db
        self.rag_service = multitenant_rag_service
        self._llamaindex_available = False
        self._initialized = False
    
    async def initialize(self):
        """Initialize LlamaIndex document readers"""
        if self._initialized:
            return
            
        try:
            # Test LlamaIndex document readers
            from llama_index.readers.file import (
                PDFReader, 
                DocxReader, 
                PptxReader,
                UnstructuredReader
            )
            from llama_index.core import SimpleDirectoryReader
            
            self._llamaindex_available = True
            print("✓ LlamaIndex document readers available")
            
        except ImportError as e:
            print(f"⚠️ LlamaIndex readers not available: {e}")
            print("  Will use simple text extraction")
            self._llamaindex_available = False
        
        self._initialized = True
    
    async def process_file(
        self, 
        file_path: Path, 
        file_record: File
    ) -> ProcessedDocument:
        """
        Process any document type using LlamaIndex
        Single path for all file types - much simpler!
        """
        try:
            await self.initialize()
            
            if self._llamaindex_available:
                return await self._process_with_llamaindex(file_path, file_record)
            else:
                return await self._process_simple_fallback(file_path, file_record)
                
        except Exception as e:
            print(f"❌ Error processing file {file_path}: {e}")
            return ProcessedDocument(
                file_id=file_record.id,
                chunks_created=0,
                processing_method="error",
                success=False,
                error_message=str(e)
            )
    
    async def _process_with_llamaindex(
        self, 
        file_path: Path, 
        file_record: File
    ) -> ProcessedDocument:
        """Use LlamaIndex to process any document type"""
        try:
            from llama_index.core import SimpleDirectoryReader
            
            # LlamaIndex automatically detects file type and uses appropriate reader
            # This handles PDF, DOCX, PPTX, TXT, HTML, CSV, etc.
            documents = SimpleDirectoryReader(
                input_files=[str(file_path)],
                filename_as_id=True
            ).load_data()
            
            if not documents:
                return ProcessedDocument(
                    file_id=file_record.id,
                    chunks_created=0,
                    processing_method="llamaindex_no_content",
                    success=False,
                    error_message="No content extracted"
                )
            
            # Add document to tenant's RAG index
            # LlamaIndex handles chunking, embedding, and storage automatically
            total_content = "\n\n".join([doc.text for doc in documents])
            
            success = await self.rag_service.add_document(
                file_content=total_content,
                tenant_id=file_record.tenant_id,
                metadata={
                    'file_id': str(file_record.id),
                    'filename': file_record.filename,
                    'file_path': file_record.file_path,
                    'mime_type': file_record.mime_type,
                    'file_size': file_record.file_size
                }
            )
            
            if success:
                # Estimate chunks (LlamaIndex handles this internally)
                estimated_chunks = max(1, len(total_content) // settings.chunk_size)
                
                return ProcessedDocument(
                    file_id=file_record.id,
                    chunks_created=estimated_chunks,
                    processing_method="llamaindex_auto",
                    success=True
                )
            else:
                return ProcessedDocument(
                    file_id=file_record.id,
                    chunks_created=0,
                    processing_method="llamaindex_failed",
                    success=False,
                    error_message="Failed to add to RAG index"
                )
                
        except Exception as e:
            print(f"⚠️ LlamaIndex processing failed: {e}")
            return await self._process_simple_fallback(file_path, file_record)
    
    async def _process_simple_fallback(
        self, 
        file_path: Path, 
        file_record: File
    ) -> ProcessedDocument:
        """Simple fallback for when LlamaIndex is not available"""
        try:
            # Simple text extraction for basic file types
            content = ""
            
            if file_path.suffix.lower() == '.txt':
                content = file_path.read_text(encoding='utf-8', errors='ignore')
            elif file_path.suffix.lower() in ['.md', '.markdown']:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
            else:
                # For other file types, just use filename as content
                content = f"File: {file_record.filename}\nSize: {file_record.file_size} bytes"
            
            if content.strip():
                # Add to RAG service (will use simple fallback)
                success = await self.rag_service.add_document(
                    file_content=content,
                    tenant_id=file_record.tenant_id,
                    metadata={
                        'file_id': str(file_record.id),
                        'filename': file_record.filename,
                        'processing_method': 'simple_fallback'
                    }
                )
                
                return ProcessedDocument(
                    file_id=file_record.id,
                    chunks_created=1 if success else 0,
                    processing_method="simple_text_only",
                    success=success
                )
            else:
                return ProcessedDocument(
                    file_id=file_record.id,
                    chunks_created=0,
                    processing_method="simple_no_content",
                    success=False,
                    error_message="No text content found"
                )
                
        except Exception as e:
            print(f"❌ Simple fallback failed: {e}")
            return ProcessedDocument(
                file_id=file_record.id,
                chunks_created=0,
                processing_method="fallback_error",
                success=False,
                error_message=str(e)
            )
    
    async def process_multiple_files(
        self, 
        file_records: List[File]
    ) -> List[ProcessedDocument]:
        """Process multiple files efficiently"""
        results = []
        
        for file_record in file_records:
            try:
                file_path = Path(settings.documents_path) / file_record.file_path
                
                if not file_path.exists():
                    results.append(ProcessedDocument(
                        file_id=file_record.id,
                        chunks_created=0,
                        processing_method="file_not_found",
                        success=False,
                        error_message=f"File not found: {file_path}"
                    ))
                    continue
                
                result = await self.process_file(file_path, file_record)
                results.append(result)
                
            except Exception as e:
                results.append(ProcessedDocument(
                    file_id=file_record.id,
                    chunks_created=0,
                    processing_method="processing_error",
                    success=False,
                    error_message=str(e)
                ))
        
        return results
    
    def get_supported_file_types(self) -> List[str]:
        """Get list of supported file extensions"""
        if self._llamaindex_available:
            # LlamaIndex supports many file types
            return [
                '.txt', '.md', '.markdown',
                '.pdf', '.docx', '.doc', 
                '.pptx', '.ppt',
                '.html', '.htm',
                '.csv', '.tsv',
                '.json', '.xml'
            ]
        else:
            # Simple fallback only supports text
            return ['.txt', '.md', '.markdown']
    
    async def get_processing_stats(self) -> Dict[str, Any]:
        """Get statistics about document processing"""
        return {
            'llamaindex_available': self._llamaindex_available,
            'supported_file_types': self.get_supported_file_types(),
            'processing_method': 'llamaindex_auto' if self._llamaindex_available else 'simple_fallback'
        }


# Factory function for dependency injection
async def get_unified_document_processor(
    db: AsyncSession,
    multitenant_rag_service
) -> UnifiedDocumentProcessor:
    """Factory function to create unified document processor"""
    processor = UnifiedDocumentProcessor(db, multitenant_rag_service)
    await processor.initialize()
    return processor