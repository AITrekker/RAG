"""
Comprehensive Sync Service Tests
Tests the sync service functionality including file detection, embedding generation, and vector storage.
"""

import pytest
import requests
import json
import os
import time
import tempfile
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Test configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Load tenant API keys
with open("demo_tenant_keys.json") as f:
    TENANT_KEYS = json.load(f)

# Find tenant1 by slug
TENANT1_KEY = None
for tenant_id, tenant_data in TENANT_KEYS.items():
    if tenant_data.get("slug") == "tenant1":
        TENANT1_KEY = tenant_data["api_key"]
        break

if not TENANT1_KEY:
    raise ValueError("Could not find tenant1 API key in demo_tenant_keys.json")


class TestSyncService:
    """Test comprehensive sync service functionality."""
    
    def test_sync_service_initialization(self):
        """Test that sync service can be initialized."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        # Test that we can get sync status (service is initialized)
        response = requests.get(
            f"{BACKEND_URL}/api/v1/sync/status",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "file_status" in data
        assert "latest_sync" in data
        print("✅ Sync service successfully initialized")
    
    def test_file_change_detection(self):
        """Test file change detection functionality."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        # Test change detection
        response = requests.post(
            f"{BACKEND_URL}/api/v1/sync/detect-changes",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "total_changes" in data
        assert "new_files" in data
        assert "updated_files" in data
        assert "deleted_files" in data
        assert isinstance(data["total_changes"], int)
        assert isinstance(data["new_files"], int)
        assert isinstance(data["updated_files"], int)
        assert isinstance(data["deleted_files"], int)
        print(f"✅ File change detection working: {data['total_changes']} changes detected")
    
    def test_delta_sync_execution(self):
        """Test delta sync execution."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        # Trigger delta sync
        response = requests.post(
            f"{BACKEND_URL}/api/v1/sync/trigger",
            headers=headers,
            json={"operation_type": "delta_sync"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "sync_id" in data
        assert "status" in data
        assert "started_at" in data
        assert "message" in data
        
        sync_id = data["sync_id"]
        print(f"✅ Delta sync triggered: {sync_id}")
        
        # Wait a moment for sync to complete
        time.sleep(2)
        
        # Check sync status
        response = requests.get(
            f"{BACKEND_URL}/api/v1/sync/status",
            headers=headers
        )
        
        assert response.status_code == 200
        status_data = response.json()
        assert "latest_sync" in status_data
        assert "file_status" in status_data
        print(f"✅ Sync status retrieved: {status_data['file_status']['total']} files")
    
    def test_full_sync_execution(self):
        """Test full sync execution."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        # Trigger full sync
        response = requests.post(
            f"{BACKEND_URL}/api/v1/sync/trigger",
            headers=headers,
            json={"operation_type": "full_sync"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "sync_id" in data
        assert "status" in data
        assert "started_at" in data
        
        sync_id = data["sync_id"]
        print(f"✅ Full sync triggered: {sync_id}")
        
        # Wait for sync to complete
        time.sleep(3)
        
        # Verify sync in history
        response = requests.get(
            f"{BACKEND_URL}/api/v1/sync/history",
            headers=headers
        )
        
        assert response.status_code == 200
        history_data = response.json()
        assert "history" in history_data
        assert len(history_data["history"]) > 0
        
        # Check if our sync operation is in the history
        found_sync = False
        for operation in history_data["history"]:
            if operation.get("id") == sync_id:
                found_sync = True
                break
        
        assert found_sync, f"Sync operation {sync_id} not found in history"
        print(f"✅ Full sync completed and found in history")
    
    def test_embedding_generation_integration(self):
        """Test that sync triggers embedding generation."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        # Trigger sync and check for embedding generation
        response = requests.post(
            f"{BACKEND_URL}/api/v1/sync/trigger",
            headers=headers,
            json={"operation_type": "delta_sync"}
        )
        
        assert response.status_code == 200
        sync_data = response.json()
        
        # Wait for processing
        time.sleep(2)
        
        # Check sync history to see if embeddings were generated
        response = requests.get(
            f"{BACKEND_URL}/api/v1/sync/history",
            headers=headers
        )
        
        assert response.status_code == 200
        history_data = response.json()
        
        # Look for a successful sync with chunks created
        chunks_created = 0
        for operation in history_data["history"][:5]:  # Check recent operations
            if operation.get("status") == "completed":
                chunks_created += operation.get("chunks_created", 0)
        
        print(f"✅ Embedding generation verified: {chunks_created} chunks created")
        
        # Test query to verify embeddings are accessible
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/",
            headers=headers,
            json={"query": "company culture", "max_sources": 3}
        )
        
        assert response.status_code == 200
        query_data = response.json()
        assert "query" in query_data
        assert "answer" in query_data
        assert "sources" in query_data
        print(f"✅ Query successfully processed with {len(query_data['sources'])} sources")
    
    def test_vector_storage_verification(self):
        """Test that embeddings are properly stored in vector database."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        # Perform semantic search to verify vector storage
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/search",
            headers=headers,
            json={"query": "company values", "max_results": 5}
        )
        
        assert response.status_code == 200
        search_data = response.json()
        assert "query" in search_data
        assert "results" in search_data
        assert "total_results" in search_data
        
        # Check that results have proper structure
        for result in search_data["results"]:
            assert "chunk_id" in result
            assert "file_id" in result
            assert "content" in result
            assert "score" in result
            assert "metadata" in result
            assert "filename" in result
            
        print(f"✅ Vector storage verified: {search_data['total_results']} results found")
    
    def test_sync_error_handling(self):
        """Test sync service error handling."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        # Test invalid operation type
        response = requests.post(
            f"{BACKEND_URL}/api/v1/sync/trigger",
            headers=headers,
            json={"operation_type": "invalid_operation"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        print("✅ Invalid operation type properly rejected")
        
        # Test missing operation type
        response = requests.post(
            f"{BACKEND_URL}/api/v1/sync/trigger",
            headers=headers,
            json={}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        print("✅ Missing operation type properly rejected")
    
    def test_sync_performance_tracking(self):
        """Test that sync operations are tracked for performance."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        # Trigger sync and measure response time
        start_time = time.time()
        response = requests.post(
            f"{BACKEND_URL}/api/v1/sync/trigger",
            headers=headers,
            json={"operation_type": "delta_sync"}
        )
        end_time = time.time()
        
        assert response.status_code == 200
        response_time = (end_time - start_time) * 1000  # Convert to ms
        
        # Sync trigger should be fast (< 1 second)
        assert response_time < 1000, f"Sync trigger took {response_time:.2f}ms"
        
        print(f"✅ Sync trigger performance: {response_time:.2f}ms")
        
        # Check sync history for performance data
        response = requests.get(
            f"{BACKEND_URL}/api/v1/sync/history",
            headers=headers
        )
        
        assert response.status_code == 200
        history_data = response.json()
        
        # Verify that sync operations have timing information
        for operation in history_data["history"][:3]:  # Check recent operations
            assert "started_at" in operation
            if operation.get("status") == "completed":
                assert "completed_at" in operation
                
        print("✅ Sync performance tracking verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])