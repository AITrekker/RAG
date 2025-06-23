#!/usr/bin/env python3
"""
System Health Check Script

Validates all critical components are working correctly.
Run this after any changes to catch integration issues early.
"""

import sys
import asyncio
import requests
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

class HealthChecker:
    """Comprehensive system health validation"""
    
    def __init__(self):
        self.api_base = "http://localhost:8000/api/v1"
        self.api_key = "dev-api-key-123"
        self.results = []
    
    def check(self, name: str, func) -> bool:
        """Run a health check and record results"""
        try:
            print(f"Checking {name}...", end=" ")
            result = func()
            if result:
                print("PASS")
                self.results.append((name, "PASS", None))
                return True
            else:
                print("FAIL")
                self.results.append((name, "FAIL", "Check returned False"))
                return False
        except Exception as e:
            print(f"ERROR: {e}")
            self.results.append((name, "ERROR", str(e)))
            return False
    
    async def check_async(self, name: str, func) -> bool:
        """Run an async health check"""
        try:
            print(f"Checking {name}...", end=" ")
            result = await func()
            if result:
                print("PASS")
                self.results.append((name, "PASS", None))
                return True
            else:
                print("FAIL")
                self.results.append((name, "FAIL", "Check returned False"))
                return False
        except Exception as e:
            print(f"ERROR: {e}")
            self.results.append((name, "ERROR", str(e)))
            return False
    
    def check_api_connectivity(self) -> bool:
        """Check if API is responding"""
        response = requests.get(f"{self.api_base}/health", timeout=10)
        return response.status_code == 200
    
    def check_database_connection(self) -> bool:
        """Check database connectivity"""
        from src.backend.db.session import get_db
        try:
            db = next(get_db())
            db.execute("SELECT 1")
            db.close()
            return True
        except:
            return False
    
    def check_vector_store(self) -> bool:
        """Check vector store connectivity"""
        from src.backend.utils.vector_store import get_vector_store_manager
        try:
            vector_manager = get_vector_store_manager()
            collections = vector_manager.client.list_collections()
            return len(collections) > 0
        except:
            return False
    
    def check_tenant_data_exists(self) -> bool:
        """Check that tenants have data"""
        from src.backend.db.session import get_db
        from sqlalchemy import text
        
        db = next(get_db())
        result = db.execute(text("""
            SELECT COUNT(*) 
            FROM documents d 
            JOIN tenants t ON d.tenant_id = t.id 
            WHERE t.tenant_id IN ('tenant1', 'tenant2')
        """))
        count = result.scalar()
        db.close()
        return count > 0
    
    def check_embedding_service(self) -> bool:
        """Check embedding service"""
        from src.backend.core.embeddings import get_embedding_service
        
        service = get_embedding_service()
        # Test encoding
        embeddings = service.encode_texts(["test query"])
        return len(embeddings) > 0 and len(embeddings[0]) > 0
    
    async def check_rag_pipeline(self) -> bool:
        """Check RAG pipeline end-to-end"""
        from src.backend.core.rag_pipeline import get_rag_pipeline
        
        pipeline = get_rag_pipeline()
        response = await pipeline.process_query("test query", "tenant1")
        return response.answer != "I could not find any relevant information"
    
    def check_tenant_isolation(self) -> bool:
        """Check tenant isolation via API"""
        # Test tenant1
        headers1 = {
            "X-Tenant-Id": "tenant1",
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        response1 = requests.post(
            f"{self.api_base}/query",
            json={"query": "company policy", "max_sources": 3},
            headers=headers1,
            timeout=30
        )
        
        if response1.status_code != 200:
            return False
        
        data1 = response1.json()
        
        # Test tenant2
        headers2 = {
            "X-Tenant-Id": "tenant2", 
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        response2 = requests.post(
            f"{self.api_base}/query",
            json={"query": "company policy", "max_sources": 3},
            headers=headers2,
            timeout=30
        )
        
        if response2.status_code != 200:
            return False
        
        data2 = response2.json()
        
        # Both should get results (different results)
        return (len(data1["sources"]) > 0 and len(data2["sources"]) > 0)
    
    def print_summary(self):
        """Print health check summary"""
        print("\n" + "="*60)
        print("SYSTEM HEALTH SUMMARY")
        print("="*60)
        
        passed = sum(1 for _, status, _ in self.results if status == "PASS")
        total = len(self.results)
        
        for name, status, error in self.results:
            icon = "[PASS]" if status == "PASS" else "[FAIL]"
            print(f"{icon} {name}: {status}")
            if error:
                print(f"   Error: {error}")
        
        print(f"\nResult: {passed}/{total} checks passed")
        
        if passed == total:
            print("All systems healthy!")
            return True
        else:
            print("System has issues that need attention")
            return False

async def main():
    """Run all health checks"""
    print("RAG Platform Health Check")
    print("="*40)
    
    checker = HealthChecker()
    
    # Core infrastructure
    checker.check("API Server", checker.check_api_connectivity)
    checker.check("Database Connection", checker.check_database_connection)
    checker.check("Vector Store", checker.check_vector_store)
    checker.check("Tenant Data Exists", checker.check_tenant_data_exists)
    
    # AI Services
    checker.check("Embedding Service", checker.check_embedding_service)
    await checker.check_async("RAG Pipeline", checker.check_rag_pipeline)
    
    # Integration
    checker.check("Tenant Isolation", checker.check_tenant_isolation)
    
    # Summary
    all_passed = checker.print_summary()
    
    if not all_passed:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 