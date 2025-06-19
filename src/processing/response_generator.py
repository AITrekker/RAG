"""
Response generation using LLM with retrieved context.

This module handles:
1. Response generation using LLM
2. Context integration
3. Response formatting
4. Citation management
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import json
from datetime import datetime

from .context_retriever import EnhancedContext
from ..config.settings import LLMSettings

logger = logging.getLogger(__name__)

@dataclass
class Citation:
    """Citation information for response sources."""
    source_id: str
    content_snippet: str
    relevance_score: float
    metadata: Dict[str, Any]

@dataclass
class GeneratedResponse:
    """Generated response with metadata."""
    response_text: str
    citations: List[Citation]
    confidence_score: float
    metadata: Dict[str, Any]
    generation_time_ms: float

class ResponseGenerator:
    """
    Manages response generation using LLM and retrieved context.
    
    Features:
    - LLM integration
    - Context integration
    - Response formatting
    - Citation tracking
    - Confidence scoring
    """
    
    def __init__(
        self,
        llm_settings: LLMSettings,
        max_context_tokens: int = 3000,
        min_confidence_score: float = 0.7,
        include_citations: bool = True
    ):
        """
        Initialize response generator.
        
        Args:
            llm_settings: LLM configuration
            max_context_tokens: Maximum context tokens for LLM
            min_confidence_score: Minimum confidence score threshold
            include_citations: Whether to include citations
        """
        self.llm_settings = llm_settings
        self.max_context_tokens = max_context_tokens
        self.min_confidence_score = min_confidence_score
        self.include_citations = include_citations
        
        # Initialize LLM client
        self._init_llm_client()
        
        logger.info(
            f"Initialized ResponseGenerator with "
            f"model={llm_settings.model_name}, "
            f"max_tokens={max_context_tokens}"
        )
    
    def _init_llm_client(self):
        """Initialize LLM client based on settings."""
        if self.llm_settings.provider == "openai":
            from openai import OpenAI
            self.llm_client = OpenAI(
                api_key=self.llm_settings.api_key
            )
        elif self.llm_settings.provider == "anthropic":
            from anthropic import Anthropic
            self.llm_client = Anthropic(
                api_key=self.llm_settings.api_key
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_settings.provider}")
    
    async def generate_response(
        self,
        query: str,
        contexts: List[EnhancedContext],
        response_type: str = "default",
        max_length: Optional[int] = None
    ) -> GeneratedResponse:
        """
        Generate response using query and retrieved contexts.
        
        Args:
            query: User query
            contexts: Retrieved and enhanced contexts
            response_type: Type of response to generate
            max_length: Maximum response length
            
        Returns:
            Generated response with metadata
        """
        import time
        start_time = time.time()
        
        try:
            # Prepare contexts
            formatted_contexts = self._format_contexts(contexts)
            
            # Generate system prompt
            system_prompt = self._get_system_prompt(
                response_type,
                len(contexts)
            )
            
            # Generate completion
            completion = await self._generate_completion(
                query,
                formatted_contexts,
                system_prompt,
                max_length
            )
            
            # Extract response and metadata
            response_text = completion.choices[0].message.content
            
            # Generate citations
            citations = self._generate_citations(contexts) if self.include_citations else []
            
            # Calculate confidence score
            confidence_score = self._calculate_confidence(
                completion,
                contexts
            )
            
            # Collect metadata
            metadata = {
                "model": self.llm_settings.model_name,
                "response_type": response_type,
                "context_count": len(contexts),
                "token_count": completion.usage.total_tokens,
                "finish_reason": completion.choices[0].finish_reason
            }
            
            generation_time = (time.time() - start_time) * 1000
            
            response = GeneratedResponse(
                response_text=response_text,
                citations=citations,
                confidence_score=confidence_score,
                metadata=metadata,
                generation_time_ms=generation_time
            )
            
            logger.info(
                f"Generated response in {generation_time:.2f}ms "
                f"with confidence {confidence_score:.2f}"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Response generation failed: {str(e)}")
            raise
    
    def _format_contexts(
        self,
        contexts: List[EnhancedContext]
    ) -> str:
        """Format contexts for LLM prompt."""
        formatted = []
        for i, ctx in enumerate(contexts, 1):
            # Format main content
            content = f"[{i}] {ctx.content}"
            
            # Add context window if available
            if ctx.context_window:
                if ctx.context_window.get('previous'):
                    content = f"Previous: {ctx.context_window['previous']}\n{content}"
                if ctx.context_window.get('next'):
                    content = f"{content}\nNext: {ctx.context_window['next']}"
            
            # Add metadata if available
            if ctx.metadata:
                meta_str = ", ".join(f"{k}: {v}" for k, v in ctx.metadata.items())
                content = f"{content}\nMetadata: {meta_str}"
            
            formatted.append(content)
        
        return "\n\n".join(formatted)
    
    def _get_system_prompt(
        self,
        response_type: str,
        context_count: int
    ) -> str:
        """Get system prompt based on response type."""
        base_prompt = (
            "You are a helpful AI assistant. "
            f"You have access to {context_count} relevant documents. "
            "Use this information to provide accurate and helpful responses. "
            "If you're unsure about something, say so clearly. "
            "Always maintain a professional and friendly tone."
        )
        
        type_prompts = {
            "technical": (
                "Provide detailed technical explanations. "
                "Include relevant technical terms and concepts. "
                "Structure the response in a clear, logical manner."
            ),
            "summary": (
                "Provide a concise summary of the key points. "
                "Focus on the most important information. "
                "Keep the response brief but comprehensive."
            ),
            "step_by_step": (
                "Break down the information into clear steps. "
                "Number each step and provide clear instructions. "
                "Include any important details or warnings."
            )
        }
        
        if response_type in type_prompts:
            return f"{base_prompt}\n\n{type_prompts[response_type]}"
        return base_prompt
    
    async def _generate_completion(
        self,
        query: str,
        formatted_contexts: str,
        system_prompt: str,
        max_length: Optional[int]
    ) -> Any:
        """Generate completion using LLM."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Query: {query}\n\nContexts:\n{formatted_contexts}"}
        ]
        
        if self.llm_settings.provider == "openai":
            return await self.llm_client.chat.completions.create(
                model=self.llm_settings.model_name,
                messages=messages,
                max_tokens=max_length,
                temperature=self.llm_settings.temperature,
                stream=False
            )
        elif self.llm_settings.provider == "anthropic":
            return await self.llm_client.messages.create(
                model=self.llm_settings.model_name,
                messages=messages,
                max_tokens=max_length,
                temperature=self.llm_settings.temperature
            )
    
    def _generate_citations(
        self,
        contexts: List[EnhancedContext]
    ) -> List[Citation]:
        """Generate citations from contexts."""
        citations = []
        for ctx in contexts:
            # Create citation with snippet
            snippet = ctx.content[:200] + "..." if len(ctx.content) > 200 else ctx.content
            
            citation = Citation(
                source_id=ctx.source_doc_id,
                content_snippet=snippet,
                relevance_score=ctx.relevance_score,
                metadata=ctx.metadata
            )
            citations.append(citation)
        
        # Sort by relevance
        citations.sort(key=lambda x: x.relevance_score, reverse=True)
        return citations
    
    def _calculate_confidence(
        self,
        completion: Any,
        contexts: List[EnhancedContext]
    ) -> float:
        """Calculate confidence score for generated response."""
        try:
            # Base confidence on multiple factors
            scores = []
            
            # Context relevance
            if contexts:
                avg_relevance = sum(ctx.relevance_score for ctx in contexts) / len(contexts)
                scores.append(avg_relevance)
            
            # Model confidence (if available)
            if hasattr(completion.choices[0], 'logprobs'):
                log_probs = completion.choices[0].logprobs
                if log_probs:
                    avg_prob = sum(log_probs) / len(log_probs)
                    normalized_prob = 1 / (1 + abs(avg_prob))  # Sigmoid-like normalization
                    scores.append(normalized_prob)
            
            # Completion status
            if completion.choices[0].finish_reason == "stop":
                scores.append(1.0)
            elif completion.choices[0].finish_reason == "length":
                scores.append(0.8)
            else:
                scores.append(0.5)
            
            # Calculate final score
            if scores:
                confidence = sum(scores) / len(scores)
                return max(0.0, min(1.0, confidence))  # Clamp between 0 and 1
            
            return 0.5  # Default confidence
            
        except Exception as e:
            logger.warning(f"Confidence calculation failed: {str(e)}")
            return 0.5  # Default confidence on error 