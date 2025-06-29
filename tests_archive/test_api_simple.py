#!/usr/bin/env python3
"""
Simple API test script
"""

import requests
import json

# API configuration
BASE_URL = "http://localhost:8000/api/v1"
ADMIN_API_KEY = "tenant_system_admin_52cc85c532cbf7c4310500333569d92d"

def test_api():
    """Test API access with different methods."""
    
    # Test 1: Health endpoint (should be public)
    print("1. Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health/")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Health endpoint works")
        else:
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 2: Admin tenants with X-API-Key header
    print("\n2. Testing admin tenants with X-API-Key...")
    try:
        headers = {"X-API-Key": ADMIN_API_KEY}
        response = requests.get(f"{BASE_URL}/admin/tenants", headers=headers)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Admin tenants endpoint works")
            data = response.json()
            print(f"   Found {len(data.get('tenants', []))} tenants")
        else:
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 3: Admin tenants with Authorization header
    print("\n3. Testing admin tenants with Authorization...")
    try:
        headers = {"Authorization": f"Bearer {ADMIN_API_KEY}"}
        response = requests.get(f"{BASE_URL}/admin/tenants", headers=headers)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Admin tenants endpoint works with Authorization")
            data = response.json()
            print(f"   Found {len(data.get('tenants', []))} tenants")
        else:
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 4: List available endpoints
    print("\n4. Testing OpenAPI endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/openapi.json")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ OpenAPI endpoint works")
            data = response.json()
            paths = list(data.get('paths', {}).keys())
            print(f"   Available endpoints: {len(paths)}")
            for path in paths[:5]:  # Show first 5
                print(f"     - {path}")
        else:
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    test_api() 