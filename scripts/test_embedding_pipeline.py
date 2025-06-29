#!/usr/bin/env python3
"""
Test script for multi-format embedding generation.
"""

import sys
import asyncio
import tempfile
from pathlib import Path
from uuid import uuid4

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.backend.database import AsyncSessionLocal
from src.backend.services.document_processing.factory import DocumentProcessorFactory
from src.backend.services.embedding_service import EmbeddingService

# Test tenant for embedding tests
TEST_TENANT_ID = uuid4()

async def create_test_files():
    """Create test files for different formats."""
    test_dir = Path(tempfile.mkdtemp(prefix="embedding_test_"))
    
    # Create TXT file
    txt_file = test_dir / "test.txt"
    txt_file.write_text("This is a test document for embedding generation. It contains multiple sentences to test chunking.")
    
    # Create HTML file
    html_file = test_dir / "test.html"
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Document</title>
        <meta name="description" content="Test HTML for embedding">
    </head>
    <body>
        <h1>Main Heading</h1>
        <p>This is the first paragraph with important content.</p>
        <p>This is the second paragraph with more information.</p>
        <ul>
            <li>First list item</li>
            <li>Second list item</li>
        </ul>
    </body>
    </html>
    """
    html_file.write_text(html_content)
    
    return test_dir, [txt_file, html_file]

async def test_document_processors():
    """Test document processors individually."""
    print("🧪 Testing Document Processors")
    print("-" * 50)
    
    test_dir, test_files = await create_test_files()
    
    for file_path in test_files:
        extension = file_path.suffix
        print(f"\n📄 Testing {extension} file: {file_path.name}")
        
        # Test if processor exists
        processor = DocumentProcessorFactory.get_processor(str(file_path))
        if not processor:
            print(f"   ❌ No processor for {extension}")
            continue
        
        print(f"   ✅ Processor: {processor.__class__.__name__}")
        
        # Test text extraction
        try:
            text = processor.extract_text(str(file_path))
            print(f"   📝 Text length: {len(text)} characters")
            print(f"   📝 Preview: {text[:100]}...")
        except Exception as e:
            print(f"   ❌ Text extraction failed: {e}")
            continue
        
        # Test metadata extraction
        try:
            metadata = processor.extract_metadata(str(file_path))
            print(f"   📊 Metadata keys: {list(metadata.keys())}")
        except Exception as e:
            print(f"   ❌ Metadata extraction failed: {e}")
        
        # Test document processing
        try:
            processed_doc = processor.process_document(str(file_path), chunk_size=200)
            print(f"   📦 Chunks created: {processed_doc.total_chunks}")
            if processed_doc.chunks:
                print(f"   📦 First chunk: {processed_doc.chunks[0].content[:50]}...")
        except Exception as e:
            print(f"   ❌ Document processing failed: {e}")

async def test_embedding_service_integration():
    """Test integration with embedding service."""
    print("\n🔗 Testing Embedding Service Integration")
    print("-" * 50)
    
    test_dir, test_files = await create_test_files()
    
    async with AsyncSessionLocal() as session:
        embedding_service = EmbeddingService(session)
        
        for file_path in test_files:
            extension = file_path.suffix
            print(f"\n📄 Testing {extension} with EmbeddingService")
            
            try:
                # Test text extraction via embedding service
                text = await embedding_service._extract_text(str(file_path), None)
                print(f"   ✅ Text extracted: {len(text)} characters")
                print(f"   📝 Preview: {text[:100]}...")
                
            except Exception as e:
                print(f"   ❌ Embedding service extraction failed: {e}")

async def test_supported_extensions():
    """Test supported extensions."""
    print("\n📋 Supported File Extensions")
    print("-" * 50)
    
    extensions = DocumentProcessorFactory.supported_extensions()
    print(f"Supported extensions: {extensions}")
    
    for ext in extensions:
        processor_class = DocumentProcessorFactory.get_processor_for_extension(ext)
        print(f"  {ext}: {processor_class.__name__ if processor_class else 'None'}")

async def main():
    """Run all embedding tests."""
    print("🚀 Multi-Format Embedding Generation Tests")
    print("=" * 60)
    
    try:
        await test_supported_extensions()
        await test_document_processors()
        await test_embedding_service_integration()
        
        print("\n" + "=" * 60)
        print("✅ All tests completed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())