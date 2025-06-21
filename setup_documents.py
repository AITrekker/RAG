#!/usr/bin/env python3
"""
Document Setup Script for Enterprise RAG Platform

This script helps you set up document processing with real files.
"""

import os
import sys
from pathlib import Path

def create_document_structure():
    """Create the document directory structure."""
    
    # Create main documents directory
    docs_dir = Path("documents")
    docs_dir.mkdir(exist_ok=True)
    
    # Create tenant-specific directories
    tenant_dirs = [
        "documents/default",
        "documents/default/pdfs",
        "documents/default/word_docs", 
        "documents/default/text_files"
    ]
    
    for dir_path in tenant_dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    print("✅ Document directory structure created:")
    for dir_path in tenant_dirs:
        print(f"   📁 {dir_path}")

def create_sample_documents():
    """Create sample documents for testing."""
    
    sample_docs = {
        "documents/default/text_files/company_policy.txt": """
Company Policy Document

1. Work Hours
Our standard work hours are 9:00 AM to 5:00 PM, Monday through Friday.
Flexible working arrangements can be discussed with your manager.

2. Remote Work Policy
Employees may work remotely up to 3 days per week with manager approval.
All remote work must be coordinated with your team.

3. Vacation Policy
All full-time employees receive 15 days of paid vacation per year.
Vacation requests must be submitted at least 2 weeks in advance.

4. Code of Conduct
All employees must maintain professional behavior and respect for colleagues.
Harassment or discrimination of any kind will not be tolerated.
""",
        
        "documents/default/text_files/product_manual.txt": """
Product Manual - RAG Platform

Overview:
The Enterprise RAG Platform is a document search and retrieval system
that uses advanced AI to answer questions based on your documents.

Key Features:
- Multi-tenant architecture for enterprise use
- Natural language query processing
- Real-time document synchronization
- Source citation and confidence scoring

Getting Started:
1. Upload your documents to the platform
2. Wait for processing and indexing
3. Start asking questions in natural language
4. Review answers with source citations

Technical Requirements:
- Python 3.8 or higher
- 8GB RAM minimum (16GB recommended)
- CUDA-compatible GPU (optional but recommended)
""",

        "documents/default/text_files/faq.txt": """
Frequently Asked Questions

Q: How do I upload documents?
A: Use the document sync feature in the web interface or API.

Q: What file formats are supported?
A: We support PDF, Word documents (.docx), text files (.txt), and Markdown (.md).

Q: How long does document processing take?
A: Processing time depends on document size. Typically 1-5 minutes per document.

Q: Can I search across all my documents at once?
A: Yes, the system searches across all documents in your tenant by default.

Q: How accurate are the answers?
A: Accuracy depends on document quality and query specificity. The system provides confidence scores.

Q: Is my data secure?
A: Yes, we use tenant isolation and enterprise security measures.
"""
    }
    
    for file_path, content in sample_docs.items():
        Path(file_path).write_text(content.strip())
        print(f"✅ Created sample document: {file_path}")

def main():
    """Main setup function."""
    print("🚀 Setting up Enterprise RAG Platform Documents\n")
    
    print("1. Creating document directory structure...")
    create_document_structure()
    
    print("\n2. Creating sample documents...")
    create_sample_documents()
    
    print(f"\n🎯 Next Steps:")
    print("1. Add your own documents to the 'documents/default/' folders")
    print("2. Run the document ingestion script: python ingest_documents.py")
    print("3. Test queries with your real documents!")
    
    print(f"\n📁 Document locations:")
    print("   • PDFs: documents/default/pdfs/")
    print("   • Word docs: documents/default/word_docs/")
    print("   • Text files: documents/default/text_files/")

if __name__ == "__main__":
    main() 