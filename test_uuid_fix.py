#!/usr/bin/env python3
"""Test script to validate the UUID fix for document processing."""

import sys
import uuid
from pathlib import Path

# Add the src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_uuid_conversion():
    """Test that we can resolve 'default' tenant to its UUID."""
    from src.backend.db.session import get_db
    from src.backend.core.tenant_manager import get_tenant_manager
    
    # Test tenant UUID resolution
    db = next(get_db())
    tenant_manager = get_tenant_manager(db)
    
    print("Testing tenant UUID resolution...")
    tenant_uuid = tenant_manager.get_tenant_uuid("default")
    
    if tenant_uuid:
        print(f"✅ Successfully resolved 'default' to UUID: {tenant_uuid}")
        
        # Validate it's a proper UUID
        try:
            uuid_obj = uuid.UUID(tenant_uuid)
            print(f"✅ UUID is valid: {uuid_obj}")
            return True
        except ValueError as e:
            print(f"❌ Invalid UUID format: {e}")
            return False
    else:
        print("❌ Failed to resolve 'default' tenant")
        return False

def test_document_creation():
    """Test document creation with resolved UUID."""
    from src.backend.models.document import create_document_from_file
    from src.backend.db.session import get_db
    from src.backend.core.tenant_manager import get_tenant_manager
    
    print("\nTesting document creation...")
    
    # Get tenant UUID
    db = next(get_db())
    tenant_manager = get_tenant_manager(db)
    tenant_uuid = tenant_manager.get_tenant_uuid("default")
    
    if not tenant_uuid:
        print("❌ Cannot test document creation - tenant UUID not found")
        return False
    
    try:
        # Test creating document with resolved UUID
        doc = create_document_from_file(
            tenant_id="default",  # Will be internally converted
            file_path="/tmp/test.txt",
            filename="test.txt",
            file_size=100,
            file_hash="abc123",
            tenant_uuid=tenant_uuid  # Pass the resolved UUID
        )
        
        print(f"✅ Successfully created document with tenant_id: {doc.tenant_id}")
        print(f"   Document filename: {doc.filename}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create document: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing UUID fix for document processing\n")
    
    success = True
    
    # Test 1: UUID resolution
    success &= test_uuid_conversion()
    
    # Test 2: Document creation
    success &= test_document_creation()
    
    print(f"\n{'✅ All tests passed!' if success else '❌ Some tests failed!'}")
    sys.exit(0 if success else 1) 