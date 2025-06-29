#!/usr/bin/env python3
"""
API Endpoint Testing Script

This script tests the RAG platform API endpoints to verify:
1. Authentication middleware with API keys
2. File management endpoints
3. Sync operations
4. Query processing

Usage:
    python scripts/test_api_endpoints.py [--host localhost] [--port 8000]
"""

import asyncio
import aiohttp
import json
import sys
import argparse
from pathlib import Path
import time


class APITester:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = None
        self.tenant_id = None
        
    async def test_health_check(self, session):
        """Test the health endpoint (no auth required)"""
        print("\n=== Testing Health Check ===")
        try:
            async with session.get(f"{self.base_url}/api/v1/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✓ Health check passed: {data}")
                    return True
                else:
                    print(f"✗ Health check failed: {response.status}")
                    return False
        except Exception as e:
            print(f"✗ Health check error: {e}")
            return False
    
    async def test_no_auth_rejection(self, session):
        """Test that protected endpoints reject requests without API key"""
        print("\n=== Testing Authentication Required ===")
        try:
            async with session.get(f"{self.base_url}/api/v1/files") as response:
                if response.status == 401:
                    print("✓ Correctly rejected request without API key")
                    return True
                else:
                    print(f"✗ Expected 401, got {response.status}")
                    return False
        except Exception as e:
            print(f"✗ Auth test error: {e}")
            return False
    
    async def create_test_tenant(self, session):
        """Create a test tenant via admin API (if available)"""
        print("\n=== Creating Test Tenant ===")
        try:
            # Try to create tenant via setup API first
            payload = {
                "admin_tenant_name": "Test Tenant",
                "admin_tenant_description": "Automated test tenant"
            }
            
            async with session.post(
                f"{self.base_url}/api/v1/setup/initialize",
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.api_key = data.get("admin_api_key")
                    self.tenant_id = data.get("admin_tenant_id")
                    print(f"✓ Test tenant created via setup")
                    print(f"  API Key: {self.api_key[:20]}...")
                    return True
                elif response.status == 400:
                    # System might already be initialized
                    print("ℹ System already initialized, trying auth endpoint...")
                    return await self.try_existing_tenant(session)
                else:
                    print(f"✗ Setup failed: {response.status}")
                    text = await response.text()
                    print(f"  Response: {text}")
                    return False
                    
        except Exception as e:
            print(f"✗ Tenant creation error: {e}")
            return False
    
    async def try_existing_tenant(self, session):
        """Try to use existing demo tenant"""
        print("\n=== Trying Existing Demo Tenant ===")
        
        # Common demo API keys to try
        demo_keys = [
            "tenant_demo1_test_key_12345",
            "tenant_demo2_test_key_12345", 
            "tenant_demo3_test_key_12345"
        ]
        
        for api_key in demo_keys:
            try:
                headers = {"X-API-Key": api_key}
                async with session.get(
                    f"{self.base_url}/api/v1/files",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        self.api_key = api_key
                        print(f"✓ Using existing tenant with key: {api_key[:20]}...")
                        return True
                    elif response.status == 401:
                        continue  # Try next key
                    else:
                        print(f"Unexpected status {response.status} for key {api_key[:20]}...")
                        
            except Exception as e:
                print(f"Error testing key {api_key[:20]}: {e}")
                continue
        
        print("✗ No working demo tenant found")
        return False
    
    async def test_file_listing(self, session):
        """Test file listing endpoint"""
        print("\n=== Testing File Listing ===")
        if not self.api_key:
            print("✗ No API key available")
            return False
            
        try:
            headers = {"X-API-Key": self.api_key}
            async with session.get(
                f"{self.base_url}/api/v1/files",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✓ File listing successful")
                    print(f"  Found {len(data.get('files', []))} files")
                    return True
                else:
                    print(f"✗ File listing failed: {response.status}")
                    text = await response.text()
                    print(f"  Response: {text}")
                    return False
        except Exception as e:
            print(f"✗ File listing error: {e}")
            return False
    
    async def test_sync_status(self, session):
        """Test sync status endpoint"""
        print("\n=== Testing Sync Status ===")
        if not self.api_key:
            print("✗ No API key available")
            return False
            
        try:
            headers = {"X-API-Key": self.api_key}
            async with session.get(
                f"{self.base_url}/api/v1/sync/status",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✓ Sync status retrieved: {data}")
                    return True
                else:
                    print(f"✗ Sync status failed: {response.status}")
                    text = await response.text()
                    print(f"  Response: {text}")
                    return False
        except Exception as e:
            print(f"✗ Sync status error: {e}")
            return False
    
    async def test_change_detection(self, session):
        """Test change detection endpoint"""
        print("\n=== Testing Change Detection ===")
        if not self.api_key:
            print("✗ No API key available")
            return False
            
        try:
            headers = {"X-API-Key": self.api_key}
            async with session.post(
                f"{self.base_url}/api/v1/sync/detect-changes",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✓ Change detection successful")
                    print(f"  Total changes: {data.get('total_changes', 0)}")
                    print(f"  New files: {data.get('new_files', 0)}")
                    print(f"  Updated files: {data.get('updated_files', 0)}")
                    print(f"  Deleted files: {data.get('deleted_files', 0)}")
                    return True
                else:
                    print(f"✗ Change detection failed: {response.status}")
                    text = await response.text()
                    print(f"  Response: {text}")
                    return False
        except Exception as e:
            print(f"✗ Change detection error: {e}")
            return False
    
    async def test_query_endpoint(self, session):
        """Test query processing endpoint"""
        print("\n=== Testing Query Processing ===")
        if not self.api_key:
            print("✗ No API key available")
            return False
            
        try:
            headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}
            payload = {
                "query": "What is the purpose of this system?",
                "max_sources": 3,
                "confidence_threshold": 0.7
            }
            
            async with session.post(
                f"{self.base_url}/api/v1/query/",
                headers=headers,
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✓ Query processing successful")
                    print(f"  Answer length: {len(data.get('answer', ''))}")
                    print(f"  Sources found: {len(data.get('sources', []))}")
                    return True
                else:
                    print(f"✗ Query processing failed: {response.status}")
                    text = await response.text()
                    print(f"  Response: {text}")
                    return False
        except Exception as e:
            print(f"✗ Query processing error: {e}")
            return False
    
    async def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting API Endpoint Tests")
        print("=" * 50)
        
        async with aiohttp.ClientSession() as session:
            tests_passed = 0
            total_tests = 0
            
            # Test 1: Health check
            total_tests += 1
            if await self.test_health_check(session):
                tests_passed += 1
            
            # Test 2: Authentication required
            total_tests += 1
            if await self.test_no_auth_rejection(session):
                tests_passed += 1
            
            # Test 3: Create/find test tenant
            total_tests += 1
            if await self.create_test_tenant(session):
                tests_passed += 1
            else:
                print("\n❌ Cannot continue without valid API key")
                return False
            
            # Test 4: File listing
            total_tests += 1
            if await self.test_file_listing(session):
                tests_passed += 1
            
            # Test 5: Sync status
            total_tests += 1
            if await self.test_sync_status(session):
                tests_passed += 1
            
            # Test 6: Change detection
            total_tests += 1
            if await self.test_change_detection(session):
                tests_passed += 1
            
            # Test 7: Query processing
            total_tests += 1
            if await self.test_query_endpoint(session):
                tests_passed += 1
            
            # Summary
            print("\n" + "=" * 50)
            print(f"🎯 Test Results: {tests_passed}/{total_tests} passed")
            
            if tests_passed == total_tests:
                print("🎉 All API tests passed!")
                print("✓ Authentication working")
                print("✓ File management functional")
                print("✓ Sync operations working")
                print("✓ Query processing available")
                return True
            else:
                print("⚠️  Some tests failed")
                return False


async def main():
    parser = argparse.ArgumentParser(description="Test RAG Platform API endpoints")
    parser.add_argument("--host", default="localhost", help="API host")
    parser.add_argument("--port", default="8000", help="API port")
    args = parser.parse_args()
    
    base_url = f"http://{args.host}:{args.port}"
    print(f"Testing API at: {base_url}")
    
    tester = APITester(base_url)
    success = await tester.run_all_tests()
    
    return success


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test runner error: {e}")
        sys.exit(1)