# Multi-Format Embedding Generation Implementation Plan

## Executive Summary

This plan outlines the implementation of a comprehensive, modular embedding generation system that supports multiple file formats (TXT, PDF, DOC/DOCX, PPT/PPTX, XLS/XLSX, HTML) while integrating seamlessly with both the sync pipeline and standalone testing workflows.

## Architecture Overview

### Core Design Principles
1. **Modular Architecture**: Each file type has its own processor
2. **Interface-Based Design**: Common interfaces for consistency
3. **Hybrid Storage**: PostgreSQL for metadata, Qdrant for vectors
4. **Pipeline Integration**: Works with existing sync_service.py
5. **Standalone Capability**: Can be used independently for testing
6. **Test Data Isolation**: Separate test collections for quality assurance

## Current State Analysis

### Existing Implementation
- ✅ **PDF Support**: `pypdf` integration in `embedding_service.py`
- ✅ **DOC/DOCX Support**: `python-docx` integration in `embedding_service.py`
- ✅ **Text Chunking**: NLTK sentence tokenization with smart chunking
- ✅ **Embedding Generation**: sentence-transformers with `all-MiniLM-L6-v2`
- ✅ **Storage**: Hybrid PostgreSQL + Qdrant implementation
- ❌ **Missing**: PPT, XLS, HTML, comprehensive testing framework

### Required Dependencies
```python
# New dependencies needed:
python-pptx>=0.6.21        # PowerPoint processing
openpyxl>=3.1.2            # Excel processing (lighter than pandas)
beautifulsoup4>=4.13.4     # HTML processing (extract from legacy)
lxml>=4.9.0                # XML parsing for Office docs
```

## Detailed Implementation Plan

### Phase 1: Core Architecture Refactoring

#### 1.1 Document Processor Interface
```python
# src/backend/services/document_processing/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class DocumentChunk:
    content: str
    chunk_index: int
    metadata: Dict[str, Any]
    chunk_type: str = "text"  # text, table, image_caption, etc.

@dataclass  
class ProcessedDocument:
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
    
    @abstractmethod
    def process_document(self, file_path: str, chunk_size: int = 1000) -> ProcessedDocument:
        """Process document into chunks with metadata."""
        pass
```

#### 1.2 Document Processor Factory
```python
# src/backend/services/document_processing/factory.py
from typing import Dict, Type, Optional
from .base import DocumentProcessor
from .processors import (
    TextProcessor, PDFProcessor, DOCXProcessor, 
    PowerPointProcessor, ExcelProcessor, HTMLProcessor
)

class DocumentProcessorFactory:
    """Factory for creating appropriate document processors."""
    
    _processors: Dict[str, Type[DocumentProcessor]] = {
        '.txt': TextProcessor,
        '.pdf': PDFProcessor,
        '.doc': DOCXProcessor,
        '.docx': DOCXProcessor,
        '.ppt': PowerPointProcessor,
        '.pptx': PowerPointProcessor,
        '.xls': ExcelProcessor,
        '.xlsx': ExcelProcessor,
        '.html': HTMLProcessor,
        '.htm': HTMLProcessor,
    }
    
    @classmethod
    def get_processor(cls, file_path: str) -> Optional[DocumentProcessor]:
        """Get appropriate processor for file extension."""
        extension = Path(file_path).suffix.lower()
        processor_class = cls._processors.get(extension)
        return processor_class() if processor_class else None
    
    @classmethod
    def supported_extensions(cls) -> List[str]:
        """Get all supported file extensions."""
        return list(cls._processors.keys())
```

### Phase 2: File Type Processors Implementation

#### 2.1 Text Processor (Simple)
```python
# src/backend/services/document_processing/processors/text_processor.py
class TextProcessor(DocumentProcessor):
    def supported_extensions(self) -> List[str]:
        return ['.txt']
    
    def extract_text(self, file_path: str) -> str:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        stat = Path(file_path).stat()
        return {
            'file_type': 'text',
            'encoding': 'utf-8',
            'size_bytes': stat.st_size,
            'modified_time': stat.st_mtime
        }
```

