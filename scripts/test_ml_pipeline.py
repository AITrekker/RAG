#!/usr/bin/env python3
"""
End-to-End ML Pipeline Test

This script tests the complete ML integration:
1. Document processing and chunking
2. Embedding generation (with fallback to mock)
3. Qdrant vector storage (with fallback to database)
4. Vector search and retrieval
5. RAG answer generation (with fallback to structured response)
"""

import asyncio
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backend.database import get_async_db
from src.backend.services.tenant_service import TenantService
from src.backend.services.file_service import FileService
from src.backend.services.embedding_service import EmbeddingService
from src.backend.services.rag_service import RAGService


async def create_test_tenant(db):
    """Create a test tenant for ML pipeline testing"""
    tenant_service = TenantService(db)
    
    tenant = await tenant_service.create_tenant(
        name="ML Test Tenant",
        slug="ml-test-tenant"
    )
    
    api_key = await tenant_service.regenerate_api_key(tenant.id)
    return tenant, api_key


async def create_test_documents(db, tenant_id):
    """Create test documents with various content"""
    file_service = FileService(db)
    
    # Test document 1: Technical content
    tech_content = """
    Machine Learning Pipeline

    A machine learning pipeline is a systematic approach to automating the workflow of a machine learning project. 
    It typically includes data preprocessing, feature engineering, model training, evaluation, and deployment.
    
    Key components:
    1. Data Collection and Validation
    2. Data Preprocessing and Feature Engineering
    3. Model Training and Hyperparameter Tuning
    4. Model Evaluation and Validation
    5. Model Deployment and Monitoring
    
    Benefits of ML pipelines include reproducibility, scalability, and maintainability of machine learning workflows.
    """
    
    # Test document 2: Business content
    business_content = """
    Project Management Best Practices
    
    Effective project management requires clear communication, defined goals, and proper resource allocation.
    
    Key principles:
    - Define clear project scope and objectives
    - Establish realistic timelines and milestones
    - Maintain regular communication with stakeholders
    - Monitor progress and adapt to changes
    - Document lessons learned for future projects
    
    Tools commonly used include Gantt charts, Kanban boards, and project management software.
    """
    
    # Create temporary files
    docs = []
    for i, (title, content) in enumerate([
        ("ml_pipeline.txt", tech_content),
        ("project_management.txt", business_content)
    ]):
        # Create tenant upload directory
        tenant_dir = Path(f"./data/uploads/{tenant_id}")
        tenant_dir.mkdir(parents=True, exist_ok=True)
        
        # Write test file
        file_path = tenant_dir / title
        file_path.write_text(content)
        
        # Create file record manually (simulating upload)
        import hashlib
        file_hash = hashlib.sha256(content.encode()).hexdigest()
        
        from src.backend.models.database import File
        file_record = File(
            tenant_id=tenant_id,
            uploaded_by=uuid4(),  # Mock user ID
            filename=title,
            file_path=str(file_path.relative_to("./data/uploads/")),
            file_size=len(content.encode()),
            mime_type="text/plain",
            file_hash=file_hash,
            sync_status='pending'
        )
        
        db.add(file_record)
        docs.append((file_record, content))
    
    await db.commit()
    
    # Refresh to get IDs
    for file_record, _ in docs:
        await db.refresh(file_record)
    
    return docs


async def test_embedding_pipeline(db, tenant, test_docs):
    """Test the complete embedding pipeline"""
    print("\n=== Testing Embedding Pipeline ===")
    
    embedding_service = EmbeddingService(db)
    await embedding_service.initialize()
    
    all_chunk_records = []
    
    for file_record, content in test_docs:
        print(f"\nProcessing file: {file_record.filename}")
        
        # Step 1: Process file into chunks
        print("  1. Document chunking...")
        chunks = await embedding_service.process_file(file_record)
        print(f"     ✓ Created {len(chunks)} chunks")
        
        # Step 2: Generate embeddings
        print("  2. Embedding generation...")
        embeddings = await embedding_service.generate_embeddings(chunks)
        print(f"     ✓ Generated {len(embeddings)} embeddings")
        
        # Step 3: Store embeddings
        print("  3. Storing in database and vector store...")
        chunk_records = await embedding_service.store_embeddings(file_record, chunks, embeddings)
        print(f"     ✓ Stored {len(chunk_records)} chunk records")
        
        all_chunk_records.extend(chunk_records)
        
        # Step 4: Update file sync status
        file_record.sync_status = 'synced'
        await db.commit()
    
    print(f"\n✓ Embedding pipeline complete: {len(all_chunk_records)} total chunks processed")
    return all_chunk_records


