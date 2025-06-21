"""
Response Generation Pipeline with Source Citation Tracking
Advanced response generation and formatting for RAG platform
"""

import logging
import time
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

# Internal imports
from .llm_service import get_llm_service, LLMResponse
from .query_processor import QueryResult
from ..config.settings import settings

logger = logging.getLogger(__name__)


class CitationStyle(Enum):
    """Citation formatting styles"""
    NUMBERED = "numbered"
    BRACKETED = "bracketed" 
    FOOTNOTE = "footnote"
    INLINE = "inline"


@dataclass
class Citation:
    """Individual citation information"""
    id: str
    source_text: str
    metadata: Dict[str, Any]
    relevance_score: float
    position_in_response: int
    citation_text: str


@dataclass
class GeneratedResponse:
    """Complete response with citations and metadata"""
    response_text: str
    citations: List[Citation]
    source_count: int
    generation_time: float
    quality_score: float
    confidence_score: float
    model_used: str
    timestamp: str
    success: bool = True
    error: Optional[str] = None


class ResponseGenerator:
    """
    Advanced response generation with citation tracking
    Handles formatting, quality assessment, and source attribution
    """
    
    def __init__(
        self,
        citation_style: CitationStyle = CitationStyle.NUMBERED,
        max_sources: int = 5,
        min_relevance_score: float = 0.6,
        enable_quality_check: bool = True
    ):
        """
        Initialize response generator
        
        Args:
            citation_style: How to format citations
            max_sources: Maximum number of sources to cite
            min_relevance_score: Minimum score for source inclusion
            enable_quality_check: Enable response quality assessment
        """
        self.citation_style = citation_style
        self.max_sources = max_sources
        self.min_relevance_score = min_relevance_score
        self.enable_quality_check = enable_quality_check
        
        # Performance tracking
        self.generation_count = 0
        self.total_generation_time = 0.0
        self.quality_scores = []
        
        logger.info(f"Response generator initialized")
        logger.info(f"  Citation style: {citation_style.value}")
        logger.info(f"  Max sources: {max_sources}")
        logger.info(f"  Min relevance: {min_relevance_score}")
    
    def generate_response(
        self,
        query: str,
        sources: List[Dict[str, Any]],
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 512
    ) -> GeneratedResponse:
        """
        Generate response with proper citation tracking
        
        Args:
            query: User query
            sources: List of source documents with metadata
            model_name: Optional model to use for generation
            temperature: Generation temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            GeneratedResponse with citations and metadata
        """
        start_time = time.time()
        
        try:
            # Filter and rank sources
            filtered_sources = self._filter_sources(sources)
            
            if not filtered_sources:
                return GeneratedResponse(
                    response_text="I couldn't find sufficient relevant information to answer your question.",
                    citations=[],
                    source_count=0,
                    generation_time=time.time() - start_time,
                    quality_score=0.0,
                    confidence_score=0.0,
                    model_used=model_name or "default",
                    timestamp=datetime.now().isoformat(),
                    success=True
                )
            
            # Generate base response
            llm_service = get_llm_service(model_name)
            llm_response = llm_service.generate_rag_response(
                query,
                filtered_sources,
                max_new_tokens=max_tokens,
                temperature=temperature
            )
            
            if not llm_response.success:
                return GeneratedResponse(
                    response_text="I encountered an error while generating the response.",
                    citations=[],
                    source_count=0,
                    generation_time=time.time() - start_time,
                    quality_score=0.0,
                    confidence_score=0.0,
                    model_used=llm_response.model_name,
                    timestamp=datetime.now().isoformat(),
                    success=False,
                    error=llm_response.error
                )
            
            # Process citations
            citations = self._create_citations(filtered_sources, llm_response.text)
            
            # Format response with citations
            formatted_response = self._format_response_with_citations(
                llm_response.text,
                citations
            )
            
            # Assess quality if enabled
            quality_score = self._assess_quality(query, formatted_response, sources) if self.enable_quality_check else 0.8
            confidence_score = self._calculate_confidence(sources, llm_response)
            
            generation_time = time.time() - start_time
            
            # Update statistics
            self.generation_count += 1
            self.total_generation_time += generation_time
            self.quality_scores.append(quality_score)
            
            result = GeneratedResponse(
                response_text=formatted_response,
                citations=citations,
                source_count=len(filtered_sources),
                generation_time=generation_time,
                quality_score=quality_score,
                confidence_score=confidence_score,
                model_used=llm_response.model_name,
                timestamp=datetime.now().isoformat(),
                success=True
            )
            
            logger.info(f"Generated response with {len(citations)} citations in {generation_time:.3f}s")
            logger.info(f"Quality score: {quality_score:.2f}, Confidence: {confidence_score:.2f}")
            
            return result
            
        except Exception as e:
            generation_time = time.time() - start_time
            logger.error(f"Response generation failed: {e}")
            
            return GeneratedResponse(
                response_text="I encountered an error while generating the response.",
                citations=[],
                source_count=0,
                generation_time=generation_time,
                quality_score=0.0,
                confidence_score=0.0,
                model_used=model_name or "unknown",
                timestamp=datetime.now().isoformat(),
                success=False,
                error=str(e)
            )
    
    def _filter_sources(self, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter sources by relevance and limit count"""
        # Filter by relevance score
        relevant_sources = [
            source for source in sources 
            if source.get("score", 0.0) >= self.min_relevance_score
        ]
        
        # Sort by relevance score
        relevant_sources.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        
        # Limit to max sources
        return relevant_sources[:self.max_sources]
    
    def _create_citations(self, sources: List[Dict[str, Any]], response_text: str) -> List[Citation]:
        """Create citation objects from sources"""
        citations = []
        
        for i, source in enumerate(sources):
            citation_id = f"cite_{i+1}"
            
            # Create citation text based on style
            citation_text = self._format_citation(i+1, source)
            
            citation = Citation(
                id=citation_id,
                source_text=source.get("text", ""),
                metadata=source.get("metadata", {}),
                relevance_score=source.get("score", 0.0),
                position_in_response=i,
                citation_text=citation_text
            )
            
            citations.append(citation)
        
        return citations
    
    def _format_citation(self, index: int, source: Dict[str, Any]) -> str:
        """Format individual citation based on style"""
        metadata = source.get("metadata", {})
        
        if self.citation_style == CitationStyle.NUMBERED:
            return f"[{index}]"
        elif self.citation_style == CitationStyle.BRACKETED:
            source_name = metadata.get("source", f"Source {index}")
            return f"[{source_name}]"
        elif self.citation_style == CitationStyle.FOOTNOTE:
            return f"^{index}"
        elif self.citation_style == CitationStyle.INLINE:
            source_name = metadata.get("source", f"Source {index}")
            return f"({source_name})"
        else:
            return f"[{index}]"
    
    def _format_response_with_citations(self, response_text: str, citations: List[Citation]) -> str:
        """Format response text with embedded citations"""
        if not citations:
            return response_text
        
        # Add citations at the end of sentences that could benefit from them
        # This is a simple heuristic - in production, you might use more sophisticated NLP
        formatted_text = response_text
        
        # Add citation markers (simple approach)
        sentences = re.split(r'(?<=[.!?])\s+', formatted_text)
        
        if sentences and len(citations) > 0:
            # Add first citation to first substantial sentence
            if len(sentences) > 0 and len(sentences[0]) > 20:
                sentences[0] += " " + citations[0].citation_text
            
            # Add more citations to other sentences if available
            if len(sentences) > 1 and len(citations) > 1:
                mid_point = len(sentences) // 2
                if mid_point < len(sentences):
                    sentences[mid_point] += " " + citations[1].citation_text
        
        formatted_text = " ".join(sentences)
        
        # Add citation list at the end
        citation_list = self._create_citation_list(citations)
        if citation_list:
            formatted_text += "\n\n" + citation_list
        
        return formatted_text
    
    def _create_citation_list(self, citations: List[Citation]) -> str:
        """Create formatted citation list"""
        if not citations:
            return ""
        
        citation_lines = []
        
        if self.citation_style == CitationStyle.NUMBERED:
            citation_lines.append("**Sources:**")
            for i, citation in enumerate(citations, 1):
                source_info = self._get_source_info(citation.metadata)
                citation_lines.append(f"{i}. {source_info}")
        
        elif self.citation_style == CitationStyle.BRACKETED:
            citation_lines.append("**Sources:**")
            for citation in citations:
                source_name = citation.metadata.get("source", "Unknown Source")
                source_info = self._get_source_info(citation.metadata)
                citation_lines.append(f"• {source_name}: {source_info}")
        
        elif self.citation_style == CitationStyle.FOOTNOTE:
            citation_lines.append("**Footnotes:**")
            for i, citation in enumerate(citations, 1):
                source_info = self._get_source_info(citation.metadata)
                citation_lines.append(f"^{i} {source_info}")
        
        return "\n".join(citation_lines)
    
    def _get_source_info(self, metadata: Dict[str, Any]) -> str:
        """Extract readable source information from metadata"""
        # Try to get meaningful source information
        if "title" in metadata:
            info = metadata["title"]
        elif "filename" in metadata:
            info = metadata["filename"]
        elif "source" in metadata:
            info = metadata["source"]
        elif "url" in metadata:
            info = metadata["url"]
        else:
            info = "Document"
        
        # Add additional info if available
        if "page" in metadata:
            info += f" (p. {metadata['page']})"
        elif "section" in metadata:
            info += f" ({metadata['section']})"
        
        return info
    
    def _assess_quality(self, query: str, response: str, sources: List[Dict[str, Any]]) -> float:
        """Assess response quality (simplified heuristic)"""
        quality_score = 0.0
        
        # Length check (not too short, not too long)
        if 50 <= len(response) <= 1000:
            quality_score += 0.3
        elif len(response) > 20:
            quality_score += 0.1
        
        # Source utilization
        if sources:
            quality_score += 0.3
        
        # Citation presence
        if "[" in response and "]" in response:
            quality_score += 0.2
        
        # Query relevance (simple keyword matching)
        query_words = set(query.lower().split())
        response_words = set(response.lower().split())
        overlap = len(query_words.intersection(response_words))
        if overlap > 0:
            quality_score += min(0.2, overlap * 0.05)
        
        return min(1.0, quality_score)
    
    def _calculate_confidence(self, sources: List[Dict[str, Any]], llm_response: LLMResponse) -> float:
        """Calculate confidence score based on sources and generation quality"""
        confidence = 0.0
        
        # Source quality
        if sources:
            avg_score = sum(s.get("score", 0.0) for s in sources) / len(sources)
            confidence += avg_score * 0.5
        
        # Generation success
        if llm_response.success:
            confidence += 0.3
        
        # Response length (indicator of completeness)
        if llm_response.completion_tokens > 20:
            confidence += 0.2
        
        return min(1.0, confidence)
    
    def batch_generate(
        self,
        queries: List[str],
        sources_list: List[List[Dict[str, Any]]],
        model_name: Optional[str] = None
    ) -> List[GeneratedResponse]:
        """Generate responses for multiple queries"""
        if len(queries) != len(sources_list):
            raise ValueError("Number of queries must match number of source lists")
        
        responses = []
        
        logger.info(f"Generating batch of {len(queries)} responses")
        
        for i, (query, sources) in enumerate(zip(queries, sources_list)):
            logger.debug(f"Generating response {i+1}/{len(queries)}")
            response = self.generate_response(query, sources, model_name)
            responses.append(response)
        
        logger.info(f"Batch generation completed: {len(responses)} responses")
        return responses
    
    def get_stats(self) -> Dict[str, Any]:
        """Get response generator statistics"""
        avg_generation_time = (
            self.total_generation_time / self.generation_count
            if self.generation_count > 0 else 0
        )
        
        avg_quality_score = (
            sum(self.quality_scores) / len(self.quality_scores)
            if self.quality_scores else 0
        )
        
        return {
            "total_responses": self.generation_count,
            "total_generation_time": self.total_generation_time,
            "average_generation_time": avg_generation_time,
            "average_quality_score": avg_quality_score,
            "citation_style": self.citation_style.value,
            "max_sources": self.max_sources,
            "min_relevance_score": self.min_relevance_score,
            "quality_check_enabled": self.enable_quality_check
        }
    
    def clear_stats(self):
        """Clear performance statistics"""
        self.generation_count = 0
        self.total_generation_time = 0.0
        self.quality_scores = []


# Global response generator instance
_response_generator: Optional[ResponseGenerator] = None


def get_response_generator(
    citation_style: CitationStyle = CitationStyle.NUMBERED,
    force_reload: bool = False,
    **kwargs
) -> ResponseGenerator:
    """
    Get or create global response generator
    
    Args:
        citation_style: Citation formatting style
        force_reload: Force creation of new generator
        **kwargs: Additional arguments for ResponseGenerator
        
    Returns:
        ResponseGenerator instance
    """
    global _response_generator
    
    if force_reload or _response_generator is None:
        logger.info(f"Creating new response generator with style: {citation_style.value}")
        _response_generator = ResponseGenerator(citation_style=citation_style, **kwargs)
    
    return _response_generator


# Convenience functions
def generate_cited_response(
    query: str,
    sources: List[Dict[str, Any]],
    citation_style: CitationStyle = CitationStyle.NUMBERED,
    model_name: Optional[str] = None
) -> str:
    """
    Generate a response with citations
    
    Args:
        query: User query
        sources: List of source documents
        citation_style: How to format citations
        model_name: Optional model to use
        
    Returns:
        Formatted response with citations
    """
    generator = get_response_generator(citation_style)
    result = generator.generate_response(query, sources, model_name)
    return result.response_text if result.success else "Sorry, I couldn't generate a response."


def format_sources_for_display(sources: List[Dict[str, Any]]) -> str:
    """
    Format sources for display in UI
    
    Args:
        sources: List of source documents
        
    Returns:
        Formatted source list
    """
    if not sources:
        return "No sources available."
    
    formatted_sources = []
    for i, source in enumerate(sources, 1):
        metadata = source.get("metadata", {})
        score = source.get("score", 0.0)
        
        # Get source identifier
        source_id = metadata.get("title") or metadata.get("filename") or f"Source {i}"
        
        formatted_sources.append(f"{i}. {source_id} (relevance: {score:.2f})")
    
    return "\n".join(formatted_sources) 