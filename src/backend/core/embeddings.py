"""
Basic Embedding Service implementation.
"""

from typing import List
import numpy as np


class EmbeddingService:
    """Basic embedding service for demo purposes."""
    
    def __init__(self):
        self.model_name = "mock-embedding-model"
        self.dimension = 384
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embeddings for text."""
        # Mock embedding - random vector
        return np.random.random(self.dimension).tolist()
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        return [self.embed_text(text) for text in texts]


def get_embedding_service():
    """Get embedding service instance."""
    return EmbeddingService() 