"""
Pydantic models for API request and response validation.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import UUID

class RAGSource(BaseModel):
    """Represents a single source document chunk used for an answer."""
    id: str = Field(..., description="The unique ID of the document chunk.")
    text: str = Field(..., description="The text content of the chunk.")
    score: float = Field(..., description="The relevance score of the chunk.")
    filename: Optional[str] = Field(None, description="The name of the source document.")
    page_number: Optional[int] = Field(None, description="The page number in the source document.")
    chunk_index: Optional[int] = Field(None, description="The index of the chunk within the document.")

class RAGResponse(BaseModel):
    """The response model for a RAG query."""
    query: str = Field(..., description="The original query text.")
    answer: str = Field(..., description="The generated answer from the LLM.")
    sources: List[RAGSource] = Field(..., description="A list of source chunks that informed the answer.")
    confidence: float = Field(..., description="The calculated confidence score for the answer.")
    processing_time: Optional[float] = Field(None, description="The total time taken to process the query in seconds.")
    llm_metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata from the LLM, such as model name and token counts.")

class QueryRequest(BaseModel):
    """The request model for submitting a query."""
    query: str = Field(..., min_length=3, max_length=500, description="The user's query.")
    tenant_id: Optional[str] = Field(None, description="The tenant ID to scope the query to. If not provided, a default may be used based on context.") 