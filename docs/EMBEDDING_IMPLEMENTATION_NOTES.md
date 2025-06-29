# Multi-Format Embedding Implementation Notes

## Implementation Status: ✅ COMPLETE (Phase 1)

**Priority formats implemented**: TXT, PDF, HTML  
**Architecture**: Modular document processor system with factory pattern  
**Testing**: Separate test tenant isolation strategy  
**Dependencies**: selectolax added for fast HTML processing  

## Key Decisions Made

### 1. HTML Processor: selectolax vs beautifulsoup4
**Decision**: Use selectolax  
**Rationale**: 
- 5-10x faster performance for text extraction
- 50% less memory usage
- Simpler API for our use case
- Removes beautifulsoup4 from dependencies (cleanup goal)

### 2. Performance/Memory Targets
**Decision**: Not prioritized for RTX 5070 local development  
**Notes**: Focus on functionality and modularity first. Performance optimization can be done later if needed.

### 3. Test Data Isolation 
**Decision**: Separate test tenant approach  
**Implementation**: `TEST_TENANT_ID = uuid4()` for complete isolation

### 4. Dependency Management
**Changes made**:
- ❌ Removed from requirements-base.txt: `unstructured`, `beautifulsoup4`, `pandas`
- ✅ Added to requirements.txt: `selectolax>=0.3.17`
- ✅ Kept heavy dependencies: `pypdf`, `python-docx` in requirements-base.txt

## Architecture Overview

```
src/backend/services/document_processing/
├── __init__.py                     # Public interface
├── base.py                         # Abstract base classes
├── factory.py                      # Processor factory
└── processors/
    ├── __init__.py
    ├── text_processor.py          # Plain text (.txt)
    ├── pdf_processor.py           # PDF files (.pdf)
    └── html_processor.py          # HTML files (.html, .htm)
```

## Implementation Details

### Base Classes
- `DocumentProcessor`: Abstract base with `extract_text()`, `extract_metadata()`, `process_document()`
- `DocumentChunk`: Data class for processed chunks
- `ProcessedDocument`: Container for full document processing results

### Factory Pattern
- `DocumentProcessorFactory`: Routes file extensions to appropriate processors
- Extensible: Easy to add new formats by registering processors
- Graceful fallbacks: Returns None for unsupported formats

### Integration Points
- `EmbeddingService._extract_text()`: Updated to use new processors first, fallback to legacy
- Backward compatibility: Existing functionality preserved
- Modular testing: Each processor can be tested independently

## File Format Support

| Format | Extensions | Processor | Status | Features |
|--------|------------|-----------|--------|----------|
| Text | .txt | TextProcessor | ✅ | Encoding detection, basic stats |
| PDF | .pdf | PDFProcessor | ✅ | Page markers, metadata extraction |
| HTML | .html, .htm | HTMLProcessor | ✅ | Structured text, meta tags, selectolax |

## Test Strategy

### Test Files Created
- `scripts/test_embedding_pipeline.py`: Comprehensive test suite
- Tests processor isolation, embedding service integration
- Creates temporary test files for each format

### Test Tenant Isolation
- Uses unique UUID for test tenant
- Complete isolation from production data
- Easy cleanup by removing test tenant

## Next Steps (Future Phases)

### Phase 2: Additional Formats
- PowerPoint (.ppt, .pptx) - requires `python-pptx`
- Excel (.xls, .xlsx) - requires `openpyxl`
- Word (.doc, .docx) - already supported via existing code

### Phase 3: Enhanced Features
- Better chunking strategies per format type
- Metadata-aware embedding generation
- Quality testing framework
- Performance optimization

### Phase 4: Production Deployment
- Monitoring and alerting
- Regular quality tests
- Performance benchmarks

## Testing Commands

```bash
# Test new processors
python scripts/test_embedding_pipeline.py

# Test with existing delta sync
python scripts/delta-sync.py

# Run in Docker
docker exec rag_backend python scripts/test_embedding_pipeline.py
```

## Performance Notes

For local RTX 5070 development:
- No specific performance targets set
- Memory usage not a concern 
- Focus on functionality and modularity
- Optimization can be added later if needed

## Dependencies Impact

**Removed from requirements-base.txt** (~200MB saved):
- unstructured>=0.17.0
- beautifulsoup4==4.13.4  
- pandas==2.2.3

**Added to requirements.txt**:
- selectolax>=0.3.17 (~2MB)

**Net savings**: ~198MB in Docker images