"""
LLM Inference Service for the Enterprise RAG Platform.

This module provides a comprehensive `LLMService` for local inference of
Large Language Models (LLMs) using the Hugging Face `transformers` library.
It is designed for high-performance generative tasks and includes features
such as:
- Automatic device placement with optimizations for NVIDIA GPUs (e.g., RTX 5070).
- Support for 8-bit quantization to reduce memory footprint.
- A text generation pipeline for handling prompts and generating responses.
- Methods for standard and Retrieval-Augmented Generation (RAG) prompts.
- Performance tracking and singleton management for efficient resource use.
"""

import logging
import time
import torch
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from datetime import datetime
import gc
import asyncio

# Hugging Face imports
from transformers import (
    AutoTokenizer, 
    AutoModelForCausalLM, 
    pipeline,
    BitsAndBytesConfig,
    TextGenerationPipeline,
    AutoModelForSeq2SeqLM,
    T5ForConditionalGeneration
)

# Internal imports
from ..config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Response from LLM generation"""
    text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    generation_time: float
    model_name: str
    temperature: float
    success: bool = True
    error: Optional[str] = None


class LLMService:
    """
    Local LLM inference service using Hugging Face transformers
    Optimized for RTX 5070 GPU acceleration
    """
    
    def __init__(
        self,
        model_name: str,
        max_length: int,
        temperature: float,
        enable_quantization: bool,
        device: Optional[str] = None,
        cache_dir: Optional[str] = None
    ):
        """
        Initialize LLM service
        
        Args:
            model_name: Hugging Face model identifier
            max_length: Maximum response length
            temperature: Generation temperature (0.0 to 1.0)
            enable_quantization: Enable 8-bit quantization for memory efficiency
            device: Computing device ('cuda', 'cpu', or None for auto-detect)
            cache_dir: Directory to cache downloaded models
        """
        self.model_name = model_name
        self.max_length = max_length
        self.temperature = temperature
        self.enable_quantization = enable_quantization
        self.cache_dir = cache_dir
        
        # Set up device (prioritize RTX 5070 if available)
        self.device = self._setup_device(device)
        
        # Initialize model components
        self.tokenizer = None
        self.model = None
        self.pipeline = None
        
        # Performance tracking
        self.generation_times = []
        self.total_tokens_generated = 0
        
        logger.info(f"Initializing LLM service with model: {model_name}")
        logger.info(f"Device: {self.device}")
        logger.info(f"Quantization enabled: {enable_quantization}")
    
    def _setup_device(self, device: Optional[str]) -> str:
        """Set up the computing device, prioritizing RTX 5070"""
        if device:
            return device
        
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            logger.info(f"CUDA available - Using GPU: {gpu_name}")
            
            # Check if RTX 5070 is detected
            if "RTX 5070" in gpu_name:
                logger.info("🎮 RTX 5070 detected - Optimizing for Blackwell architecture")
                # Set memory optimization for RTX 5070
                torch.cuda.empty_cache()
                
            return "cuda"
        else:
            logger.warning("CUDA not available - Using CPU (will be slower)")
            return "cpu"
    
    def load_model(self) -> None:
        """Load the LLM model with GPU optimization"""
        try:
            logger.info(f"Loading LLM model: {self.model_name}")
            start_time = time.time()
            
            # Configure quantization for RTX 5070 memory efficiency
            quantization_config = None
            if self.enable_quantization and self.device == "cuda":
                quantization_config = BitsAndBytesConfig(
                    load_in_8bit=True,
                    llm_int8_threshold=6.0,
                    llm_int8_has_fp16_weight=False,
                )
                logger.info("Enabling 8-bit quantization for memory efficiency")
            
            # Determine the correct AutoModel class and pipeline task
            if "t5" in self.model_name or "flan" in self.model_name:
                model_class = AutoModelForSeq2SeqLM
                pipeline_task = "text2text-generation"
                logger.info("Using Seq2Seq model architecture.")
            else:
                model_class = AutoModelForCausalLM
                pipeline_task = "text-generation"
                logger.info("Using Causal LM model architecture.")

            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                cache_dir=self.cache_dir,
                trust_remote_code=True
            )
            
            # Add padding token if not present
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # Load model
            model_kwargs = {
                "cache_dir": self.cache_dir,
                "trust_remote_code": True,
                "torch_dtype": torch.float16 if self.device == "cuda" else torch.float32,
            }
            
            if quantization_config:
                model_kwargs["quantization_config"] = quantization_config
                model_kwargs["device_map"] = "auto"
            else:
                model_kwargs["device_map"] = "auto" if self.device == "cuda" else None
            
            self.model = model_class.from_pretrained(
                self.model_name,
                **model_kwargs
            )
            
            # Create text generation pipeline
            pipeline_kwargs = {
                "task": pipeline_task,
                "model": self.model,
                "tokenizer": self.tokenizer,
                "torch_dtype": torch.float16 if self.device == "cuda" else torch.float32,
            }
            
            # Only add device argument if not using quantization (accelerate)
            if not quantization_config:
                pipeline_kwargs["device"] = 0 if self.device == "cuda" else -1
            
            self.pipeline = pipeline(**pipeline_kwargs)
            
            load_time = time.time() - start_time
            logger.info(f"✅ LLM model loaded successfully in {load_time:.2f} seconds")
            
            # Get model info
            model_params = sum(p.numel() for p in self.model.parameters())
            logger.info(f"Model parameters: {model_params:,}")
            
            if self.device == "cuda":
                memory_allocated = torch.cuda.memory_allocated() / 1024**3
                logger.info(f"GPU memory allocated: {memory_allocated:.2f} GB")
            
        except Exception as e:
            logger.error(f"Failed to load LLM model {self.model_name}: {e}")
            raise
    
    def generate_response(
        self,
        prompt: str,
        context: Optional[List[str]] = None,
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        do_sample: bool = True,
        top_p: float = 0.9,
        top_k: int = 50,
        repetition_penalty: float = 1.1
    ) -> LLMResponse:
        """
        Generate a response from the LLM
        
        Args:
            prompt: Input prompt
            context: Optional context information
            max_new_tokens: Maximum tokens to generate
            temperature: Generation temperature
            do_sample: Whether to use sampling
            top_p: Top-p sampling parameter
            top_k: Top-k sampling parameter
            repetition_penalty: Repetition penalty
            
        Returns:
            LLMResponse object
        """
        if not self.pipeline:
            return LLMResponse(
                text="",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                generation_time=0.0,
                model_name=self.model_name,
                temperature=temperature or self.temperature,
                success=False,
                error="Model not loaded"
            )
        
        start_time = time.time()
        
        try:
            # Prepare the prompt
            full_prompt = self._prepare_prompt(prompt, context)
            
            # Tokenize to get prompt length
            prompt_tokens = len(self.tokenizer.encode(full_prompt))
            
            # Set generation parameters
            max_new_tokens = max_new_tokens or self.max_length
            temperature = temperature or self.temperature
            
            # Generate response
            generation_kwargs = {
                "max_new_tokens": max_new_tokens,
                "temperature": temperature,
                "do_sample": do_sample,
                "top_p": top_p,
                "top_k": top_k,
                "repetition_penalty": repetition_penalty,
                "pad_token_id": self.tokenizer.eos_token_id,
                "eos_token_id": self.tokenizer.eos_token_id,
            }
            
            # Generate
            outputs = self.pipeline(full_prompt, **generation_kwargs)
            generated_text = outputs[0]["generated_text"]
            
            # Extract only the new content (remove the prompt)
            response_text = generated_text[len(full_prompt):].strip()

            # Calculate token counts
            completion_tokens = len(self.tokenizer.encode(response_text))
            total_tokens = prompt_tokens + completion_tokens
            
            generation_time = time.time() - start_time
            
            # Update statistics
            self.generation_times.append(generation_time)
            self.total_tokens_generated += completion_tokens
            
            logger.debug(f"Generated {completion_tokens} tokens in {generation_time:.3f}s")
            
            return LLMResponse(
                text=response_text,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                generation_time=generation_time,
                model_name=self.model_name,
                temperature=temperature,
                success=True
            )
            
        except Exception as e:
            generation_time = time.time() - start_time
            logger.error(f"Error generating response: {e}")
            
            return LLMResponse(
                text="",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                generation_time=generation_time,
                model_name=self.model_name,
                temperature=temperature or self.temperature,
                success=False,
                error=str(e)
            )
    
    async def generate_response_async(
        self,
        prompt: str,
        context: Optional[List[str]] = None,
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        do_sample: bool = True,
        top_p: float = 0.9,
        top_k: int = 50,
        repetition_penalty: float = 1.1
    ) -> LLMResponse:
        """
        Generate a response from the LLM asynchronously
        
        Args:
            prompt: Input prompt
            context: Optional context information
            max_new_tokens: Maximum tokens to generate
            temperature: Generation temperature
            do_sample: Whether to use sampling
            top_p: Top-p sampling parameter
            top_k: Top-k sampling parameter
            repetition_penalty: Repetition penalty
            
        Returns:
            LLMResponse object
        """
        # Run the sync method in a thread pool for CPU/GPU-bound work
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.generate_response,
            prompt,
            context,
            max_new_tokens,
            temperature,
            do_sample,
            top_p,
            top_k,
            repetition_penalty
            )
    
    def _prepare_rag_prompt(self, query: str, context: Optional[List[str]] = None) -> str:
        """Prepare a RAG-style prompt with context"""
        if not context:
            return query

        context_text = "\n\n".join(context)
        return f"""Context information:
{context_text}

