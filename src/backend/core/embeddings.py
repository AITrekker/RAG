"""
Hugging Face Transformers Embedding Service for RAG Platform
Optimized for RTX 5070 GPU acceleration
"""

import os
import torch
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
import time
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModel
import numpy as np

# Import configuration settings
from ..config.settings import settings, get_embedding_model_config, validate_rtx_5070_compatibility

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    High-performance embedding service using Hugging Face transformers
    Optimized for RTX 5070 GPU acceleration
    """
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        cache_dir: Optional[str] = None,
        max_seq_length: Optional[int] = None,
        batch_size: Optional[int] = None,
        use_config: bool = True
    ):
        """
        Initialize the embedding service
        
        Args:
            model_name: HuggingFace model identifier (overrides config)
            device: Computing device ('cuda', 'cpu', or None for auto-detect)
            cache_dir: Directory to cache downloaded models
            max_seq_length: Maximum sequence length for tokenization
            batch_size: Batch size for processing multiple texts
            use_config: Whether to use configuration settings as defaults
        """
        # Load configuration if requested
        if use_config:
            config = get_embedding_model_config()
            # Ensure model_name is a string, not an enum
            configured_model = config["model_name"]
            if hasattr(configured_model, 'value'):
                configured_model = configured_model.value
            self.model_name = model_name or configured_model
            self.max_seq_length = max_seq_length or config["max_seq_length"]
            self.batch_size = batch_size or config["batch_size"]
            self.cache_dir = cache_dir or config["cache_dir"]
            self.enable_mixed_precision = config["enable_mixed_precision"]
            self.target_performance = config["target_performance"]
        else:
            # Use provided parameters or defaults
            self.model_name = model_name or "sentence-transformers/all-MiniLM-L6-v2"
            self.max_seq_length = max_seq_length or 512
            self.batch_size = batch_size or 32
            self.cache_dir = cache_dir or "./cache/transformers"
            self.enable_mixed_precision = True
            self.target_performance = 16.3
        
        # Set up device (prioritize RTX 5070 if available)
        self.device = self._setup_device(device)
        
        # Set up cache directory
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
        
        # Initialize model and tokenizer
        self.model = None
        self.tokenizer = None
        self.sentence_transformer = None
        
        # Performance metrics
        self.embedding_times = []
        
        # Validate RTX 5070 compatibility and log recommendations
        compatibility = validate_rtx_5070_compatibility()
        
        logger.info(f"Initializing EmbeddingService with model: {self.model_name}")
        logger.info(f"Device: {self.device}")
        logger.info(f"Cache directory: {self.cache_dir}")
        logger.info(f"Batch size: {self.batch_size}")
        logger.info(f"Mixed precision: {self.enable_mixed_precision}")
        logger.info(f"Target performance: {self.target_performance} texts/sec")
        
        # Log RTX 5070 compatibility info
        if compatibility["cuda_available"]:
            if compatibility["rtx_5070_detected"]:
                logger.info("🎮 RTX 5070 detected - Using optimized settings")
                for rec in compatibility["recommendations"]:
                    logger.info(f"  • {rec}")
            else:
                logger.info(f"GPU detected: {compatibility.get('gpu_name', 'Unknown')}")
        else:
            logger.warning("CUDA not available - Performance will be limited")
    
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
        """Load the embedding model with GPU optimization"""
        try:
            logger.info(f"Loading model: {self.model_name}")
            start_time = time.time()
            
            # Use SentenceTransformers for better performance and ease of use
            self.sentence_transformer = SentenceTransformer(
                self.model_name,
                device=self.device,
                cache_folder=self.cache_dir
            )
            
            # Set max sequence length
            self.sentence_transformer.max_seq_length = self.max_seq_length
            
            # Enable mixed precision for RTX 5070 if using CUDA
            if self.device == "cuda" and hasattr(torch.cuda, 'amp'):
                logger.info("Enabling mixed precision (FP16) for RTX 5070 optimization")
                # This will be used in the encode method
            
            load_time = time.time() - start_time
            logger.info(f"✅ Model loaded successfully in {load_time:.2f} seconds")
            
            # Get model info
            embedding_dim = self.sentence_transformer.get_sentence_embedding_dimension()
            logger.info(f"Embedding dimension: {embedding_dim}")
            
        except Exception as e:
            logger.error(f"Failed to load model {self.model_name}: {e}")
            raise
    
    def encode_texts(
        self,
        texts: List[str],
        normalize_embeddings: bool = True,
        show_progress_bar: bool = False
    ) -> np.ndarray:
        """
        Generate embeddings for a list of texts
        
        Args:
            texts: List of text strings to embed
            normalize_embeddings: Whether to normalize embeddings to unit vectors
            show_progress_bar: Whether to show progress during encoding
            
        Returns:
            numpy array of embeddings with shape (len(texts), embedding_dim)
        """
        if not self.sentence_transformer:
            self.load_model()
        
        if not texts:
            return np.array([])
        
        start_time = time.time()
        
        try:
            # Use mixed precision if available and enabled (RTX 5070 optimization)
            if self.device == "cuda" and self.enable_mixed_precision:
                with torch.cuda.amp.autocast():
                    embeddings = self.sentence_transformer.encode(
                        texts,
                        batch_size=self.batch_size,
                        normalize_embeddings=normalize_embeddings,
                        show_progress_bar=show_progress_bar,
                        convert_to_numpy=True
                    )
            else:
                embeddings = self.sentence_transformer.encode(
                    texts,
                    batch_size=self.batch_size,
                    normalize_embeddings=normalize_embeddings,
                    show_progress_bar=show_progress_bar,
                    convert_to_numpy=True
                )
            
            encoding_time = time.time() - start_time
            self.embedding_times.append(encoding_time)
            
            texts_per_second = len(texts) / encoding_time
            performance_ratio = texts_per_second / self.target_performance
            
            logger.info(f"Generated embeddings for {len(texts)} texts in {encoding_time:.3f}s")
            logger.info(f"Speed: {texts_per_second:.1f} texts/second")
            logger.info(f"Performance vs target ({self.target_performance:.1f}): {performance_ratio:.2f}x")
            
            # Warn if significantly under target performance
            if performance_ratio < 0.5:
                logger.warning(
                    f"Performance is {performance_ratio:.2f}x target. Consider optimizing batch size or GPU settings."
                )
            elif performance_ratio > 1.2:
                logger.info(f"🚀 Exceeding target performance by {((performance_ratio - 1) * 100):.0f}%")
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise
    
    def encode_single_text(self, text: str) -> np.ndarray:
        """Generate embedding for a single text"""
        return self.encode_texts([text])[0]
    
    def similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings"""
        # Ensure embeddings are numpy arrays
        emb1 = np.array(embedding1)
        emb2 = np.array(embedding2)
        
        # Calculate cosine similarity
        dot_product = np.dot(emb1, emb2)
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def batch_similarity(self, query_embedding: np.ndarray, document_embeddings: np.ndarray) -> np.ndarray:
        """Calculate similarity between query and multiple documents efficiently"""
        query_emb = np.array(query_embedding)
        doc_embs = np.array(document_embeddings)
        
        # Normalize embeddings if not already normalized
        query_norm = query_emb / np.linalg.norm(query_emb)
        doc_norms = doc_embs / np.linalg.norm(doc_embs, axis=1, keepdims=True)
        
        # Calculate cosine similarities
        similarities = np.dot(doc_norms, query_norm)
        return similarities
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        if not self.embedding_times:
            return {"message": "No embeddings generated yet"}
        
        avg_time = np.mean(self.embedding_times)
        total_time = sum(self.embedding_times)
        
        return {
            "device": self.device,
            "model_name": self.model_name,
            "total_embeddings_generated": len(self.embedding_times),
            "total_time_seconds": total_time,
            "average_time_per_batch": avg_time,
            "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A"
        }
    
    def clear_cache(self) -> None:
        """Clear GPU memory cache"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.info("GPU memory cache cleared")
    
    def __del__(self):
        """Cleanup when service is destroyed"""
        self.clear_cache()


# Global embedding service instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service(
    model_name: Optional[str] = None,
    use_config: bool = True,
    force_reload: bool = False,
    **kwargs
) -> EmbeddingService:
    """
    Get or create the global embedding service instance
    
    Args:
        model_name: HuggingFace model identifier (overrides config)
        use_config: Whether to use configuration settings
        force_reload: Force creation of new service instance
        **kwargs: Additional arguments for EmbeddingService
    
    Returns:
        EmbeddingService instance
    """
    global _embedding_service
    
    # Determine effective model name
    if use_config and model_name is None:
        config = get_embedding_model_config()
        effective_model = config["model_name"]
        # Ensure it's a string, not an enum
        if hasattr(effective_model, 'value'):
            effective_model = effective_model.value
    else:
        effective_model = model_name or "sentence-transformers/all-MiniLM-L6-v2"
    
    if (_embedding_service is None or 
        _embedding_service.model_name != effective_model or 
        force_reload):
        logger.info(f"Creating new embedding service with model: {effective_model}")
        _embedding_service = EmbeddingService(
            model_name=model_name, 
            use_config=use_config, 
            **kwargs
        )
        _embedding_service.load_model()
    
    return _embedding_service


def test_embedding_service():
    """Test function to verify embedding service works with RTX 5070"""
    logger.info("🧪 Testing Embedding Service...")
    
    # Test texts
    test_texts = [
        "This is a test document about artificial intelligence and machine learning.",
        "The RAG platform provides document search and question answering capabilities.",
        "RTX 5070 GPU acceleration makes embedding generation much faster."
    ]
    
    try:
        # Create service
        service = get_embedding_service()
        
        # Generate embeddings
        embeddings = service.encode_texts(test_texts)
        logger.info(f"✅ Generated embeddings shape: {embeddings.shape}")
        
        # Test similarity
        similarity = service.similarity(embeddings[0], embeddings[1])
        logger.info(f"✅ Similarity between first two texts: {similarity:.3f}")
        
        # Performance stats
        stats = service.get_performance_stats()
        logger.info(f"✅ Performance stats: {stats}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Embedding service test failed: {e}")
        return False


if __name__ == "__main__":
    # Configure logging for standalone testing
    logging.basicConfig(level=logging.INFO)
    
    # Run test
    success = test_embedding_service()
    print(f"\n{'✅ Test passed!' if success else '❌ Test failed!'}") 