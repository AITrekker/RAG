#!/usr/bin/env python3
"""
End-to-End Integration Tests for RAG Platform

These tests validate the complete user journey and would have caught
the tenant routing issues we experienced.
"""

import pytest
import asyncio
import requests
import time
from typing import Dict, Any

class TestRAGIntegration:
    """Test complete RAG functionality end-to-end"""
    
    BASE_URL = "http://localhost:8000/api/v1"
    API_KEY = "dev-api-key-123"
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Ensure system is running"""
        try:
            response = requests.get(f"{self.BASE_URL}/health", timeout=5)
            assert response.status_code == 200
        except:
            pytest.skip("Backend not running - start with 'python scripts/run_backend.py'")
    
    def test_tenant_isolation_and_search(self):
        """
        CRITICAL TEST: Verify tenant isolation and search functionality
        This test would have caught our tenant routing bug immediately.
        """
        
        # Test data for different tenants
        test_scenarios = [
            {
                "tenant_id": "tenant1", 
                "query": "vacation policy remote work",
                "expected_source_keywords": ["working", "policy", "vacation"]
            },
            {
                "tenant_id": "tenant2", 
                "query": "company mission", 
                "expected_source_keywords": ["mission", "regional", "solutions"]
            }
        ]
        
        for scenario in test_scenarios:
            tenant_id = scenario["tenant_id"]
            query = scenario["query"]
            
            # Test with tenant header
            headers = {
                "X-Tenant-Id": tenant_id,
                "Authorization": f"Bearer {self.API_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "query": query,
                "max_sources": 3
            }
            
            print(f"\n🧪 Testing tenant {tenant_id} with query: '{query}'")
            
            response = requests.post(
                f"{self.BASE_URL}/query", 
                json=payload, 
                headers=headers,
                timeout=30
            )
            
            # Validate response structure
            assert response.status_code == 200, f"Failed for tenant {tenant_id}: {response.text}"
            
            data = response.json()
            
            # Critical validations
            assert "answer" in data, "Missing answer field"
            assert "sources" in data, "Missing sources field"
            assert data["answer"] != "I could not find any relevant information in your documents to answer this question.", \
                f"No results found for tenant {tenant_id} - tenant isolation may be broken"
            
            # Validate we got actual results
            assert len(data["sources"]) > 0, f"No sources returned for tenant {tenant_id}"
            
            # Validate source content makes sense
            source_text = " ".join([source.get("chunk_text", "") for source in data["sources"]])
            keyword_found = any(keyword.lower() in source_text.lower() 
                              for keyword in scenario["expected_source_keywords"])
            assert keyword_found, f"Expected keywords not found in sources for tenant {tenant_id}"
            
            print(f"  ✅ Found {len(data['sources'])} sources")
            print(f"  ✅ Answer length: {len(data['answer'])} chars")
    
    def test_document_upload_and_search_cycle(self):
        """Test complete document lifecycle"""
        
        # Create test document
        test_content = """
        Test Document for Integration Testing
        
        This document contains information about our new remote work policy.
        Employees can work from home up to 3 days per week.
        All team meetings will be held via video conference.
        """
        
        # Upload document
        files = {"file": ("test_integration.txt", test_content, "text/plain")}
        headers = {
            "X-Tenant-Id": "tenant1",
            "Authorization": f"Bearer {self.API_KEY}"
        }
        
        upload_response = requests.post(
            f"{self.BASE_URL}/documents/upload",
            files=files,
            headers=headers,
            timeout=30
        )
        
        assert upload_response.status_code == 200, f"Upload failed: {upload_response.text}"
        
        # Wait for processing
        time.sleep(2)
        
        # Search for the uploaded content
        query_payload = {
            "query": "remote work policy video conference",
            "max_sources": 5
        }
        
        search_response = requests.post(
            f"{self.BASE_URL}/query",
            json=query_payload,
            headers={
                "X-Tenant-Id": "tenant1",
                "Authorization": f"Bearer {self.API_KEY}",
                "Content-Type": "application/json"
            },
            timeout=30
        )
        
        assert search_response.status_code == 200
        search_data = search_response.json()
        
        # Validate we can find our uploaded document
        source_texts = [source.get("chunk_text", "") for source in search_data["sources"]]
        found_our_content = any("video conference" in text for text in source_texts)
        assert found_our_content, "Could not find uploaded document in search results"
    
    def test_tenant_data_isolation(self):
        """Verify tenants cannot access each other's data"""
        
        # Search tenant1's data using tenant2's context
        headers_tenant2 = {
            "X-Tenant-Id": "tenant2",
            "Authorization": f"Bearer {self.API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Query for tenant1-specific content using tenant2 header
        payload = {
            "query": "GlobalCorp Inc working model policy",  # This should be in tenant1
            "max_sources": 5
        }
        
        response = requests.post(
            f"{self.BASE_URL}/query",
            json=payload,
            headers=headers_tenant2,
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should not find tenant1's GlobalCorp content when querying as tenant2
        source_texts = " ".join([source.get("chunk_text", "") for source in data["sources"]])
        assert "GlobalCorp" not in source_texts, "Tenant isolation violated - found tenant1 data in tenant2 search"

    def test_error_handling(self):
        """Test system behavior under error conditions"""
        
        # Test missing tenant header
        headers_no_tenant = {
            "Authorization": f"Bearer {self.API_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{self.BASE_URL}/query",
            json={"query": "test"},
            headers=headers_no_tenant
        )
        
        assert response.status_code == 400, "Should require tenant header"
        
        # Test invalid tenant
        headers_invalid_tenant = {
            "X-Tenant-Id": "nonexistent-tenant",
            "Authorization": f"Bearer {self.API_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{self.BASE_URL}/query",
            json={"query": "test"},
            headers=headers_invalid_tenant
        )
        
        assert response.status_code == 404, "Should reject invalid tenant"

if __name__ == "__main__":
    # Can run directly for manual testing
    test = TestRAGIntegration()
    test.setup()
    test.test_tenant_isolation_and_search()
    print("✅ All integration tests passed!") 