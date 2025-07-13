"""
Embedding Engine - Configurable Embedding Generation
Supports multiple models, chunking strategies, and similarity methods
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import asyncio
from pathlib import Path

from src.backend.config.settings import get_settings

settings = get_settings()


class EmbeddingModel(str, Enum):
    """Available embedding models"""
    MINI_LM = "sentence-transformers/all-MiniLM-L6-v2"
    MPNET = "sentence-transformers/all-mpnet-base-v2"
    E5_LARGE = "sentence-transformers/e5-large"


class ChunkingStrategy(str, Enum):
    """Available chunking strategies"""
    FIXED_SIZE = "fixed-size"
    SLIDING_WINDOW = "sliding-window"
    SEMANTIC = "semantic"


class SimilarityMethod(str, Enum):
    """Available similarity methods"""
    COSINE = "cosine"
    DOT_PRODUCT = "dot-product"
    EUCLIDEAN = "euclidean"


@dataclass
class EmbeddingConfig:
    """Embedding configuration"""
    model: EmbeddingModel = EmbeddingModel.MINI_LM
    chunking: ChunkingStrategy = ChunkingStrategy.FIXED_SIZE
    similarity: SimilarityMethod = SimilarityMethod.COSINE
    chunk_size: int = 512
    chunk_overlap: int = 50
    max_chunks: int = 1000


@dataclass
class TextChunk:
    """A chunk of text with metadata"""
    text: str
    index: int
    start_char: int
    end_char: int
    token_count: int


@dataclass
class EmbeddedChunk:
    """A chunk with its embedding"""
    chunk: TextChunk
    embedding: List[float]
    embedding_model: str


class SingletonEmbeddingModel:
    """Singleton embedding model to prevent memory leaks"""
    _instance = None
    _model = None
    _current_model_name = None
    
    @classmethod
    def get_model(cls, model_name: str):
        """Get or create embedding model instance"""
        if cls._instance is None:
            cls._instance = cls()
        
        # Only reload if model changed
        if cls._current_model_name != model_name:
            cls._load_model(model_name)
        
        return cls._model
    
    @classmethod
    def _load_model(cls, model_name: str):
        """Load embedding model with GPU optimization"""
        try:
            from sentence_transformers import SentenceTransformer
            import torch
            import gc
            
            # Clear any existing model first
            if cls._model is not None:
                print(f"🔄 Clearing existing model")
                del cls._model
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                gc.collect()
            
            print(f"🤖 Loading embedding model: {model_name}")
            
            # Use GPU if available, otherwise CPU
            if torch.cuda.is_available():
                device = 'cuda'
                print(f"🚀 GPU detected: {torch.cuda.get_device_name()}")
            else:
                device = 'cpu'
                print("💻 Using CPU (no GPU available)")
            
            cls._model = SentenceTransformer(model_name, device=device)
            cls._current_model_name = model_name
            
            # Set model to eval mode and optimize memory
            cls._model.eval()
            if device == 'cuda':
                torch.cuda.empty_cache()
            
            print(f"✅ Model loaded on {device}")
            
        except Exception as e:
            print(f"❌ Failed to load model {model_name}: {e}")
            raise


def extract_text_from_file(file_path: Path) -> str:
    """Extract text from file based on extension"""
    try:
        suffix = file_path.suffix.lower()
        
        if suffix == '.txt':
            return file_path.read_text(encoding='utf-8', errors='ignore')
        elif suffix == '.md':
            return file_path.read_text(encoding='utf-8', errors='ignore')
        else:
            # Try as text anyway
            return file_path.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        print(f"❌ Failed to extract text from {file_path}: {e}")
        return ""


def chunk_text_fixed_size(text: str, chunk_size: int = 512, overlap: int = 50) -> List[TextChunk]:
    """Fixed-size chunking strategy"""
    words = text.split()
    chunks = []
    start = 0
    
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]
        chunk_text = " ".join(chunk_words)
        
        # Calculate character positions (approximate)
        start_char = len(" ".join(words[:start])) if start > 0 else 0
        end_char = start_char + len(chunk_text)
        
        chunks.append(TextChunk(
            text=chunk_text,
            index=len(chunks),
            start_char=start_char,
            end_char=end_char,
            token_count=len(chunk_words)
        ))
        
        start = end - overlap
    
    return chunks


def chunk_text_sliding_window(text: str, chunk_size: int = 512, overlap: int = 100) -> List[TextChunk]:
    """Sliding window chunking strategy"""
    return chunk_text_fixed_size(text, chunk_size, overlap)


def chunk_text_semantic(text: str, chunk_size: int = 512, overlap: int = 50) -> List[TextChunk]:
    """Semantic chunking strategy (sentence boundaries)"""
    # Simple implementation: split by sentences, then group
    sentences = text.split('. ')
    chunks = []
    current_chunk = []
    current_size = 0
    
    for sentence in sentences:
        words = sentence.split()
        if current_size + len(words) > chunk_size and current_chunk:
            # Create chunk
            chunk_text = ". ".join(current_chunk) + "."
            chunks.append(TextChunk(
                text=chunk_text,
                index=len(chunks),
                start_char=0,  # Simplified
                end_char=len(chunk_text),
                token_count=len(chunk_text.split())
            ))
            current_chunk = []
            current_size = 0
        
        current_chunk.append(sentence)
        current_size += len(words)
    
    # Add remaining chunk
    if current_chunk:
        chunk_text = ". ".join(current_chunk) + "."
        chunks.append(TextChunk(
            text=chunk_text,
            index=len(chunks),
            start_char=0,
            end_char=len(chunk_text),
            token_count=len(chunk_text.split())
        ))
    
    return chunks


def chunk_text(text: str, strategy: ChunkingStrategy, chunk_size: int = 512, overlap: int = 50) -> List[TextChunk]:
    """Chunk text using specified strategy"""
    if strategy == ChunkingStrategy.FIXED_SIZE:
        return chunk_text_fixed_size(text, chunk_size, overlap)
    elif strategy == ChunkingStrategy.SLIDING_WINDOW:
        return chunk_text_sliding_window(text, chunk_size, overlap)
    elif strategy == ChunkingStrategy.SEMANTIC:
        return chunk_text_semantic(text, chunk_size, overlap)
    else:
        return chunk_text_fixed_size(text, chunk_size, overlap)


def generate_embeddings(chunks: List[TextChunk], config: EmbeddingConfig) -> List[EmbeddedChunk]:
    """Generate embeddings with optimized GPU memory management"""
    if not chunks:
        return []
    
    try:
        import gc
        import torch
        
        # Get singleton model
        model = SingletonEmbeddingModel.get_model(config.model.value)
        device = next(model.parameters()).device if hasattr(model, 'parameters') else 'cpu'
        is_gpu = device.type == 'cuda'
        
        print(f"🔢 Generating embeddings for {len(chunks)} chunks on {device}")
        
        # Extract texts
        texts = [chunk.text for chunk in chunks]
        
        # Adaptive batch size based on device and text length
        if is_gpu:
            # Smaller batches for GPU to prevent OOM
            avg_text_len = sum(len(text) for text in texts) / len(texts) if texts else 0
            if avg_text_len > 1000:  # Long texts
                batch_size = 8
            elif avg_text_len > 500:  # Medium texts
                batch_size = 16
            else:  # Short texts
                batch_size = 32
        else:
            # Larger batches for CPU
            batch_size = 64
        
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            print(f"   📦 Processing batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1} ({len(batch_texts)} items)")
            
            # Generate embeddings with memory optimization
            with torch.no_grad():  # Disable gradients for inference
                batch_embeddings = model.encode(
                    batch_texts,
                    convert_to_tensor=False,
                    show_progress_bar=False,
                    batch_size=min(8, len(batch_texts)) if is_gpu else min(32, len(batch_texts))
                )
            
            embeddings.extend(batch_embeddings)
            
            # Aggressive memory cleanup after each batch
            if is_gpu and torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()  # Wait for GPU operations to complete
            
            gc.collect()
        
        # Create embedded chunks
        embedded_chunks = []
        for chunk, embedding in zip(chunks, embeddings):
            embedded_chunks.append(EmbeddedChunk(
                chunk=chunk,
                embedding=embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding),
                embedding_model=config.model.value
            ))
        
        # Final cleanup
        if is_gpu and torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        gc.collect()
        
        print(f"✅ Generated {len(embedded_chunks)} embeddings successfully")
        return embedded_chunks
        
    except Exception as e:
        print(f"❌ Failed to generate embeddings: {e}")
        import traceback
        traceback.print_exc()
        
        # Emergency cleanup on failure
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
        return []


def process_file_to_embeddings(
    file_path: Path, 
    config: EmbeddingConfig
) -> List[EmbeddedChunk]:
    """Complete pipeline: file → text → chunks → embeddings"""
    
    # Extract text
    text = extract_text_from_file(file_path)
    if not text or len(text.strip()) < 10:
        print(f"⚠️ No meaningful text extracted from {file_path}")
        return []
    
    # Chunk text
    chunks = chunk_text(text, config.chunking, config.chunk_size, config.chunk_overlap)
    if not chunks:
        print(f"⚠️ No chunks created from {file_path}")
        return []
    
    # Limit chunks
    if len(chunks) > config.max_chunks:
        chunks = chunks[:config.max_chunks]
        print(f"⚠️ Limited to {config.max_chunks} chunks for {file_path}")
    
    # Generate embeddings
    embedded_chunks = generate_embeddings(chunks, config)
    
    print(f"✅ Processed {file_path.name}: {len(embedded_chunks)} chunks")
    return embedded_chunks


def get_available_models() -> List[Dict[str, str]]:
    """Get list of available embedding models"""
    return [
        {"value": EmbeddingModel.MINI_LM.value, "name": "MiniLM-L6-v2 (Fast, Lightweight)"},
        {"value": EmbeddingModel.MPNET.value, "name": "MPNet Base (Balanced)"},
        {"value": EmbeddingModel.E5_LARGE.value, "name": "E5 Large (High Quality)"}
    ]


def get_available_strategies() -> List[Dict[str, str]]:
    """Get list of available chunking strategies"""
    return [
        {"value": ChunkingStrategy.FIXED_SIZE.value, "name": "Fixed Size (Simple)"},
        {"value": ChunkingStrategy.SLIDING_WINDOW.value, "name": "Sliding Window (Overlap)"},
        {"value": ChunkingStrategy.SEMANTIC.value, "name": "Semantic (Sentence Boundaries)"}
    ]