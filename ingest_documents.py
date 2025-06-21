#!/usr/bin/env python3
"""
Document Ingestion Script for Enterprise RAG Platform

This script processes real documents and sets up the vector store for actual RAG queries.
"""

import os
import sys
from pathlib import Path
import sqlite3
from datetime import datetime
import hashlib
import json

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

def setup_database():
    """Initialize the database with document tables."""
    
    db_path = "data/rag_platform.db"
    os.makedirs("data", exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create documents table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            file_hash TEXT,
            content_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processing_status TEXT DEFAULT 'pending',
            metadata TEXT
        )
    """)
    
    # Create document chunks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER,
            chunk_index INTEGER,
            content TEXT NOT NULL,
            token_count INTEGER,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents (id)
        )
    """)
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

def calculate_file_hash(file_path):
    """Calculate MD5 hash of a file."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def chunk_text(text, chunk_size=1000, overlap=100):
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        
        # Try to break at sentence boundary
        if end < len(text):
            last_period = chunk.rfind('.')
            last_newline = chunk.rfind('\n')
            break_point = max(last_period, last_newline)
            
            if break_point > start + chunk_size // 2:
                chunk = text[start:break_point + 1]
                end = break_point + 1
        
        chunks.append(chunk.strip())
        start = end - overlap
        
        if end >= len(text):
            break
    
    return chunks

def process_document(file_path, tenant_id="default"):
    """Process a single document and store in database."""
    
    print(f"📄 Processing: {file_path}")
    
    # Read file content
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        print(f"❌ Could not read {file_path} - unsupported encoding")
        return False
    
    # Calculate file metadata
    file_size = os.path.getsize(file_path)
    file_hash = calculate_file_hash(file_path)
    filename = os.path.basename(file_path)
    
    # Connect to database
    conn = sqlite3.connect("data/rag_platform.db")
    cursor = conn.cursor()
    
    # Check if document already exists
    cursor.execute(
        "SELECT id FROM documents WHERE file_hash = ? AND tenant_id = ?",
        (file_hash, tenant_id)
    )
    existing = cursor.fetchone()
    
    if existing:
        print(f"⚠️  Document already exists: {filename}")
        conn.close()
        return True
    
    # Insert document record
    cursor.execute("""
        INSERT INTO documents 
        (tenant_id, filename, file_path, file_size, file_hash, content_type, processing_status, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        tenant_id,
        filename,
        str(file_path),
        file_size,
        file_hash,
        "text/plain",
        "processing",
        json.dumps({"original_path": str(file_path)})
    ))
    
    document_id = cursor.lastrowid
    
    # Chunk the content
    chunks = chunk_text(content)
    print(f"   📝 Created {len(chunks)} chunks")
    
    # Insert chunks
    for i, chunk in enumerate(chunks):
        cursor.execute("""
            INSERT INTO document_chunks 
            (document_id, chunk_index, content, token_count, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (
            document_id,
            i,
            chunk,
            len(chunk.split()),  # Rough token count
            json.dumps({"chunk_size": len(chunk)})
        ))
    
    # Update document status
    cursor.execute(
        "UPDATE documents SET processing_status = 'completed' WHERE id = ?",
        (document_id,)
    )
    
    conn.commit()
    conn.close()
    
    print(f"✅ Processed: {filename} ({len(chunks)} chunks)")
    return True

def scan_and_process_documents():
    """Scan document directories and process all files."""
    
    document_dirs = [
        "documents/default/text_files",
        "documents/default/pdfs",
        "documents/default/word_docs"
    ]
    
    processed_count = 0
    
    for doc_dir in document_dirs:
        if not os.path.exists(doc_dir):
            print(f"⚠️  Directory not found: {doc_dir}")
            continue
        
        print(f"\n📁 Scanning: {doc_dir}")
        
        for file_path in Path(doc_dir).glob("*"):
            if file_path.is_file() and file_path.suffix.lower() in ['.txt', '.md']:
                if process_document(file_path):
                    processed_count += 1
    
    return processed_count

def update_rag_service():
    """Update the RAG service to use real documents instead of mock responses."""
    
    rag_service_path = "src/backend/core/rag_pipeline.py"
    
    # Read current file
    with open(rag_service_path, 'r') as f:
        content = f.read()
    
    # Replace mock implementation with real one
    new_content = '''"""
Enhanced RAG Pipeline with Real Document Processing
"""

import sqlite3
import json
from typing import List, Dict, Any, Optional
from pathlib import Path

class RAGPipeline:
    """Real RAG Pipeline that queries actual documents."""
    
    def __init__(self, db_path: str = "data/rag_platform.db"):
        self.db_path = db_path
    
    def search_documents(self, query: str, tenant_id: str = "default", limit: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant document chunks using simple text matching."""
        
        if not Path(self.db_path).exists():
            return []
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Simple keyword search (in production, this would use vector similarity)
        query_words = query.lower().split()
        
        # Search in document chunks
        cursor.execute("""
            SELECT 
                dc.content,
                dc.chunk_index,
                d.filename,
                d.file_path,
                dc.metadata
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.id
            WHERE d.tenant_id = ? AND d.processing_status = 'completed'
            ORDER BY dc.id
        """, (tenant_id,))
        
        chunks = cursor.fetchall()
        conn.close()
        
        # Score chunks based on keyword matches
        scored_chunks = []
        for content, chunk_index, filename, file_path, metadata in chunks:
            content_lower = content.lower()
            score = sum(1 for word in query_words if word in content_lower)
            
            if score > 0:
                scored_chunks.append({
                    'content': content,
                    'score': score,
                    'chunk_index': chunk_index,
                    'filename': filename,
                    'file_path': file_path,
                    'metadata': json.loads(metadata) if metadata else {}
                })
        
        # Sort by score and return top results
        scored_chunks.sort(key=lambda x: x['score'], reverse=True)
        return scored_chunks[:limit]
    
    def generate_response(self, query: str, context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate response based on retrieved context."""
        
        if not context_chunks:
            return {
                "answer": "I couldn't find relevant information in your documents to answer this question.",
                "confidence": 0.0,
                "sources": []
            }
        
        # Simple response generation (in production, this would use an LLM)
        relevant_content = []
        sources = []
        
        for chunk in context_chunks:
            relevant_content.append(chunk['content'][:200] + "...")
            sources.append({
                "filename": chunk['filename'],
                "chunk_index": chunk['chunk_index'],
                "confidence": min(chunk['score'] * 0.2, 1.0)  # Simple confidence scoring
            })
        
        # Create a basic answer
        answer = f"Based on your documents, here's what I found:\\n\\n"
        answer += "\\n\\n".join(relevant_content)
        
        return {
            "answer": answer,
            "confidence": min(len(context_chunks) * 0.2, 0.9),
            "sources": sources
        }
    
    async def process_query(self, query: str, tenant_id: str = "default") -> Dict[str, Any]:
        """Process a query and return response with sources."""
        
        # Search for relevant documents
        context_chunks = self.search_documents(query, tenant_id)
        
        # Generate response
        response = self.generate_response(query, context_chunks)
        
        return {
            "query": query,
            "answer": response["answer"],
            "confidence": response["confidence"],
            "sources": response["sources"],
            "processing_time": 0.5,  # Mock processing time
            "context_used": len(context_chunks)
        }

# Global instance
rag_pipeline = RAGPipeline()
'''
    
    # Write updated content
    with open(rag_service_path, 'w') as f:
        f.write(new_content)
    
    print("✅ Updated RAG service to use real documents")

def main():
    """Main ingestion process."""
    
    print("🚀 Enterprise RAG Platform - Document Ingestion\n")
    
    # Check if documents directory exists
    if not os.path.exists("documents"):
        print("❌ Documents directory not found!")
        print("   Run: python setup_documents.py first")
        return
    
    print("1. Setting up database...")
    setup_database()
    
    print("\n2. Processing documents...")
    processed_count = scan_and_process_documents()
    
    print("\n3. Updating RAG service...")
    update_rag_service()
    
    print(f"\n🎉 Document ingestion complete!")
    print(f"   📊 Processed {processed_count} documents")
    print(f"   🔍 Ready for real queries!")
    
    print(f"\n🎯 Next Steps:")
    print("1. Restart your backend server: python run_backend.py")
    print("2. Try asking questions about your documents!")
    print("3. Example queries:")
    print("   • 'What are the work hours?'")
    print("   • 'How do I request vacation?'")
    print("   • 'What file formats are supported?'")

if __name__ == "__main__":
    main() 