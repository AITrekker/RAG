"""
Pipeline orchestrator for the RAG system.

This module coordinates:
1. Query processing
2. Context retrieval
3. Response generation
4. Error handling and retries
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import time
import asyncio
from datetime import datetime

from .query_validator import QueryValidator
from .query_parser import QueryParser
from .query_intent import IntentClassifier
from .query_metadata import QueryMetadataExtractor
from .context_retriever import ContextRetriever, EnhancedContext
from .response_generator import ResponseGenerator, GeneratedResponse
from ..config.settings import Settings

logger = logging.getLogger(__name__)

@dataclass
class PipelineMetrics:
    """Pipeline execution metrics."""
    query_processing_time_ms: float
    context_retrieval_time_ms: float
    response_generation_time_ms: float
    total_time_ms: float
    context_count: int
    token_count: int
    confidence_score: float

@dataclass
class PipelineResponse:
    """Complete pipeline response."""
    query_id: str
    original_query: str
    processed_query: Dict[str, Any]
    response: GeneratedResponse
    contexts: List[EnhancedContext]
    metrics: PipelineMetrics
    timestamp: datetime

class PipelineOrchestrator:
    """
    Orchestrates the complete RAG pipeline.
    
    Features:
    - Query processing coordination
    - Context retrieval management
    - Response generation control
    - Error handling and retries
    - Metrics collection
    """
    
    def __init__(
        self,
        settings: Settings,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize pipeline orchestrator.
        
        Args:
            settings: Global settings
            max_retries: Maximum number of retries
            retry_delay: Delay between retries in seconds
        """
        self.settings = settings
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Initialize components
        self.query_validator = QueryValidator()
        self.query_parser = QueryParser()
        self.intent_classifier = IntentClassifier()
        self.metadata_extractor = QueryMetadataExtractor()
        
        self.context_retriever = ContextRetriever(
            vector_store=settings.vector_store,
            min_relevance_score=0.3,
            max_context_length=2000
        )
        
        self.response_generator = ResponseGenerator(
            llm_settings=settings.llm,
            max_context_tokens=3000,
            min_confidence_score=0.7
        )
        
        logger.info("Initialized PipelineOrchestrator")
    
    async def process_query(
        self,
        query: str,
        query_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PipelineResponse:
        """
        Process a query through the complete pipeline.
        
        Args:
            query: User query
            query_id: Optional query identifier
            metadata: Optional query metadata
            
        Returns:
            Complete pipeline response
        """
        start_time = time.time()
        
        try:
            # Process query
            query_start = time.time()
            processed_query = await self._process_query(query, metadata)
            query_time = (time.time() - query_start) * 1000
            
            # Retrieve context
            context_start = time.time()
            contexts = await self._retrieve_context(
                processed_query,
                metadata
            )
            context_time = (time.time() - context_start) * 1000
            
            # Generate response
            response_start = time.time()
            response = await self._generate_response(
                query,
                processed_query,
                contexts
            )
            response_time = (time.time() - response_start) * 1000
            
            # Calculate metrics
            total_time = (time.time() - start_time) * 1000
            metrics = PipelineMetrics(
                query_processing_time_ms=query_time,
                context_retrieval_time_ms=context_time,
                response_generation_time_ms=response_time,
                total_time_ms=total_time,
                context_count=len(contexts),
                token_count=response.metadata.get("token_count", 0),
                confidence_score=response.confidence_score
            )
            
            # Create pipeline response
            pipeline_response = PipelineResponse(
                query_id=query_id or str(int(time.time() * 1000)),
                original_query=query,
                processed_query=processed_query,
                response=response,
                contexts=contexts,
                metrics=metrics,
                timestamp=datetime.now()
            )
            
            logger.info(
                f"Pipeline completed in {total_time:.2f}ms "
                f"with confidence {response.confidence_score:.2f}"
            )
            
            return pipeline_response
            
        except Exception as e:
            logger.error(f"Pipeline processing failed: {str(e)}")
            raise
    
    async def _process_query(
        self,
        query: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process and analyze query."""
        try:
            # Validate query
            self.query_validator.validate(query)
            
            # Parse query
            parsed_query = self.query_parser.parse(query)
            
            # Classify intent
            intent = self.intent_classifier.classify(
                query,
                parsed_query
            )
            
            # Extract metadata
            query_metadata = self.metadata_extractor.extract(
                query,
                parsed_query,
                metadata
            )
            
            return {
                "original": query,
                "parsed": parsed_query,
                "intent": intent,
                "metadata": query_metadata
            }
            
        except Exception as e:
            logger.error(f"Query processing failed: {str(e)}")
            raise
    
    async def _retrieve_context(
        self,
        processed_query: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[EnhancedContext]:
        """Retrieve relevant context."""
        for attempt in range(self.max_retries):
            try:
                # Prepare filters from metadata
                filters = self._prepare_filters(
                    processed_query,
                    metadata
                )
                
                # Get contexts
                contexts = await self.context_retriever.retrieve_context(
                    query=processed_query["original"],
                    filters=filters
                )
                
                return contexts
                
            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Context retrieval failed after {self.max_retries} attempts: {str(e)}")
                    raise
                
                logger.warning(f"Context retrieval attempt {attempt + 1} failed: {str(e)}")
                await asyncio.sleep(self.retry_delay)
    
    async def _generate_response(
        self,
        query: str,
        processed_query: Dict[str, Any],
        contexts: List[EnhancedContext]
    ) -> GeneratedResponse:
        """Generate response using contexts."""
        for attempt in range(self.max_retries):
            try:
                # Determine response type from intent
                response_type = self._get_response_type(
                    processed_query["intent"]
                )
                
                # Generate response
                response = await self.response_generator.generate_response(
                    query=query,
                    contexts=contexts,
                    response_type=response_type
                )
                
                return response
                
            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Response generation failed after {self.max_retries} attempts: {str(e)}")
                    raise
                
                logger.warning(f"Response generation attempt {attempt + 1} failed: {str(e)}")
                await asyncio.sleep(self.retry_delay)
    
    def _prepare_filters(
        self,
        processed_query: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Prepare context filters from query and metadata."""
        filters = {}
        
        # Add intent-based filters
        intent = processed_query["intent"]
        if intent.get("type") == "technical":
            filters["document_type"] = "technical"
        elif intent.get("type") == "business":
            filters["document_type"] = "business"
        
        # Add metadata filters
        if metadata:
            # Add relevant metadata as filters
            if doc_type := metadata.get("document_type"):
                filters["document_type"] = doc_type
            if department := metadata.get("department"):
                filters["department"] = department
            if date_range := metadata.get("date_range"):
                filters["created_at"] = date_range
        
        return filters
    
    def _get_response_type(self, intent: Dict[str, Any]) -> str:
        """Determine response type from intent."""
        intent_type = intent.get("type", "")
        
        if intent_type == "technical":
            return "technical"
        elif intent_type == "summary":
            return "summary"
        elif intent_type == "step_by_step":
            return "step_by_step"
        
        return "default" 