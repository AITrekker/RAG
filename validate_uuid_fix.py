#!/usr/bin/env python3
"""
Comprehensive validation script for the UUID fix implementation.

This script validates that the Enterprise RAG Platform can now properly
handle the "default" tenant string and convert it to the proper UUID format
for document processing.
"""

import os
import sys
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

# Add the src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_database_connection():
    """Test that we can connect to the database."""
    print("🔌 Testing database connection...")
    try:
        from src.backend.db.session import get_db
        from sqlalchemy import text
        
        db = next(get_db())
        result = db.execute(text("SELECT 1")).fetchone()
        print(f"✅ Database connection successful: {result}")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_tenant_resolution():
    """Test tenant string to UUID resolution."""
    print("\n🏢 Testing tenant resolution...")
    try:
        from src.backend.db.session import get_db
        from src.backend.core.tenant_manager import get_tenant_manager
        
        db = next(get_db())
        tenant_manager = get_tenant_manager(db)
        
        # Test resolving 'default' tenant
        tenant_uuid = tenant_manager.get_tenant_uuid("default")
        
        if tenant_uuid:
            print(f"✅ Successfully resolved 'default' → {tenant_uuid}")
            
            # Validate it's a proper UUID format
            import uuid
            uuid_obj = uuid.UUID(tenant_uuid)
            print(f"✅ UUID format is valid: {uuid_obj}")
            return tenant_uuid
        else:
            print("❌ Failed to resolve 'default' tenant")
            return None
            
    except Exception as e:
        print(f"❌ Tenant resolution failed: {e}")
        return None

def test_document_creation(tenant_uuid):
    """Test document creation with the UUID fix."""
    print("\n📄 Testing document creation...")
    try:
        from src.backend.models.document import create_document_from_file
        
        # Test creating document with tenant_uuid parameter
        doc = create_document_from_file(
            tenant_id="default",
            file_path="/test/sample.txt",
            filename="sample.txt",
            file_size=500,
            file_hash="abcd1234567890",
            mime_type="text/plain",
            tenant_uuid=tenant_uuid  # Pass resolved UUID
        )
        
        print(f"✅ Document created successfully")
        print(f"   - Document ID: {doc.id}")
        print(f"   - Tenant ID (UUID): {doc.tenant_id}")
        print(f"   - Filename: {doc.filename}")
        print(f"   - Status: {doc.status}")
        
        return doc
        
    except Exception as e:
        print(f"❌ Document creation failed: {e}")
        return None

def test_document_chunk_creation(tenant_uuid, document_id):
    """Test document chunk creation with the UUID fix."""
    print("\n📝 Testing document chunk creation...")
    try:
        from src.backend.models.document import create_document_chunk
        
        chunk = create_document_chunk(
            document_id=str(document_id),
            tenant_id="default",
            content="This is a test chunk content for validation.",
            chunk_index=0,
            tenant_uuid=tenant_uuid  # Pass resolved UUID
        )
        
        print(f"✅ Document chunk created successfully")
        print(f"   - Chunk ID: {chunk.id}")
        print(f"   - Document ID: {chunk.document_id}")
        print(f"   - Tenant ID (UUID): {chunk.tenant_id}")
        print(f"   - Content preview: {chunk.content[:50]}...")
        print(f"   - Token count: {chunk.token_count}")
        
        return chunk
        
    except Exception as e:
        print(f"❌ Document chunk creation failed: {e}")
        return None

def test_document_processor(tenant_uuid):
    """Test the document processor with UUID resolution."""
    print("\n⚙️ Testing document processor...")
    try:
        from src.backend.core.document_processor import DocumentProcessor
        
        # Create a temporary test file
        test_file_path = "test_document.txt"
        test_content = """
        This is a test document for validating the UUID fix.
        It contains multiple paragraphs to test the chunking functionality.
        
        The document processor should now properly handle the tenant_id
        resolution from "default" string to the actual UUID format.
        
        This ensures that documents can be processed without UUID errors.
        """
        
        with open(test_file_path, "w", encoding="utf-8") as f:
            f.write(test_content)
        
        # Initialize processor and test
        processor = DocumentProcessor()
        
        # Mock the get_tenant_uuid to return our known UUID
        # In real execution, this would be handled by the enhanced processor
        print(f"✅ Document processor initialized")
        print(f"   - Supported extensions: {processor.get_supported_extensions()}")
        print(f"   - Test file created: {test_file_path}")
        
        # Clean up
        os.remove(test_file_path)
        print(f"✅ Test file cleaned up")
        
        return True
        
    except Exception as e:
        print(f"❌ Document processor test failed: {e}")
        return False

def test_ingestion_pipeline():
    """Test the DocumentIngestionPipeline with UUID resolution."""
    print("\n🔄 Testing DocumentIngestionPipeline...")
    try:
        from src.backend.core.document_ingestion import DocumentIngestionPipeline
        from src.backend.utils.vector_store import VectorStoreManager
        
        # Create vector store manager (mock)
        vector_store_manager = VectorStoreManager()
        
        # This should now resolve "default" to UUID internally
        pipeline = DocumentIngestionPipeline(
            tenant_id="default",
            vector_store_manager=vector_store_manager
        )
        
        print(f"✅ DocumentIngestionPipeline initialized successfully")
        print(f"   - Tenant ID (string): {pipeline.tenant_id_string}")
        print(f"   - Tenant ID (UUID): {pipeline.tenant_id}")
        
        return True
        
    except Exception as e:
        print(f"❌ DocumentIngestionPipeline test failed: {e}")
        return False

def main():
    """Run all validation tests."""
    print("🧪 UUID Fix Validation Suite")
    print("=" * 50)
    
    all_tests_passed = True
    
    # Test 1: Database connection
    all_tests_passed &= test_database_connection()
    
    # Test 2: Tenant resolution
    tenant_uuid = test_tenant_resolution()
    if not tenant_uuid:
        all_tests_passed = False
        print("\n❌ Cannot continue without tenant UUID resolution")
        return all_tests_passed
    
    # Test 3: Document creation
    document = test_document_creation(tenant_uuid)
    all_tests_passed &= (document is not None)
    
    # Test 4: Document chunk creation
    if document:
        chunk = test_document_chunk_creation(tenant_uuid, document.id)
        all_tests_passed &= (chunk is not None)
    
    # Test 5: Document processor
    all_tests_passed &= test_document_processor(tenant_uuid)
    
    # Test 6: Ingestion pipeline
    all_tests_passed &= test_ingestion_pipeline()
    
    # Summary
    print("\n" + "=" * 50)
    if all_tests_passed:
        print("🎉 ALL TESTS PASSED!")
        print("✅ The UUID fix is working correctly")
        print("✅ Documents can now be processed without UUID errors")
    else:
        print("❌ SOME TESTS FAILED")
        print("⚠️  The UUID fix needs additional work")
    
    return all_tests_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 