Question: {query}

Answer:"""

    def _prepare_prompt(self, prompt: str, context: Optional[List[str]] = None) -> str:
        """Prepare the full prompt with optional context"""
        if not context:
        return prompt
        
        context_text = "\n\n".join(context)
        return f"Context: {context_text}\n\nQuestion: {prompt}\n\nAnswer:"

    def generate_rag_response(
        self,
        query: str,
        sources: List[Dict[str, Any]],
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> LLMResponse:
        """
        Generate a RAG response using provided sources
        
        Args:
            query: User query
            sources: List of source documents
            max_new_tokens: Maximum tokens to generate
            temperature: Generation temperature
            
        Returns:
            LLMResponse object
        """
        # Extract context from sources
        context = []
        for source in sources:
            if "content" in source:
                context.append(source["content"])
            elif "text" in source:
                context.append(source["text"])
        
        # Use RAG prompt format
        prompt = self._prepare_rag_prompt(query, context)
        
        return self.generate_response(
            prompt=prompt,
            max_new_tokens=max_new_tokens,
            temperature=temperature
        )
    
    async def generate_rag_response_async(
        self,
        query: str,
        sources: List[Dict[str, Any]],
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> LLMResponse:
        """
        Generate a RAG response using provided sources asynchronously
        
        Args:
            query: User query
            sources: List of source documents
            max_new_tokens: Maximum tokens to generate
            temperature: Generation temperature
            
        Returns:
            LLMResponse object
        """
        # Run the sync method in a thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.generate_rag_response,
            query,
            sources,
            max_new_tokens,
            temperature
        )
    
    def batch_generate(
        self,
        prompts: List[str],
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> List[LLMResponse]:
        """
        Generate responses for multiple prompts (synchronous)
        
        Args:
            prompts: List of prompts
            max_new_tokens: Maximum tokens per response
            temperature: Generation temperature
            
        Returns:
            List of LLMResponse objects
        """
        responses = []
        
        logger.info(f"Generating batch of {len(prompts)} responses")
        
        for i, prompt in enumerate(prompts):
            logger.debug(f"Generating response {i+1}/{len(prompts)}")
            response = self.generate_response(
                prompt,
                max_new_tokens=max_new_tokens,
                temperature=temperature
            )
            responses.append(response)
        
        logger.info(f"Batch generation completed: {len(responses)} responses")
        return responses
    
    async def batch_generate_async(
        self,
        prompts: List[str],
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        max_concurrent: int = 3
    ) -> List[LLMResponse]:
        """
        Generate responses for multiple prompts asynchronously with concurrency control
        
        Args:
            prompts: List of prompts
            max_new_tokens: Maximum tokens per response
            temperature: Generation temperature
            max_concurrent: Maximum concurrent generations
            
        Returns:
            List of LLMResponse objects
        """
        logger.info(f"Generating async batch of {len(prompts)} responses (max {max_concurrent} concurrent)")
        
        # Create semaphore to limit concurrent operations
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def generate_single(prompt: str) -> LLMResponse:
            async with semaphore:
                return await self.generate_response_async(
                    prompt,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature
                )
        
        # Generate all responses concurrently
        tasks = [generate_single(prompt) for prompt in prompts]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        final_responses = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                logger.error(f"Error generating response {i+1}: {response}")
                final_responses.append(LLMResponse(
                    text="",
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    generation_time=0.0,
                    model_name=self.model_name,
                    temperature=temperature or self.temperature,
                    success=False,
                    error=str(response)
                ))
            else:
                final_responses.append(response)
        
        logger.info(f"Async batch generation completed: {len(final_responses)} responses")
        return final_responses
    
    def get_stats(self) -> Dict[str, Any]:
        """Get LLM service performance statistics"""
        avg_generation_time = (
            sum(self.generation_times) / len(self.generation_times)
            if self.generation_times else 0
        )
        
        total_generation_time = sum(self.generation_times)
        tokens_per_second = (
            self.total_tokens_generated / total_generation_time
            if total_generation_time > 0 else 0
        )
        
        stats = {
            "model_name": self.model_name,
            "device": self.device,
            "total_generations": len(self.generation_times),
            "total_tokens_generated": self.total_tokens_generated,
            "total_generation_time": total_generation_time,
            "average_generation_time": avg_generation_time,
            "tokens_per_second": tokens_per_second,
            "quantization_enabled": self.enable_quantization
        }
        
        # Add GPU memory stats if available
        if self.device == "cuda" and torch.cuda.is_available():
            stats.update({
                "gpu_memory_allocated": torch.cuda.memory_allocated() / 1024**3,
                "gpu_memory_reserved": torch.cuda.memory_reserved() / 1024**3,
                "gpu_name": torch.cuda.get_device_name(0)
            })
        
        return stats
    
    def clear_cache(self):
        """Clear GPU memory cache"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            gc.collect()
            logger.info("GPU memory cache cleared")
    
    def clear_stats(self):
        """Clear performance statistics"""
        self.generation_times = []
        self.total_tokens_generated = 0
        logger.info("LLM statistics cleared")
    
    def __del__(self):
        """Cleanup when service is destroyed"""
        self.clear_cache()


