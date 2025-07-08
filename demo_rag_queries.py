#!/usr/bin/env python3
"""
RAG Query Demo - How to query and use RAG with test tenants

This script demonstrates how to:
1. Trigger sync operations to process documents
2. Perform RAG queries to get AI-generated answers
3. Use semantic search to find relevant documents
4. Validate queries and get suggestions

Usage:
    python demo_rag_queries.py
    python demo_rag_queries.py --tenant tenant2
    python demo_rag_queries.py --query "What is the company's mission?"
"""

import argparse
import json
import requests
import time
from typing import Dict, List, Any

# Configuration
BACKEND_URL = "http://localhost:8000"

# Load tenant API keys
with open("demo_tenant_keys.json") as f:
    TENANT_KEYS = json.load(f)

class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(title: str):
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")

def print_success(message: str):
    """Print success message."""
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")

def print_info(message: str):
    """Print info message."""
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")

def print_warning(message: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")

def get_tenant_headers(tenant_name: str) -> Dict[str, str]:
    """Get API headers for a specific tenant."""
    if tenant_name not in TENANT_KEYS:
        raise ValueError(f"Unknown tenant: {tenant_name}")
    
    return {
        "X-API-Key": TENANT_KEYS[tenant_name]["api_key"],
        "Content-Type": "application/json"
    }

def trigger_sync(tenant_name: str) -> Dict[str, Any]:
    """Trigger sync operation for a tenant."""
    print_header(f"TRIGGERING SYNC FOR {tenant_name.upper()}")
    
    headers = get_tenant_headers(tenant_name)
    
    response = requests.post(
        f"{BACKEND_URL}/api/v1/sync/trigger",
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        print_success(f"Sync triggered successfully!")
        print(f"   Sync ID: {data.get('sync_id', 'N/A')}")
        print(f"   Status: {data.get('status', 'N/A')}")
        print(f"   Message: {data.get('message', 'N/A')}")
        return data
    else:
        print_warning(f"Sync failed with status {response.status_code}")
        print(f"Response: {response.text}")
        return {}

def perform_rag_query(tenant_name: str, query: str) -> Dict[str, Any]:
    """Perform a RAG query and get AI-generated answers."""
    print_header(f"RAG QUERY FOR {tenant_name.upper()}")
    print(f"{Colors.BOLD}Query:{Colors.END} {query}")
    
    headers = get_tenant_headers(tenant_name)
    
    payload = {
        "query": query,
        "max_sources": 5,
        "confidence_threshold": 0.3
    }
    
    response = requests.post(
        f"{BACKEND_URL}/api/v1/query/",
        headers=headers,
        json=payload
    )
    
    if response.status_code == 200:
        data = response.json()
        
        print_success("RAG query successful!")
        print(f"\n{Colors.BOLD}AI-Generated Answer:{Colors.END}")
        print(f"{data.get('answer', 'No answer generated')}")
        
        print(f"\n{Colors.BOLD}Sources Used:{Colors.END}")
        sources = data.get('sources', [])
        for i, source in enumerate(sources, 1):
            print(f"   {i}. {source.get('filename', 'Unknown')} (score: {source.get('score', 'N/A'):.3f})")
            if source.get('content'):
                preview = source['content'][:100] + "..." if len(source['content']) > 100 else source['content']
                print(f"      Preview: {preview}")
        
        print(f"\n{Colors.BOLD}Query Metadata:{Colors.END}")
        print(f"   Confidence: {data.get('confidence', 0):.3f}")
        print(f"   Processing Time: {data.get('processing_time', 0):.3f}s")
        print(f"   Model Used: {data.get('model_used', 'N/A')}")
        print(f"   Tokens Used: {data.get('tokens_used', 'N/A')}")
        
        return data
    else:
        print_warning(f"RAG query failed with status {response.status_code}")
        print(f"Response: {response.text}")
        return {}

def semantic_search(tenant_name: str, query: str) -> Dict[str, Any]:
    """Perform semantic search to find relevant documents."""
    print_header(f"SEMANTIC SEARCH FOR {tenant_name.upper()}")
    print(f"{Colors.BOLD}Search Query:{Colors.END} {query}")
    
    headers = get_tenant_headers(tenant_name)
    
    payload = {
        "query": query,
        "max_results": 10
    }
    
    response = requests.post(
        f"{BACKEND_URL}/api/v1/query/search",
        headers=headers,
        json=payload
    )
    
    if response.status_code == 200:
        data = response.json()
        results = data.get('results', [])
        
        print_success(f"Found {len(results)} relevant documents!")
        
        for i, result in enumerate(results, 1):
            print(f"\n{Colors.BOLD}{i}. {result.get('filename', 'Unknown File')}{Colors.END}")
            print(f"   Relevance Score: {result.get('score', 0):.3f}")
            content = result.get('content', '')
            preview = content[:200] + "..." if len(content) > 200 else content
            print(f"   Content Preview: {preview}")
        
        return data
    else:
        print_warning(f"Semantic search failed with status {response.status_code}")
        print(f"Response: {response.text}")
        return {}

def validate_query(tenant_name: str, query: str) -> Dict[str, Any]:
    """Validate a query and get suggestions."""
    print_header(f"QUERY VALIDATION FOR {tenant_name.upper()}")
    
    headers = get_tenant_headers(tenant_name)
    
    payload = {"query": query}
    
    response = requests.post(
        f"{BACKEND_URL}/api/v1/query/validate",
        headers=headers,
        json=payload
    )
    
    if response.status_code == 200:
        data = response.json()
        is_valid = data.get('is_valid', False)
        suggestions = data.get('suggestions', [])
        
        if is_valid:
            print_success("Query is valid!")
        else:
            print_warning("Query needs improvement")
        
        if suggestions:
            print(f"\n{Colors.BOLD}Suggestions:{Colors.END}")
            for suggestion in suggestions:
                print(f"   • {suggestion}")
        
        return data
    else:
        print_warning(f"Query validation failed with status {response.status_code}")
        return {}

def get_query_suggestions(tenant_name: str, partial_query: str) -> Dict[str, Any]:
    """Get query suggestions based on partial input."""
    print_header(f"QUERY SUGGESTIONS FOR {tenant_name.upper()}")
    
    headers = get_tenant_headers(tenant_name)
    
    params = {
        "partial_query": partial_query,
        "max_suggestions": 5
    }
    
    response = requests.get(
        f"{BACKEND_URL}/api/v1/query/suggestions",
        headers=headers,
        params=params
    )
    
    if response.status_code == 200:
        data = response.json()
        suggestions = data.get('suggestions', [])
        
        print_success(f"Found {len(suggestions)} query suggestions!")
        
        for i, suggestion in enumerate(suggestions, 1):
            print(f"   {i}. {suggestion}")
        
        return data
    else:
        print_warning(f"Query suggestions failed with status {response.status_code}")
        return {}

def demo_full_workflow(tenant_name: str):
    """Demonstrate the complete RAG workflow."""
    print_header(f"COMPLETE RAG WORKFLOW DEMO - {tenant_name.upper()}")
    
    # Step 1: Trigger sync to ensure documents are processed
    print_info("Step 1: Triggering document sync...")
    trigger_sync(tenant_name)
    
    # Wait a moment for sync to process
    time.sleep(2)
    
    # Step 2: Perform various RAG queries
    sample_queries = [
        "What is the company's mission and vision?",
        "Tell me about the financial performance",
        "What products does the company offer?",
        "Who are the key team members?",
        "What are the main technical requirements?"
    ]
    
    print_info("Step 2: Performing RAG queries...")
    for query in sample_queries[:2]:  # Limit to 2 queries for demo
        perform_rag_query(tenant_name, query)
        time.sleep(1)
    
    # Step 3: Semantic search
    print_info("Step 3: Performing semantic search...")
    semantic_search(tenant_name, "company overview")
    
    # Step 4: Query validation and suggestions
    print_info("Step 4: Query validation and suggestions...")
    validate_query(tenant_name, "What is the company?")
    get_query_suggestions(tenant_name, "company")

def main():
    """Main demo function."""
    parser = argparse.ArgumentParser(description="RAG Query Demo")
    parser.add_argument("--tenant", choices=list(TENANT_KEYS.keys()), 
                       default="tenant1", help="Tenant to query")
    parser.add_argument("--query", help="Specific query to run")
    parser.add_argument("--workflow", action="store_true", 
                       help="Run complete workflow demo")
    
    args = parser.parse_args()
    
    print_header("RAG SYSTEM QUERY DEMO")
    print(f"{Colors.BOLD}Backend URL:{Colors.END} {BACKEND_URL}")
    print(f"{Colors.BOLD}Selected Tenant:{Colors.END} {args.tenant}")
    print(f"{Colors.BOLD}Description:{Colors.END} {TENANT_KEYS[args.tenant]['description']}")
    
    try:
        if args.workflow:
            demo_full_workflow(args.tenant)
        elif args.query:
            # First trigger sync, then run the query
            trigger_sync(args.tenant)
            time.sleep(2)
            perform_rag_query(args.tenant, args.query)
        else:
            # Interactive demo
            print_info("Running interactive demo...")
            
            # Show available operations
            print(f"\n{Colors.BOLD}Available Operations:{Colors.END}")
            print("1. Trigger sync")
            print("2. Ask a question (RAG query)")
            print("3. Search documents (semantic search)")
            print("4. Validate query")
            print("5. Get query suggestions")
            print("6. Complete workflow demo")
            
            # For now, run a simple demo
            demo_full_workflow(args.tenant)
            
    except KeyboardInterrupt:
        print_info("\nDemo interrupted by user")
    except Exception as e:
        print_warning(f"Demo failed: {e}")

if __name__ == "__main__":
    main()