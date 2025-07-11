"""Factory for creating document processors."""

from typing import Dict, Type, Optional, List
from pathlib import Path
from .base import DocumentProcessor
from .processors.text_processor import TextProcessor
from .processors.pdf_processor import PDFProcessor
from .processors.html_processor import HTMLProcessor

class DocumentProcessorFactory:
    """Factory for creating appropriate document processors."""
    
    _processors: Dict[str, Type[DocumentProcessor]] = {
        '.txt': TextProcessor,
        '.pdf': PDFProcessor,
        '.html': HTMLProcessor,
        '.htm': HTMLProcessor,
    }
    
    @classmethod
    def get_processor(cls, file_path: str) -> Optional[DocumentProcessor]:
        """Get appropriate processor for file extension."""
        extension = Path(file_path).suffix.lower()
        processor_class = cls._processors.get(extension)
        
        if processor_class:
            try:
                return processor_class()
            except Exception as e:
                # Log the error but don't fail completely
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to initialize processor for {extension}: {e}")
                return None
        
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"No processor class found for extension: {extension}. Available: {list(cls._processors.keys())}")
        return None
    
    @classmethod
    def supported_extensions(cls) -> List[str]:
        """Get all supported file extensions."""
        return list(cls._processors.keys())
    
    @classmethod
    def is_supported(cls, file_path: str) -> bool:
        """Check if file extension is supported."""
        extension = Path(file_path).suffix.lower()
        return extension in cls._processors
    
    @classmethod
    def register_processor(cls, extension: str, processor_class: Type[DocumentProcessor]):
        """Register a new processor for an extension."""
        cls._processors[extension.lower()] = processor_class
    
    @classmethod
    def get_processor_for_extension(cls, extension: str) -> Optional[Type[DocumentProcessor]]:
        """Get processor class for extension without instantiation."""
        return cls._processors.get(extension.lower())