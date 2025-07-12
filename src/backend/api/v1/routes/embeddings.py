"""
Embedding generation API routes for testing and debugging
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
import numpy as np

from src.backend.dependencies import get_embedding_model
from src.backend.middleware.api_key_auth import get_current_tenant

router = APIRouter()

class EmbeddingRequest(BaseModel):
    text: str
    normalize: bool = True

class EmbeddingResponse(BaseModel):
    embedding: List[float]
    dimensions: int
    model: str

class SimilarityRequest(BaseModel):
    text1: str
    text2: str

class SimilarityResponse(BaseModel):
    similarity: float
    text1_embedding: List[float]
    text2_embedding: List[float]

@router.post("/generate", response_model=EmbeddingResponse)
async def generate_embedding(
    request: EmbeddingRequest,
    embedding_model = Depends(get_embedding_model),
    current_tenant = Depends(get_current_tenant)
):
    """Generate embedding for given text"""
    try:
        # Generate embedding
        embedding = embedding_model.encode(request.text, normalize_embeddings=request.normalize)
        
        # Convert to list (numpy array -> list)
        embedding_list = embedding.tolist()
        
        return EmbeddingResponse(
            embedding=embedding_list,
            dimensions=len(embedding_list),
            model=embedding_model.get_model_info().get('name', 'unknown')
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate embedding: {str(e)}")

@router.post("/similarity", response_model=SimilarityResponse)
async def calculate_similarity(
    request: SimilarityRequest,
    embedding_model = Depends(get_embedding_model),
    current_tenant = Depends(get_current_tenant)
):
    """Calculate cosine similarity between two texts"""
    try:
        # Generate embeddings for both texts
        emb1 = embedding_model.encode(request.text1, normalize_embeddings=True)
        emb2 = embedding_model.encode(request.text2, normalize_embeddings=True)
        
        # Calculate cosine similarity
        similarity = float(np.dot(emb1, emb2))
        
        return SimilarityResponse(
            similarity=similarity,
            text1_embedding=emb1.tolist(),
            text2_embedding=emb2.tolist()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate similarity: {str(e)}")

@router.get("/model-info")
async def get_model_info(
    embedding_model = Depends(get_embedding_model),
    current_tenant = Depends(get_current_tenant)
):
    """Get information about the embedding model"""
    try:
        info = embedding_model.get_model_info()
        return {
            "model_name": info.get('name', 'unknown'),
            "max_seq_length": info.get('max_seq_length', 'unknown'),
            "dimensions": info.get('sentence_embedding_dimension', 'unknown'),
            "similarity_function": info.get('similarity_fn_name', 'unknown')
        }
    except Exception as e:
        return {
            "model_name": "unknown",
            "error": str(e)
        }