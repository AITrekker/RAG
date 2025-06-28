#!/usr/bin/env python3
"""
System Health Check Script for the Enterprise RAG Platform.

This script acts as a client to the running services and validates that all
critical API endpoints are working correctly. It does not import any backend
code directly, ensuring it tests the system as a true external client would.
"""

import requests
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class HealthChecker:
    """Performs API-based health checks on the RAG platform."""

    def __init__(self, base_url="http://localhost:8000/api/v1"):
        self.base_url = base_url
        self.session = requests.Session()
        self.results = {}

    def run_check(self, name: str, func, *args, **kwargs) -> None:
        """Runs a health check and stores the result."""
        try:
            logging.info(f"CHECKING: {name}...")
            result = func(*args, **kwargs)
            self.results[name] = {"status": "PASS", "details": result}
            logging.info(f"  -> PASS: {result}")
        except Exception as e:
            error_message = f"{type(e).__name__}: {str(e)}"
            self.results[name] = {"status": "FAIL", "details": error_message}
            logging.error(f"  -> FAIL: {error_message}", exc_info=True)

    def check_liveness(self):
        """Pings the main health endpoint."""
        response = self.session.get(f"{self.base_url}/health/liveness")
        response.raise_for_status()
        return response.json()

    def check_readiness(self):
        """Checks if all services the backend depends on are ready."""
        response = self.session.get(f"{self.base_url}/health/readiness")
        response.raise_for_status()
        return response.json()

    def check_query_e2e(self):
        """Performs an end-to-end check by sending a test query."""
        headers = {"X-Tenant-Id": "healthcheck-tenant"}
        payload = {"query": "What is the meaning of life?"}
        
        # It's okay if this returns a 404 or an empty response,
        # as long as it's not a 500-level server error.
        response = self.session.post(f"{self.base_url}/query", json=payload, headers=headers)
        
        if response.status_code >= 500:
            raise requests.HTTPError(f"Query endpoint returned status {response.status_code}", response=response)
        
        return {"status_code": response.status_code, "response": response.json()}

    def print_summary(self):
        """Prints a summary of the health check results."""
        print("\n" + "="*40)
        print("RAG PLATFORM HEALTH CHECK SUMMARY")
        print("="*40)
        
        all_passed = True
        for name, result in self.results.items():
            print(f"[{result['status']}] {name}")
            if result['status'] == "FAIL":
                all_passed = False
                print(f"  -> Details: {result['details']}")
        
        print("="*40)
        if all_passed:
            print("✅ All systems operational.")
        else:
            print("❌ System has issues that need attention.")
        print("="*40)
        return all_passed

def main():
    """Main entry point for the health check script."""
    # Give services a moment to start up fully
    time.sleep(5)
    
    checker = HealthChecker()
    checker.run_check("API Liveness", checker.check_liveness)
    checker.run_check("API Readiness", checker.check_readiness)
    checker.run_check("API E2E Query", checker.check_query_e2e)
    
    if not checker.print_summary():
        exit(1)

if __name__ == "__main__":
    main() 