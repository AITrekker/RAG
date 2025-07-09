#!/usr/bin/env python3
"""
Hard Delete Tests for RAG System

Comprehensive pytest tests for hard delete functionality.
Tests the conversion from soft delete to hard delete and ensures
no constraint violations occur during file recreation.
"""

import pytest
import requests
import os
import json
import tempfile
from pathlib import Path
from typing import Dict, List, Optional
import time

# Test configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")

# Skip tests if no API key
pytestmark = pytest.mark.skipif(
    not ADMIN_API_KEY,
    reason="ADMIN_API_KEY not available"
)

@pytest.fixture
def api_headers():
    """Fixture providing API headers for requests"""
    return {
        "Authorization": f"Bearer {ADMIN_API_KEY}",
        "Content-Type": "application/json"
    }

@pytest.fixture
def admin_tenant_id():
    """Fixture providing admin tenant ID"""
    # Try to get from demo_admin_keys.json
    project_root = Path(__file__).parent.parent
    keys_file = project_root / "demo_admin_keys.json"
    
    if keys_file.exists():
        with open(keys_file, 'r') as f:
            data = json.load(f)
            return data.get("admin_tenant_id", "")
    
    # Fallback to environment
    tenant_id = os.getenv("ADMIN_TENANT_ID", "")
    if not tenant_id:
        pytest.skip("Admin tenant ID not available")
    
    return tenant_id

@pytest.fixture
def tenant_upload_dir(admin_tenant_id):
    """Fixture providing tenant upload directory"""
    project_root = Path(__file__).parent.parent
    tenant_dir = project_root / "data" / "uploads" / admin_tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    return tenant_dir

@pytest.fixture
def test_files():
    """Fixture providing test file definitions"""
    return [
        {
            "name": "hard_delete_test_1.txt",
            "content": "Test file 1 for hard delete functionality testing."
        },
        {
            "name": "hard_delete_test_2.txt",
            "content": "Test file 2 with different content for hard delete testing."
        },
        {
            "name": "unicode_test_文件.txt",
            "content": "Unicode test file: αβγ δεζ 中文 🔥 testing special characters."
        }
    ]

@pytest.fixture(autouse=True)
def cleanup_test_files(tenant_upload_dir, test_files, api_headers):
    """Auto-cleanup fixture to remove test files before and after each test"""
    # Cleanup before test
    for test_file in test_files:
        file_path = tenant_upload_dir / test_file["name"]
        if file_path.exists():
            file_path.unlink()
    
    # Additional cleanup patterns
    cleanup_patterns = [
        "hard_delete_test_*.txt",
        "unicode_test_*.txt",
        "recreation_test_*.txt",
        "batch_test_*.txt"
    ]
    
    for pattern in cleanup_patterns:
        for file_path in tenant_upload_dir.glob(pattern):
            if file_path.exists():
                file_path.unlink()
    
    # Sync to clean database
    requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=api_headers)
    
    yield
    
    # Cleanup after test
    for test_file in test_files:
        file_path = tenant_upload_dir / test_file["name"]
        if file_path.exists():
            file_path.unlink()
    
    for pattern in cleanup_patterns:
        for file_path in tenant_upload_dir.glob(pattern):
            if file_path.exists():
                file_path.unlink()
    
    # Final sync to clean database
    requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=api_headers)

def create_test_files(tenant_upload_dir: Path, test_files: List[Dict]):
    """Helper to create test files in tenant directory"""
    for test_file in test_files:
        file_path = tenant_upload_dir / test_file["name"]
        file_path.write_text(test_file["content"], encoding='utf-8')

def get_latest_sync_result(api_headers: Dict) -> Dict:
    """Helper to get the latest sync operation result"""
    response = requests.get(f"{BACKEND_URL}/api/v1/sync/history", headers=api_headers)
    assert response.status_code == 200
    
    history = response.json()
    assert "history" in history
    assert len(history["history"]) > 0
    
    return history["history"][0]