#### 2.2 PowerPoint Processor (New)
```python
# src/backend/services/document_processing/processors/powerpoint_processor.py
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

class PowerPointProcessor(DocumentProcessor):
    def supported_extensions(self) -> List[str]:
        return ['.ppt', '.pptx']
    
    def extract_text(self, file_path: str) -> str:
        prs = Presentation(file_path)
        text_content = []
        
        for slide_num, slide in enumerate(prs.slides, 1):
            slide_text = []
            
            # Extract text from all shapes
            for shape in slide.shapes:
                if hasattr(shape, 'text') and shape.text.strip():
                    slide_text.append(shape.text.strip())
                
                # Handle tables
                if shape.shape_type == MSO_SHAPE_TYPE.TABLE:
                    table_text = self._extract_table_text(shape.table)
                    if table_text:
                        slide_text.append(table_text)
            
            if slide_text:
                slide_content = f"[Slide {slide_num}]\n" + '\n'.join(slide_text)
                text_content.append(slide_content)
        
        return '\n\n'.join(text_content)
    
    def _extract_table_text(self, table) -> str:
        """Extract text from PowerPoint table."""
        rows = []
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                rows.append(' | '.join(cells))
        return '\n'.join(rows) if rows else ''
    
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        prs = Presentation(file_path)
        stat = Path(file_path).stat()
        
        # Extract core properties if available
        core_props = prs.core_properties
        
        return {
            'file_type': 'powerpoint',
            'slide_count': len(prs.slides),
            'size_bytes': stat.st_size,
            'title': getattr(core_props, 'title', '') or '',
            'author': getattr(core_props, 'author', '') or '',
            'subject': getattr(core_props, 'subject', '') or '',
            'created': getattr(core_props, 'created', None),
            'modified': getattr(core_props, 'modified', None) or stat.st_mtime
        }
```

#### 2.3 Excel Processor (New)
```python
# src/backend/services/document_processing/processors/excel_processor.py
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

class ExcelProcessor(DocumentProcessor):
    def supported_extensions(self) -> List[str]:
        return ['.xls', '.xlsx']
    
    def extract_text(self, file_path: str) -> str:
        try:
            workbook = load_workbook(file_path, data_only=True, read_only=True)
            text_content = []
            
            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                sheet_text = [f"[Sheet: {sheet_name}]"]
                
                # Extract cell values row by row
                rows_with_data = []
                for row in sheet.iter_rows(values_only=True):
                    # Filter out None values and convert to strings
                    cell_values = [str(cell).strip() for cell in row if cell is not None]
                    if cell_values:  # Only add non-empty rows
                        rows_with_data.append(' | '.join(cell_values))
                
                if rows_with_data:
                    sheet_text.extend(rows_with_data)
                    text_content.append('\n'.join(sheet_text))
            
            workbook.close()
            return '\n\n'.join(text_content)
            
        except InvalidFileException as e:
            raise ValueError(f"Invalid Excel file: {e}")
        except Exception as e:
            raise ValueError(f"Error processing Excel file: {e}")
    
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        workbook = load_workbook(file_path, read_only=True)
        stat = Path(file_path).stat()
        
        # Extract properties if available
        props = workbook.properties
        
        metadata = {
            'file_type': 'excel',
            'sheet_count': len(workbook.sheetnames),
            'sheet_names': workbook.sheetnames,
            'size_bytes': stat.st_size,
            'title': getattr(props, 'title', '') or '',
            'creator': getattr(props, 'creator', '') or '',
            'description': getattr(props, 'description', '') or '',
            'created': getattr(props, 'created', None),
            'modified': getattr(props, 'modified', None) or stat.st_mtime
        }
        
        workbook.close()
        return metadata
```

