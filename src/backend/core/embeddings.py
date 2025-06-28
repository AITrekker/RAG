"""
Hugging Face Transformers-based Embedding Service for the RAG Platform.

This module provides a service for generating high-quality sentence embeddings
using state-of-the-art models from the sentence-transformers library.
It automatically handles device placement (GPU/CPU) and batch processing.
"""

import logging
from typing import List
import torch
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingService:
    """A service for generating sentence embeddings using SentenceTransformers."""

    def __init__(self, model_name: str, batch_size: int = 32):
        """
        Initializes the EmbeddingService.

        Args:
            model_name: The name of the sentence-transformer model to use.
            batch_size: The batch size for encoding embeddings.
        """
        self.device = self._get_device()
        self.model_name = model_name
        self.batch_size = batch_size
        
        try:
            logger.info(f"Loading SentenceTransformer model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name, device=self.device)
            logger.info(f"Model '{self.model_name}' loaded successfully on device '{self.device}'.")
        except Exception as e:
            logger.error(f"Failed to load SentenceTransformer model '{self.model_name}'. Error: {e}", exc_info=True)
            raise RuntimeError(f"Could not initialize EmbeddingService") from e

    def _get_device(self) -> str:
        """Determines the most appropriate device for computation (GPU or CPU)."""
        if torch.cuda.is_available():
            logger.info("CUDA is available. Using GPU for embeddings.")
            return "cuda"
        else:
            logger.info("CUDA not available. Using CPU for embeddings.")
            return "cpu"

    @property
    def dimension(self) -> int:
        """Returns the dimension of the embeddings."""
        return self.model.get_sentence_embedding_dimension()

    def encode_texts(
        self, 
        texts: List[str], 
        show_progress_bar: bool = False,
        normalize_embeddings: bool = False
    ) -> np.ndarray:
        """
        Generates embeddings for a list of texts.

        Args:
            texts: A list of strings to be embedded.
            show_progress_bar: Whether to show a progress bar during encoding.
            normalize_embeddings: Whether to normalize embeddings to unit length.

        Returns:
            A numpy array of embeddings.
        """
        if not texts:
            return np.array([])
            
        logger.info(f"Generating embeddings for {len(texts)} texts...")
        
        # The encode method of sentence-transformers handles batching and device placement automatically.
        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=show_progress_bar,
            normalize_embeddings=normalize_embeddings,
            convert_to_numpy=True
        )
        
        logger.info("Finished generating embeddings.")
        return embeddings

_embedding_service_instance = None

def get_embedding_service() -> EmbeddingService:
    """
    Returns a singleton instance of the EmbeddingService.
    This ensures the model is loaded only once.
    """
    global _embedding_service_instance
    if _embedding_service_instance is None:
        from ..config.settings import settings
        logger.info("Initializing singleton EmbeddingService instance.")
        config = settings.get_embedding_config()
        _embedding_service_instance = EmbeddingService(
            model_name=config['model_name'],
            batch_size=config['batch_size']
        )
    return _embedding_service_instance 