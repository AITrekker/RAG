#!/usr/bin/env python3
"""
RAG Platform Data Explorer

This script helps you explore documents, embeddings, and other data 
stored in your RAG platform.

Usage:
    python scripts/explore_data.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# from src.backend.db.session import get_db
from src.backend.utils.vector_store import get_vector_store_manager
from src.backend.core.embeddings import get_embedding_service
# from sqlalchemy import text
import numpy as np

def show_overview():
    """Show a quick overview of the system data."""
    print("RAG Platform Data Explorer")
    print("=" * 60)
    
    try:
        # db = next(get_db())
        
        # # Quick stats
        # doc_count = db.execute(text("SELECT COUNT(*) FROM documents")).scalar()
        # chunk_count = db.execute(text("SELECT COUNT(*) FROM document_chunks")).scalar()
        # tenant_count = db.execute(text("SELECT COUNT(*) FROM tenants")).scalar()
        
        # print(f"Quick Stats:")
        # print(f"   Documents: {doc_count}")
        # print(f"   Chunks: {chunk_count}")
        # print(f"   Tenants: {tenant_count}")
        
        # Vector store info
        vector_manager = get_vector_store_manager()
        collections = vector_manager.client.get_collections().collections
        
        total_vectors = 0
        for collection in collections:
            count_result = vector_manager.client.count(collection_name=collection.name, exact=True)
            total_vectors += count_result.count

        print(f"   Vector Collections: {len(collections)}")
        print(f"   Total Vectors: {total_vectors}")
        
        # db.close()
        
    except Exception as e:
        print(f"Error getting overview: {e}")

def show_documents_detailed():
    """Show detailed document information."""
    print("\nDocuments in Database")
    print("=" * 50)
    
    try:
        # db = next(get_db())
        
        # # Get documents with tenant names
        # result = db.execute(text("""
        #     SELECT d.filename, d.file_size, d.status, 
        #            t.name as tenant_name, d.created_at,
        #            COUNT(dc.id) as chunk_count
        #     FROM documents d
        #     JOIN tenants t ON d.tenant_id = t.id
        #     LEFT JOIN document_chunks dc ON d.id = dc.document_id
        #     GROUP BY d.id, d.filename, d.file_size, d.status, t.name, d.created_at
        #     ORDER BY d.created_at DESC 
        #     LIMIT 10
        # """))
        
        # documents = result.fetchall()
        
        # if documents:
        #     print(f"Recent documents:")
        #     for filename, file_size, status, tenant_name, created_at, chunk_count in documents:
        #         size_kb = file_size / 1024 if file_size else 0
        #         print(f"  {filename}")
        #         print(f"     Tenant: {tenant_name}")
        #         print(f"     Size: {size_kb:.1f} KB")
        #         print(f"     Status: {status}")
        #         print(f"     Chunks: {chunk_count}")
        #         print(f"     Created: {created_at.strftime('%Y-%m-%d %H:%M')}")
        #         print()
        # else:
        #     print("No documents found.")
            
        # db.close()
        print("Note: This function needs to be rewritten to fetch data from Qdrant.")
        
    except Exception as e:
        print(f"Error querying documents: {e}")

def show_embeddings_sample():
    """Show sample embeddings from the vector store."""
    print("\nSample Embeddings")
    print("=" * 50)
    
    try:
        vector_manager = get_vector_store_manager()
        collections_response = vector_manager.client.get_collections()
        collections = collections_response.collections
        
        if not collections:
            print("No collections found.")
            return

        # Find collection with most documents
        best_collection_name = ""
        max_count = -1
        for collection in collections:
            count_result = vector_manager.client.count(collection_name=collection.name, exact=True)
            if count_result.count > max_count:
                max_count = count_result.count
                best_collection_name = collection.name

        if best_collection_name and max_count > 0:
            print(f"Collection: {best_collection_name} ({max_count} documents)")
            
            # Get sample with embedding
            sample, _ = vector_manager.client.scroll(
                collection_name=best_collection_name,
                limit=1,
                with_payload=True,
                with_vectors=True
            )
            
            if sample and sample[0].vector:
                embedding = sample[0].vector
                print(f"  Document ID: {sample[0].id}")
                print(f"  Embedding dimensions: {len(embedding)}")
                print(f"  Sample values: {[round(x, 4) for x in embedding[:5]]} ... {[round(x, 4) for x in embedding[-3:]]}")
                
                # Statistics
                embedding_array = np.array(embedding)
                print(f"  Min: {embedding_array.min():.4f}")
                print(f"  Max: {embedding_array.max():.4f}")
                print(f"  Mean: {embedding_array.mean():.4f}")
                
        else:
            print("No embeddings found.")
            
    except Exception as e:
        print(f"Error showing embeddings: {e}")

def test_search(query="What is the company mission?"):
    """Test semantic search functionality."""
    print(f"\nTesting Search: '{query}'")
    print("=" * 50)
    
    try:
        vector_manager = get_vector_store_manager()
        embedding_service = get_embedding_service()
        
        collections_response = vector_manager.client.get_collections()
        collections = collections_response.collections

        if not collections:
            print("No collections with data available for search.")
            return

        # Find best collection
        best_collection_name = ""
        max_count = -1
        for collection in collections:
            count_result = vector_manager.client.count(collection_name=collection.name, exact=True)
            if count_result.count > max_count:
                max_count = count_result.count
                best_collection_name = collection.name

        if not best_collection_name:
            print("No collections with data available for search.")
            return
            
        print(f"Searching in: {best_collection_name}")
        
        # Create query embedding
        query_embedding = embedding_service.encode_texts([query])[0].tolist()
        
        # Search
        results = vector_manager.similarity_search(
            tenant_id="default",  # Assuming a default tenant for this script
            query_embedding=query_embedding,
            top_k=3
        )
        
        if results:
            print(f"Top {len(results)} results:")
            for i, result in enumerate(results):
                similarity = result.score
                content = result.payload.get('text', 'N/A')
                print(f"\n  {i+1}. Similarity: {similarity:.3f}")
                print(f"     Content: {content[:100]}...")
        else:
            print("No results found.")
            
    except Exception as e:
        print(f"Error in search: {e}")

def show_direct_access_info():
    """Show how to access the databases directly."""
    print("\nDirect Database Access")
    print("=" * 50)
    
    print("Qdrant Vector Database (Embeddings & Metadata):")
    print("   Web UI / API: http://localhost:6333/dashboard")
    print("   gRPC port: 6334")
    print()
    print("Useful Qdrant Client commands:")
    print("   client.get_collections()")
    print("   client.scroll(collection_name='your_collection', limit=10)")
    print("   client.count(collection_name='your_collection', exact=True)")

def main():
    """Main function with menu options."""
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        test_search(query)
        return
    
    show_overview()
    show_documents_detailed()
    show_embeddings_sample()
    test_search()
    show_direct_access_info()
    
    print("\n" + "=" * 60)
    print("Exploration Complete!")
    print("\nUsage:")
    print("   python scripts/explore_data.py                    # Full exploration")
    print("   python scripts/explore_data.py 'your query here'  # Test specific search")

if __name__ == "__main__":
    main() 