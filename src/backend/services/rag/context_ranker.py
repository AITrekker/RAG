"""Context ranking and filtering for RAG system."""

import re
from typing import List, Set
from collections import Counter

from .base import RetrievedChunk, RankerInterface

class ContextRanker(RankerInterface):
    """Ranks and filters retrieved chunks for optimal context."""
    
    def __init__(self, max_chunks: int = 5, diversity_threshold: float = 0.8):
        self.max_chunks = max_chunks
        self.diversity_threshold = diversity_threshold
    
    def rank_chunks(self, chunks: List[RetrievedChunk], query: str) -> List[RetrievedChunk]:
        """Rank chunks by relevance to query."""
        if not chunks:
            return chunks
        
        # Calculate additional relevance scores
        for chunk in chunks:
            # Base score from vector similarity
            base_score = chunk.score
            
            # Keyword matching bonus
            keyword_score = self._calculate_keyword_score(chunk.content, query)
            
            # Position bonus (earlier chunks often more important)
            position_score = self._calculate_position_score(chunk.chunk_index)
            
            # File type bonus
            file_type_score = self._calculate_file_type_score(chunk.metadata.get("file_type", ""))
            
            # Combine scores
            chunk.score = (
                base_score * 0.6 +           # Vector similarity (primary)
                keyword_score * 0.2 +        # Keyword matching
                position_score * 0.1 +       # Position in document  
                file_type_score * 0.1        # File type preference
            )
        
        # Sort by combined score
        ranked_chunks = sorted(chunks, key=lambda x: x.score, reverse=True)
        
        return ranked_chunks[:self.max_chunks]
    
    def filter_duplicates(self, chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
        """Remove duplicate or near-duplicate content."""
        if not chunks:
            return chunks
        
        filtered_chunks = []
        seen_content = set()
        
        for chunk in chunks:
            # Create content signature for duplicate detection
            content_signature = self._create_content_signature(chunk.content)
            
            # Check for near-duplicates
            is_duplicate = False
            for seen_sig in seen_content:
                if self._calculate_similarity(content_signature, seen_sig) > self.diversity_threshold:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                filtered_chunks.append(chunk)
                seen_content.add(content_signature)
        
        return filtered_chunks
    
    def apply_diversity(self, chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
        """Ensure source diversity in results."""
        if not chunks:
            return chunks
        
        # Group chunks by source file
        file_groups = {}
        for chunk in chunks:
            file_id = chunk.file_id
            if file_id not in file_groups:
                file_groups[file_id] = []
            file_groups[file_id].append(chunk)
        
        # Select best chunk from each file first
        diverse_chunks = []
        for file_chunks in file_groups.values():
            # Take the highest scoring chunk from each file
            best_chunk = max(file_chunks, key=lambda x: x.score)
            diverse_chunks.append(best_chunk)
        
        # Sort by score
        diverse_chunks.sort(key=lambda x: x.score, reverse=True)
        
        # Fill remaining slots with next best chunks if needed
        if len(diverse_chunks) < self.max_chunks:
            remaining_chunks = [
                chunk for chunk in chunks 
                if chunk.chunk_id not in {c.chunk_id for c in diverse_chunks}
            ]
            remaining_chunks.sort(key=lambda x: x.score, reverse=True)
            
            slots_remaining = self.max_chunks - len(diverse_chunks)
            diverse_chunks.extend(remaining_chunks[:slots_remaining])
        
        return diverse_chunks[:self.max_chunks]
    
    def _calculate_keyword_score(self, content: str, query: str) -> float:
        """Calculate keyword matching score."""
        # Extract keywords from query (simple approach)
        query_words = set(re.findall(r'\b\w+\b', query.lower()))
        content_words = set(re.findall(r'\b\w+\b', content.lower()))
        
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'}
        query_words -= stop_words
        
        if not query_words:
            return 0.0
        
        # Calculate overlap
        matches = query_words.intersection(content_words)
        return len(matches) / len(query_words)
    
    def _calculate_position_score(self, chunk_index: int) -> float:
        """Calculate position-based score (earlier chunks preferred)."""
        # Exponential decay for position
        return max(0.1, 1.0 / (1.0 + chunk_index * 0.1))
    
    def _calculate_file_type_score(self, file_type: str) -> float:
        """Calculate file type preference score."""
        # Preference weights for different file types
        type_weights = {
            "text/plain": 1.0,
            "text/html": 0.9,
            "application/pdf": 0.8,
            "application/msword": 0.7,
            "unknown": 0.5
        }
        
        return type_weights.get(file_type, 0.5)
    
    def _create_content_signature(self, content: str) -> str:
        """Create a signature for content to detect duplicates."""
        # Remove punctuation and extra spaces
        cleaned = re.sub(r'[^\w\s]', '', content.lower())
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Take first 100 characters as signature
        return cleaned[:100]
    
    def _calculate_similarity(self, sig1: str, sig2: str) -> float:
        """Calculate similarity between two content signatures."""
        if not sig1 or not sig2:
            return 0.0
        
        # Simple Jaccard similarity
        words1 = set(sig1.split())
        words2 = set(sig2.split())
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def get_context_stats(self, chunks: List[RetrievedChunk]) -> dict:
        """Get statistics about the context chunks."""
        if not chunks:
            return {}
        
        # File source distribution
        file_counts = Counter(chunk.filename for chunk in chunks)
        
        # Score distribution
        scores = [chunk.score for chunk in chunks]
        
        # Content length distribution
        content_lengths = [len(chunk.content) for chunk in chunks]
        
        return {
            "total_chunks": len(chunks),
            "unique_sources": len(file_counts),
            "source_distribution": dict(file_counts),
            "score_range": {"min": min(scores), "max": max(scores), "avg": sum(scores) / len(scores)},
            "content_length": {"min": min(content_lengths), "max": max(content_lengths), "avg": sum(content_lengths) / len(content_lengths)},
            "total_content_length": sum(content_lengths)
        }