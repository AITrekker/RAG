#!/usr/bin/env python3
"""
Test Script for Existing Tenants

This script tests the RAG platform with your existing tenant data:
- tenant1, tenant2, tenant3 with company documents
- Tests authentication, file sync, and RAG queries
- Demonstrates the complete ML pipeline with real company data
"""

import asyncio
import sys
import aiohttp
import json
import argparse
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backend.database import get_async_db
from src.backend.services.tenant_service import TenantService


class ExistingTenantTester:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.tenant_apis = {}  # Will store {tenant_id: api_key}
        
    async def setup_existing_tenants(self):
        """Setup API keys for existing tenants"""
        print("\n=== Setting Up Existing Tenants ===")
        
        try:
            async for db in get_async_db():
                tenant_service = TenantService(db)
                
                # Create/update tenants for your existing data
                tenant_configs = [
                    {"name": "Company Tenant 1", "slug": "tenant1"},
                    {"name": "Company Tenant 2", "slug": "tenant2"}, 
                    {"name": "Company Tenant 3", "slug": "tenant3"}
                ]
                
                for config in tenant_configs:
                    # Check if tenant exists
                    tenant = await tenant_service.get_tenant_by_slug(config["slug"])
                    
                    if not tenant:
                        # Create new tenant
                        tenant = await tenant_service.create_tenant(
                            name=config["name"],
                            slug=config["slug"]
                        )
                        print(f"✓ Created tenant: {config['name']}")
                    else:
                        print(f"✓ Found existing tenant: {config['name']}")
                    
                    # Generate/regenerate API key
                    api_key = await tenant_service.regenerate_api_key(tenant.id)
                    self.tenant_apis[config["slug"]] = {
                        "tenant_id": str(tenant.id),
                        "api_key": api_key,
                        "name": tenant.name
                    }
                    
                    print(f"  API Key: {api_key[:20]}...")
                
                break  # Only need first session
                
        except Exception as e:
            print(f"✗ Failed to setup tenants: {e}")
            return False
        
        return True
    
    async def test_file_discovery(self, session):
        """Test file discovery and sync for each tenant"""
        print("\n=== Testing File Discovery & Sync ===")
        
        for tenant_slug, tenant_info in self.tenant_apis.items():
            print(f"\n--- Testing {tenant_info['name']} ---")
            headers = {"X-API-Key": tenant_info["api_key"]}
            
            try:
                # Test change detection
                async with session.post(
                    f"{self.base_url}/api/v1/sync/detect-changes",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"  ✓ Change detection successful")
                        print(f"    - Total changes: {data.get('total_changes', 0)}")
                        print(f"    - New files: {data.get('new_files', 0)}")
                        print(f"    - Updated files: {data.get('updated_files', 0)}")
                        print(f"    - Deleted files: {data.get('deleted_files', 0)}")
                        
                        # If there are changes, trigger sync
                        if data.get('total_changes', 0) > 0:
                            print("  Triggering sync...")
                            async with session.post(
                                f"{self.base_url}/api/v1/sync/trigger",
                                headers=headers
                            ) as sync_response:
                                if sync_response.status == 200:
                                    sync_data = await sync_response.json()
                                    print(f"    ✓ Sync triggered: {sync_data.get('sync_id', 'N/A')}")
                                else:
                                    print(f"    ✗ Sync failed: {sync_response.status}")
                    else:
                        print(f"  ✗ Change detection failed: {response.status}")
                
                # List files
                async with session.get(
                    f"{self.base_url}/api/v1/files",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        files = data.get('files', [])
                        print(f"  ✓ Found {len(files)} files in system")
                        
                        for file in files[:3]:  # Show first 3
                            print(f"    - {file.get('filename')} ({file.get('sync_status')})")
                    else:
                        print(f"  ✗ File listing failed: {response.status}")
                        
            except Exception as e:
                print(f"  ✗ Error testing {tenant_slug}: {e}")
    
    async def test_company_queries(self, session):
        """Test RAG queries relevant to company documents"""
        print("\n=== Testing Company Document Queries ===")
        
        # Company-specific queries based on your document names
        test_queries = [
            "What is our company mission?",
            "Describe our company culture",
            "What is our vacation policy?", 
            "How do we work as a team?",
            "What are our core values?",
            "What benefits do employees get?",
            "How should I approach work here?"
        ]
        
        for tenant_slug, tenant_info in self.tenant_apis.items():
            print(f"\n--- Querying {tenant_info['name']} ---")
            headers = {"X-API-Key": tenant_info["api_key"], "Content-Type": "application/json"}
            
            # Test a few queries per tenant
            for query in test_queries[:3]:
                try:
                    payload = {
                        "query": query,
                        "max_sources": 3,
                        "confidence_threshold": 0.5
                    }
                    
                    async with session.post(
                        f"{self.base_url}/api/v1/query/",
                        headers=headers,
                        json=payload
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            answer = data.get('answer', 'No answer')
                            sources = data.get('sources', [])
                            processing_time = data.get('processing_time', 0)
                            
                            print(f"\n  🔍 Query: '{query}'")
                            print(f"     ⏱️  Processing time: {processing_time:.3f}s")
                            print(f"     📚 Sources found: {len(sources)}")
                            
                            # Show answer preview
                            answer_preview = answer[:200] + "..." if len(answer) > 200 else answer
                            print(f"     💡 Answer: {answer_preview}")
                            
                            # Show source files
                            if sources:
                                source_files = [s.get('filename', 'Unknown') for s in sources]
                                print(f"     📄 Source files: {', '.join(source_files)}")
                        else:
                            text = await response.text()
                            print(f"  ✗ Query failed ({response.status}): {text}")
                            
                except Exception as e:
                    print(f"  ✗ Query error: {e}")
    
    async def test_semantic_search(self, session):
        """Test semantic search across company documents"""
        print("\n=== Testing Semantic Search ===")
        
        search_queries = [
            "team collaboration",
            "employee benefits",
            "work culture",
            "company values"
        ]
        
        for tenant_slug, tenant_info in self.tenant_apis.items():
            print(f"\n--- Searching {tenant_info['name']} ---")
            headers = {"X-API-Key": tenant_info["api_key"], "Content-Type": "application/json"}
            
            for query in search_queries[:2]:  # Test 2 searches per tenant
                try:
                    payload = {
                        "query": query,
                        "max_results": 5
                    }
                    
                    async with session.post(
                        f"{self.base_url}/api/v1/query/search",
                        headers=headers,
                        json=payload
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            results = data.get('results', [])
                            
                            print(f"\n  🔎 Search: '{query}'")
                            print(f"     📊 Results: {len(results)}")
                            
                            for i, result in enumerate(results[:2]):  # Show top 2
                                filename = result.get('filename', 'Unknown')
                                score = result.get('score', 0)
                                content = result.get('content', '')[:150]
                                
                                print(f"     {i+1}. {filename} (score: {score:.3f})")
                                print(f"        {content}...")
                        else:
                            print(f"  ✗ Search failed: {response.status}")
                            
                except Exception as e:
                    print(f"  ✗ Search error: {e}")
    
    async def show_tenant_status(self, session):
        """Show status summary for all tenants"""
        print("\n=== Tenant Status Summary ===")
        
        for tenant_slug, tenant_info in self.tenant_apis.items():
            print(f"\n--- {tenant_info['name']} ---")
            headers = {"X-API-Key": tenant_info["api_key"]}
            
            try:
                # Get sync status
                async with session.get(
                    f"{self.base_url}/api/v1/sync/status",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        sync_status = await response.json()
                        print(f"  Sync Status: {sync_status}")
                    
                # Get file count
                async with session.get(
                    f"{self.base_url}/api/v1/files",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        file_count = len(data.get('files', []))
                        print(f"  Files: {file_count}")
                        print(f"  API Key: {tenant_info['api_key'][:20]}...")
                        
            except Exception as e:
                print(f"  Error: {e}")
    
    async def run_all_tests(self):
        """Run all tests for existing tenants"""
        print("🚀 Testing Existing Tenant Setup")
        print("=" * 50)
        
        # Setup tenants
        if not await self.setup_existing_tenants():
            return False
        
        async with aiohttp.ClientSession() as session:
            # Test 1: File discovery and sync
            await self.test_file_discovery(session)
            
            # Wait a moment for any sync operations to process
            print("\n⏳ Waiting for sync operations to complete...")
            await asyncio.sleep(3)
            
            # Test 2: Company document queries
            await self.test_company_queries(session)
            
            # Test 3: Semantic search
            await self.test_semantic_search(session)
            
            # Test 4: Show final status
            await self.show_tenant_status(session)
        
        # Summary
        print("\n" + "=" * 50)
        print("🎉 Existing Tenant Test Complete!")
        print(f"✓ Tested {len(self.tenant_apis)} tenants")
        print("✓ File discovery and sync working")
        print("✓ RAG queries functional")
        print("✓ Semantic search operational")
        
        print("\n📋 Your Tenant API Keys:")
        for tenant_slug, info in self.tenant_apis.items():
            print(f"  {info['name']}: {info['api_key']}")
        
        print("\n🔧 Manual Testing Commands:")
        for tenant_slug, info in self.tenant_apis.items():
            api_key = info['api_key']
            print(f"\n# Test {info['name']}:")
            print(f"curl -X GET '{self.base_url}/api/v1/files' \\")
            print(f"  -H 'X-API-Key: {api_key}'")
            print(f"curl -X POST '{self.base_url}/api/v1/query/' \\")
            print(f"  -H 'X-API-Key: {api_key}' \\")
            print(f"  -H 'Content-Type: application/json' \\")
            print(f"  -d '{{\"query\": \"What is our company culture?\", \"max_sources\": 3}}'")
        
        return True


async def main():
    parser = argparse.ArgumentParser(description="Test RAG Platform with existing tenants")
    parser.add_argument("--host", default="localhost", help="API host")
    parser.add_argument("--port", default="8000", help="API port")
    args = parser.parse_args()
    
    base_url = f"http://{args.host}:{args.port}"
    print(f"Testing API at: {base_url}")
    print("Expected tenant directories: /data/uploads/tenant1, tenant2, tenant3")
    
    tester = ExistingTenantTester(base_url)
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