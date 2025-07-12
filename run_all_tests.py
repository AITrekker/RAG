#!/usr/bin/env python3
"""
Comprehensive Test Runner for RAG System

This script runs all API tests and provides a detailed summary of results.
It checks prerequisites, runs tests, and provides clear output for CI/CD integration.

Usage:
    python run_all_tests.py
    python run_all_tests.py --verbose
    python run_all_tests.py --fast  # Skip slower tests
    python run_all_tests.py --category health  # Run specific category
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")

# Test categories
TEST_CATEGORIES = {
    "health": ["tests/test_api_health.py"],
    "sync": ["tests/test_api_sync.py", "tests/test_sync_service.py"], 
    "embedding": ["tests/test_embedding_service.py"],
    "query": ["tests/test_api_query.py"],
    "rag": ["tests/test_rag_comprehensive.py"],
    "multitenancy": ["tests/test_api_multitenancy.py"],
    "templates": ["tests/test_api_templates.py"],
    # "analytics": ["tests/test_analytics_api.py"],  # Removed: analytics complexity eliminated
    "comprehensive_sync": ["tests/test_comprehensive_sync_embeddings.py"],
    "comprehensive": [
        "tests/test_sync_service.py",
        "tests/test_embedding_service.py", 
        "tests/test_rag_comprehensive.py",
        "tests/test_comprehensive_sync_embeddings.py"
    ],
    "critical": [
        "tests/test_api_health.py",
        "tests/test_comprehensive_sync_embeddings.py",
        "tests/test_api_query.py"
    ],
    "all": [
        "tests/test_api_health.py",
        "tests/test_api_sync.py", 
        "tests/test_sync_service.py",
        "tests/test_embedding_service.py",
        "tests/test_api_query.py",
        "tests/test_rag_comprehensive.py",
        "tests/test_api_multitenancy.py",
        "tests/test_api_templates.py",
        #"tests/test_analytics_api.py",
        "tests/test_comprehensive_sync_embeddings.py"
    ]
}

class Colors:
    """ANSI color codes for terminal output."""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def print_header(title: str):
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{title.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")

def print_success(message: str):
    """Print success message."""
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")

def print_error(message: str):
    """Print error message."""
    print(f"{Colors.RED}❌ {message}{Colors.END}")

def print_warning(message: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")

def print_info(message: str):
    """Print info message."""
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")

def check_prerequisites() -> bool:
    """Check if all prerequisites are met."""
    print_header("CHECKING PREREQUISITES")
    
    all_good = True
    
    # 1. Check backend is running
    try:
        response = requests.get(f"{BACKEND_URL}/api/v1/health/liveness", timeout=5)
        if response.status_code == 200:
            print_success(f"Backend running at {BACKEND_URL}")
        else:
            print_error(f"Backend unhealthy (status: {response.status_code})")
            all_good = False
    except requests.exceptions.RequestException as e:
        print_error(f"Backend not accessible: {e}")
        print_info("Start backend with: docker-compose up -d")
        all_good = False
    
    # 2. Check demo tenant keys exist
    demo_keys_file = Path("demo_tenant_keys.json")
    if demo_keys_file.exists():
        try:
            with open(demo_keys_file) as f:
                keys = json.load(f)
            tenant_count = len(keys)
            print_success(f"Demo tenant keys found ({tenant_count} tenants)")
            
            # Validate key format
            for tenant_name, tenant_data in keys.items():
                if not tenant_data.get("api_key", "").startswith("tenant_"):
                    print_warning(f"Invalid API key format for {tenant_name}")
                    
        except Exception as e:
            print_error(f"Failed to load demo tenant keys: {e}")
            all_good = False
    else:
        print_error("Demo tenant keys not found")
        print_info("Run: python scripts/workflow/setup_demo_tenants.py --env development")
        all_good = False
    
    # 3. Check test dependencies
    required_packages = [
        ("pytest", "pytest"),
        ("requests", "requests"), 
        ("python-dotenv", "dotenv")
    ]
    missing_packages = []
    
    for package_name, import_name in required_packages:
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(package_name)
    
    if missing_packages:
        print_error(f"Missing packages: {', '.join(missing_packages)}")
        print_info("Install with: pip install -r tests/requirements-minimal.txt")
        all_good = False
    else:
        print_success("All test dependencies available")
    
    # 4. Check pytest is available
    try:
        # Try python3 first, then fallback to python for Windows compatibility
        python_cmd = "python3"
        result = subprocess.run([python_cmd, "-m", "pytest", "--version"], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            # Fallback to 'python' command for Windows
            python_cmd = "python"
            result = subprocess.run([python_cmd, "-m", "pytest", "--version"], 
                                  capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            pytest_version = result.stdout.strip().split()[-1]
            print_success(f"Pytest available (version {pytest_version})")
        else:
            print_error("Pytest not working properly")
            print_info(f"Command output: {result.stderr}")
            all_good = False
    except Exception as e:
        print_error(f"Failed to check pytest: {e}")
        all_good = False
    
    return all_good

def run_test_category(category: str, verbose: bool = False, fast: bool = False) -> Dict:
    """Run tests for a specific category."""
    if category not in TEST_CATEGORIES:
        raise ValueError(f"Unknown category: {category}")
    
    test_files = TEST_CATEGORIES[category]
    results = {
        "category": category,
        "total_tests": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "duration": 0,
        "failed_tests": [],
        "output": ""
    }
    
    print_header(f"RUNNING {category.upper()} TESTS")
    
    # Build pytest command (Windows compatible)
    python_cmd = "python3"
    try:
        # Test if python3 works, otherwise use python
        subprocess.run([python_cmd, "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        python_cmd = "python"
    
    # Ensure we're in the right directory for imports
    cmd = [python_cmd, "-m", "pytest"] + test_files
    cmd.extend(["--rootdir=."])  # Set root directory explicitly
    
    if verbose:
        cmd.extend(["-v", "-s"])
    else:
        cmd.append("-v")
    
    if fast:
        cmd.extend(["-x"])  # Stop on first failure
    
    # Add output formatting
    cmd.extend(["--tb=short"])
    
    start_time = time.time()
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        duration = time.time() - start_time
        
        results["duration"] = duration
        results["output"] = result.stdout + result.stderr
        
        # Parse pytest output for results
        output_lines = result.stdout.split('\n')
        
        for line in output_lines:
            if " passed" in line and (" failed" in line or " error" in line):
                # Parse line like "5 failed, 18 passed in 34.08s"
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "passed" and i > 0:
                        try:
                            results["passed"] = int(parts[i-1])
                        except (ValueError, IndexError):
                            pass
                    elif part == "failed" and i > 0:
                        try:
                            results["failed"] = int(parts[i-1])
                        except (ValueError, IndexError):
                            pass
                    elif part == "skipped" and i > 0:
                        try:
                            results["skipped"] = int(parts[i-1])
                        except (ValueError, IndexError):
                            pass
                break
            elif " passed" in line and " failed" not in line and " error" not in line:
                # Parse line like "23 passed in 34.60s" 
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "passed" and i > 0:
                        try:
                            results["passed"] = int(parts[i-1])
                        except (ValueError, IndexError):
                            pass
                        break
        
        results["total_tests"] = results["passed"] + results["failed"] + results["skipped"]
        
        # Extract failed test names
        if result.returncode != 0:
            in_failures = False
            for line in output_lines:
                if "FAILURES" in line:
                    in_failures = True
                elif in_failures and line.startswith("_"):
                    test_name = line.split()[0].replace("_", "").strip()
                    if test_name and test_name not in results["failed_tests"]:
                        results["failed_tests"].append(test_name)
        
        # Print summary
        if results["failed"] == 0:
            print_success(f"{category.title()} tests: {results['passed']}/{results['total_tests']} passed ({duration:.1f}s)")
        else:
            print_error(f"{category.title()} tests: {results['passed']}/{results['total_tests']} passed, {results['failed']} failed ({duration:.1f}s)")
            
            if results["failed_tests"]:
                print_info(f"Failed tests: {', '.join(results['failed_tests'])}")
        
    except subprocess.TimeoutExpired:
        print_error(f"{category.title()} tests timed out after 5 minutes")
        results["failed"] = 1
        results["output"] = "Tests timed out"
    except Exception as e:
        print_error(f"Error running {category} tests: {e}")
        results["failed"] = 1
        results["output"] = str(e)
    
    return results

def generate_report(all_results: List[Dict], total_duration: float):
    """Generate a comprehensive test report."""
    print_header("TEST REPORT SUMMARY")
    
    total_tests = sum(r["total_tests"] for r in all_results)
    total_passed = sum(r["passed"] for r in all_results)
    total_failed = sum(r["failed"] for r in all_results)
    total_skipped = sum(r["skipped"] for r in all_results)
    
    print(f"\n{Colors.BOLD}Overall Results:{Colors.END}")
    print(f"  Total Tests: {total_tests}")
    print(f"  Passed: {Colors.GREEN}{total_passed}{Colors.END}")
    print(f"  Failed: {Colors.RED}{total_failed}{Colors.END}")
    print(f"  Skipped: {Colors.YELLOW}{total_skipped}{Colors.END}")
    print(f"  Total Duration: {total_duration:.1f}s")
    print(f"  Success Rate: {(total_passed/total_tests*100) if total_tests > 0 else 0:.1f}%")
    
    print(f"\n{Colors.BOLD}Category Breakdown:{Colors.END}")
    for result in all_results:
        category = result["category"]
        passed = result["passed"]
        total = result["total_tests"]
        duration = result["duration"]
        
        if result["failed"] == 0:
            status = f"{Colors.GREEN}PASS{Colors.END}"
        else:
            status = f"{Colors.RED}FAIL{Colors.END}"
        
        print(f"  {category.title():12} {status} {passed:2}/{total:2} tests ({duration:5.1f}s)")
    
    # Failed tests details
    failed_tests = []
    for result in all_results:
        if result["failed_tests"]:
            failed_tests.extend([(result["category"], test) for test in result["failed_tests"]])
    
    if failed_tests:
        print(f"\n{Colors.BOLD}Failed Tests:{Colors.END}")
        for category, test_name in failed_tests:
            print(f"  {Colors.RED}•{Colors.END} {category}/{test_name}")
    
    # Performance insights
    print(f"\n{Colors.BOLD}Performance Insights:{Colors.END}")
    avg_time_per_test = total_duration / total_tests if total_tests > 0 else 0
    print(f"  Average time per test: {avg_time_per_test:.2f}s")
    
    slowest_category = max(all_results, key=lambda x: x["duration"])
    print(f"  Slowest category: {slowest_category['category']} ({slowest_category['duration']:.1f}s)")
    
    # Exit code
    exit_code = 0 if total_failed == 0 else 1
    
    if exit_code == 0:
        print(f"\n{Colors.BOLD}{Colors.GREEN}🎉 ALL TESTS PASSED!{Colors.END}")
        print(f"{Colors.GREEN}RAG System API is working correctly.{Colors.END}")
    else:
        print(f"\n{Colors.BOLD}{Colors.RED}❌ SOME TESTS FAILED{Colors.END}")
        print(f"{Colors.RED}Please check the failed tests above.{Colors.END}")
    
    return exit_code

def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="Run RAG system API tests")
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help="Verbose output with detailed test information")
    parser.add_argument("--fast", action="store_true",
                       help="Stop on first failure for faster feedback")
    parser.add_argument("--category", choices=list(TEST_CATEGORIES.keys()),
                       default="all", help="Run specific test category")
    parser.add_argument("--skip-prereq", action="store_true",
                       help="Skip prerequisite checks")
    parser.add_argument("--output", choices=["summary", "full"],
                       default="summary", help="Output detail level")
    
    args = parser.parse_args()
    
    print_header("RAG SYSTEM API TEST RUNNER")
    print(f"{Colors.BOLD}Backend URL:{Colors.END} {BACKEND_URL}")
    print(f"{Colors.BOLD}Test Category:{Colors.END} {args.category}")
    print(f"{Colors.BOLD}Verbose Mode:{Colors.END} {args.verbose}")
    
    # Check prerequisites
    if not args.skip_prereq:
        if not check_prerequisites():
            print_error("Prerequisites not met. Fix issues above and try again.")
            sys.exit(1)
    
    # Run tests
    total_start_time = time.time()
    all_results = []
    
    if args.category == "all":
        categories_to_run = ["health", "comprehensive_sync", "sync", "embedding", "query", "rag", "multitenancy", "analytics"]
    else:
        categories_to_run = [args.category]
    
    for category in categories_to_run:
        results = run_test_category(category, args.verbose, args.fast)
        all_results.append(results)
        
        # Stop on first failure if --fast
        if args.fast and results["failed"] > 0:
            print_warning("Stopping on first failure (--fast mode)")
            break
    
    total_duration = time.time() - total_start_time
    
    # Generate report
    exit_code = generate_report(all_results, total_duration)
    
    # Save detailed results if requested
    if args.output == "full":
        report_file = "test_results.json"
        with open(report_file, 'w') as f:
            json.dump({
                "timestamp": time.time(),
                "total_duration": total_duration,
                "results": all_results
            }, f, indent=2)
        print_info(f"Detailed results saved to {report_file}")
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()