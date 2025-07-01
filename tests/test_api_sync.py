"""
API Sync Tests - API calls only, no business logic.
"""

import pytest
import requests
import json
import os
import time
from dotenv import load_dotenv

load_dotenv()

# Test configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Load tenant API keys
with open("demo_tenant_keys.json") as f:
    TENANT_KEYS = json.load(f)

TENANT1_KEY = TENANT_KEYS["tenant1"]["api_key"]


class TestAPISync:
    """Test sync API endpoints."""
    
    def test_sync_trigger(self):
        """Test triggering sync operation."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{BACKEND_URL}/api/v1/sync/trigger",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "sync_id" in data
        assert "status" in data
        assert "message" in data
        print(f"✅ Sync triggered: {data['sync_id']}")
        
        # Test passes if we get here
    
    def test_sync_status_not_implemented(self):
        """Test that sync status endpoint returns not implemented."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{BACKEND_URL}/api/v1/sync/status",
            headers=headers
        )
        
        assert response.status_code == 501
        data = response.json()
        assert data.get("code") == "INTERNAL_ERROR"
        print(f"✅ Sync status endpoint correctly returns not implemented")
    
    def test_sync_history_not_implemented(self):
        """Test that sync history endpoint returns not implemented."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{BACKEND_URL}/api/v1/sync/history",
            headers=headers
        )
        
        assert response.status_code == 501
        data = response.json()
        assert data.get("code") == "INTERNAL_ERROR"
        print(f"✅ Sync history endpoint correctly returns not implemented")
    
    def test_sync_detect_changes(self):
        """Test detecting file changes."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
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
        print(f"✅ Change detection: {data['total_changes']} total changes")
    
    def test_sync_unauthorized(self):
        """Test sync endpoint without authentication."""
        response = requests.post(f"{BACKEND_URL}/api/v1/sync/trigger")
        
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        print("✅ Unauthorized access properly rejected")
    
    def test_sync_invalid_api_key(self):
        """Test sync with invalid API key."""
        headers = {
            "X-API-Key": "invalid_key_12345",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{BACKEND_URL}/api/v1/sync/trigger",
            headers=headers
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        print("✅ Invalid API key properly rejected")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])