class TestHardDeleteBasic:
    """Basic hard delete functionality tests"""
    
    def test_hard_delete_single_file(self, tenant_upload_dir, test_files, api_headers):
        """Test hard delete of a single file"""
        # Create a single test file
        test_file = test_files[0]
        file_path = tenant_upload_dir / test_file["name"]
        file_path.write_text(test_file["content"], encoding='utf-8')
        
        # Sync to create file record
        response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=api_headers)
        assert response.status_code == 200
        
        sync_result = response.json()
        assert sync_result["status"] == "completed"
        
        # Verify file was created
        latest_sync = get_latest_sync_result(api_headers)
        assert latest_sync["files_added"] >= 1
        
        # Delete file from filesystem
        file_path.unlink()
        
        # Sync to hard delete from database
        response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=api_headers)
        assert response.status_code == 200
        
        sync_result = response.json()
        assert sync_result["status"] == "completed"
        
        # Verify file was hard deleted
        latest_sync = get_latest_sync_result(api_headers)
        assert latest_sync["files_deleted"] >= 1
        
        # Verify embedding chunks were also deleted
        if latest_sync["chunks_deleted"] > 0:
            assert latest_sync["chunks_deleted"] >= 1
    
    def test_hard_delete_multiple_files(self, tenant_upload_dir, test_files, api_headers):
        """Test hard delete of multiple files"""
        # Create all test files
        create_test_files(tenant_upload_dir, test_files)
        
        # Sync to create file records
        response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=api_headers)
        assert response.status_code == 200
        
        sync_result = response.json()
        assert sync_result["status"] == "completed"
        
        # Verify files were created
        latest_sync = get_latest_sync_result(api_headers)
        files_added = latest_sync["files_added"]
        assert files_added >= len(test_files)
        
        # Delete all files from filesystem
        for test_file in test_files:
            file_path = tenant_upload_dir / test_file["name"]
            if file_path.exists():
                file_path.unlink()
        
        # Sync to hard delete from database
        response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=api_headers)
        assert response.status_code == 200
        
        sync_result = response.json()
        assert sync_result["status"] == "completed"
        
        # Verify all files were hard deleted
        latest_sync = get_latest_sync_result(api_headers)
        files_deleted = latest_sync["files_deleted"]
        assert files_deleted >= len(test_files)

class TestHardDeleteRecreation:
    """Tests for file recreation after hard delete"""
    
    def test_file_recreation_no_constraints(self, tenant_upload_dir, api_headers):
        """Test that files can be recreated after hard delete without constraint violations"""
        test_file = "recreation_test_constraint.txt"
        original_content = "Original content for constraint test"
        new_content = "New content after hard delete and recreation"
        
        file_path = tenant_upload_dir / test_file
        
        # Create file
        file_path.write_text(original_content, encoding='utf-8')
        
        # Sync to create record
        response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=api_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        
        # Delete file
        file_path.unlink()
        
        # Sync to hard delete record
        response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=api_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        
        # Verify deletion
        latest_sync = get_latest_sync_result(api_headers)
        assert latest_sync["files_deleted"] >= 1
        
        # Recreate file with different content
        file_path.write_text(new_content, encoding='utf-8')
        
        # Sync to recreate record - this should NOT fail with constraint violations
        response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=api_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        
        # Verify recreation
        latest_sync = get_latest_sync_result(api_headers)
        assert latest_sync["files_added"] >= 1
    
    def test_multiple_recreation_cycles(self, tenant_upload_dir, api_headers):
        """Test multiple delete/recreate cycles for the same file"""
        test_file = "recreation_test_cycles.txt"
        file_path = tenant_upload_dir / test_file
        
        for cycle in range(3):
            content = f"Content for cycle {cycle + 1}"
            
            # Create file
            file_path.write_text(content, encoding='utf-8')
            
            # Sync to create
            response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=api_headers)
            assert response.status_code == 200
            assert response.json()["status"] == "completed"
            
            # Delete file
            file_path.unlink()
            
            # Sync to delete
            response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=api_headers)
            assert response.status_code == 200
            assert response.json()["status"] == "completed"