#### 2.4 HTML Processor (Extracted from Legacy)
```python
# src/backend/services/document_processing/processors/html_processor.py
from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin, urlparse

class HTMLProcessor(DocumentProcessor):
    def supported_extensions(self) -> List[str]:
        return ['.html', '.htm']
    
    def extract_text(self, file_path: str) -> str:
        """Extract text from HTML file."""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            html_content = f.read()
        
        return self._parse_html_content(html_content)
    
    def _parse_html_content(self, html_content: str) -> str:
        """Parse HTML content and extract meaningful text."""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "meta", "link"]):
            script.decompose()
        
        # Extract text with structure preservation
        text_parts = []
        
        # Title
        title = soup.find('title')
        if title and title.get_text().strip():
            text_parts.append(f"Title: {title.get_text().strip()}")
        
        # Headers
        for header in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            if header.get_text().strip():
                text_parts.append(f"[{header.name.upper()}] {header.get_text().strip()}")
        
        # Paragraphs and other content
        for elem in soup.find_all(['p', 'div', 'article', 'section']):
            text = elem.get_text().strip()
            if text and len(text) > 20:  # Filter out very short content
                text_parts.append(text)
        
        # Lists
        for ul in soup.find_all(['ul', 'ol']):
            items = [li.get_text().strip() for li in ul.find_all('li') if li.get_text().strip()]
            if items:
                text_parts.append('• ' + '\n• '.join(items))
        
        return '\n\n'.join(text_parts)
    
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, 'html.parser')
        stat = Path(file_path).stat()
        
        # Extract meta tags
        meta_description = soup.find('meta', attrs={'name': 'description'})
        meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
        meta_author = soup.find('meta', attrs={'name': 'author'})
        
        return {
            'file_type': 'html',
            'title': soup.title.get_text() if soup.title else '',
            'description': meta_description.get('content', '') if meta_description else '',
            'keywords': meta_keywords.get('content', '') if meta_keywords else '',
            'author': meta_author.get('content', '') if meta_author else '',
            'size_bytes': stat.st_size,
            'modified_time': stat.st_mtime,
            'links_count': len(soup.find_all('a')),
            'images_count': len(soup.find_all('img'))
        }
```

### Phase 3: Enhanced Embedding Service Integration

#### 3.1 Updated Embedding Service
```python
# src/backend/services/embedding_service.py (enhanced)
from .document_processing.factory import DocumentProcessorFactory
from .document_processing.base import ProcessedDocument, DocumentChunk

class EmbeddingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        # ... existing initialization ...
        
    async def process_file_for_embeddings(
        self, 
        file_path: str, 
        file_id: UUID, 
        tenant_id: UUID
    ) -> Dict[str, Any]:
        """Enhanced file processing with multi-format support."""
        
        # Get appropriate processor
        processor = DocumentProcessorFactory.get_processor(file_path)
        if not processor:
            raise ValueError(f"Unsupported file type: {Path(file_path).suffix}")
        
        try:
            # Process document
            processed_doc = processor.process_document(file_path)
            
            # Generate embeddings for each chunk
            embeddings_created = 0
            collection_name = f"tenant_{tenant_id}_documents"
            
            for chunk in processed_doc.chunks:
                # Generate embedding
                embedding = self._generate_embedding(chunk.content)
                
                # Create Qdrant point
                point_id = uuid4()
                payload = {
                    "chunk_id": str(uuid4()),
                    "file_id": str(file_id),
                    "tenant_id": str(tenant_id),
                    "chunk_index": chunk.chunk_index,
                    "chunk_type": chunk.chunk_type,
                    "metadata": chunk.metadata
                }
                
                # Store in Qdrant
                await self._store_in_qdrant(collection_name, point_id, embedding, payload)
                
                # Store chunk metadata in PostgreSQL
                await self._store_chunk_metadata(
                    file_id, tenant_id, chunk, point_id, collection_name
                )
                
                embeddings_created += 1
            
            return {
                "chunks_processed": processed_doc.total_chunks,
                "embeddings_created": embeddings_created,
                "processing_stats": processed_doc.processing_stats,
                "file_metadata": processed_doc.metadata
            }
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            raise
```

### Phase 4: Testing Framework Design

#### 4.1 Test Data Isolation Strategy

