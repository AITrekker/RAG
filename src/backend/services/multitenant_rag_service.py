"""
Multi-Tenant RAG Service - Clean LlamaIndex Integration
Replaces the complex hybrid system with proper LlamaIndex usage for multi-tenancy
"""

import asyncio
import time
from typing import List, Dict, Any, Optional
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from src.backend.models.database import File, Tenant
from src.backend.services.file_service import FileService
from src.backend.config.settings import get_settings

settings = get_settings()


@dataclass
class RAGResponse:
    """Clean RAG response format"""
    query: str
    answer: str
    sources: List[Dict[str, Any]]
    confidence: float
    processing_time: float
    method: str
    tenant_id: str


class MultiTenantRAGService:
    """
    Single, clean RAG service leveraging LlamaIndex properly for multi-tenancy
    
    This replaces:
    - rag_service.py (694 lines)
    - hybrid_rag_service.py (376 lines) 
    - simple_rag_replacement.py (57 lines)
    
    With one clean implementation that actually uses LlamaIndex correctly.
    """
    
    def __init__(
        self, 
        db: AsyncSession, 
        file_service: FileService,
        embedding_model=None
    ):
        self.db = db
        self.file_service = file_service
        self.embedding_model = embedding_model
        
        # Per-tenant LlamaIndex components (proper multi-tenancy)
        self.tenant_vector_stores = {}
        self.tenant_indexes = {}
        self.tenant_query_engines = {}
        
        # LlamaIndex availability
        self._llamaindex_available = False
        self._initialized = False
    
    async def initialize(self):
        """Initialize LlamaIndex components for multi-tenancy"""
        if self._initialized:
            return
            
        try:
            # Test LlamaIndex imports
            from llama_index.core import VectorStoreIndex, Document
            from llama_index.vector_stores.postgres import PGVectorStore
            from llama_index.core.query_engine import RetrieverQueryEngine
            
            self._llamaindex_available = True
            print("✓ LlamaIndex components available for multi-tenant RAG")
            
        except ImportError as e:
            print(f"⚠️ LlamaIndex not available: {e}")
            print("  Falling back to simple RAG without LlamaIndex synthesis")
            self._llamaindex_available = False
        
        self._initialized = True
    
    async def get_tenant_components(self, tenant_id: UUID):
        """
        Get or create LlamaIndex components for a specific tenant
        This is the key to proper multi-tenancy with LlamaIndex
        """
        tenant_key = str(tenant_id)
        
        if tenant_key not in self.tenant_vector_stores and self._llamaindex_available:
            try:
                from llama_index.core import VectorStoreIndex
                from llama_index.vector_stores.postgres import PGVectorStore
                
                # Create tenant-specific vector store
                vector_store = PGVectorStore.from_params(
                    connection_string=settings.database_url,
                    table_name=f"tenant_{tenant_key}_vectors",
                    embed_dim=384,  # all-MiniLM-L6-v2 dimensions
                    hybrid_search=True,
                    text_search_config="english"
                )
                
                # Create tenant-specific index
                index = VectorStoreIndex.from_vector_store(vector_store)
                
                # Create tenant-specific query engine
                query_engine = index.as_query_engine(
                    similarity_top_k=5,
                    response_mode="compact",
                    streaming=False
                )
                
                # Cache components
                self.tenant_vector_stores[tenant_key] = vector_store
                self.tenant_indexes[tenant_key] = index
                self.tenant_query_engines[tenant_key] = query_engine
                
                print(f"✓ Created LlamaIndex components for tenant {tenant_key}")
                
            except Exception as e:
                print(f"⚠️ Failed to create LlamaIndex components for tenant {tenant_key}: {e}")
                return None, None, None
        
        return (
            self.tenant_vector_stores.get(tenant_key),
            self.tenant_indexes.get(tenant_key), 
            self.tenant_query_engines.get(tenant_key)
        )
    
    async def add_document(
        self, 
        file_content: str, 
        tenant_id: UUID, 
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Add document to tenant's index
        LlamaIndex handles chunking, embedding, and storage automatically
        """
        try:
            if not self._llamaindex_available:
                print("⚠️ LlamaIndex not available, skipping document indexing")
                return False
            
            # Get tenant components
            vector_store, index, query_engine = await self.get_tenant_components(tenant_id)
            if not index:
                return False
            
            # Create LlamaIndex document
            from llama_index.core import Document
            
            document = Document(
                text=file_content,
                metadata={
                    **metadata,
                    'tenant_id': str(tenant_id),
                    'indexed_at': time.time()
                }
            )
            
            # Insert into tenant's index (LlamaIndex handles everything)
            index.insert(document)
            
            print(f"✓ Added document to tenant {tenant_id} index")
            return True
            
        except Exception as e:
            print(f"❌ Error adding document to tenant {tenant_id}: {e}")
            return False
    
    async def query(
        self, 
        question: str, 
        tenant_id: UUID,
        max_sources: int = 5
    ) -> RAGResponse:
        """
        Process RAG query with proper tenant isolation
        Uses LlamaIndex when available, falls back to simple retrieval
        """
        start_time = time.time()
        
        try:
            # Ensure initialization
            await self.initialize()
            
            if self._llamaindex_available:
                # Use LlamaIndex for full RAG pipeline
                response = await self._llamaindex_query(question, tenant_id, max_sources)
            else:
                # Fallback to simple retrieval
                response = await self._simple_query(question, tenant_id, max_sources)
            
            response.processing_time = time.time() - start_time
            return response
            
        except Exception as e:
            print(f"❌ Error in RAG query: {e}")
            return RAGResponse(
                query=question,
                answer=f"Sorry, I encountered an error: {str(e)}",
                sources=[],
                confidence=0.0,
                processing_time=time.time() - start_time,
                method="error",
                tenant_id=str(tenant_id)
            )
    
    async def _llamaindex_query(
        self, 
        question: str, 
        tenant_id: UUID, 
        max_sources: int
    ) -> RAGResponse:
        """Use LlamaIndex for complete RAG pipeline"""
        try:
            # Get tenant components
            vector_store, index, query_engine = await self.get_tenant_components(tenant_id)
            
            if not query_engine:
                return await self._simple_query(question, tenant_id, max_sources)
            
            # LlamaIndex handles retrieval + generation
            response = query_engine.query(question)
            
            # Extract sources
            sources = []
            if hasattr(response, 'source_nodes') and response.source_nodes:
                for i, node in enumerate(response.source_nodes[:max_sources]):
                    sources.append({
                        'content': node.text[:500] + "..." if len(node.text) > 500 else node.text,
                        'metadata': node.metadata,
                        'score': getattr(node, 'score', 0.8),
                        'rank': i + 1
                    })
            
            return RAGResponse(
                query=question,
                answer=str(response),
                sources=sources,
                confidence=0.8 if sources else 0.0,  # Simple confidence based on sources
                processing_time=0.0,  # Will be set by caller
                method="llamaindex_complete",
                tenant_id=str(tenant_id)
            )
            
        except Exception as e:
            print(f"⚠️ LlamaIndex query failed: {e}, falling back to simple")
            return await self._simple_query(question, tenant_id, max_sources)
    
    async def _simple_query(
        self, 
        question: str, 
        tenant_id: UUID, 
        max_sources: int
    ) -> RAGResponse:
        """Simple fallback when LlamaIndex is not available"""
        try:
            # Basic tenant file retrieval
            result = await self.db.execute(
                select(File).where(
                    File.tenant_id == tenant_id,
                    File.sync_status == 'synced',
                    File.deleted_at.is_(None)
                ).limit(max_sources)
            )
            files = result.scalars().all()
            
            # Simple response based on available files
            if files:
                sources = [
                    {
                        'content': f"File: {file.filename}",
                        'metadata': {
                            'filename': file.filename,
                            'file_size': file.file_size,
                            'file_id': str(file.id)
                        },
                        'score': 0.5,
                        'rank': i + 1
                    }
                    for i, file in enumerate(files)
                ]
                
                answer = f"Based on {len(files)} available documents, I found relevant information. However, LlamaIndex is not available for detailed analysis."
                confidence = 0.3
            else:
                sources = []
                answer = "No relevant documents found in your collection."
                confidence = 0.0
            
            return RAGResponse(
                query=question,
                answer=answer,
                sources=sources,
                confidence=confidence,
                processing_time=0.0,  # Will be set by caller
                method="simple_fallback",
                tenant_id=str(tenant_id)
            )
            
        except Exception as e:
            print(f"❌ Simple query failed: {e}")
            return RAGResponse(
                query=question,
                answer="Unable to process query due to database error.",
                sources=[],
                confidence=0.0,
                processing_time=0.0,
                method="error_fallback",
                tenant_id=str(tenant_id)
            )
    
    async def get_tenant_stats(self, tenant_id: UUID) -> Dict[str, Any]:
        """Get statistics for a tenant's RAG system"""
        try:
            # Get document count
            result = await self.db.execute(
                select(File).where(
                    File.tenant_id == tenant_id,
                    File.deleted_at.is_(None)
                )
            )
            files = result.scalars().all()
            
            stats = {
                'tenant_id': str(tenant_id),
                'total_documents': len(files),
                'synced_documents': len([f for f in files if f.sync_status == 'synced']),
                'llamaindex_available': self._llamaindex_available,
                'has_index': str(tenant_id) in self.tenant_indexes
            }
            
            return stats
            
        except Exception as e:
            print(f"❌ Error getting tenant stats: {e}")
            return {'error': str(e)}
    
    async def reset_tenant_index(self, tenant_id: UUID) -> bool:
        """Reset/clear a tenant's index"""
        try:
            tenant_key = str(tenant_id)
            
            # Remove from memory
            if tenant_key in self.tenant_vector_stores:
                del self.tenant_vector_stores[tenant_key]
            if tenant_key in self.tenant_indexes:
                del self.tenant_indexes[tenant_key]
            if tenant_key in self.tenant_query_engines:
                del self.tenant_query_engines[tenant_key]
            
            print(f"✓ Reset index for tenant {tenant_id}")
            return True
            
        except Exception as e:
            print(f"❌ Error resetting tenant index: {e}")
            return False


# Factory function for dependency injection
async def get_multitenant_rag_service(
    db: AsyncSession,
    file_service: FileService,
    embedding_model=None
) -> MultiTenantRAGService:
    """Factory function to create and initialize multi-tenant RAG service"""
    service = MultiTenantRAGService(db, file_service, embedding_model)
    await service.initialize()
    return service