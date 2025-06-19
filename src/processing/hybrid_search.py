"""
Hybrid search implementation combining semantic and keyword-based search.

This module provides a hybrid search approach that combines:
1. Dense retrieval (semantic search using embeddings)
2. Sparse retrieval (BM25/keyword-based search)
3. Hybrid ranking and reranking
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import MinMaxScaler

logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    """Represents a single search result."""
    node_id: str
    content: str
    score: float
    metadata: Dict[str, Any]
    source: str  # 'semantic', 'keyword', or 'hybrid'

@dataclass
class HybridSearchResults:
    """Container for hybrid search results."""
    results: List[SearchResult]
    semantic_time_ms: float
    keyword_time_ms: float
    rerank_time_ms: float
    total_time_ms: float
    stats: Dict[str, Any]

class HybridSearcher:
    """
    Implements hybrid search combining semantic and keyword-based approaches.
    
    Features:
    - Semantic search using sentence transformers
    - Keyword search using BM25
    - Configurable weights for hybrid scoring
    - Advanced reranking
    - Result deduplication
    """
    
    def __init__(
        self,
        embedding_model: str = "all-MiniLM-L6-v2",
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
        max_results: int = 10,
        rerank_top_k: int = 20
    ):
        """
        Initialize the hybrid searcher.
        
        Args:
            embedding_model: Name of the sentence transformer model
            semantic_weight: Weight for semantic search scores (0-1)
            keyword_weight: Weight for keyword search scores (0-1)
            max_results: Maximum number of final results
            rerank_top_k: Number of top results to rerank
        """
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        self.max_results = max_results
        self.rerank_top_k = rerank_top_k
        
        # Initialize embedding model
        self.embedding_model = SentenceTransformer(embedding_model)
        
        # Initialize score normalizers
        self.semantic_scaler = MinMaxScaler()
        self.keyword_scaler = MinMaxScaler()
        
        logger.info(
            f"Initialized HybridSearcher with model {embedding_model}, "
            f"weights: semantic={semantic_weight}, keyword={keyword_weight}"
        )
    
    def search(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        filters: Optional[Dict[str, Any]] = None
    ) -> HybridSearchResults:
        """
        Perform hybrid search over documents.
        
        Args:
            query: Search query
            documents: List of document dictionaries with 'content' and 'metadata'
            filters: Optional filters to apply
            
        Returns:
            HybridSearchResults: Search results and statistics
        """
        import time
        start_time = time.time()
        
        try:
            # Extract document content
            contents = [doc['content'] for doc in documents]
            
            # Semantic search
            semantic_start = time.time()
            semantic_results = self._semantic_search(query, contents, documents)
            semantic_time = (time.time() - semantic_start) * 1000
            
            # Keyword search
            keyword_start = time.time()
            keyword_results = self._keyword_search(query, contents, documents)
            keyword_time = (time.time() - keyword_start) * 1000
            
            # Combine and rerank results
            rerank_start = time.time()
            final_results = self._combine_and_rerank(
                query,
                semantic_results,
                keyword_results,
                filters
            )
            rerank_time = (time.time() - rerank_start) * 1000
            
            total_time = (time.time() - start_time) * 1000
            
            # Collect statistics
            stats = {
                "total_documents": len(documents),
                "semantic_results": len(semantic_results),
                "keyword_results": len(keyword_results),
                "final_results": len(final_results),
                "semantic_weight": self.semantic_weight,
                "keyword_weight": self.keyword_weight
            }
            
            results = HybridSearchResults(
                results=final_results[:self.max_results],
                semantic_time_ms=semantic_time,
                keyword_time_ms=keyword_time,
                rerank_time_ms=rerank_time,
                total_time_ms=total_time,
                stats=stats
            )
            
            logger.info(
                f"Hybrid search completed in {total_time:.2f}ms: "
                f"{len(final_results)} results"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {str(e)}")
            raise
    
    def _semantic_search(
        self,
        query: str,
        contents: List[str],
        documents: List[Dict[str, Any]]
    ) -> List[SearchResult]:
        """Perform semantic search using sentence transformers."""
        # Generate embeddings
        query_embedding = self.embedding_model.encode(query, convert_to_tensor=True)
        doc_embeddings = self.embedding_model.encode(contents, convert_to_tensor=True)
        
        # Calculate cosine similarities
        similarities = np.inner(query_embedding, doc_embeddings)
        
        # Normalize scores
        normalized_scores = self.semantic_scaler.fit_transform(
            similarities.reshape(-1, 1)
        ).flatten()
        
        # Create results
        results = []
        for idx, score in enumerate(normalized_scores):
            results.append(SearchResult(
                node_id=str(idx),
                content=contents[idx],
                score=float(score),
                metadata=documents[idx].get('metadata', {}),
                source='semantic'
            ))
        
        # Sort by score
        results.sort(key=lambda x: x.score, reverse=True)
        return results
    
    def _keyword_search(
        self,
        query: str,
        contents: List[str],
        documents: List[Dict[str, Any]]
    ) -> List[SearchResult]:
        """Perform keyword search using BM25."""
        # Tokenize documents
        tokenized_corpus = [doc.split() for doc in contents]
        
        # Initialize BM25
        bm25 = BM25Okapi(tokenized_corpus)
        
        # Get scores
        scores = bm25.get_scores(query.split())
        
        # Normalize scores
        normalized_scores = self.keyword_scaler.fit_transform(
            scores.reshape(-1, 1)
        ).flatten()
        
        # Create results
        results = []
        for idx, score in enumerate(normalized_scores):
            results.append(SearchResult(
                node_id=str(idx),
                content=contents[idx],
                score=float(score),
                metadata=documents[idx].get('metadata', {}),
                source='keyword'
            ))
        
        # Sort by score
        results.sort(key=lambda x: x.score, reverse=True)
        return results
    
    def _combine_and_rerank(
        self,
        query: str,
        semantic_results: List[SearchResult],
        keyword_results: List[SearchResult],
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """Combine and rerank results."""
        # Get top K results from each source
        top_semantic = semantic_results[:self.rerank_top_k]
        top_keyword = keyword_results[:self.rerank_top_k]
        
        # Combine results
        combined_results = {}
        
        # Add semantic results
        for result in top_semantic:
            combined_results[result.node_id] = {
                'result': result,
                'semantic_score': result.score,
                'keyword_score': 0.0
            }
        
        # Add or update with keyword results
        for result in top_keyword:
            if result.node_id in combined_results:
                combined_results[result.node_id]['keyword_score'] = result.score
            else:
                combined_results[result.node_id] = {
                    'result': result,
                    'semantic_score': 0.0,
                    'keyword_score': result.score
                }
        
        # Calculate hybrid scores
        final_results = []
        for node_id, scores in combined_results.items():
            hybrid_score = (
                self.semantic_weight * scores['semantic_score'] +
                self.keyword_weight * scores['keyword_score']
            )
            
            result = scores['result']
            result.score = hybrid_score
            result.source = 'hybrid'
            
            # Apply filters if provided
            if filters and not self._apply_filters(result, filters):
                continue
            
            final_results.append(result)
        
        # Sort by hybrid score
        final_results.sort(key=lambda x: x.score, reverse=True)
        return final_results
    
    def _apply_filters(self, result: SearchResult, filters: Dict[str, Any]) -> bool:
        """Apply metadata filters to a result."""
        for key, value in filters.items():
            # Handle nested metadata keys (e.g., 'author.name')
            keys = key.split('.')
            current = result.metadata
            
            # Traverse nested structure
            for k in keys[:-1]:
                if not isinstance(current, dict) or k not in current:
                    return False
                current = current[k]
            
            # Check final key
            final_key = keys[-1]
            if not isinstance(current, dict) or final_key not in current:
                return False
            
            # Compare values
            if current[final_key] != value:
                return False
        
        return True 