"""
RAG Pipeline using LlamaIndex for document processing and query orchestration
Optimized for RTX 5070 GPU acceleration and multi-tenant architecture
"""

import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import asyncio
from datetime import datetime

# LlamaIndex imports
from llama_index.core import (
    VectorStoreIndex, 
    ServiceContext, 
    StorageContext,
    Document,
    Settings
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.embeddings import BaseEmbedding

from llama_index.core.query_engine import BaseQueryEngine
from llama_index.core.schema import QueryBundle
from llama_index.core.response_synthesizers import ResponseMode
from llama_index.core.callbacks import CallbackManager, LlamaDebugHandler
from llama_index.vector_stores.chroma import ChromaVectorStore

# Internal imports
from .embeddings import get_embedding_service, EmbeddingService
from ..config.settings import settings
from ..utils.vector_store import get_chroma_client

logger = logging.getLogger(__name__)


class HuggingFaceEmbeddingWrapper(BaseEmbedding):
    """
    Wrapper to integrate our RTX 5070 optimized embedding service with LlamaIndex
    """
    
    def __init__(self, embedding_service: EmbeddingService):
        """Initialize with our embedding service"""
        self.embedding_service = embedding_service
        # Get embedding dimension from the service
        if not self.embedding_service.sentence_transformer:
            self.embedding_service.load_model()
        
        embed_dim = self.embedding_service.sentence_transformer.get_sentence_embedding_dimension()
        super().__init__(embed_batch_size=embedding_service.batch_size, embed_dim=embed_dim)
    
    def _get_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for a single query"""
        embedding = self.embedding_service.encode_single_text(query)
        return embedding.tolist()
    
    def _get_text_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        embedding = self.embedding_service.encode_single_text(text)
        return embedding.tolist()
    
    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        embeddings = self.embedding_service.encode_texts(texts)
        return embeddings.tolist()
    
    async def _aget_query_embedding(self, query: str) -> List[float]:
        """Async version of query embedding"""
        return self._get_query_embedding(query)
    
    async def _aget_text_embedding(self, text: str) -> List[float]:
        """Async version of text embedding"""
        return self._get_text_embedding(text)


class RAGPipeline:
    """
    Main RAG Pipeline orchestrator using LlamaIndex
    Handles document ingestion, indexing, and query processing
    """
    
    def __init__(
        self,
        tenant_id: str = "default",
        collection_name: Optional[str] = None,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        enable_debug: bool = False
    ):
        """
        Initialize the RAG Pipeline
        
        Args:
            tenant_id: Tenant identifier for data isolation
            collection_name: Vector store collection name
            chunk_size: Document chunk size in tokens
            chunk_overlap: Overlap between chunks
            enable_debug: Enable LlamaIndex debug logging
        """
        self.tenant_id = tenant_id
        self.collection_name = collection_name or f"{settings.vector_store.collection_name_prefix}_{tenant_id}"
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Initialize components
        self.embedding_service = None
        self.embedding_wrapper = None
        self.vector_store = None
        self.storage_context = None
        self.index = None
        self.query_engine = None
        
        # Performance tracking
        self.query_times = []
        self.index_times = []
        
        # Debug setup
        if enable_debug:
            llama_debug = LlamaDebugHandler(print_trace_on_end=True)
            callback_manager = CallbackManager([llama_debug])
            Settings.callback_manager = callback_manager
        
        logger.info(f"Initializing RAG Pipeline for tenant: {tenant_id}")
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize all RAG pipeline components"""
        try:
            # Initialize embedding service with RTX 5070 optimization
            logger.info("Initializing embedding service...")
            self.embedding_service = get_embedding_service()
            self.embedding_wrapper = HuggingFaceEmbeddingWrapper(self.embedding_service)
            
            # Initialize vector store (Chroma)
            logger.info(f"Initializing vector store: {self.collection_name}")
            chroma_client = get_chroma_client()
            chroma_collection = chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"tenant_id": self.tenant_id}
            )
            self.vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
            
            # Create storage context
            self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
            
            # Configure global settings
            Settings.embed_model = self.embedding_wrapper
            Settings.chunk_size = self.chunk_size
            Settings.chunk_overlap = self.chunk_overlap
            
            logger.info("✅ RAG Pipeline components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG pipeline components: {e}")
            raise
    
    def create_index(self, documents: List[Document] = None) -> VectorStoreIndex:
        """
        Create or load vector index
        
        Args:
            documents: Optional list of documents to index immediately
            
        Returns:
            VectorStoreIndex instance
        """
        start_time = time.time()
        
        try:
            if documents:
                logger.info(f"Creating new index with {len(documents)} documents...")
                # Create index with documents
                self.index = VectorStoreIndex.from_documents(
                    documents,
                    storage_context=self.storage_context,
                    show_progress=True
                )
            else:
                # Try to load existing index or create empty one
                try:
                    logger.info("Loading existing index...")
                    self.index = VectorStoreIndex.from_vector_store(
                        vector_store=self.vector_store,
                        storage_context=self.storage_context
                    )
                except Exception:
                    logger.info("Creating new empty index...")
                    self.index = VectorStoreIndex(
                        [],
                        storage_context=self.storage_context
                    )
            
            # Create query engine
            self.query_engine = self.index.as_query_engine(
                similarity_top_k=settings.vector_store.max_results,
                response_mode="compact"
            )
            
            creation_time = time.time() - start_time
            self.index_times.append(creation_time)
            
            logger.info(f"✅ Index created/loaded in {creation_time:.2f} seconds")
            return self.index
            
        except Exception as e:
            logger.error(f"Failed to create/load index: {e}")
            raise
    
    def add_documents(self, documents: List[Document]) -> None:
        """
        Add documents to existing index
        
        Args:
            documents: List of LlamaIndex Document objects
        """
        if not self.index:
            raise ValueError("Index not initialized. Call create_index() first.")
        
        start_time = time.time()
        
        try:
            logger.info(f"Adding {len(documents)} documents to index...")
            
            # Insert documents into index
            for doc in documents:
                self.index.insert(doc)
            
            # Refresh query engine
            self.query_engine = self.index.as_query_engine(
                similarity_top_k=settings.vector_store.max_results,
                response_mode="compact"
            )
            
            add_time = time.time() - start_time
            logger.info(f"✅ Added {len(documents)} documents in {add_time:.2f} seconds")
            
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            raise
    
    def query(
        self, 
        query_text: str, 
        top_k: Optional[int] = None,
        include_metadata: bool = True,
        use_local_llm: bool = True
    ) -> Dict[str, Any]:
        """
        Query the RAG system
        
        Args:
            query_text: User query
            top_k: Number of top results to return
            include_metadata: Whether to include source metadata
            use_local_llm: Whether to use local LLM for generation
            
        Returns:
            Dictionary with response, sources, and metadata
        """
        if not self.query_engine:
            raise ValueError("Query engine not initialized. Call create_index() first.")
        
        start_time = time.time()
        
        try:
            logger.info(f"Processing query: {query_text[:100]}...")
            
            # Update top_k if provided
            if top_k:
                self.query_engine.retriever.similarity_top_k = top_k
            
            if use_local_llm:
                # Use our local LLM service for generation
                from .llm_service import get_llm_service
                
                # Get relevant documents using retriever
                retriever = self.query_engine.retriever
                retrieved_nodes = retriever.retrieve(query_text)
                
                # Extract source information
                sources = []
                for node in retrieved_nodes:
                    source_info = {
                        "text": node.text,
                        "score": node.score if hasattr(node, 'score') else 0.0,
                    }
                    
                    if include_metadata and node.metadata:
                        source_info["metadata"] = node.metadata
                    
                    sources.append(source_info)
                
                # Generate response using local LLM
                if sources:
                    llm_service = get_llm_service()
                    llm_response = llm_service.generate_rag_response(query_text, sources)
                    response_text = llm_response.text
                else:
                    response_text = "I couldn't find relevant information to answer your question."
                
            else:
                # Use LlamaIndex default query engine
                response: Response = self.query_engine.query(query_text)
                response_text = str(response)
                
                # Extract source information
                sources = []
                for node in response.source_nodes:
                    source_info = {
                        "text": node.text,
                        "score": node.score if hasattr(node, 'score') else 0.0,
                    }
                    
                    if include_metadata and node.metadata:
                        source_info["metadata"] = node.metadata
                    
                    sources.append(source_info)
            
            query_time = time.time() - start_time
            self.query_times.append(query_time)
            
            result = {
                "response": response_text,
                "sources": sources if include_metadata else [],
                "query_time": query_time,
                "timestamp": datetime.now().isoformat(),
                "tenant_id": self.tenant_id
            }
            
            logger.info(f"✅ Query processed in {query_time:.3f} seconds")
            logger.info(f"Found {len(sources)} relevant sources")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to process query: {e}")
            raise
    
    async def async_query(
        self, 
        query_text: str, 
        top_k: Optional[int] = None,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Async version of query processing
        
        Args:
            query_text: User query
            top_k: Number of top results to return
            include_metadata: Whether to include source metadata
            
        Returns:
            Dictionary with response, sources, and metadata
        """
        # For now, just run sync version in executor
        # LlamaIndex will add better async support in future versions
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            self.query,
            query_text,
            top_k,
            include_metadata
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline performance statistics"""
        stats = {
            "tenant_id": self.tenant_id,
            "collection_name": self.collection_name,
            "embedding_service_stats": self.embedding_service.get_performance_stats() if self.embedding_service else {},
            "queries_processed": len(self.query_times),
            "indexes_created": len(self.index_times),
        }
        
        if self.query_times:
            stats.update({
                "average_query_time": sum(self.query_times) / len(self.query_times),
                "total_query_time": sum(self.query_times),
                "fastest_query": min(self.query_times),
                "slowest_query": max(self.query_times)
            })
        
        if self.index_times:
            stats.update({
                "average_index_time": sum(self.index_times) / len(self.index_times),
                "total_index_time": sum(self.index_times)
            })
        
        return stats
    
    def clear_cache(self):
        """Clear caches and free memory"""
        if self.embedding_service:
            self.embedding_service.clear_cache()
        
        # Clear query times to free memory
        self.query_times = []
        self.index_times = []
        
        logger.info("Pipeline caches cleared")


def create_documents_from_texts(
    texts: List[str],
    metadatas: List[Dict[str, Any]] = None,
    doc_ids: List[str] = None
) -> List[Document]:
    """
    Create LlamaIndex Document objects from texts
    
    Args:
        texts: List of text content
        metadatas: Optional metadata for each text
        doc_ids: Optional document IDs
        
    Returns:
        List of LlamaIndex Document objects
    """
    documents = []
    
    for i, text in enumerate(texts):
        metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
        doc_id = doc_ids[i] if doc_ids and i < len(doc_ids) else f"doc_{i}"
        
        doc = Document(
            text=text,
            metadata=metadata,
            id_=doc_id
        )
        documents.append(doc)
    
    return documents


# Global pipeline instances for reuse
_pipeline_instances: Dict[str, RAGPipeline] = {}


def get_rag_pipeline(
    tenant_id: str = "default",
    force_reload: bool = False,
    **kwargs
) -> RAGPipeline:
    """
    Get or create RAG pipeline instance for a tenant
    
    Args:
        tenant_id: Tenant identifier
        force_reload: Force creation of new pipeline
        **kwargs: Additional arguments for RAGPipeline
        
    Returns:
        RAGPipeline instance
    """
    global _pipeline_instances
    
    if force_reload or tenant_id not in _pipeline_instances:
        logger.info(f"Creating new RAG pipeline for tenant: {tenant_id}")
        _pipeline_instances[tenant_id] = RAGPipeline(tenant_id=tenant_id, **kwargs)
    
    return _pipeline_instances[tenant_id] 