"""
Simple RAG Service - Replace the over-engineered hybrid system

This is what your RAG service should look like to leverage LlamaIndex properly.
"""

from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from llama_index.core import Document, VectorStoreIndex
from llama_index.vector_stores.postgres import PGVectorStore
from llama_index.core.query_engine import RetrieverQueryEngine

class SimpleRAGService:
    def __init__(self, db: AsyncSession, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id
        
        # This is where LlamaIndex shines - simple setup
        self.vector_store = PGVectorStore.from_params(
            connection_string=DATABASE_URL,
            table_name=f"tenant_{tenant_id}_vectors",
            embed_dim=384
        )
        self.index = VectorStoreIndex.from_vector_store(self.vector_store)
        self.query_engine = self.index.as_query_engine()
    
    async def add_document(self, file_content: str, metadata: Dict[str, Any]) -> None:
        """Add document to index - LlamaIndex handles chunking and embedding"""
        doc = Document(text=file_content, metadata=metadata)
        self.index.insert(doc)
    
    async def query(self, question: str) -> Dict[str, Any]:
        """Query the index - LlamaIndex handles retrieval and generation"""
        response = self.query_engine.query(question)
        
        return {
            "answer": str(response),
            "sources": [
                {
                    "content": node.text,
                    "metadata": node.metadata,
                    "score": node.score
                }
                for node in response.source_nodes
            ]
        }

# That's it. 30 lines vs your current 500+ lines of complexity.
# LlamaIndex handles:
# - Document chunking
# - Embedding generation  
# - Vector storage
# - Retrieval
# - Response generation
# - Source attribution

# To use this properly, you'd replace your entire hybrid system with this.