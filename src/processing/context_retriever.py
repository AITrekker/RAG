"""
Context retrieval and enhancement for RAG pipeline.

This module handles:
1. Context retrieval using hybrid search
2. Context enhancement with metadata
3. Context filtering and ranking
4. Context window management
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import json
from datetime import datetime

from .hybrid_search import HybridSearcher, SearchResult, HybridSearchResults
from ..storage.vector_store import VectorStore
from ..db.models import Document, Metadata

logger = logging.getLogger(__name__)

@dataclass
class EnhancedContext:
    """Enhanced context with metadata and relevance info."""
    content: str
    metadata: Dict[str, Any]
    relevance_score: float
    source_doc_id: str
    timestamp: datetime
    context_window: Dict[str, Any]  # Additional context like prev/next paragraphs

class ContextRetriever:
    """
    Manages context retrieval and enhancement for the RAG pipeline.
    
    Features:
    - Hybrid search integration
    - Context window management
    - Metadata enhancement
    - Dynamic context sizing
    - Relevance filtering
    """
    
    def __init__(
        self,
        vector_store: VectorStore,
        min_relevance_score: float = 0.3,
        max_context_length: int = 2000,
        context_overlap: float = 0.2,
        include_metadata: bool = True
    ):
        """
        Initialize context retriever.
        
        Args:
            vector_store: Vector store instance
            min_relevance_score: Minimum relevance score threshold
            max_context_length: Maximum context length in chars
            context_overlap: Overlap ratio between context windows
            include_metadata: Whether to include metadata in results
        """
        self.vector_store = vector_store
        self.min_relevance_score = min_relevance_score
        self.max_context_length = max_context_length
        self.context_overlap = context_overlap
        self.include_metadata = include_metadata
        
        # Initialize hybrid searcher
        self.searcher = HybridSearcher(
            semantic_weight=0.7,
            keyword_weight=0.3,
            max_results=10
        )
        
        logger.info(
            f"Initialized ContextRetriever with "
            f"min_score={min_relevance_score}, "
            f"max_length={max_context_length}"
        )
    
    async def retrieve_context(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        k: int = 5
    ) -> List[EnhancedContext]:
        """
        Retrieve and enhance context for a query.
        
        Args:
            query: User query
            filters: Optional metadata filters
            k: Number of contexts to retrieve
            
        Returns:
            List of enhanced contexts
        """
        try:
            # Get candidate documents
            documents = await self._get_candidate_documents(filters)
            
            # Perform hybrid search
            search_results = self.searcher.search(
                query=query,
                documents=documents,
                filters=filters
            )
            
            # Filter by relevance
            relevant_results = self._filter_by_relevance(search_results.results)
            
            # Enhance contexts
            enhanced_contexts = []
            for result in relevant_results[:k]:
                context = await self._enhance_context(result)
                if context:
                    enhanced_contexts.append(context)
            
            logger.info(
                f"Retrieved {len(enhanced_contexts)} contexts "
                f"for query: {query[:50]}..."
            )
            
            return enhanced_contexts
            
        except Exception as e:
            logger.error(f"Context retrieval failed: {str(e)}")
            raise
    
    async def _get_candidate_documents(
        self,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Get candidate documents from vector store."""
        # Get documents matching filters
        docs = await self.vector_store.get_documents(filters)
        
        # Convert to dictionary format
        documents = []
        for doc in docs:
            documents.append({
                'content': doc.content,
                'metadata': doc.metadata,
                'id': str(doc.id),
                'timestamp': doc.created_at
            })
        
        return documents
    
    def _filter_by_relevance(
        self,
        results: List[SearchResult]
    ) -> List[SearchResult]:
        """Filter search results by relevance score."""
        return [
            result for result in results
            if result.score >= self.min_relevance_score
        ]
    
    async def _enhance_context(
        self,
        result: SearchResult
    ) -> Optional[EnhancedContext]:
        """Enhance a search result with additional context."""
        try:
            # Get document from vector store
            doc = await self.vector_store.get_document(result.node_id)
            if not doc:
                return None
            
            # Get context window
            context_window = self._get_context_window(
                doc.content,
                result.content
            )
            
            # Create enhanced context
            context = EnhancedContext(
                content=result.content,
                metadata=result.metadata if self.include_metadata else {},
                relevance_score=result.score,
                source_doc_id=result.node_id,
                timestamp=doc.created_at,
                context_window=context_window
            )
            
            return context
            
        except Exception as e:
            logger.error(f"Context enhancement failed: {str(e)}")
            return None
    
    def _get_context_window(
        self,
        full_content: str,
        match_content: str
    ) -> Dict[str, Any]:
        """Get context window around matched content."""
        try:
            # Find match position
            start_pos = full_content.find(match_content)
            if start_pos == -1:
                return {}
            
            end_pos = start_pos + len(match_content)
            
            # Calculate window size
            window_size = int(self.max_context_length * (1 + self.context_overlap))
            half_window = window_size // 2
            
            # Get previous context
            prev_start = max(0, start_pos - half_window)
            previous = full_content[prev_start:start_pos].strip()
            
            # Get next context
            next_end = min(len(full_content), end_pos + half_window)
            next_text = full_content[end_pos:next_end].strip()
            
            return {
                'previous': previous,
                'next': next_text,
                'start_pos': start_pos,
                'end_pos': end_pos
            }
            
        except Exception as e:
            logger.error(f"Context window extraction failed: {str(e)}")
            return {} 