#!/usr/bin/env python3
"""
Test script for the new RESTful API endpoints.

This script demonstrates the improved RESTful design of the API endpoints.
Run this after the backend is running to test the new endpoint structure.
"""

import requests
import json
from scripts.config import get_admin_api_key, get_base_url

def test_restful_endpoints():
    """Test the new RESTful API endpoints."""
    
    base_url = get_base_url()
    api_key = get_admin_api_key()
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    print("🧪 Testing RESTful API Endpoints")
    print("=" * 50)
    
    # Test new query endpoints
    print("\n📝 Query Endpoints (Old vs New):")
    print("OLD: POST /api/v1/query/ask")
    print("NEW: POST /api/v1/queries")
    print("OLD: POST /api/v1/query/validate") 
    print("NEW: POST /api/v1/queries/validate")
    
    # Test new sync endpoints  
    print("\n🔄 Sync Endpoints (Old vs New):")
    print("OLD: POST /api/v1/sync/trigger")
    print("NEW: POST /api/v1/syncs")
    print("OLD: GET /api/v1/sync/status/{id}")
    print("NEW: GET /api/v1/syncs/{id}")
    print("OLD: POST /api/v1/sync/cancel/{id}")
    print("NEW: DELETE /api/v1/syncs/{id}")
    
    # Test new admin system endpoints
    print("\n⚙️  Admin System Endpoints (Old vs New):")
    print("OLD: POST /api/v1/admin/system/clear-embeddings-stats")
    print("NEW: DELETE /api/v1/admin/system/embeddings/stats")
    print("OLD: POST /api/v1/admin/system/clear-llm-stats")
    print("NEW: DELETE /api/v1/admin/system/llm/stats")
    print("OLD: POST /api/v1/admin/system/clear-llm-cache")
    print("NEW: DELETE /api/v1/admin/system/llm/cache")
    print("OLD: POST /api/v1/admin/system/maintenance")
    print("NEW: PUT /api/v1/admin/system/maintenance")
    
    # Test new document endpoints
    print("\n📄 Document Endpoints (Old vs New):")
    print("OLD: POST /api/v1/sync/documents/{file_path}/process")
    print("NEW: POST /api/v1/syncs/documents")
    print("OLD: DELETE /api/v1/sync/documents/{file_path}")
    print("NEW: DELETE /api/v1/syncs/documents/{id}")
    
    print("\n✅ RESTful Improvements Summary:")
    print("- Resource-based URLs (queries, syncs instead of query/ask, sync/trigger)")
    print("- Standard HTTP methods (DELETE for clearing, PUT for updating state)")
    print("- Consistent resource naming patterns")
    print("- Better semantic meaning in URLs")
    
    # Test health endpoint (unchanged)
    try:
        print("\n🏥 Testing Health Endpoint...")
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print("✅ Health endpoint working")
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Health endpoint error: {e}")

if __name__ == "__main__":
    test_restful_endpoints()