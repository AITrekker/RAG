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

from src.backend.db.session import get_db
from src.backend.utils.vector_store import get_vector_store_manager
from src.backend.core.embeddings import get_embedding_service
from sqlalchemy import text
import numpy as np

def show_overview():
    """Show a quick overview of the system data."""
    print("RAG Platform Data Explorer")
    print("=" * 60)
    
    try:
        db = next(get_db())
        
        # Quick stats
        doc_count = db.execute(text("SELECT COUNT(*) FROM documents")).scalar()
        chunk_count = db.execute(text("SELECT COUNT(*) FROM document_chunks")).scalar()
        tenant_count = db.execute(text("SELECT COUNT(*) FROM tenants")).scalar()
        
        print(f"Quick Stats:")
        print(f"   Documents: {doc_count}")
        print(f"   Chunks: {chunk_count}")
        print(f"   Tenants: {tenant_count}")
        
        # Vector store info
        vector_manager = get_vector_store_manager()
        collections = vector_manager.client.list_collections()
        total_vectors = sum(collection.count() for collection in collections)
        
        print(f"   Vector Collections: {len(collections)}")
        print(f"   Total Vectors: {total_vectors}")
        
        db.close()
        
    except Exception as e:
        print(f"Error getting overview: {e}")

def show_documents_detailed():
    """Show detailed document information."""
    print("\nDocuments in Database")
    print("=" * 50)
    
    try:
        db = next(get_db())
        
        # Get documents with tenant names
        result = db.execute(text("""
            SELECT d.filename, d.file_size, d.status, 
                   t.name as tenant_name, d.created_at,
                   COUNT(dc.id) as chunk_count
            FROM documents d
            JOIN tenants t ON d.tenant_id = t.id
            LEFT JOIN document_chunks dc ON d.id = dc.document_id
            GROUP BY d.id, d.filename, d.file_size, d.status, t.name, d.created_at
            ORDER BY d.created_at DESC 
            LIMIT 10
        """))
        
        documents = result.fetchall()
        
        if documents:
            print(f"Recent documents:")
            for filename, file_size, status, tenant_name, created_at, chunk_count in documents:
                size_kb = file_size / 1024 if file_size else 0
                print(f"  {filename}")
                print(f"     Tenant: {tenant_name}")
                print(f"     Size: {size_kb:.1f} KB")
                print(f"     Status: {status}")
                print(f"     Chunks: {chunk_count}")
                print(f"     Created: {created_at.strftime('%Y-%m-%d %H:%M')}")
                print()
        else:
            print("No documents found.")
            
        db.close()
        
    except Exception as e:
        print(f"Error querying documents: {e}")

def show_embeddings_sample():
    """Show sample embeddings from the vector store."""
    print("\nSample Embeddings")
    print("=" * 50)
    
    try:
        vector_manager = get_vector_store_manager()
        collections = vector_manager.client.list_collections()
        
        # Find collection with most documents
        best_collection = max(collections, key=lambda c: c.count(), default=None)
        
        if best_collection and best_collection.count() > 0:
            print(f"Collection: {best_collection.name} ({best_collection.count()} documents)")
            
            # Get sample with embedding
            sample = best_collection.get(limit=1, include=['documents', 'embeddings', 'metadatas'])
            
            if sample.get('embeddings') and len(sample['embeddings']) > 0:
                embedding = sample['embeddings'][0]
                print(f"  Document ID: {sample['ids'][0]}")
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
        
        # Find best collection
        collections = vector_manager.client.list_collections()
        best_collection = max(collections, key=lambda c: c.count(), default=None)
        
        if not best_collection or best_collection.count() == 0:
            print("No collections with data available for search.")
            return
            
        print(f"Searching in: {best_collection.name}")
        
        # Create query embedding
        query_embedding = embedding_service.encode_texts([query])[0]
        
        # Search
        results = best_collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=3,
            include=['documents', 'distances']
        )
        
        if results['ids'] and results['ids'][0]:
            print(f"Top {len(results['ids'][0])} results:")
            for i, (doc_id, doc, distance) in enumerate(zip(
                results['ids'][0], 
                results['documents'][0], 
                results['distances'][0]
            )):
                similarity = 1 - distance
                print(f"\n  {i+1}. Similarity: {similarity:.3f}")
                print(f"     Content: {doc[:100]}...")
        else:
            print("No results found.")
            
    except Exception as e:
        print(f"Error in search: {e}")

def show_direct_access_info():
    """Show how to access the databases directly."""
    print("\nDirect Database Access")
    print("=" * 50)
    
    print("PostgreSQL (Document metadata):")
    print("   Connection: postgresql://rag_user:rag_password@localhost:5432/rag_database")
    print("   Docker exec: docker exec -it rag_postgres psql -U rag_user -d rag_database")
    print()
    print("Chroma Vector Store (Embeddings):")
    print("   HTTP API: http://localhost:8000")
    print("   Admin UI: Access via Chroma client")
    print()
    print("Useful SQL queries:")
    print("   SELECT filename, status FROM documents ORDER BY created_at DESC;")
    print("   SELECT t.name, COUNT(d.id) FROM tenants t LEFT JOIN documents d ON t.id = d.tenant_id GROUP BY t.name;")
    print("   SELECT content FROM document_chunks WHERE document_id = 'your-doc-id';")

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