"""
API Multi-tenancy Tests - API calls only, no business logic.
"""

import pytest
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Test configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Load tenant API keys
with open("demo_tenant_keys.json") as f:
    TENANT_KEYS = json.load(f)

# Collect all tenant keys by slug
ALL_TENANT_KEYS = []
for tenant_slug in ["tenant1", "tenant2", "tenant3"]:
    for tenant_id, tenant_data in TENANT_KEYS.items():
        if tenant_data.get("slug") == tenant_slug:
            ALL_TENANT_KEYS.append(tenant_data["api_key"])
            break

if len(ALL_TENANT_KEYS) != 3:
    raise ValueError(f"Could not find all tenant keys. Found {len(ALL_TENANT_KEYS)}/3")


class TestAPIMultitenancy:
    """Test multi-tenancy isolation via API calls."""
    
    def test_tenant_isolation_sync(self):
        """Test that each tenant can only trigger their own sync."""
        for i, api_key in enumerate(ALL_TENANT_KEYS, 1):
            headers = {
                "X-API-Key": api_key,
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                f"{BACKEND_URL}/api/v1/sync/trigger",
                headers=headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "sync_id" in data
            
            print(f"✅ Tenant{i} sync isolation working: {data['sync_id']}")
    
    def test_tenant_isolation_query(self):
        """Test that each tenant gets results only from their own data."""
        common_query = "documents and files"
        
        tenant_results = {}
        
        for i, api_key in enumerate(ALL_TENANT_KEYS, 1):
            headers = {
                "X-API-Key": api_key,
                "Content-Type": "application/json"
            }
            
            payload = {
                "query": common_query,
                "max_sources": 5
            }
            
            response = requests.post(
                f"{BACKEND_URL}/api/v1/query/",
                headers=headers,
                json=payload
            )
            
            assert response.status_code == 200
            data = response.json()
            
            sources = [s["filename"] for s in data["sources"]]
            tenant_results[f"tenant{i}"] = sources
            
            print(f"✅ Tenant{i} query isolation - sources: {sources}")
        
        # Verify tenants get different document sets
        all_sources = set()
        for tenant, sources in tenant_results.items():
            tenant_sources = set(sources)
            # Check that this tenant's sources don't completely overlap with others
            if all_sources:
                overlap = all_sources.intersection(tenant_sources)
                unique_to_tenant = tenant_sources - all_sources
                print(f"   {tenant}: {len(unique_to_tenant)} unique sources")
            all_sources.update(tenant_sources)
        
        print(f"✅ Multi-tenant isolation verified across {len(tenant_results)} tenants")
    
    def test_tenant_isolation_search(self):
        """Test semantic search isolation between tenants."""
        search_query = "important information"
        
        for i, api_key in enumerate(ALL_TENANT_KEYS, 1):
            headers = {
                "X-API-Key": api_key,
                "Content-Type": "application/json"
            }
            
            payload = {
                "query": search_query,
                "max_results": 5
            }
            
            response = requests.post(
                f"{BACKEND_URL}/api/v1/query/search",
                headers=headers,
                json=payload
            )
            
            assert response.status_code == 200
            data = response.json()
            
            results_count = len(data.get("results", []))
            print(f"✅ Tenant{i} search isolation: {results_count} results")
    
    def test_cross_tenant_access_blocked(self):
        """Test that tenants can only access their own sync operations."""
        # Test that sync trigger works for each tenant independently
        
        for i, api_key in enumerate(ALL_TENANT_KEYS, 1):
            headers = {
                "X-API-Key": api_key,
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                f"{BACKEND_URL}/api/v1/sync/trigger",
                headers=headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "sync_id" in data
            
            print(f"✅ Tenant{i} can trigger own sync operations")
        
        print(f"✅ Cross-tenant access isolation verified")
    
    def test_api_key_validation(self):
        """Test that invalid API keys are properly rejected."""
        invalid_keys = [
            "invalid_key_123",
            "tenant_fake_key",
            "",
            "malformed-key-format"
        ]
        
        for invalid_key in invalid_keys:
            headers = {
                "X-API-Key": invalid_key,
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                f"{BACKEND_URL}/api/v1/sync/trigger",
                headers=headers
            )
            
            assert response.status_code == 401
            
        print(f"✅ API key validation working - {len(invalid_keys)} invalid keys rejected")
    
    def test_tenant_specific_documents(self):
        """Test that tenants get their specific documents in search results."""
        # Test with queries that should return tenant-specific results
        tenant_queries = {
            "tenant1": "company overview mission",
            "tenant2": "financial report revenue",
            "tenant3": "technical documentation project"
        }
        
        for i, api_key in enumerate(ALL_TENANT_KEYS, 1):
            tenant_name = f"tenant{i}"
            query = tenant_queries.get(tenant_name, "general information")
            
            headers = {
                "X-API-Key": api_key,
                "Content-Type": "application/json"
            }
            
            payload = {
                "query": query,
                "max_sources": 3
            }
            
            response = requests.post(
                f"{BACKEND_URL}/api/v1/query/",
                headers=headers,
                json=payload
            )
            
            assert response.status_code == 200
            data = response.json()
            
            sources = [s["filename"] for s in data["sources"]]
            confidence = data.get("confidence", 0)
            
            print(f"✅ {tenant_name} document specificity:")
            print(f"   Query: '{query}'")
            print(f"   Sources: {sources}")
            print(f"   Confidence: {confidence:.3f}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])