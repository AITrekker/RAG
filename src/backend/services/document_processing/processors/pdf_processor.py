"""PDF file processor."""

from typing import List, Dict, Any
from pathlib import Path
import pypdf
from ..base import DocumentProcessor

class PDFProcessor(DocumentProcessor):
    """Processor for PDF files."""
    
    def supported_extensions(self) -> List[str]:
        return ['.pdf']
    
    def extract_text(self, file_path: str) -> str:
        """Extract text from PDF file."""
        try:
            text_content = []
            
            with open(file_path, 'rb') as file:
                pdf_reader = pypdf.PdfReader(file)
                
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    try:
                        page_text = page.extract_text()
                        if page_text.strip():
                            # Add page marker for better chunking context
                            text_content.append(f"[Page {page_num}]\n{page_text.strip()}")
                    except Exception as e:
                        # Skip problematic pages but continue processing
                        text_content.append(f"[Page {page_num} - Error extracting text: {e}]")
                        continue
            
            return '\n\n'.join(text_content)
            
        except Exception as e:
            raise ValueError(f"Error processing PDF {file_path}: {e}")
    
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract metadata from PDF file."""
        path = Path(file_path)
        stat = path.stat()
        
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = pypdf.PdfReader(file)
                
                # Extract PDF metadata
                pdf_info = pdf_reader.metadata or {}
                
                metadata = {
                    'file_type': 'pdf',
                    'page_count': len(pdf_reader.pages),
                    'size_bytes': stat.st_size,
                    'modified_time': stat.st_mtime,
                    'created_time': stat.st_ctime,
                    'title': pdf_info.get('/Title', ''),
                    'author': pdf_info.get('/Author', ''),
                    'subject': pdf_info.get('/Subject', ''),
                    'creator': pdf_info.get('/Creator', ''),
                    'producer': pdf_info.get('/Producer', ''),
                    'creation_date': pdf_info.get('/CreationDate', ''),
                    'modification_date': pdf_info.get('/ModDate', ''),
                    'encrypted': pdf_reader.is_encrypted
                }
                
                # Clean up metadata values
                for key, value in metadata.items():
                    if isinstance(value, str):
                        metadata[key] = value.strip()
                
                return metadata
                
        except Exception as e:
            # Fallback metadata if PDF reading fails
            return {
                'file_type': 'pdf',
                'size_bytes': stat.st_size,
                'modified_time': stat.st_mtime,
                'created_time': stat.st_ctime,
                'error': str(e)
            }