"""Base classes and interfaces for RAG system."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Iterator, AsyncIterator
from uuid import UUID
from datetime import datetime

@dataclass
class Query:
    """Represents a processed user query."""
    text: str
    tenant_id: UUID
    user_id: Optional[UUID] = None
    filters: Dict[str, Any] = field(default_factory=dict)
    max_results: int = 10
    min_score: float = 0.3  # Lower threshold for better recall
    original_text: str = ""
    
    def __post_init__(self):
        if not self.original_text:
            self.original_text = self.text

@dataclass 
class RetrievedChunk:
    """Represents a chunk retrieved from vector search."""
    chunk_id: UUID
    content: str
    file_id: UUID
    filename: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunk_index: int = 0
    file_path: str = ""

@dataclass
class RAGContext:
    """Context assembled for answer generation."""
    chunks: List[RetrievedChunk]
    total_chunks: int
    search_query: str
    filters_applied: Dict[str, Any] = field(default_factory=dict)
    retrieval_time: float = 0.0
    
    @property
    def combined_content(self) -> str:
        """Get all chunk content as single string."""
        return "\n\n".join([f"[{chunk.filename}]\n{chunk.content}" for chunk in self.chunks])
    
    @property
    def unique_sources(self) -> List[str]:
        """Get list of unique source filenames."""
        return list(set(chunk.filename for chunk in self.chunks))

@dataclass
class RAGResponse:
    """Complete RAG response with answer and metadata."""
    answer: str
    sources: List[Dict[str, Any]]
    confidence: float
    context_used: List[str]
    processing_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    query: str = ""
    tenant_id: Optional[UUID] = None
    timestamp: datetime = field(default_factory=datetime.now)

class QueryProcessorInterface(ABC):
    """Interface for query processors."""
    
    @abstractmethod
    def process_query(self, raw_query: str, tenant_id: UUID, user_id: Optional[UUID] = None) -> Query:
        """Process and validate user query."""
        pass
    
    @abstractmethod
    def extract_filters(self, query: str) -> tuple[str, Dict[str, Any]]:
        """Extract filters from query text."""
        pass

class RetrieverInterface(ABC):
    """Interface for content retrievers."""
    
    @abstractmethod
    async def search(self, query: Query) -> List[RetrievedChunk]:
        """Perform vector search."""
        pass
    
    @abstractmethod
    async def get_context(self, query: Query) -> RAGContext:
        """Get complete context for query."""
        pass

class RankerInterface(ABC):
    """Interface for context rankers."""
    
    @abstractmethod
    def rank_chunks(self, chunks: List[RetrievedChunk], query: str) -> List[RetrievedChunk]:
        """Rank chunks by relevance."""
        pass
    
    @abstractmethod
    def filter_duplicates(self, chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
        """Remove duplicate or near-duplicate content."""
        pass

class GeneratorInterface(ABC):
    """Interface for answer generators."""
    
    @abstractmethod
    async def generate_answer(self, context: RAGContext, query: str) -> str:
        """Generate answer from context."""
        pass
    
    @abstractmethod
    async def generate_with_citations(self, context: RAGContext, query: str) -> tuple[str, List[Dict[str, Any]]]:
        """Generate answer with source citations."""
        pass

class RAGPipelineInterface(ABC):
    """Interface for complete RAG pipelines."""
    
    @abstractmethod
    async def process_query(self, raw_query: str, tenant_id: UUID, user_id: Optional[UUID] = None) -> RAGResponse:
        """Process complete RAG query."""
        pass
    
    @abstractmethod
    async def stream_response(self, raw_query: str, tenant_id: UUID, user_id: Optional[UUID] = None) -> AsyncIterator[str]:
        """Stream RAG response."""
        pass