# Global LLM service instance
_llm_service_instance: Optional[LLMService] = None


def get_llm_service(
    model_name: Optional[str] = None,
    force_reload: bool = False,
    **kwargs
) -> LLMService:
    """Get singleton instance of LLM service, loading if needed."""
    global _llm_service_instance
    
    if _llm_service_instance is None or force_reload:
        if force_reload and _llm_service_instance:
            _llm_service_instance.clear_cache()
            
        logger.info("Initializing LLM service singleton...")
        
        # Combine settings from config and kwargs
        config = settings.get_llm_config()
        if model_name: # Override model name if provided
            config['model_name'] = model_name
        config.update(kwargs)
        
        _llm_service_instance = LLMService(**config)
        _llm_service_instance.load_model()
    
    return _llm_service_instance


# Model recommendations for different use cases
def get_model_recommendations() -> Dict[str, Dict[str, Any]]:
    """
    Get LLM model recommendations for different use cases on RTX 5070
    
    Returns:
        Dictionary with model recommendations and their characteristics
    """
    return {
        "lightweight": {
            "model": "microsoft/DialoGPT-medium",
            "description": "Lightweight conversational model, good for RTX 5070",
            "parameters": "774M",
            "memory_usage_gb": 2.5,
            "use_case": "Quick responses, limited VRAM",
            "quantization_recommended": False
        },
        "balanced": {
            "model": "microsoft/DialoGPT-large",
            "description": "Balanced performance and quality",
            "parameters": "1.5B",
            "memory_usage_gb": 4.0,
            "use_case": "General purpose RAG responses",
            "quantization_recommended": True
        },
        "quality": {
            "model": "EleutherAI/gpt-neo-2.7B",
            "description": "Higher quality responses, requires more memory",
            "parameters": "2.7B",
            "memory_usage_gb": 8.0,
            "use_case": "High-quality text generation",
            "quantization_recommended": True
        },
        "efficient": {
            "model": "distilgpt2",
            "description": "Most efficient option for RTX 5070",
            "parameters": "82M",
            "memory_usage_gb": 1.0,
            "use_case": "Fast responses with minimal memory",
            "quantization_recommended": False
        }
    }