**Option A: Separate Test Tenant (Recommended)**
```python
# Advantages:
# - Complete isolation using existing tenant system
# - Can test full pipeline including tenant permissions
# - Easy cleanup (delete tenant)
# - Realistic testing environment

TEST_TENANT_ID = "test-embeddings-00000000-0000-0000-0000-000000000000"
TEST_COLLECTION = f"tenant_{TEST_TENANT_ID}_documents"
```

**Option B: Separate Qdrant Collections**
```python
# Alternative approach:
TEST_COLLECTIONS = {
    "embedding_quality": "test_embedding_quality",
    "performance_benchmark": "test_performance_benchmark", 
    "regression_tests": "test_regression_suite"
}
```

#### 4.2 Test Suite Structure
```python
# tests/embedding_tests/
├── test_data/
│   ├── samples/
│   │   ├── document.pdf
│   │   ├── presentation.pptx
│   │   ├── spreadsheet.xlsx
│   │   ├── webpage.html
│   │   └── plaintext.txt
│   └── expected_outputs/
│       ├── document_chunks.json
│       └── quality_benchmarks.json
├── unit_tests/
│   ├── test_text_processor.py
│   ├── test_pdf_processor.py
│   ├── test_powerpoint_processor.py
│   ├── test_excel_processor.py
│   └── test_html_processor.py
├── integration_tests/
│   ├── test_embedding_pipeline.py
│   ├── test_search_quality.py
│   └── test_performance_benchmarks.py
└── quality_tests/
    ├── test_embedding_consistency.py
    ├── test_semantic_similarity.py
    └── test_retrieval_accuracy.py
```

#### 4.3 Quality Testing Framework
```python
# tests/embedding_tests/quality_tests/embedding_quality_suite.py
class EmbeddingQualityTestSuite:
    """Comprehensive embedding quality testing."""
    
    def __init__(self, test_tenant_id: UUID):
        self.test_tenant_id = test_tenant_id
        self.embedding_service = EmbeddingService()
        
    async def run_quality_tests(self) -> Dict[str, Any]:
        """Run all quality tests and return results."""
        results = {
            "consistency_test": await self.test_embedding_consistency(),
            "similarity_test": await self.test_semantic_similarity(),
            "retrieval_test": await self.test_retrieval_accuracy(),
            "performance_test": await self.test_performance_benchmarks()
        }
        return results
    
    async def test_embedding_consistency(self) -> Dict[str, Any]:
        """Test that same content produces same embeddings."""
        test_content = "This is a test document for consistency checking."
        
        embedding1 = self.embedding_service._generate_embedding(test_content)
        embedding2 = self.embedding_service._generate_embedding(test_content)
        
        similarity = self._cosine_similarity(embedding1, embedding2)
        
        return {
            "passed": similarity > 0.999,  # Should be nearly identical
            "similarity_score": similarity,
            "threshold": 0.999
        }
    
    async def test_semantic_similarity(self) -> Dict[str, Any]:
        """Test semantic similarity between related content."""
        similar_docs = [
            "Machine learning is a subset of artificial intelligence.",
            "AI includes machine learning as one of its components.",
            "Artificial intelligence encompasses machine learning techniques."
        ]
        
        embeddings = [self.embedding_service._generate_embedding(doc) for doc in similar_docs]
        
        # Test pairwise similarities
        similarities = []
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                sim = self._cosine_similarity(embeddings[i], embeddings[j])
                similarities.append(sim)
        
        avg_similarity = sum(similarities) / len(similarities)
        
        return {
            "passed": avg_similarity > 0.7,  # Related content should be similar
            "average_similarity": avg_similarity,
            "threshold": 0.7,
            "individual_similarities": similarities
        }
```

### Phase 5: Regular Testing & Monitoring

