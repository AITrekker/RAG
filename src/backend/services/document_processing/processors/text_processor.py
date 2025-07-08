"""Text file processor."""

from typing import List, Dict, Any
from pathlib import Path
from ..base import DocumentProcessor

class TextProcessor(DocumentProcessor):
    """Processor for plain text files."""
    
    def supported_extensions(self) -> List[str]:
        return ['.txt']
    
    def extract_text(self, file_path: str) -> str:
        """Extract text from plain text file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            raise ValueError(f"Error reading text file {file_path}: {e}")
    
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract metadata from text file."""
        path = Path(file_path)
        stat = path.stat()
        
        # Read file to get basic stats
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            return {
                'file_type': 'text',
                'encoding': 'utf-8',
                'size_bytes': stat.st_size,
                'character_count': len(content),
                'line_count': content.count('\n') + 1,
                'word_count': len(content.split()),
                'modified_time': stat.st_mtime,
                'created_time': stat.st_ctime
            }
        except Exception as e:
            # Fallback metadata if file reading fails
            return {
                'file_type': 'text',
                'encoding': 'unknown',
                'size_bytes': stat.st_size,
                'modified_time': stat.st_mtime,
                'created_time': stat.st_ctime,
                'error': str(e)
            }