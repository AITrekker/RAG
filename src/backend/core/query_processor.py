"""
Query Processing Module for RAG Platform
Handles vector similarity search, query preprocessing, and result ranking
"""

import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import numpy as np

# Internal imports
from .embeddings import get_embedding_service
from .rag_pipeline import get_rag_pipeline
from ..config.settings import settings
from ..utils.vector_store import get_chroma_manager

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """Result from query processing"""
    query: str
    response: str
    sources: List[Dict[str, Any]]
    embeddings_used: int
    processing_time: float
    similarity_scores: List[float]
    tenant_id: str
    timestamp: str
    success: bool = True
    error: Optional[str] = None


class QueryProcessor:
    """
    Main query processing engine for RAG platform
    Handles similarity search, ranking, and response generation
    """
    
    def __init__(
        self,
        tenant_id: str = "default",
        similarity_threshold: float = None,
        max_results: int = None,
        enable_reranking: bool = False
    ):
        """
        Initialize query processor
        
        Args:
            tenant_id: Tenant identifier for data isolation
            similarity_threshold: Minimum similarity threshold for results
            max_results: Maximum number of results to return
            enable_reranking: Enable semantic reranking of results
        """
        self.tenant_id = tenant_id
        self.similarity_threshold = similarity_threshold or settings.vector_store.similarity_threshold
        self.max_results = max_results or settings.vector_store.max_results
        self.enable_reranking = enable_reranking
        
        # Initialize components
        self.embedding_service = get_embedding_service()
        self.rag_pipeline = get_rag_pipeline(tenant_id=tenant_id)
        self.chroma_manager = get_chroma_manager()
        
        # Performance tracking
        self.query_count = 0
        self.total_query_time = 0.0
        self.successful_queries = 0
        
        logger.info(f"Query processor initialized for tenant: {tenant_id}")
        logger.info(f"  Similarity threshold: {self.similarity_threshold}")
        logger.info(f"  Max results: {self.max_results}")
        logger.info(f"  Reranking enabled: {self.enable_reranking}")
    
    def preprocess_query(self, query: str) -> str:
        """
        Preprocess query text for better search results
        
        Args:
            query: Raw query text
            
        Returns:
            Preprocessed query text
        """
        # Basic preprocessing
        processed_query = query.strip()
        
        # Remove excessive whitespace
        processed_query = " ".join(processed_query.split())
        
        # Could add more sophisticated preprocessing here:
        # - Query expansion
        # - Spelling correction
        # - Intent classification
        
        logger.debug(f"Preprocessed query: '{query}' -> '{processed_query}'")
        return processed_query
    
    def similarity_search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform similarity search against vector database
        
        Args:
            query: Search query
            top_k: Number of top results to return
            filter_metadata: Optional metadata filters
            
        Returns:
            List of search results with scores and metadata
        """
        start_time = time.time()
        
        try:
            # Get query embedding
            query_embedding = self.embedding_service.encode_single_text(query)
            
            # Get tenant collection
            collection = self.chroma_manager.get_collection_for_tenant(self.tenant_id)
            
            # Prepare search parameters
            n_results = top_k or self.max_results
            where_clause = {"tenant_id": self.tenant_id}
            
            # Add additional filters if provided
            if filter_metadata:
                where_clause.update(filter_metadata)
            
            # Perform similarity search
            search_results = collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=n_results,
                where=where_clause,
                include=["documents", "metadatas", "distances"]
            )
            
            search_time = time.time() - start_time
            
            # Process results
            results = []
            if search_results["documents"] and search_results["documents"][0]:
                documents = search_results["documents"][0]
                metadatas = search_results["metadatas"][0] if search_results["metadatas"] else [{}] * len(documents)
                distances = search_results["distances"][0] if search_results["distances"] else [0.0] * len(documents)
                
                for doc, metadata, distance in zip(documents, metadatas, distances):
                    # Convert distance to similarity score (Chroma uses L2 distance)
                    similarity_score = 1.0 / (1.0 + distance)
                    
                    # Apply similarity threshold
                    if similarity_score >= self.similarity_threshold:
                        results.append({
                            "text": doc,
                            "metadata": metadata,
                            "score": similarity_score,
                            "distance": distance
                        })
            
            logger.debug(f"Similarity search completed in {search_time:.3f}s, found {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Similarity search failed: {e}")
            return []
    
    def rerank_results(self, query: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rerank search results using semantic similarity
        
        Args:
            query: Original query
            results: Initial search results
            
        Returns:
            Reranked results
        """
        if not self.enable_reranking or len(results) <= 1:
            return results
        
        try:
            # For now, just return sorted by similarity score
            # Could implement more sophisticated reranking here:
            # - Cross-encoder models
            # - BM25 scoring
            # - Learning-to-rank models
            
            reranked = sorted(results, key=lambda x: x["score"], reverse=True)
            logger.debug(f"Reranked {len(results)} results")
            return reranked
            
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            return results
    
    def process_query(
        self,
        query: str,
        top_k: Optional[int] = None,
        include_metadata: bool = True,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> QueryResult:
        """
        Process a complete query with similarity search and response generation
        
        Args:
            query: User query
            top_k: Number of top results to consider
            include_metadata: Whether to include metadata in results
            filter_metadata: Optional metadata filters
            
        Returns:
            QueryResult with response and source information
        """
        start_time = time.time()
        
        try:
            # Preprocess query
            processed_query = self.preprocess_query(query)
            
            # Perform similarity search
            search_results = self.similarity_search(
                processed_query,
                top_k=top_k,
                filter_metadata=filter_metadata
            )
            
            # Rerank results if enabled
            if self.enable_reranking:
                search_results = self.rerank_results(processed_query, search_results)
            
            # Generate response using RAG pipeline
            if search_results:
                try:
                    # Use RAG pipeline for response generation
                    rag_response = self.rag_pipeline.query(
                        processed_query,
                        top_k=len(search_results),
                        include_metadata=include_metadata
                    )
                    
                    response_text = rag_response["response"]
                    rag_sources = rag_response.get("sources", [])
                    
                except Exception as e:
                    logger.warning(f"RAG pipeline failed, using fallback: {e}")
                    # Fallback: concatenate top results
                    response_text = self._create_fallback_response(search_results)
                    rag_sources = search_results
            else:
                response_text = "I couldn't find any relevant information to answer your question."
                rag_sources = []
            
            processing_time = time.time() - start_time
            
            # Update statistics
            self.query_count += 1
            self.total_query_time += processing_time
            self.successful_queries += 1
            
            # Create result
            result = QueryResult(
                query=query,
                response=response_text,
                sources=rag_sources,
                embeddings_used=len(search_results),
                processing_time=processing_time,
                similarity_scores=[r["score"] for r in search_results],
                tenant_id=self.tenant_id,
                timestamp=datetime.now().isoformat(),
                success=True
            )
            
            logger.info(f"Query processed successfully in {processing_time:.3f}s")
            logger.info(f"Found {len(search_results)} relevant sources")
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            
            self.query_count += 1
            self.total_query_time += processing_time
            
            logger.error(f"Query processing failed: {e}")
            
            return QueryResult(
                query=query,
                response="I encountered an error while processing your query. Please try again.",
                sources=[],
                embeddings_used=0,
                processing_time=processing_time,
                similarity_scores=[],
                tenant_id=self.tenant_id,
                timestamp=datetime.now().isoformat(),
                success=False,
                error=str(e)
            )
    
    def _create_fallback_response(self, search_results: List[Dict[str, Any]]) -> str:
        """Create a fallback response by concatenating search results"""
        if not search_results:
            return "No relevant information found."
        
        # Take top 3 results and create a summary
        top_results = search_results[:3]
        response_parts = []
        
        for i, result in enumerate(top_results, 1):
            text = result["text"][:200]  # Truncate to 200 chars
            response_parts.append(f"{i}. {text}...")
        
        return "Based on the available information:\n\n" + "\n\n".join(response_parts)
    
    def batch_query(
        self,
        queries: List[str],
        top_k: Optional[int] = None,
        include_metadata: bool = True
    ) -> List[QueryResult]:
        """
        Process multiple queries in batch
        
        Args:
            queries: List of queries to process
            top_k: Number of top results for each query
            include_metadata: Whether to include metadata
            
        Returns:
            List of QueryResult objects
        """
        results = []
        
        logger.info(f"Processing batch of {len(queries)} queries")
        
        for i, query in enumerate(queries):
            logger.debug(f"Processing query {i+1}/{len(queries)}: {query[:50]}...")
            result = self.process_query(query, top_k, include_metadata)
            results.append(result)
        
        logger.info(f"Batch processing completed: {len(results)} results")
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get query processor performance statistics"""
        avg_query_time = (
            self.total_query_time / self.query_count 
            if self.query_count > 0 else 0
        )
        
        success_rate = (
            self.successful_queries / self.query_count 
            if self.query_count > 0 else 0
        )
        
        return {
            "tenant_id": self.tenant_id,
            "total_queries": self.query_count,
            "successful_queries": self.successful_queries,
            "success_rate": success_rate,
            "total_query_time": self.total_query_time,
            "average_query_time": avg_query_time,
            "similarity_threshold": self.similarity_threshold,
            "max_results": self.max_results,
            "reranking_enabled": self.enable_reranking
        }
    
    def clear_stats(self):
        """Clear performance statistics"""
        self.query_count = 0
        self.total_query_time = 0.0
        self.successful_queries = 0


# Global query processor instances
_query_processors: Dict[str, QueryProcessor] = {}


def get_query_processor(
    tenant_id: str = "default",
    force_reload: bool = False,
    **kwargs
) -> QueryProcessor:
    """
    Get or create query processor for a tenant
    
    Args:
        tenant_id: Tenant identifier
        force_reload: Force creation of new processor
        **kwargs: Additional arguments for QueryProcessor
        
    Returns:
        QueryProcessor instance
    """
    global _query_processors
    
    if force_reload or tenant_id not in _query_processors:
        logger.info(f"Creating new query processor for tenant: {tenant_id}")
        _query_processors[tenant_id] = QueryProcessor(tenant_id=tenant_id, **kwargs)
    
    return _query_processors[tenant_id]


# Convenience functions

def search_documents(
    query: str,
    tenant_id: str = "default",
    top_k: int = 10,
    include_metadata: bool = True
) -> List[Dict[str, Any]]:
    """
    Simple document search function
    
    Args:
        query: Search query
        tenant_id: Tenant identifier
        top_k: Number of results to return
        include_metadata: Whether to include metadata
        
    Returns:
        List of search results
    """
    processor = get_query_processor(tenant_id)
    return processor.similarity_search(query, top_k)


def ask_question(
    question: str,
    tenant_id: str = "default",
    top_k: Optional[int] = None
) -> str:
    """
    Simple question answering function
    
    Args:
        question: User question
        tenant_id: Tenant identifier
        top_k: Number of sources to consider
        
    Returns:
        Answer text
    """
    processor = get_query_processor(tenant_id)
    result = processor.process_query(question, top_k)
    return result.response 