#### 5.1 Automated Test Execution
```python
# scripts/test_embeddings.py
"""Regular embedding quality testing script."""

async def run_daily_embedding_tests():
    """Run daily embedding quality tests."""
    
    # Initialize test suite
    test_suite = EmbeddingQualityTestSuite(TEST_TENANT_ID)
    
    # Run tests
    results = await test_suite.run_quality_tests()
    
    # Log results
    logger.info("Daily embedding quality test results:")
    for test_name, result in results.items():
        status = "PASS" if result["passed"] else "FAIL"
        logger.info(f"  {test_name}: {status}")
        
        if not result["passed"]:
            logger.warning(f"    Details: {result}")
    
    # Store results in monitoring system
    await store_test_results(results)
    
    # Alert if tests fail
    failed_tests = [name for name, result in results.items() if not result["passed"]]
    if failed_tests:
        await send_alert(f"Embedding tests failed: {failed_tests}")

if __name__ == "__main__":
    asyncio.run(run_daily_embedding_tests())
```

#### 5.2 Performance Monitoring
```python
# Monitoring metrics to track:
EMBEDDING_METRICS = {
    "processing_time_per_file": "milliseconds",
    "chunks_per_second": "rate",
    "embedding_generation_time": "milliseconds", 
    "memory_usage_peak": "bytes",
    "gpu_utilization": "percentage",
    "storage_efficiency": "bytes_per_chunk"
}
```

## Implementation Timeline

### Week 1: Foundation
- [ ] Implement base DocumentProcessor interface
- [ ] Create DocumentProcessorFactory
- [ ] Refactor existing PDF/DOCX processors to use new interface
- [ ] Add new dependencies to requirements

### Week 2: New Processors
- [ ] Implement PowerPointProcessor
- [ ] Implement ExcelProcessor  
- [ ] Implement HTMLProcessor
- [ ] Extract and refactor TextProcessor

### Week 3: Integration
- [ ] Update EmbeddingService to use new processors
- [ ] Integrate with existing sync pipeline
- [ ] Update API endpoints for multi-format support
- [ ] Create test data isolation (test tenant)

### Week 4: Testing Framework
- [ ] Build comprehensive test suite
- [ ] Implement quality testing framework
- [ ] Create automated test runner
- [ ] Set up monitoring and alerting

### Week 5: Performance & Optimization
- [ ] Performance testing and optimization
- [ ] Memory usage optimization
- [ ] Error handling improvements
- [ ] Documentation and deployment

## Success Metrics

### Functionality Metrics
- **File Format Coverage**: 6 formats supported (TXT, PDF, DOC/DOCX, PPT/PPTX, XLS/XLSX, HTML)
- **Processing Success Rate**: >95% successful processing across all formats
- **Text Extraction Quality**: Manual review of sample outputs

### Performance Metrics
- **Processing Speed**: <5 seconds per MB for most file types
- **Memory Efficiency**: <2GB peak memory usage for large files
- **Embedding Quality**: >0.8 average similarity for semantically related content

### Integration Metrics
- **Sync Pipeline Integration**: Zero breaking changes to existing workflow
- **API Compatibility**: All existing endpoints continue to work
- **Test Coverage**: >90% code coverage for new processors

## Risk Mitigation

### Technical Risks
1. **Dependency Conflicts**: Pin specific versions, test thoroughly
2. **Memory Usage**: Implement streaming for large files
3. **Format Variations**: Extensive testing with real-world files
4. **Performance Degradation**: Profiling and optimization

### Operational Risks
1. **Production Impact**: Gradual rollout with feature flags
2. **Data Quality**: Comprehensive testing framework
3. **Monitoring**: Real-time quality metrics
4. **Rollback Plan**: Keep existing processors as fallback

## Questions for Review

1. **Testing Strategy**: Do you prefer separate test tenant or separate Qdrant collections?
2. **File Type Priority**: Should we implement all formats at once or prioritize certain types?
3. **Performance Targets**: Are the proposed performance metrics acceptable?
4. **Integration Approach**: Should new processors be opt-in initially or replace existing ones immediately?
5. **Error Handling**: How should we handle files that fail processing (retry, skip, alert)?

This plan provides a comprehensive, modular approach to multi-format embedding generation while maintaining system stability and enabling thorough testing. The phased implementation ensures minimal risk while delivering maximum value.