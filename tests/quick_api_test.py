#!/usr/bin/env python3
"""
Quick API Test Script for Enterprise RAG Platform

This script tests all the main API endpoints so you don't have to use the UI.
Run this after starting the backend to verify everything is working.
"""

import requests
import json
import time
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000"
API_KEY = "dev-api-key-123"  # Default API key

# Headers for authenticated requests
AUTH_HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

def test_endpoint(method: str, endpoint: str, data: Dict[Any, Any] = None, 
                 files: Dict[str, Any] = None, expect_status: int = 200) -> bool:
    """Test a single API endpoint."""
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, headers=AUTH_HEADERS, timeout=10)
        elif method == "POST":
            if files:
                # For file uploads, don't include Content-Type in headers
                headers = {"X-API-Key": API_KEY}
                response = requests.post(url, headers=headers, files=files, timeout=10)
            else:
                response = requests.post(url, headers=AUTH_HEADERS, json=data, timeout=10)
        elif method == "DELETE":
            response = requests.delete(url, headers=AUTH_HEADERS, timeout=10)
        else:
            print(f"Unsupported method: {method}")
            return False
        
        success = response.status_code == expect_status
        status_icon = "[OK]" if success else "[FAIL]"
        
        print(f"{status_icon} {method} {endpoint} -> {response.status_code}")
        
        if not success:
            print(f"   Expected {expect_status}, got {response.status_code}")
            if response.text:
                print(f"   Response: {response.text[:200]}...")
        
        return success
    
    except requests.exceptions.ConnectionError:
        print(f"[FAIL] {method} {endpoint} -> Connection Error (Is server running?)")
        return False
    except Exception as e:
        print(f"[FAIL] {method} {endpoint} -> Error: {e}")
        return False

def main():
    """Run all API endpoint tests."""
    print("Enterprise RAG Platform - API Endpoint Test Suite")
    print("=" * 60)
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"Server is running at {BASE_URL}")
    except:
        print(f"Server is not running at {BASE_URL}")
        print("Please start the backend with: python -m src.backend.main")
        return
    
    print("\nTesting API Endpoints:")
    print("-" * 40)
    
    results = []
    
    # Health Check Endpoints (No auth required)
    print("\nHealth Endpoints:")
    results.append(test_endpoint("GET", "/api/v1/health/"))
    results.append(test_endpoint("GET", "/api/v1/health/detailed"))
    results.append(test_endpoint("GET", "/api/v1/health/readiness"))
    results.append(test_endpoint("GET", "/api/v1/health/liveness"))
    
    # Document Endpoints
    print("\nDocument Endpoints:")
    results.append(test_endpoint("GET", "/api/v1/documents"))
    results.append(test_endpoint("GET", "/api/v1/documents?page=1&page_size=5"))
    
    # Test document upload (if you have a test file)
    test_file_content = b"This is a test document for the RAG platform."
    files = {"file": ("test.txt", test_file_content, "text/plain")}
    upload_success = test_endpoint("POST", "/api/v1/documents/upload", files=files, expect_status=201)
    results.append(upload_success)
    
    # Test getting a specific document (mock ID)
    results.append(test_endpoint("GET", "/api/v1/documents/doc-123"))
    
    # Query Endpoints
    print("\nQuery Endpoints:")
    query_data = {"query": "What is the Enterprise RAG Platform?"}
    results.append(test_endpoint("POST", "/api/v1/query/", data=query_data))
    results.append(test_endpoint("GET", "/api/v1/query/history"))
    
    # Sync Endpoints
    print("\nSync Endpoints:")
    results.append(test_endpoint("GET", "/api/v1/sync/status"))
    sync_data = {"force_full_sync": False}
    results.append(test_endpoint("POST", "/api/v1/sync/trigger", data=sync_data))
    
    # Audit Endpoints
    print("\nAudit Endpoints:")
    results.append(test_endpoint("GET", "/api/v1/audit/events"))
    
    # Tenant Endpoints
    print("\nTenant Endpoints:")
    results.append(test_endpoint("GET", "/api/v1/tenants/"))
    
    # Summary
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    success_rate = (passed / total) * 100 if total > 0 else 0
    
    print(f"Test Summary: {passed}/{total} endpoints passed ({success_rate:.1f}%)")
    
    if success_rate >= 80:
        print("Great! Most endpoints are working properly.")
    elif success_rate >= 50:
        print("Some endpoints need attention.")
    else:
        print("Many endpoints are failing. Check server logs.")
    
    print("\nTip: You can also run the full test suite with:")
    print("   python -m pytest tests/test_api_endpoints.py -v")

if __name__ == "__main__":
    main() 