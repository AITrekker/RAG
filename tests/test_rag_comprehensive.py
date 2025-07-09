"""
Comprehensive RAG System Tests
Tests the complete RAG pipeline from document ingestion to query answering.
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

# Find tenant1 by slug
TENANT1_KEY = None
for tenant_id, tenant_data in TENANT_KEYS.items():
    if tenant_data.get("slug") == "tenant1":
        TENANT1_KEY = tenant_data["api_key"]
        break

if not TENANT1_KEY:
    raise ValueError("Could not find tenant1 API key in demo_tenant_keys.json")


class TestRAGSystem:
    """Test comprehensive RAG system functionality."""
    
    def test_end_to_end_rag_pipeline(self):
        """Test complete RAG pipeline from sync to query."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        # Step 1: Ensure documents are synced
        response = requests.post(
            f"{BACKEND_URL}/api/v1/sync/trigger",
            headers=headers,
            json={"operation_type": "delta_sync"}
        )
        
        assert response.status_code == 200
        sync_data = response.json()
        print(f"✅ Step 1: Sync triggered - {sync_data['sync_id']}")
        
        # Wait for sync to complete
        time.sleep(3)
        
        # Step 2: Verify documents are processed
        response = requests.get(
            f"{BACKEND_URL}/api/v1/sync/status",
            headers=headers
        )
        
        assert response.status_code == 200
        status_data = response.json()
        assert status_data["file_status"]["total"] > 0
        print(f"✅ Step 2: Documents processed - {status_data['file_status']['total']} files")
        
        # Step 3: Test semantic search
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/search",
            headers=headers,
            json={"query": "company culture", "max_results": 3}
        )
        
        assert response.status_code == 200
        search_data = response.json()
        assert len(search_data["results"]) > 0
        print(f"✅ Step 3: Semantic search working - {len(search_data['results'])} results")
        
        # Step 4: Test RAG query with answer generation
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/",
            headers=headers,
            json={"query": "What is our company culture?", "max_sources": 3}
        )
        
        assert response.status_code == 200
        rag_data = response.json()
        assert "query" in rag_data
        assert "answer" in rag_data
        assert "sources" in rag_data
        assert "confidence" in rag_data
        assert "processing_time" in rag_data
        print(f"✅ Step 4: RAG query completed - {len(rag_data['sources'])} sources, confidence: {rag_data['confidence']:.2f}")
        print(f"    Answer: {rag_data['answer'][:100]}...")
    
    def test_rag_query_quality(self):
        """Test quality of RAG responses."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        # Test various types of queries
        test_queries = [
            {
                "query": "What is our company culture?",
                "expected_keywords": ["culture", "company", "values"],
                "min_sources": 1
            },
            {
                "query": "What is our vacation policy?",
                "expected_keywords": ["vacation", "policy", "time"],
                "min_sources": 1
            },
            {
                "query": "How do we work?",
                "expected_keywords": ["work", "working", "style"],
                "min_sources": 1
            }
        ]
        
        for test_case in test_queries:
            response = requests.post(
                f"{BACKEND_URL}/api/v1/query/",
                headers=headers,
                json={"query": test_case["query"], "max_sources": 5}
            )
            
            assert response.status_code == 200
            rag_data = response.json()
            
            # Check basic structure
            assert "query" in rag_data
            assert "answer" in rag_data
            assert "sources" in rag_data
            assert "confidence" in rag_data
            
            # Check minimum sources
            assert len(rag_data["sources"]) >= test_case["min_sources"]
            
            # Check answer quality (not empty)
            assert len(rag_data["answer"].strip()) > 0
            
            # Check for expected keywords in sources
            source_content = " ".join([s["content"] for s in rag_data["sources"]])
            found_keywords = []
            for keyword in test_case["expected_keywords"]:
                if keyword.lower() in source_content.lower():
                    found_keywords.append(keyword)
            
            assert len(found_keywords) > 0, f"No expected keywords found in sources for query: {test_case['query']}"
            
            print(f"✅ Query quality verified: '{test_case['query']}' - {len(rag_data['sources'])} sources, keywords: {found_keywords}")
    
    def test_rag_response_consistency(self):
        """Test that RAG responses are consistent across multiple runs."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        query = "What is our company culture?"
        responses = []
        
        # Run same query multiple times
        for i in range(3):
            response = requests.post(
                f"{BACKEND_URL}/api/v1/query/",
                headers=headers,
                json={"query": query, "max_sources": 3}
            )
            
            assert response.status_code == 200
            rag_data = response.json()
            responses.append(rag_data)
            time.sleep(0.5)  # Small delay
        
        # Check that top sources are consistent
        for i in range(1, len(responses)):
            if responses[0]["sources"] and responses[i]["sources"]:
                first_source = responses[0]["sources"][0]["chunk_id"]
                current_source = responses[i]["sources"][0]["chunk_id"]
                
                # Top source should be the same (allowing for some variation)
                # We'll check that at least some sources overlap
                overlap = 0
                for src1 in responses[0]["sources"]:
                    for src2 in responses[i]["sources"]:
                        if src1["chunk_id"] == src2["chunk_id"]:
                            overlap += 1
                            break
                
                assert overlap > 0, "Responses should have some overlapping sources"
        
        print(f"✅ RAG response consistency verified across {len(responses)} runs")
    
    def test_rag_performance_requirements(self):
        """Test that RAG system meets performance requirements."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        # Test query performance
        start_time = time.time()
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/",
            headers=headers,
            json={"query": "What is our company culture?", "max_sources": 3}
        )
        end_time = time.time()
        
        assert response.status_code == 200
        query_time = (end_time - start_time) * 1000  # Convert to ms
        
        # RAG query should complete in reasonable time (< 10 seconds)
        assert query_time < 10000, f"RAG query took {query_time:.2f}ms, expected < 10000ms"
        
        # Check processing time reported by system
        rag_data = response.json()
        system_time = rag_data.get("processing_time", 0) * 1000  # Convert to ms
        
        assert system_time > 0, "System should report processing time"
        assert system_time < query_time, "System time should be less than total request time"
        
        print(f"✅ RAG performance verified: {query_time:.2f}ms total, {system_time:.2f}ms processing")
    
    def test_rag_multi_document_integration(self):
        """Test RAG integration across multiple documents."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        # Query that should pull from multiple documents
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/",
            headers=headers,
            json={"query": "Tell me about our policies and culture", "max_sources": 5}
        )
        
        assert response.status_code == 200
        rag_data = response.json()
        
        # Check that we get sources from multiple files
        unique_files = set()
        for source in rag_data["sources"]:
            unique_files.add(source["filename"])
        
        assert len(unique_files) > 1, "Should get sources from multiple documents"
        
        # Check that answer integrates information
        answer = rag_data["answer"].lower()
        assert len(answer) > 50, "Answer should be substantial"
        
        print(f"✅ Multi-document integration verified: {len(unique_files)} files, answer length: {len(answer)}")
    
    def test_rag_error_handling(self):
        """Test RAG system error handling."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        # Test empty query
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/",
            headers=headers,
            json={"query": "", "max_sources": 3}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        print("✅ Empty query properly rejected")
        
        # Test invalid max_sources
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/",
            headers=headers,
            json={"query": "test", "max_sources": 0}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        print("✅ Invalid max_sources properly rejected")
        
        # Test unauthorized access
        bad_headers = {
            "X-API-Key": "invalid_key",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/",
            headers=bad_headers,
            json={"query": "test", "max_sources": 3}
        )
        
        assert response.status_code == 401
        print("✅ Unauthorized access properly rejected")
    
    def test_rag_confidence_scoring(self):
        """Test RAG confidence scoring functionality."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        # Test with clear, specific query
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/",
            headers=headers,
            json={"query": "company culture", "max_sources": 3}
        )
        
        assert response.status_code == 200
        rag_data = response.json()
        
        # Check confidence score
        confidence = rag_data.get("confidence", 0)
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0
        
        # Check source scores
        for source in rag_data["sources"]:
            assert "score" in source
            assert isinstance(source["score"], float)
            assert 0.0 <= source["score"] <= 1.0
        
        print(f"✅ Confidence scoring verified: overall={confidence:.3f}, sources={[s['score'] for s in rag_data['sources']]}")
    
    def test_rag_source_attribution(self):
        """Test proper source attribution in RAG responses."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/",
            headers=headers,
            json={"query": "What is our working style?", "max_sources": 3}
        )
        
        assert response.status_code == 200
        rag_data = response.json()
        
        # Check source attribution
        for source in rag_data["sources"]:
            assert "chunk_id" in source
            assert "file_id" in source
            assert "filename" in source
            assert "content" in source
            assert "score" in source
            assert "metadata" in source
            assert "chunk_index" in source
            
            # Verify metadata structure
            metadata = source["metadata"]
            assert isinstance(metadata, dict)
            assert "filename" in metadata
            assert "chunk_index" in metadata
            
            print(f"✅ Source attribution verified: {source['filename']} chunk {source['chunk_index']} (score: {source['score']:.3f})")
    
    def test_rag_analytics_integration(self):
        """Test that RAG queries are properly logged for analytics."""
        headers = {
            "X-API-Key": TENANT1_KEY,
            "Content-Type": "application/json"
        }
        
        # Perform a query
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query/",
            headers=headers,
            json={"query": "analytics test query", "max_sources": 2}
        )
        
        assert response.status_code == 200
        rag_data = response.json()
        
        # Check that query ID is returned
        assert "query_id" in rag_data
        assert rag_data["query_id"] is not None
        
        # Check that response type is set
        assert "response_type" in rag_data
        assert rag_data["response_type"] in ["success", "no_answer", "error"]
        
        print(f"✅ Analytics integration verified: query_id={rag_data['query_id']}, type={rag_data['response_type']}")
        
        # Wait a moment for analytics to be processed
        time.sleep(1)
        
        # Check analytics endpoints (if available)
        try:
            response = requests.get(
                f"{BACKEND_URL}/api/v1/analytics/summary",
                headers=headers
            )
            
            if response.status_code == 200:
                analytics_data = response.json()
                assert "today" in analytics_data
                print(f"✅ Analytics data accessible: {analytics_data['today']['queries']} queries today")
            else:
                print("ℹ️  Analytics endpoint not fully implemented yet")
        except:
            print("ℹ️  Analytics endpoint not available")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])