"""
Simple Embedder - Zero Memory Leaks
Replaces complex embedding_engine.py with direct, explicit memory management
"""

import torch
import gc
from typing import List
from pathlib import Path


def generate_embeddings_simple(texts: List[str], model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> List[List[float]]:
    """
    Generate embeddings with explicit memory management
    No singletons, no caching, immediate cleanup
    """
    if not texts:
        return []
    
    model = None
    try:
        from sentence_transformers import SentenceTransformer
        
        # Load model fresh (prevents accumulation)
        print(f"🤖 Loading model: {model_name}")
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        model = SentenceTransformer(model_name, device=device)
        model.eval()  # Set to evaluation mode
        
        print(f"📍 Using device: {device}")
        if device == 'cuda':
            print(f"🚀 GPU: {torch.cuda.get_device_name()}")
        
        # Process in tiny batches to prevent OOM
        embeddings = []
        batch_size = 8 if device == 'cuda' else 16  # Smaller batches for GPU
        
        print(f"🔢 Processing {len(texts)} texts in batches of {batch_size}")
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(texts) - 1) // batch_size + 1
            
            print(f"   📦 Batch {batch_num}/{total_batches}: {len(batch)} texts")
            
            # Generate embeddings with no gradient computation
            with torch.no_grad():
                batch_emb = model.encode(
                    batch, 
                    convert_to_tensor=False,
                    show_progress_bar=False,
                    batch_size=min(4, len(batch)) if device == 'cuda' else min(8, len(batch))
                )
                
                # Convert to list immediately
                if hasattr(batch_emb, 'tolist'):
                    batch_list = batch_emb.tolist()
                else:
                    batch_list = [emb.tolist() if hasattr(emb, 'tolist') else list(emb) for emb in batch_emb]
                
                embeddings.extend(batch_list)
            
            # Aggressive cleanup after each batch
            del batch_emb, batch_list
            if device == 'cuda' and torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            gc.collect()
        
        print(f"✅ Generated {len(embeddings)} embeddings successfully")
        return embeddings
        
    except Exception as e:
        print(f"❌ Failed to generate embeddings: {e}")
        import traceback
        traceback.print_exc()
        return []
        
    finally:
        # Explicit cleanup - critical for preventing leaks
        if model is not None:
            print("🧹 Cleaning up model...")
            del model
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        
        gc.collect()
        print("✅ Memory cleanup completed")


def chunk_text_simple(text: str, chunk_size: int = 512, overlap: int = 50) -> List[str]:
    """
    Simple text chunking - no complex classes
    Returns list of text chunks
    """
    if not text or len(text.strip()) < 10:
        return []
    
    words = text.split()
    if len(words) <= chunk_size:
        return [text]  # Return whole text if small enough
    
    chunks = []
    start = 0
    
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]
        chunk_text = " ".join(chunk_words)
        chunks.append(chunk_text)
        
        # Move start position with overlap
        start = end - overlap
        if start >= len(words):
            break
    
    return chunks


def extract_text_simple(file_path: Path) -> str:
    """
    Simple text extraction from files
    Supports: .txt, .md, and fallback to text
    """
    try:
        if not file_path.exists():
            print(f"⚠️ File not found: {file_path}")
            return ""
        
        # Read as text with error handling
        text = file_path.read_text(encoding='utf-8', errors='ignore')
        
        # Basic cleanup
        text = text.strip()
        
        if len(text) < 10:
            print(f"⚠️ File too short: {file_path}")
            return ""
        
        print(f"📄 Extracted {len(text)} characters from {file_path.name}")
        return text
        
    except Exception as e:
        print(f"❌ Failed to extract text from {file_path}: {e}")
        return ""


def process_file_to_embeddings_simple(
    file_path: Path, 
    chunk_size: int = 512, 
    chunk_overlap: int = 50,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    max_chunks: int = 1000
) -> List[dict]:
    """
    Complete pipeline: file → text → chunks → embeddings
    Returns list of chunk dictionaries with embeddings
    """
    
    print(f"🔄 Processing file: {file_path.name}")
    
    # 1. Extract text
    text = extract_text_simple(file_path)
    if not text:
        return []
    
    # 2. Chunk text
    chunks = chunk_text_simple(text, chunk_size, chunk_overlap)
    if not chunks:
        print(f"⚠️ No chunks created from {file_path.name}")
        return []
    
    # 3. Limit chunks if too many
    if len(chunks) > max_chunks:
        print(f"⚠️ Limiting to {max_chunks} chunks (was {len(chunks)})")
        chunks = chunks[:max_chunks]
    
    print(f"📦 Created {len(chunks)} chunks")
    
    # 4. Generate embeddings
    embeddings = generate_embeddings_simple(chunks, model_name)
    if not embeddings:
        print(f"❌ No embeddings generated for {file_path.name}")
        return []
    
    # 5. Combine chunks with embeddings
    result = []
    for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
        result.append({
            "index": i,
            "text": chunk_text,
            "embedding": embedding,
            "model": model_name
        })
    
    print(f"✅ Processed {file_path.name}: {len(result)} embedded chunks")
    
    # 6. Cleanup
    del text, chunks, embeddings
    gc.collect()
    
    return result


# Available models for the API
def get_available_models():
    """Get list of available embedding models"""
    return [
        {"value": "sentence-transformers/all-MiniLM-L6-v2", "name": "MiniLM-L6-v2 (Fast, Lightweight)"},
        {"value": "sentence-transformers/all-mpnet-base-v2", "name": "MPNet Base (Balanced)"},
        {"value": "sentence-transformers/e5-large", "name": "E5 Large (High Quality)"}
    ]


def get_available_strategies():
    """Get list of available chunking strategies"""
    return [
        {"value": "fixed-size", "name": "Fixed Size (Simple)"},
        {"value": "sliding-window", "name": "Sliding Window (Overlap)"},
        {"value": "semantic", "name": "Semantic (Sentence Boundaries)"}
    ]