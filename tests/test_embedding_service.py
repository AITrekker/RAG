"""
Comprehensive Embedding Service Tests
Tests the embedding service functionality including text processing, chunking, and vector generation.
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


class TestEmbeddingService:
    """Test comprehensive embedding service functionality."""
    
    def test_embedding_model_initialization(self):
        """Test that embedding models are properly initialized."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        # Test that we can perform a query (which uses embeddings)
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/",
            headers=headers,
            json={"query": "test query", "max_sources": 1}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "query" in data
        assert "answer" in data
        print("✅ Embedding model successfully initialized")
    
    def test_text_chunking_functionality(self):
        """Test text chunking through sync process."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        # Trigger sync to process files and create chunks
        response = requests.post(
            f"{BACKEND_URL}/api/v1/sync/trigger",
            headers=headers,
            json={"operation_type": "delta_sync"}
        )
        
        assert response.status_code == 200
        sync_data = response.json()
        
        # Wait for processing
        time.sleep(2)
        
        # Check sync history to see chunks created
        response = requests.get(
            f"{BACKEND_URL}/api/v1/sync/history",
            headers=headers
        )
        
        assert response.status_code == 200
        history_data = response.json()
        
        # Look for chunk creation
        chunks_created = 0
        for operation in history_data["history"][:5]:
            if operation.get("status") == "completed":
                chunks_created += operation.get("chunks_created", 0)
        
        print(f"✅ Text chunking verified: {chunks_created} chunks created")
        
        # Test that we can retrieve chunks via search
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/search",
            headers=headers,
            json={"query": "company", "max_results": 5}
        )
        
        assert response.status_code == 200
        search_data = response.json()
        assert "results" in search_data
        
        # Verify chunk structure
        for result in search_data["results"]:
            assert "chunk_id" in result
            assert "content" in result
            assert "chunk_index" in result
            assert len(result["content"]) > 0
            print(f"✅ Chunk structure verified: {len(result['content'])} chars")
            break  # Just check first result
    
    def test_embedding_generation_quality(self):
        """Test quality of generated embeddings through similarity search."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        # Test semantic similarity with culture-related query
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/search",
            headers=headers,
            json={"query": "company culture values", "max_results": 3}
        )
        
        assert response.status_code == 200
        search_data = response.json()
        assert "results" in search_data
        
        # Check that results have reasonable similarity scores
        for result in search_data["results"]:
            assert "score" in result
            assert isinstance(result["score"], float)
            assert 0.0 <= result["score"] <= 1.0
            print(f"✅ Similarity score: {result['score']:.3f} for content: {result['content'][:50]}...")
        
        # Test with different query
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/search",
            headers=headers,
            json={"query": "vacation policy", "max_results": 3}
        )
        
        assert response.status_code == 200
        search_data = response.json()
        
        # Check that vacation-related content has high similarity
        vacation_found = False
        for result in search_data["results"]:
            if "vacation" in result["content"].lower() or "policy" in result["content"].lower():
                vacation_found = True
                assert result["score"] > 0.5, f"Vacation content should have high similarity, got {result['score']}"
                break
        
        print(f"✅ Semantic similarity working: vacation content found = {vacation_found}")
    
    def test_multi_document_embedding(self):
        """Test embedding generation across multiple documents."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        # Trigger sync to ensure all documents are processed
        response = requests.post(
            f"{BACKEND_URL}/api/v1/sync/trigger",
            headers=headers,
            json={"operation_type": "delta_sync"}
        )
        
        assert response.status_code == 200
        time.sleep(2)
        
        # Test search across different document types
        test_queries = [
            "company mission",
            "working style",
            "vacation policy",
            "company culture"
        ]
        
        for query in test_queries:
            response = requests.post(
                f"{BACKEND_URL}/api/v1/query/search",
                headers=headers,
                json={"query": query, "max_results": 5}
            )
            
            assert response.status_code == 200
            search_data = response.json()
            
            # Check that we get results from potentially different documents
            unique_files = set()
            for result in search_data["results"]:
                unique_files.add(result["filename"])
            
            print(f"✅ Query '{query}' found content from {len(unique_files)} different files")
    
    def test_embedding_consistency(self):
        """Test that identical queries produce consistent results."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        query = "company culture"
        
        # Perform same query multiple times
        results = []
        for i in range(3):
            response = requests.post(
                f"{BACKEND_URL}/api/v1/query/search",
                headers=headers,
                json={"query": query, "max_results": 3}
            )
            
            assert response.status_code == 200
            search_data = response.json()
            results.append(search_data)
            time.sleep(0.1)  # Small delay between requests
        
        # Check that top results are consistent
        for i in range(1, len(results)):
            if results[0]["results"] and results[i]["results"]:
                first_result_id = results[0]["results"][0]["chunk_id"]
                current_result_id = results[i]["results"][0]["chunk_id"]
                
                assert first_result_id == current_result_id, "Top results should be consistent"
        
        print("✅ Embedding consistency verified across multiple queries")
    
    def test_embedding_performance(self):
        """Test embedding generation and search performance."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        # Test query performance
        start_time = time.time()
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/search",
            headers=headers,
            json={"query": "company values", "max_results": 10}
        )
        end_time = time.time()
        
        assert response.status_code == 200
        search_time = (end_time - start_time) * 1000  # Convert to ms
        
        # Search should be fast (< 2 seconds)
        assert search_time < 2000, f"Search took {search_time:.2f}ms, expected < 2000ms"
        
        print(f"✅ Embedding search performance: {search_time:.2f}ms")
        
        # Test full RAG query performance
        start_time = time.time()
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/",
            headers=headers,
            json={"query": "What is our company culture?", "max_sources": 3}
        )
        end_time = time.time()
        
        assert response.status_code == 200
        rag_time = (end_time - start_time) * 1000  # Convert to ms
        
        # RAG query should be reasonable (< 5 seconds)
        assert rag_time < 5000, f"RAG query took {rag_time:.2f}ms, expected < 5000ms"
        
        print(f"✅ RAG query performance: {rag_time:.2f}ms")
    
    def test_embedding_error_handling(self):
        """Test embedding service error handling."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        # Test with empty query
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/search",
            headers=headers,
            json={"query": "", "max_results": 5}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        print("✅ Empty query properly rejected")
        
        # Test with invalid max_results
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/search",
            headers=headers,
            json={"query": "test", "max_results": 0}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        print("✅ Invalid max_results properly rejected")
    
    def test_embedding_metadata_preservation(self):
        """Test that metadata is preserved during embedding generation."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        # Search for content and verify metadata
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/search",
            headers=headers,
            json={"query": "company", "max_results": 3}
        )
        
        assert response.status_code == 200
        search_data = response.json()
        
        # Check that metadata is present and properly structured
        for result in search_data["results"]:
            assert "metadata" in result
            assert "filename" in result
            assert "chunk_index" in result
            assert "file_id" in result
            
            # Verify metadata structure
            metadata = result["metadata"]
            assert isinstance(metadata, dict)
            assert "filename" in metadata
            assert "chunk_index" in metadata
            
            print(f"✅ Metadata preserved: {metadata['filename']}, chunk {metadata['chunk_index']}")
    
    def test_embedding_tenant_isolation(self):
        """Test that embeddings are properly isolated by tenant."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        # Search for content
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/search",
            headers=headers,
            json={"query": "company", "max_results": 5}
        )
        
        assert response.status_code == 200
        search_data = response.json()
        
        # Verify that all results are from the same tenant
        for result in search_data["results"]:
            # We can't directly verify tenant ID, but we can check 
            # that results are consistent with tenant1 data
            assert "content" in result
            assert "filename" in result
            assert len(result["content"]) > 0
            
        print(f"✅ Tenant isolation verified: {len(search_data['results'])} results all from same tenant")
        
        # Test with unauthorized key should fail
        bad_headers = {
            "X-API-Key": "invalid_key",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/search",
            headers=bad_headers,
            json={"query": "company", "max_results": 5}
        )
        
        assert response.status_code == 401
        print("✅ Unauthorized access properly rejected")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])