class TestHardDeleteBatch:
    """Tests for batch hard delete operations"""
    
    def test_batch_hard_delete_performance(self, tenant_upload_dir, api_headers):
        """Test batch hard delete performance"""
        # Create multiple files for batch testing
        batch_files = []
        for i in range(10):
            file_info = {
                "name": f"batch_test_{i:03d}.txt",
                "content": f"Batch test file {i} content. " * 10
            }
            batch_files.append(file_info)
        
        # Create all files
        create_test_files(tenant_upload_dir, batch_files)
        
        # Sync to create records
        response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=api_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        
        # Delete all files simultaneously
        for file_info in batch_files:
            file_path = tenant_upload_dir / file_info["name"]
            if file_path.exists():
                file_path.unlink()
        
        # Measure batch delete performance
        start_time = time.time()
        response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=api_headers)
        batch_delete_time = time.time() - start_time
        
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        
        # Verify all files were deleted
        latest_sync = get_latest_sync_result(api_headers)
        files_deleted = latest_sync["files_deleted"]
        assert files_deleted >= len(batch_files)
        
        # Performance assertion - batch delete should be reasonably fast
        assert batch_delete_time < 10.0  # Should complete within 10 seconds
    
    def test_mixed_operations_batch(self, tenant_upload_dir, api_headers):
        """Test batch operations with mixed add/delete operations"""
        # Create initial files
        initial_files = [
            {"name": "mixed_initial_1.txt", "content": "Initial file 1"},
            {"name": "mixed_initial_2.txt", "content": "Initial file 2"}
        ]
        create_test_files(tenant_upload_dir, initial_files)
        
        # Sync to create
        response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=api_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        
        # Delete first file, keep second, add new files
        (tenant_upload_dir / initial_files[0]["name"]).unlink()
        
        new_files = [
            {"name": "mixed_new_1.txt", "content": "New file 1"},
            {"name": "mixed_new_2.txt", "content": "New file 2"}
        ]
        create_test_files(tenant_upload_dir, new_files)
        
        # Sync mixed operations
        response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=api_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        
        # Verify mixed operations
        latest_sync = get_latest_sync_result(api_headers)
        assert latest_sync["files_added"] >= len(new_files)
        assert latest_sync["files_deleted"] >= 1

class TestHardDeleteEmbeddings:
    """Tests for embedding cleanup during hard delete"""
    
    def test_embedding_cleanup_verification(self, tenant_upload_dir, api_headers):
        """Test that embeddings are properly cleaned up during hard delete"""
        # Create a file with substantial content to generate embeddings
        test_file = "embedding_cleanup_test.txt"
        content = "This is a test file with substantial content. " * 50
        
        file_path = tenant_upload_dir / test_file
        file_path.write_text(content, encoding='utf-8')
        
        # Sync to create embeddings
        response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=api_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        
        # Verify embeddings were created
        latest_sync = get_latest_sync_result(api_headers)
        chunks_created = latest_sync.get("chunks_created", 0)
        assert chunks_created > 0
        
        # Delete file
        file_path.unlink()
        
        # Sync to delete and cleanup embeddings
        response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=api_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        
        # Verify embeddings were cleaned up
        latest_sync = get_latest_sync_result(api_headers)
        chunks_deleted = latest_sync.get("chunks_deleted", 0)
        assert chunks_deleted > 0
        
        # Verify file was deleted
        assert latest_sync["files_deleted"] >= 1

class TestHardDeleteErrorHandling:
    """Tests for error handling in hard delete operations"""
    
    def test_sync_status_after_hard_delete(self, tenant_upload_dir, api_headers):
        """Test that sync status is properly updated after hard delete"""
        test_file = "sync_status_test.txt"
        file_path = tenant_upload_dir / test_file
        
        # Create and sync file
        file_path.write_text("Test content", encoding='utf-8')
        response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=api_headers)
        assert response.status_code == 200
        
        # Delete and sync
        file_path.unlink()
        response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=api_headers)
        assert response.status_code == 200
        
        # Check sync status
        response = requests.get(f"{BACKEND_URL}/api/v1/sync/status", headers=api_headers)
        assert response.status_code == 200
        
        status = response.json()
        assert "latest_sync" in status
        assert status["latest_sync"]["status"] == "completed"
        assert status["latest_sync"]["error_message"] is None
    
    def test_hard_delete_with_nonexistent_files(self, tenant_upload_dir, api_headers):
        """Test hard delete behavior with files that don't exist"""
        # Try to sync when no files exist (should not fail)
        response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger", headers=api_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        
        # Verify no errors in sync status
        response = requests.get(f"{BACKEND_URL}/api/v1/sync/status", headers=api_headers)
        assert response.status_code == 200
        
        status = response.json()
        assert status["latest_sync"]["status"] == "completed"
        assert status["latest_sync"]["error_message"] is None

if __name__ == "__main__":
    pytest.main([__file__, "-v"])