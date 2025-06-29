#!/usr/bin/env python3
"""
Direct Qdrant test to verify vector search functionality.
"""

import requests
import json
from uuid import UUID

def test_qdrant_direct():
    """Test Qdrant directly with REST API."""
    print("🔍 Direct Qdrant Test")
    print("=" * 50)
    
    qdrant_url = "http://localhost:6333"
    tenant_id = "110174a1-8e2f-47a1-af19-1478f1be07a8"
    collection_name = f"tenant_{tenant_id}_documents"
    
    try:
        # Check collection info
        response = requests.get(f"{qdrant_url}/collections/{collection_name}")
        if response.status_code == 200:
            info = response.json()
            print(f"✅ Collection exists: {collection_name}")
            print(f"📊 Points count: {info['result']['points_count']}")
            print(f"📊 Vectors count: {info['result']['vectors_count']}")
        else:
            print(f"❌ Collection not found: {response.status_code}")
            return
        
        # Try a simple search with dummy vector
        search_payload = {
            "vector": [0.0] * 384,  # Dummy vector
            "limit": 3,
            "with_payload": True
        }
        
        response = requests.post(
            f"{qdrant_url}/collections/{collection_name}/points/search",
            json=search_payload
        )
        
        if response.status_code == 200:
            results = response.json()
            print(f"✅ Search successful!")
            print(f"📦 Found {len(results['result'])} results")
            
            for i, result in enumerate(results['result'][:2], 1):
                payload = result.get('payload', {})
                print(f"  {i}. Point ID: {result['id']}")
                print(f"     Score: {result['score']:.4f}")
                print(f"     Payload: {payload}")
        else:
            print(f"❌ Search failed: {response.status_code}")
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_qdrant_direct()