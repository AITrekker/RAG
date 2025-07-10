"""
LlamaIndex-based query engine with multi-tenant context and response synthesis
"""

import asyncio
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.backend.models.database import File, EmbeddingChunk, Tenant
from src.backend.config.settings import get_settings

settings = get_settings()


@dataclass
class TenantQueryResult:
    """Query result with tenant isolation"""
    response: str
    source_nodes: List[Dict[str, Any]]
    confidence: float
    processing_time: float
    tenant_id: UUID
    query_metadata: Dict[str, Any]


class TenantIsolatedQueryEngine:
    """
    LlamaIndex QueryEngine with strict tenant isolation and response synthesis
    """
    
    def __init__(self, tenant_id: UUID, db_session: AsyncSession):
        self.tenant_id = tenant_id
        self.db = db_session
        self._query_engine = None
        self._index = None
        self._vector_store = None
        self._embedding_model = None
        
    async def initialize(self):
        """Initialize LlamaIndex query engine with tenant-specific context"""
        try:
            # Import LlamaIndex components
            from llama_index.core.query_engine import RetrieverQueryEngine
            from llama_index.core.retrievers import VectorIndexRetriever
            from llama_index.core.response_synthesizers import ResponseMode
            from llama_index.core import get_response_synthesizer
            from llama_index.core.indices import VectorStoreIndex
            from llama_index.vector_stores.qdrant import QdrantVectorStore
            from llama_index.embeddings.huggingface import HuggingFaceEmbedding
            
            # Initialize tenant-specific vector store
            await self._initialize_tenant_vector_store()
            
            # Create tenant-isolated embedding model
            self._embedding_model = HuggingFaceEmbedding(
                model_name=settings.embedding_model,
                device="cuda" if settings.use_gpu else "cpu"
            )
            
            # Create vector store index with tenant isolation
            self._index = VectorStoreIndex.from_vector_store(
                self._vector_store,
                embed_model=self._embedding_model
            )
            
            # Create retriever with tenant-specific filtering
            retriever = VectorIndexRetriever(
                index=self._index,
                similarity_top_k=settings.get_rag_retrieval_config().get("max_sources", 5),
                filters=self._get_tenant_filters()
            )
            
            # Create response synthesizer with tenant-aware prompts
            response_synthesizer = get_response_synthesizer(
                response_mode=ResponseMode.COMPACT,
                use_async=True,
                streaming=False,
                service_context=None  # Will use default with our embedding model
            )
            
            # Create tenant-isolated query engine
            self._query_engine = RetrieverQueryEngine(
                retriever=retriever,
                response_synthesizer=response_synthesizer,
            )
            
            print(f"✓ LlamaIndex query engine initialized for tenant {self.tenant_id}")
            
        except ImportError as e:
            print(f"⚠️ LlamaIndex not available: {e}")
            self._query_engine = None
        except Exception as e:
            print(f"⚠️ Error initializing LlamaIndex query engine: {e}")
            self._query_engine = None
    
    async def _initialize_tenant_vector_store(self):
        """Initialize tenant-specific Qdrant vector store"""
        try:
            from qdrant_client import QdrantClient
            from llama_index.vector_stores.qdrant import QdrantVectorStore
            import os
            
            # Get environment-specific collection name
            environment = os.getenv("RAG_ENVIRONMENT", "development")
            collection_name = f"documents_{environment}"
            
            # Initialize Qdrant client
            qdrant_client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port
            )
            
            # Create tenant-isolated vector store
            self._vector_store = QdrantVectorStore(
                client=qdrant_client,
                collection_name=collection_name,
                enable_hybrid=False  # Disable hybrid search for simplicity
            )
            
        except Exception as e:
            print(f"⚠️ Failed to initialize tenant vector store: {e}")
            self._vector_store = None
    
    def _get_tenant_filters(self) -> Dict[str, Any]:
        """Get tenant-specific filters for query isolation"""
        return {
            "must": [
                {"key": "tenant_id", "match": {"value": str(self.tenant_id)}}
            ]
        }
    
    async def query(
        self, 
        query_text: str,
        max_sources: Optional[int] = None,
        metadata_filters: Optional[Dict[str, Any]] = None
    ) -> TenantQueryResult:
        """
        Process query with tenant isolation and response synthesis
        """
        start_time = datetime.utcnow()
        
        if self._query_engine is None:
            # Fallback to simple retrieval if LlamaIndex not available
            return await self._fallback_query(query_text, max_sources, metadata_filters)
        
        try:
            # Add tenant-specific metadata filters
            combined_filters = self._get_tenant_filters()
            if metadata_filters:
                combined_filters["must"].extend([
                    {"key": f"metadata.{k}", "match": {"value": v}}
                    for k, v in metadata_filters.items()
                    if v is not None
                ])
            
            # Update retriever with new filters if needed
            if max_sources:
                self._query_engine.retriever.similarity_top_k = max_sources
            
            # Execute query with tenant isolation
            response = await self._query_engine.aquery(query_text)
            
            # Process source nodes with tenant validation
            source_nodes = []
            for node in response.source_nodes:
                # Validate tenant isolation
                node_tenant_id = node.metadata.get("tenant_id")
                if node_tenant_id == str(self.tenant_id):
                    source_nodes.append({
                        "content": node.text,
                        "metadata": node.metadata,
                        "score": node.score if hasattr(node, 'score') else 0.0,
                        "node_id": node.node_id,
                        "file_id": node.metadata.get("file_id"),
                        "filename": node.metadata.get("filename", "unknown")
                    })
                else:
                    print(f"⚠️ Tenant isolation breach detected: {node_tenant_id} != {self.tenant_id}")
            
            # Calculate processing time
            end_time = datetime.utcnow()
            processing_time = (end_time - start_time).total_seconds()
            
            # Calculate confidence based on source scores
            confidence = (
                sum(node.get("score", 0) for node in source_nodes) / len(source_nodes)
                if source_nodes else 0.0
            )
            
            return TenantQueryResult(
                response=str(response),
                source_nodes=source_nodes,
                confidence=confidence,
                processing_time=processing_time,
                tenant_id=self.tenant_id,
                query_metadata={
                    "query_text": query_text,
                    "max_sources": max_sources,
                    "total_sources": len(source_nodes),
                    "model_used": "llamaindex_query_engine",
                    "filters_applied": combined_filters
                }
            )
            
        except Exception as e:
            print(f"⚠️ LlamaIndex query failed: {e}, falling back to simple retrieval")
            return await self._fallback_query(query_text, max_sources, metadata_filters)
    
    async def _fallback_query(
        self, 
        query_text: str,
        max_sources: Optional[int] = None,
        metadata_filters: Optional[Dict[str, Any]] = None
    ) -> TenantQueryResult:
        """Fallback query processing when LlamaIndex is not available"""
        start_time = datetime.utcnow()
        
        # Simple database-based retrieval with tenant isolation
        max_sources = max_sources or 5
        
        # Query database for tenant-specific chunks
        result = await self.db.execute(
            select(EmbeddingChunk, File)
            .join(File)
            .where(
                EmbeddingChunk.tenant_id == self.tenant_id,
                File.deleted_at.is_(None)
            )
            .limit(max_sources)
        )
        
        chunks_and_files = result.all()
        
        # Create source nodes
        source_nodes = []
        for chunk, file in chunks_and_files:
            # Simple relevance scoring based on keyword matching
            relevance_score = self._calculate_simple_relevance(query_text, chunk.chunk_content)
            
            source_nodes.append({
                "content": chunk.chunk_content,
                "metadata": {
                    "tenant_id": str(self.tenant_id),
                    "file_id": str(file.id),
                    "filename": file.filename,
                    "chunk_index": chunk.chunk_index,
                    "file_path": file.file_path
                },
                "score": relevance_score,
                "node_id": str(chunk.id),
                "file_id": str(file.id),
                "filename": file.filename
            })
        
        # Sort by relevance score
        source_nodes.sort(key=lambda x: x["score"], reverse=True)
        
        # Generate simple response
        response = self._generate_simple_response(query_text, source_nodes[:max_sources])
        
        # Calculate processing time
        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()
        
        # Calculate confidence
        confidence = (
            sum(node["score"] for node in source_nodes) / len(source_nodes)
            if source_nodes else 0.0
        )
        
        return TenantQueryResult(
            response=response,
            source_nodes=source_nodes[:max_sources],
            confidence=confidence,
            processing_time=processing_time,
            tenant_id=self.tenant_id,
            query_metadata={
                "query_text": query_text,
                "max_sources": max_sources,
                "total_sources": len(source_nodes),
                "model_used": "fallback_database_query",
                "filters_applied": {"tenant_id": str(self.tenant_id)}
            }
        )
    
    def _calculate_simple_relevance(self, query: str, content: str) -> float:
        """Calculate simple relevance score based on keyword matching"""
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())
        
        # Calculate Jaccard similarity
        intersection = query_words.intersection(content_words)
        union = query_words.union(content_words)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _generate_simple_response(self, query: str, source_nodes: List[Dict[str, Any]]) -> str:
        """Generate simple response when LlamaIndex is not available"""
        if not source_nodes:
            return f"I couldn't find relevant information to answer your question about '{query}'."
        
        # Create structured response
        response_parts = [
            f"Based on the available documents, here's what I found regarding '{query}':"
        ]
        
        for i, node in enumerate(source_nodes[:3]):  # Limit to top 3
            snippet = node["content"][:200] + "..." if len(node["content"]) > 200 else node["content"]
            confidence_text = "highly relevant" if node["score"] > 0.3 else "relevant" if node["score"] > 0.1 else "somewhat relevant"
            
            response_parts.append(
                f"\\n{i+1}. From {node['filename']} ({confidence_text}, score: {node['score']:.3f}):\\n   {snippet}"
            )
        
        if len(source_nodes) > 3:
            response_parts.append(f"\\n...and {len(source_nodes) - 3} more relevant sources.")
        
        response_parts.append("\\nNote: This response is generated from document excerpts with tenant isolation maintained.")
        
        return "\\n".join(response_parts)
    
    async def get_tenant_statistics(self) -> Dict[str, Any]:
        """Get query engine statistics for the tenant"""
        try:
            # Get document count
            result = await self.db.execute(
                select(File).where(
                    File.tenant_id == self.tenant_id,
                    File.deleted_at.is_(None)
                )
            )
            document_count = len(result.scalars().all())
            
            # Get chunk count
            result = await self.db.execute(
                select(EmbeddingChunk).where(
                    EmbeddingChunk.tenant_id == self.tenant_id
                )
            )
            chunk_count = len(result.scalars().all())
            
            return {
                "tenant_id": str(self.tenant_id),
                "document_count": document_count,
                "chunk_count": chunk_count,
                "query_engine_available": self._query_engine is not None,
                "vector_store_available": self._vector_store is not None,
                "embedding_model": settings.embedding_model
            }
            
        except Exception as e:
            print(f"⚠️ Error getting tenant statistics: {e}")
            return {
                "tenant_id": str(self.tenant_id),
                "document_count": 0,
                "chunk_count": 0,
                "query_engine_available": False,
                "vector_store_available": False,
                "error": str(e)
            }


# Factory function for creating tenant-isolated query engines
async def create_tenant_query_engine(tenant_id: UUID, db_session: AsyncSession) -> TenantIsolatedQueryEngine:
    """Create and initialize a tenant-isolated LlamaIndex query engine"""
    query_engine = TenantIsolatedQueryEngine(tenant_id, db_session)
    await query_engine.initialize()
    return query_engine