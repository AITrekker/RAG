#!/usr/bin/env python3
"""
Test script for real RAG functionality
"""

import requests
import json
import time

def test_query(query_text):
    """Test a single query."""
    print(f"\n🔍 Testing query: '{query_text}'")
    
    url = "http://localhost:8000/api/v1/query"
    headers = {"Content-Type": "application/json"}
    data = {"query": query_text}
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Query successful!")
            print(f"📝 Answer: {result['answer'][:200]}...")
            print(f"📊 Sources: {len(result['sources'])} found")
            print(f"⏱️ Processing time: {result['processing_time']:.2f}s")
            
            if result['sources']:
                print(f"📄 Source files:")
                for source in result['sources']:
                    print(f"   • {source['filename']} (confidence: {source['confidence_score']:.2f})")
            
            return True
        else:
            print(f"❌ Query failed: {response.status_code}")
            print(f"   Error: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection error: {e}")
        return False

def main():
    """Run test queries."""
    print("🚀 Testing Real RAG Functionality\n")
    
    # Check if server is running
    try:
        response = requests.get("http://localhost:8000/api/v1/health", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running")
        else:
            print("❌ Server health check failed")
            return
    except requests.exceptions.RequestException:
        print("❌ Server is not running. Please start with: python run_backend.py")
        return
    
    # Test queries
    test_queries = [
        "What are the work hours?",
        "How do I request vacation?",
        "What file formats are supported?",
        "What is the remote work policy?",
        "How long does document processing take?"
    ]
    
    successful_tests = 0
    total_tests = len(test_queries)
    
    for query in test_queries:
        if test_query(query):
            successful_tests += 1
        time.sleep(1)  # Small delay between queries
    
    print(f"\n🎯 Test Results: {successful_tests}/{total_tests} queries successful")
    
    if successful_tests == total_tests:
        print("🎉 All tests passed! Your RAG system is working with real documents!")
    else:
        print("⚠️ Some tests failed. Check the server logs for details.")

if __name__ == "__main__":
    main() 