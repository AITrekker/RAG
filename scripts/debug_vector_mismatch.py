#!/usr/bin/env python3
"""
Debug why vector search isn't finding results.
"""

import sys
import requests
import json
import numpy as np
from pathlib import Path
from uuid import UUID
from sentence_transformers import SentenceTransformer

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def check_qdrant_data():
    """Check what's actually in Qdrant."""
    print("🔍 Checking Qdrant Data")
    print("=" * 50)
    
    qdrant_url = "http://rag_qdrant:6333"  # Use Docker service name
    tenant_id = "110174a1-8e2f-47a1-af19-1478f1be07a8"
    collection_name = f"tenant_{tenant_id}_documents"
    
    # Get a few sample points
    scroll_payload = {
        "limit": 5,
        "with_payload": True,
        "with_vectors": True
    }
    
    response = requests.post(
        f"{qdrant_url}/collections/{collection_name}/points/scroll",
        json=scroll_payload
    )
    
    if response.status_code == 200:
        data = response.json()
        points = data['result']['points']
        
        print(f"✅ Found {len(points)} sample points")
        
        for i, point in enumerate(points, 1):
            payload = point.get('payload', {})
            vector = point.get('vector', [])
            
            print(f"\n📄 Point {i}:")
            print(f"   ID: {point['id']}")
            print(f"   File: {payload.get('filename', 'unknown')}")
            print(f"   Vector dim: {len(vector) if vector else 'no vector'}")
            
            if vector:
                # Check vector properties
                vector_np = np.array(vector)
                print(f"   Vector range: [{vector_np.min():.3f}, {vector_np.max():.3f}]")
                print(f"   Vector norm: {np.linalg.norm(vector_np):.3f}")
                
                # Show first few values
                print(f"   First 5 values: {vector[:5]}")
        
        return points
    else:
        print(f"❌ Failed to get points: {response.status_code}")
        return []

def test_embedding_compatibility():
    """Test if our embeddings match Qdrant format."""
    print("\n🧪 Testing Embedding Compatibility")
    print("=" * 50)
    
    # Generate test embeddings
    model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device='cuda')
    
    test_texts = [
        "company mission innovation",
        "work from home remote",
        "vacation policy"
    ]
    
    print("🔥 Generating test embeddings...")
    embeddings = model.encode(test_texts)
    
    for i, (text, embedding) in enumerate(zip(test_texts, embeddings), 1):
        emb_np = np.array(embedding)
        print(f"\n📝 Text {i}: '{text}'")
        print(f"   Embedding dim: {len(embedding)}")
        print(f"   Range: [{emb_np.min():.3f}, {emb_np.max():.3f}]")
        print(f"   Norm: {np.linalg.norm(emb_np):.3f}")
        print(f"   First 5 values: {embedding[:5].tolist()}")
    
    return embeddings

def test_manual_search():
    """Test manual search with known good embedding."""
    print("\n🎯 Manual Search Test")
    print("=" * 50)
    
    qdrant_url = "http://rag_qdrant:6333"  # Use Docker service name
    tenant_id = "110174a1-8e2f-47a1-af19-1478f1be07a8"
    collection_name = f"tenant_{tenant_id}_documents"
    
    # Generate embedding for a simple query
    model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device='cuda')
    query_embedding = model.encode("company mission").tolist()
    
    print(f"🔍 Searching for 'company mission'...")
    print(f"   Query embedding dim: {len(query_embedding)}")
    print(f"   Query norm: {np.linalg.norm(query_embedding):.3f}")
    
    # Try different search parameters
    search_configs = [
        {"limit": 5, "score_threshold": 0.0},  # No threshold
        {"limit": 5, "score_threshold": 0.3},  # Low threshold
        {"limit": 10, "score_threshold": 0.0}, # More results
    ]
    
    for i, config in enumerate(search_configs, 1):
        print(f"\n🔍 Search config {i}: {config}")
        
        search_payload = {
            "vector": query_embedding,
            "with_payload": True,
            **config
        }
        
        response = requests.post(
            f"{qdrant_url}/collections/{collection_name}/points/search",
            json=search_payload
        )
        
        if response.status_code == 200:
            results = response.json()
            points = results.get('result', [])
            
            print(f"   Found {len(points)} results")
            
            for j, point in enumerate(points[:3], 1):
                payload = point.get('payload', {})
                score = point.get('score', 0)
                print(f"     {j}. {payload.get('filename', 'unknown')} (score: {score:.4f})")
        else:
            print(f"   ❌ Search failed: {response.status_code}")

def check_embedding_model_version():
    """Check if embedding model versions match."""
    print("\n🔧 Checking Embedding Model Consistency")
    print("=" * 50)
    
    # Check what model was used to create the vectors
    qdrant_points = check_qdrant_data()
    
    if qdrant_points:
        # Generate embeddings with current model
        model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device='cuda')
        
        # Try to find content that should match
        test_content = "InnovateFast Mission"  # From company_mission.txt
        test_embedding = model.encode(test_content)
        
        print(f"\n🧪 Test content: '{test_content}'")
        print(f"   Current model embedding:")
        print(f"   Dim: {len(test_embedding)}")
        print(f"   Norm: {np.linalg.norm(test_embedding):.3f}")
        print(f"   Range: [{test_embedding.min():.3f}, {test_embedding.max():.3f}]")
        
        # Compare with stored vector characteristics
        if qdrant_points:
            stored_vector = qdrant_points[0].get('vector', [])
            if stored_vector:
                stored_np = np.array(stored_vector)
                print(f"\n   Stored vector characteristics:")
                print(f"   Dim: {len(stored_vector)}")
                print(f"   Norm: {np.linalg.norm(stored_np):.3f}")
                print(f"   Range: [{stored_np.min():.3f}, {stored_np.max():.3f}]")
                
                # Check if they're in similar ranges
                if abs(np.linalg.norm(test_embedding) - np.linalg.norm(stored_np)) > 0.5:
                    print("⚠️  WARNING: Embedding norms are very different!")
                    print("   This suggests different models or normalization!")

def main():
    """Run all debug tests."""
    print("🔍 Vector Search Mismatch Debug")
    print("=" * 60)
    
    try:
        qdrant_points = check_qdrant_data()
        test_embedding_compatibility()
        test_manual_search()
        check_embedding_model_version()
        
        print("\n" + "=" * 60)
        print("🎯 Debug Summary:")
        print("If manual search found results, the issue is in RAG code.")
        print("If manual search found nothing, the issue is embedding mismatch.")
        print("Check if vectors were created with different model version.")
        
    except Exception as e:
        print(f"\n❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()