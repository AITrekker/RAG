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

# Hugging Face imports
from transformers import (
    AutoTokenizer, 
    AutoModelForCausalLM, 
    pipeline,
    BitsAndBytesConfig,
    TextGenerationPipeline
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
            
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                **model_kwargs
            )
            
            # Create text generation pipeline
            self.pipeline = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                device=0 if self.device == "cuda" and not quantization_config else -1,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
            )
            
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
        Generate response using the LLM
        
        Args:
            prompt: Input prompt
            context: Optional context information
            max_new_tokens: Maximum number of new tokens to generate
            temperature: Generation temperature (overrides default)
            do_sample: Whether to use sampling
            top_p: Top-p sampling parameter
            top_k: Top-k sampling parameter
            repetition_penalty: Repetition penalty
            
        Returns:
            LLMResponse with generated text and metadata
        """
        if not self.pipeline:
            self.load_model()
        
        start_time = time.time()
        
        try:
            # Use provided parameters or defaults
            gen_temperature = temperature if temperature is not None else self.temperature
            max_tokens = max_new_tokens or min(self.max_length, 256)
            
            # Prepare full prompt with context using a structured template
            full_prompt = self._prepare_rag_prompt(prompt, context)
            
            # Count input tokens
            input_tokens = len(self.tokenizer.encode(full_prompt))
            
            # Generate response
            generation_kwargs = {
                "max_new_tokens": max_tokens,
                "temperature": gen_temperature,
                "do_sample": do_sample,
                "top_p": top_p,
                "top_k": top_k,
                "repetition_penalty": repetition_penalty,
                "pad_token_id": self.tokenizer.eos_token_id,
                "return_full_text": False,  # Only return new tokens
                "clean_up_tokenization_spaces": True
            }
            
            # Generate with the pipeline
            outputs = self.pipeline(full_prompt, **generation_kwargs)
            
            # Extract generated text
            if outputs and len(outputs) > 0:
                generated_text = outputs[0]["generated_text"]
            else:
                generated_text = ""
            
            # Clean up the response to remove the prompt
            if full_prompt in generated_text:
                generated_text = generated_text.replace(full_prompt, "").strip()

            # Count output tokens
            output_tokens = len(self.tokenizer.encode(generated_text))
            total_tokens = input_tokens + output_tokens
            
            generation_time = time.time() - start_time
            
            # Update statistics
            self.generation_times.append(generation_time)
            self.total_tokens_generated += output_tokens
            
            # Create response
            response = LLMResponse(
                text=generated_text,
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
                total_tokens=total_tokens,
                generation_time=generation_time,
                model_name=self.model_name,
                temperature=gen_temperature,
                success=True
            )
            
            logger.info(f"Generated response in {generation_time:.3f}s")
            logger.info(f"Tokens: {input_tokens} input + {output_tokens} output = {total_tokens} total")
            
            return response
            
        except Exception as e:
            generation_time = time.time() - start_time
            logger.error(f"Failed to generate response: {e}")
            
            return LLMResponse(
                text="",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                generation_time=generation_time,
                model_name=self.model_name,
                temperature=gen_temperature,
                success=False,
                error=str(e)
            )
    
    def _prepare_rag_prompt(self, query: str, context: Optional[List[str]] = None) -> str:
        """Prepares a structured prompt for RAG."""
        if not context:
            # For Falcon-Instruct, a simple user/assistant format works well without context.
            return f"User: {query}\nAssistant:"

        context_str = "\n\n".join(context)
        prompt = f"""Answer the following question based on the provided context. If the context does not contain the answer, say "I cannot answer this question based on the provided context."

Context:
---
{context_str}
---

Question: {query}

Answer:"""
        return prompt

    def _prepare_prompt(self, prompt: str, context: Optional[List[str]] = None) -> str:
        """Prepares a full prompt by combining a query and optional context.
        DEPRECATED: Use _prepare_rag_prompt for clearer RAG structure.
        """
        if context:
            context_str = "\n\n".join(context)
            return f"Context:\n{context_str}\n\nQuestion: {prompt}\nAnswer:"
        return prompt

    def generate_rag_response(
        self,
        query: str,
        sources: List[Dict[str, Any]],
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> LLMResponse:
        """
        Generate RAG response using provided sources
        
        Args:
            query: User query
            sources: List of source documents with text and metadata
            max_new_tokens: Maximum tokens to generate
            temperature: Generation temperature
            
        Returns:
            LLMResponse with generated answer
        """
        full_prompt = self._prepare_rag_prompt(query, [source['text'] for source in sources])
        
        return self.generate_response(
            prompt=full_prompt,  # The prompt is now the full structured text
            context=None, # Context is already in the prompt
            max_new_tokens=max_new_tokens,
            temperature=temperature
        )
    
    def batch_generate(
        self,
        prompts: List[str],
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> List[LLMResponse]:
        """
        Generate responses for multiple prompts
        
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


def get_llm_stats() -> Dict[str, Any]:
    """Get stats from the global LLM service"""
    llm_service = get_llm_service()
    return llm_service.get_stats() 