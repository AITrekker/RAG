"""
LlamaIndex-based document chunking with tenant isolation
"""

import asyncio
from typing import List, Dict, Any, Optional
from uuid import UUID
from dataclasses import dataclass

from src.backend.config.settings import get_settings

settings = get_settings()


@dataclass
class LlamaIndexChunk:
    """Chunk produced by LlamaIndex with tenant isolation"""
    content: str
    chunk_index: int
    metadata: Dict[str, Any]
    token_count: int
    
    @property
    def hash(self) -> str:
        import hashlib
        return hashlib.sha256(self.content.encode()).hexdigest()


class TenantIsolatedLlamaIndexChunker:
    """
    LlamaIndex semantic chunking with strict tenant isolation
    """
    
    def __init__(self, tenant_id: UUID):
        self.tenant_id = tenant_id
        self._text_splitter = None
        self._node_parser = None
        
    async def initialize(self):
        """Initialize LlamaIndex components with tenant-specific configuration"""
        try:
            # Import LlamaIndex components
            from llama_index.core.text_splitter import SentenceSplitter
            from llama_index.core.node_parser import SimpleNodeParser
            
            # Create tenant-specific text splitter
            self._text_splitter = SentenceSplitter(
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
                separator=" ",
                backup_separators=["\n", "\n\n", ".", "!", "?"]
            )
            
            # Create node parser with tenant isolation
            self._node_parser = SimpleNodeParser(
                text_splitter=self._text_splitter,
                include_metadata=True,
                include_prev_next_rel=False  # Disable for tenant isolation
            )
            
            print(f"✓ LlamaIndex chunker initialized for tenant {self.tenant_id}")
            
        except ImportError as e:
            print(f"⚠️ LlamaIndex not available: {e}")
            self._text_splitter = None
            self._node_parser = None
        except Exception as e:
            print(f"⚠️ Error initializing LlamaIndex chunker: {e}")
            self._text_splitter = None
            self._node_parser = None
    
    async def chunk_text(
        self, 
        text: str, 
        file_id: UUID, 
        filename: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[LlamaIndexChunk]:
        """
        Chunk text using LlamaIndex with tenant isolation
        """
        if self._node_parser is None:
            # Fallback to simple chunking if LlamaIndex not available
            return await self._fallback_chunking(text, file_id, filename, metadata)
        
        try:
            from llama_index.core.schema import Document
            
            # Create LlamaIndex document with tenant-specific metadata
            base_metadata = {
                "tenant_id": str(self.tenant_id),
                "file_id": str(file_id),
                "filename": filename,
                "source": "tenant_upload",
                **(metadata or {})
            }
            
            document = Document(
                text=text,
                metadata=base_metadata,
                excluded_embed_metadata_keys=["tenant_id", "file_id"],  # Don't embed these
                excluded_llm_metadata_keys=["tenant_id", "file_id"]  # Don't use in LLM context
            )
            
            # Parse into nodes with tenant isolation
            nodes = self._node_parser.get_nodes_from_documents([document])
            
            # Convert to our chunk format
            chunks = []
            for i, node in enumerate(nodes):
                # Ensure tenant isolation in metadata
                node_metadata = node.metadata.copy()
                node_metadata.update({
                    "tenant_id": str(self.tenant_id),
                    "file_id": str(file_id),
                    "filename": filename,
                    "chunk_index": i,
                    "node_id": node.node_id,
                    "chunking_method": "llamaindex_semantic"
                })
                
                chunk = LlamaIndexChunk(
                    content=node.text,
                    chunk_index=i,
                    metadata=node_metadata,
                    token_count=len(node.text.split())  # Simple token count
                )
                chunks.append(chunk)
            
            print(f"✓ LlamaIndex chunked {filename} into {len(chunks)} semantic chunks")
            return chunks
            
        except Exception as e:
            print(f"⚠️ LlamaIndex chunking failed: {e}, falling back to simple chunking")
            return await self._fallback_chunking(text, file_id, filename, metadata)
    
    async def _fallback_chunking(
        self, 
        text: str, 
        file_id: UUID, 
        filename: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[LlamaIndexChunk]:
        """Fallback chunking when LlamaIndex is not available"""
        chunks = []
        chunk_size = settings.chunk_size
        overlap = settings.chunk_overlap
        
        start = 0
        chunk_index = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk_text = text[start:end]
            
            if chunk_text.strip():
                base_metadata = {
                    "tenant_id": str(self.tenant_id),
                    "file_id": str(file_id),
                    "filename": filename,
                    "chunk_index": chunk_index,
                    "start_char": start,
                    "end_char": end,
                    "chunking_method": "character_fallback",
                    **(metadata or {})
                }
                
                chunk = LlamaIndexChunk(
                    content=chunk_text.strip(),
                    chunk_index=chunk_index,
                    metadata=base_metadata,
                    token_count=len(chunk_text.split())
                )
                chunks.append(chunk)
                chunk_index += 1
            
            start = end - overlap if end < len(text) else end
        
        return chunks
    
    async def batch_chunk_texts(
        self, 
        texts_and_metadata: List[tuple[str, UUID, str, Dict[str, Any]]]
    ) -> List[List[LlamaIndexChunk]]:
        """
        Batch process multiple texts with tenant isolation
        """
        tasks = []
        for text, file_id, filename, metadata in texts_and_metadata:
            task = self.chunk_text(text, file_id, filename, metadata)
            tasks.append(task)
        
        # Process concurrently with tenant isolation maintained
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"⚠️ Chunking failed for text {i}: {result}")
                # Return empty chunks for failed processing
                processed_results.append([])
            else:
                processed_results.append(result)
        
        return processed_results
    
    def get_chunk_statistics(self, chunks: List[LlamaIndexChunk]) -> Dict[str, Any]:
        """Get statistics about the generated chunks"""
        if not chunks:
            return {
                "total_chunks": 0,
                "avg_chunk_length": 0,
                "avg_token_count": 0,
                "min_chunk_length": 0,
                "max_chunk_length": 0,
                "total_tokens": 0
            }
        
        chunk_lengths = [len(chunk.content) for chunk in chunks]
        token_counts = [chunk.token_count for chunk in chunks]
        
        return {
            "total_chunks": len(chunks),
            "avg_chunk_length": sum(chunk_lengths) / len(chunk_lengths),
            "avg_token_count": sum(token_counts) / len(token_counts),
            "min_chunk_length": min(chunk_lengths),
            "max_chunk_length": max(chunk_lengths),
            "total_tokens": sum(token_counts),
            "tenant_id": str(self.tenant_id)
        }


# Factory function for creating tenant-isolated chunkers
async def create_tenant_chunker(tenant_id: UUID) -> TenantIsolatedLlamaIndexChunker:
    """Create and initialize a tenant-isolated LlamaIndex chunker"""
    chunker = TenantIsolatedLlamaIndexChunker(tenant_id)
    await chunker.initialize()
    return chunker