# Convenience functions
def generate_answer(
    question: str,
    context: Optional[List[str]] = None,
    model_name: Optional[str] = None
) -> str:
    """
    Simple function to generate an answer to a question
    
    Args:
        question: Question to answer
        context: Optional context information
        model_name: Optional model to use
        
    Returns:
        Generated answer text
    """
    llm_service = get_llm_service(model_name)
    response = llm_service.generate_response(question, context)
    return response.text if response.success else "Sorry, I couldn't generate a response."


async def generate_answer_async(
    question: str,
    context: Optional[List[str]] = None,
    model_name: Optional[str] = None
) -> str:
    """
    Simple async function to generate an answer to a question
    
    Args:
        question: Question to answer
        context: Optional context information
        model_name: Optional model to use
        
    Returns:
        Generated answer text
    """
    llm_service = get_llm_service(model_name)
    response = await llm_service.generate_response_async(question, context)
    return response.text if response.success else "Sorry, I couldn't generate a response."


def generate_rag_answer(
    query: str,
    sources: List[Dict[str, Any]],
    model_name: Optional[str] = None
) -> str:
    """
    Generate RAG answer using provided sources
    
    Args:
        query: User query
        sources: List of source documents
        model_name: Optional model to use
        
    Returns:
        Generated answer text
    """
    llm_service = get_llm_service(model_name)
    response = llm_service.generate_rag_response(query, sources)
    return response.text if response.success else "Sorry, I couldn't generate a response."


async def generate_rag_answer_async(
    query: str,
    sources: List[Dict[str, Any]],
    model_name: Optional[str] = None
) -> str:
    """
    Generate RAG answer using provided sources asynchronously
    
    Args:
        query: User query
        sources: List of source documents
        model_name: Optional model to use
        
    Returns:
        Generated answer text
    """
    llm_service = get_llm_service(model_name)
    response = await llm_service.generate_rag_response_async(query, sources)
    return response.text if response.success else "Sorry, I couldn't generate a response."


def get_llm_stats() -> Dict[str, Any]:
    """
    Get performance statistics from the global LLM service.
    
    Returns:
        A dictionary of performance stats.
    """
    llm_service = get_llm_service()
    return llm_service.get_stats() 