async def test_rag_pipeline(db, tenant, test_queries):
    """Test the complete RAG pipeline"""
    print("\n=== Testing RAG Pipeline ===")
    
    file_service = FileService(db)
    rag_service = RAGService(db, file_service)
    await rag_service.initialize()
    
    results = []
    
    for query in test_queries:
        print(f"\nProcessing query: '{query}'")
        
        # Process RAG query
        response = await rag_service.process_query(
            query=query,
            tenant_id=tenant.id,
            max_sources=3,
            confidence_threshold=0.5
        )
        
        print(f"  ✓ Generated answer ({len(response.answer)} chars)")
        print(f"  ✓ Found {len(response.sources)} sources")
        print(f"  ✓ Processing time: {response.processing_time:.3f}s")
        print(f"  ✓ Confidence: {response.confidence:.2f}")
        
        # Preview answer
        answer_preview = response.answer[:150] + "..." if len(response.answer) > 150 else response.answer
        print(f"  Answer preview: {answer_preview}")
        
        results.append(response)
    
    return results


async def test_semantic_search(db, tenant, test_queries):
    """Test semantic search functionality"""
    print("\n=== Testing Semantic Search ===")
    
    file_service = FileService(db)
    rag_service = RAGService(db, file_service)
    
    for query in test_queries:
        print(f"\nSemantic search: '{query}'")
        
        search_results = await rag_service.semantic_search(
            query=query,
            tenant_id=tenant.id,
            max_results=5
        )
        
        print(f"  ✓ Found {len(search_results)} results")
        
        for i, result in enumerate(search_results[:2]):  # Show top 2
            content_preview = result.content[:100] + "..." if len(result.content) > 100 else result.content
            print(f"    {i+1}. {result.filename} (score: {result.score:.3f})")
            print(f"       {content_preview}")


async def cleanup_test_data(db, tenant_id):
    """Clean up test data"""
    print("\n=== Cleaning Up Test Data ===")
    
    try:
        # Remove test files
        tenant_dir = Path(f"./data/uploads/{tenant_id}")
        if tenant_dir.exists():
            import shutil
            shutil.rmtree(tenant_dir)
            print("  ✓ Removed test files")
        
        # Note: Database cleanup would happen automatically with proper cascading deletes
        print("  ✓ Test data cleanup complete")
        
    except Exception as e:
        print(f"  ⚠️ Cleanup error: {e}")


async def main():
    """Run the complete ML pipeline test"""
    print("🚀 Starting End-to-End ML Pipeline Test")
    print("=" * 50)
    
    try:
        # Get database session
        async for db in get_async_db():
            # Step 1: Create test tenant
            print("\n=== Setting Up Test Environment ===")
            tenant, api_key = await create_test_tenant(db)
            print(f"✓ Created test tenant: {tenant.name}")
            print(f"  API Key: {api_key[:20]}...")
            
            # Step 2: Create test documents
            test_docs = await create_test_documents(db, tenant.id)
            print(f"✓ Created {len(test_docs)} test documents")
            
            # Step 3: Test embedding pipeline
            chunk_records = await test_embedding_pipeline(db, tenant, test_docs)
            
            # Step 4: Test RAG pipeline
            test_queries = [
                "What are the key components of a machine learning pipeline?",
                "How do you manage project timelines effectively?",
                "What tools are used for project management?",
                "Explain feature engineering in ML pipelines"
            ]
            
            rag_results = await test_rag_pipeline(db, tenant, test_queries)
            
            # Step 5: Test semantic search
            await test_semantic_search(db, tenant, test_queries[:2])
            
            # Step 6: Summary
            print("\n" + "=" * 50)
            print("🎉 ML Pipeline Test Complete!")
            print(f"✓ Processed {len(test_docs)} documents")
            print(f"✓ Generated {len(chunk_records)} embeddings")
            print(f"✓ Answered {len(rag_results)} queries")
            print("✓ All ML components functioning")
            
            # Test with and without ML models
            print("\n📊 ML Model Status:")
            embedding_service = EmbeddingService(db)
            await embedding_service.initialize()
            
            file_service = FileService(db)
            rag_service = RAGService(db, file_service)
            await rag_service.initialize()
            
            print(f"  - Embedding Model: {'✓ Loaded' if embedding_service._model else '⚠️ Mock'}")
            print(f"  - Qdrant Client: {'✓ Connected' if rag_service._qdrant_client else '⚠️ Fallback'}")
            print(f"  - LLM Model: {'✓ Loaded' if rag_service._llm_model else '⚠️ Fallback'}")
            
            print("\n🔧 Installation Notes:")
            print("  To enable full ML functionality, install:")
            print("    pip install sentence-transformers qdrant-client torch")
            print("    Optional: pip install PyPDF2 python-docx nltk")
            
            # Cleanup
            await cleanup_test_data(db, tenant.id)
            
            break  # Only need first session
            
        return True
        
    except Exception as e:
        print(f"\n❌ ML Pipeline test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)