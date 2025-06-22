#!/usr/bin/env python3
"""
Comprehensive Test Runner for Enterprise RAG Platform Backend

Executes all test suites and provides comprehensive coverage reporting.
This script runs all tests and generates a detailed report of backend functionality coverage.
"""

import sys
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Tuple
import importlib.util

# Update the path to ensure 'src' is in our import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestRunner:
    """Comprehensive test runner for the RAG platform."""
    
    def __init__(self):
        self.test_files = [
            "test_api_endpoints.py",
            "test_utils_and_services.py", 
            "test_middleware_and_db.py",
            "test_core_components.py",
            "test_tenant_isolation.py",
            "test_document_processing.py",
            "test_delta_sync.py",
            "test_embedding_config.py",
            "test_section_2_complete.py",
            "test_auditing.py",
            "test_real_rag.py"
        ]
        
        self.results = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "skipped_tests": 0,
            "errors": [],
            "test_file_results": {}
        }
        
        self.coverage_map = {
            # API Layer
            "Documents API": ["test_api_endpoints.py"],
            "Query API": ["test_api_endpoints.py"],
            "Health API": ["test_api_endpoints.py"],
            "Tenants API": ["test_api_endpoints.py"],
            "Sync API": ["test_api_endpoints.py"],
            "Audit API": ["test_api_endpoints.py"],
            
            # Core Services
            "Embedding Service": ["test_core_components.py", "test_embedding_config.py", "test_section_2_complete.py"],
            "Vector Store": ["test_core_components.py", "test_utils_and_services.py", "test_section_2_complete.py"],
            "RAG Pipeline": ["test_section_2_complete.py", "test_real_rag.py"],
            "LLM Service": ["test_utils_and_services.py", "test_section_2_complete.py"],
            "Document Processing": ["test_document_processing.py", "test_section_2_complete.py"],
            "Document Ingestion": ["test_document_processing.py"],
            "Delta Sync": ["test_delta_sync.py"],
            "Auditing": ["test_auditing.py"],
            
            # Infrastructure
            "Tenant Isolation": ["test_tenant_isolation.py"],
            "Tenant Management": ["test_tenant_isolation.py", "test_middleware_and_db.py"],
            "Authentication": ["test_middleware_and_db.py"],
            "Database Models": ["test_middleware_and_db.py"],
            "File Monitoring": ["test_utils_and_services.py", "test_document_processing.py"],
            "HTML Processing": ["test_utils_and_services.py", "test_document_processing.py"],
            "Performance Monitoring": ["test_utils_and_services.py", "test_section_2_complete.py"],
            
            # Utilities
            "Filesystem Management": ["test_utils_and_services.py"],
            "Configuration": ["test_embedding_config.py", "test_core_components.py"],
            "Error Handling": ["test_api_endpoints.py", "test_document_processing.py"],
        }
    
    def print_banner(self):
        """Print test runner banner."""
        print("=" * 80)
        print("🧪 ENTERPRISE RAG PLATFORM - COMPREHENSIVE TEST SUITE")
        print("=" * 80)
        print(f"📋 Running {len(self.test_files)} test files")
        print(f"🎯 Testing {len(self.coverage_map)} functional areas")
        print("=" * 80)
    
    def run_single_test_file(self, test_file: str) -> Dict:
        """Run a single test file and return results."""
        print(f"\n📝 Running {test_file}...")
        
        try:
            # Run pytest on the specific file
            result = subprocess.run([
                sys.executable, "-m", "pytest", test_file, "-v", "--tb=short"
            ], capture_output=True, text=True, timeout=300)
            
            # Parse results
            output = result.stdout + result.stderr
            
            # Count test results from output
            passed = output.count("PASSED")
            failed = output.count("FAILED")
            skipped = output.count("SKIPPED")
            errors = output.count("ERROR")
            
            file_result = {
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "errors": errors,
                "total": passed + failed + skipped + errors,
                "success": result.returncode == 0,
                "output": output,
                "duration": 0  # Would need timing to implement
            }
            
            if file_result["success"]:
                print(f"✅ {test_file}: {file_result['total']} tests ({passed} passed)")
            else:
                print(f"❌ {test_file}: {failed + errors} failures/errors")
                if failed > 0 or errors > 0:
                    print(f"   Output preview: {output[:200]}...")
            
            return file_result
            
        except subprocess.TimeoutExpired:
            print(f"⏰ {test_file}: Timeout after 5 minutes")
            return {
                "passed": 0, "failed": 0, "skipped": 0, "errors": 1,
                "total": 1, "success": False, "output": "Timeout", "duration": 300
            }
        except Exception as e:
            print(f"💥 {test_file}: Exception - {str(e)}")
            return {
                "passed": 0, "failed": 0, "skipped": 0, "errors": 1,
                "total": 1, "success": False, "output": str(e), "duration": 0
            }
    
    def run_all_tests(self):
        """Run all test files."""
        self.print_banner()
        
        start_time = time.time()
        
        # Run each test file
        for test_file in self.test_files:
            if os.path.exists(test_file):
                file_result = self.run_single_test_file(test_file)
                self.results["test_file_results"][test_file] = file_result
                
                # Update totals
                self.results["total_tests"] += file_result["total"]
                self.results["passed_tests"] += file_result["passed"]
                self.results["failed_tests"] += file_result["failed"] + file_result["errors"]
                self.results["skipped_tests"] += file_result["skipped"]
                
                if not file_result["success"]:
                    self.results["errors"].append(f"{test_file}: {file_result['output'][:100]}")
            else:
                print(f"⚠️  {test_file}: File not found, skipping")
        
        duration = time.time() - start_time
        
        # Generate final report
        self.generate_comprehensive_report(duration)
    
    def generate_comprehensive_report(self, duration: float):
        """Generate comprehensive test results report."""
        print("\n" + "=" * 80)
        print("📊 COMPREHENSIVE TEST RESULTS REPORT")
        print("=" * 80)
        
        # Overall statistics
        total = self.results["total_tests"]
        passed = self.results["passed_tests"]
        failed = self.results["failed_tests"]
        skipped = self.results["skipped_tests"]
        
        success_rate = (passed / total * 100) if total > 0 else 0
        
        print(f"\n🎯 OVERALL RESULTS:")
        print(f"   Total Tests: {total}")
        print(f"   ✅ Passed: {passed} ({success_rate:.1f}%)")
        print(f"   ❌ Failed: {failed}")
        print(f"   ⏭️  Skipped: {skipped}")
        print(f"   ⏱️  Duration: {duration:.2f} seconds")
        
        # Per-file results
        print(f"\n📋 TEST FILE RESULTS:")
        for test_file, result in self.results["test_file_results"].items():
            status = "✅" if result["success"] else "❌"
            print(f"   {status} {test_file}: {result['passed']}/{result['total']} passed")
        
        # Functional coverage report
        self.generate_coverage_report()
        
        # Error summary
        if self.results["errors"]:
            print(f"\n🚨 ERRORS SUMMARY:")
            for error in self.results["errors"][:5]:  # Show first 5 errors
                print(f"   • {error}")
            if len(self.results["errors"]) > 5:
                print(f"   ... and {len(self.results['errors']) - 5} more errors")
        
        # Recommendations
        self.generate_recommendations()
        
        # Final status
        print("\n" + "=" * 80)
        if success_rate >= 95:
            print("🎉 EXCELLENT: Test suite is comprehensive and well-maintained!")
        elif success_rate >= 85:
            print("👍 GOOD: Test suite provides solid coverage with minor issues.")
        elif success_rate >= 70:
            print("⚠️  FAIR: Test suite needs improvements for better coverage.")
        else:
            print("🔴 POOR: Test suite requires significant attention and fixes.")
        print("=" * 80)
    
    def generate_coverage_report(self):
        """Generate functional area coverage report."""
        print(f"\n🎯 FUNCTIONAL AREA COVERAGE:")
        
        for area, test_files in self.coverage_map.items():
            area_tested = any(
                test_file in self.results["test_file_results"] and 
                self.results["test_file_results"][test_file]["success"]
                for test_file in test_files
            )
            
            status = "✅" if area_tested else "❌"
            print(f"   {status} {area}")
        
        # Calculate coverage percentage
        total_areas = len(self.coverage_map)
        covered_areas = sum(
            1 for area, test_files in self.coverage_map.items()
            if any(
                test_file in self.results["test_file_results"] and 
                self.results["test_file_results"][test_file]["success"]
                for test_file in test_files
            )
        )
        
        coverage_percent = (covered_areas / total_areas * 100) if total_areas > 0 else 0
        print(f"\n   📈 Functional Coverage: {covered_areas}/{total_areas} ({coverage_percent:.1f}%)")
    
    def generate_recommendations(self):
        """Generate recommendations for improving test coverage."""
        print(f"\n💡 RECOMMENDATIONS:")
        
        # Check for missing functional areas
        uncovered_areas = []
        for area, test_files in self.coverage_map.items():
            area_tested = any(
                test_file in self.results["test_file_results"] and 
                self.results["test_file_results"][test_file]["success"]
                for test_file in test_files
            )
            if not area_tested:
                uncovered_areas.append(area)
        
        if uncovered_areas:
            print(f"   🎯 Focus on uncovered areas: {', '.join(uncovered_areas[:3])}")
        
        # Check for failing test files
        failing_files = [
            test_file for test_file, result in self.results["test_file_results"].items()
            if not result["success"]
        ]
        
        if failing_files:
            print(f"   🔧 Fix failing test files: {', '.join(failing_files[:3])}")
        
        # Performance recommendations
        if self.results["total_tests"] < 100:
            print(f"   📈 Consider adding more granular unit tests")
        
        if self.results["skipped_tests"] > 10:
            print(f"   ⚡ Review and enable {self.results['skipped_tests']} skipped tests")
        
        # Integration recommendations
        print(f"   🔗 Consider adding integration tests for end-to-end workflows")
        print(f"   📊 Add performance benchmarking tests")
        print(f"   🛡️  Add security and penetration testing")
    
    def run_specific_area(self, area: str):
        """Run tests for a specific functional area."""
        if area not in self.coverage_map:
            print(f"❌ Unknown functional area: {area}")
            print(f"Available areas: {', '.join(self.coverage_map.keys())}")
            return
        
        print(f"🎯 Running tests for: {area}")
        test_files = self.coverage_map[area]
        
        for test_file in test_files:
            if test_file in self.test_files and os.path.exists(test_file):
                self.run_single_test_file(test_file)


def main():
    """Main entry point for test runner."""
    runner = TestRunner()
    
    # Check command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "--list-areas":
            print("Available functional areas:")
            for area in runner.coverage_map.keys():
                print(f"  • {area}")
            return
        
        elif command == "--area" and len(sys.argv) > 2:
            area = sys.argv[2]
            runner.run_specific_area(area)
            return
        
        elif command == "--help":
            print("RAG Platform Test Runner")
            print("Usage:")
            print("  python run_all_tests.py                 # Run all tests")
            print("  python run_all_tests.py --list-areas    # List functional areas")
            print("  python run_all_tests.py --area <name>   # Run tests for specific area")
            print("  python run_all_tests.py --help          # Show this help")
            return
    
    # Run all tests by default
    runner.run_all_tests()


if __name__ == "__main__":
    main() 