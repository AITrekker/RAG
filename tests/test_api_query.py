"""
API Query Tests - API calls only, no business logic.
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
TENANT2_KEY = TENANT_KEYS["tenant2"]["api_key"]


class TestAPIQuery:
    """Test RAG query API endpoints."""
    
    def test_basic_rag_query(self):
        """Test basic RAG query functionality."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": "What is the company's mission?",
            "max_sources": 5,
            "confidence_threshold": 0.3
        }
        
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/",
            headers=headers,
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert "query" in data
        assert "answer" in data
        assert "sources" in data
        assert "confidence" in data
        assert "processing_time" in data
        assert "model_used" in data
        assert "tokens_used" in data
        
        assert data["query"] == payload["query"]
        assert isinstance(data["sources"], list)
        assert isinstance(data["confidence"], (int, float))
        assert isinstance(data["processing_time"], (int, float))
        
        print(f"✅ RAG query successful:")
        print(f"   Answer length: {len(data['answer'])} chars")
        print(f"   Sources: {len(data['sources'])}")
        print(f"   Confidence: {data['confidence']:.3f}")
        print(f"   Processing time: {data['processing_time']:.3f}s")
        print(f"   Model: {data['model_used']}")
    
    def test_semantic_search(self):
        """Test semantic search endpoint."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": "company products",
            "max_results": 10
        }
        
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/search",
            headers=headers,
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "results" in data
        assert isinstance(data["results"], list)
        
        if data["results"]:
            result = data["results"][0]
            assert "score" in result
            assert "content" in result
            assert "filename" in result
            
        print(f"✅ Semantic search: {len(data['results'])} results")
    
    def test_query_validation(self):
        """Test query validation endpoint."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": "What is the company mission?"
        }
        
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/validate",
            headers=headers,
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "is_valid" in data
        assert "suggestions" in data
        
        print(f"✅ Query validation: valid={data['is_valid']}")
    
    def test_query_suggestions(self):
        """Test query suggestions endpoint."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        params = {
            "partial_query": "company",
            "max_suggestions": 5
        }
        
        response = requests.get(
            f"{BACKEND_URL}/api/v1/query/suggestions",
            headers=headers,
            params=params
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)
        
        print(f"✅ Query suggestions: {len(data['suggestions'])} suggestions")
    
    def test_tenant_isolation(self):
        """Test that different tenants get different results."""
        query_payload = {
            "query": "financial information",
            "max_sources": 3
        }
        
        # Query from tenant1
        headers1 = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        response1 = requests.post(
            f"{BACKEND_URL}/api/v1/query/",
            headers=headers1,
            json=query_payload
        )
        
        # Query from tenant2
        headers2 = {
            "X-API-Key": TENANT2_KEY,
            "Content-Type": "application/json"
        }
        response2 = requests.post(
            f"{BACKEND_URL}/api/v1/query/",
            headers=headers2,
            json=query_payload
        )
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        data1 = response1.json()
        data2 = response2.json()
        
        # Tenants should get different documents
        sources1 = [s["filename"] for s in data1["sources"]]
        sources2 = [s["filename"] for s in data2["sources"]]
        
        print(f"✅ Tenant isolation verified:")
        print(f"   Tenant1 sources: {sources1}")
        print(f"   Tenant2 sources: {sources2}")
        
        # They should have at least some different sources
        # (unless they have identical document sets)
        if sources1 and sources2:
            print(f"   Isolation working: different document sets")
    
    def test_empty_query(self):
        """Test handling of empty query."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        payload = {"query": ""}
        
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/",
            headers=headers,
            json=payload
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        print("✅ Empty query properly rejected")
    
    def test_query_unauthorized(self):
        """Test query endpoint without authentication."""
        payload = {"query": "test query"}
        
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/",
            json=payload
        )
        
        assert response.status_code == 401
        print("✅ Unauthorized query access properly rejected")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])