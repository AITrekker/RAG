"""
Simple Analytics API Tests
Basic validation tests that can run without full backend dependencies
"""

import pytest
import requests
import json
import os

# Simple test configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
TEST_API_KEY = "test_api_key"

def test_analytics_endpoints_exist():
    """Test that analytics endpoints are accessible (basic smoke test)"""
    
    # Test without API key - should get 401
    try:
        response = requests.get(f"{BACKEND_URL}/api/v1/analytics/summary", timeout=5)
        # Should get 401 unauthorized, not 404 not found
        assert response.status_code in [401, 422], f"Expected 401/422, got {response.status_code}"
    except requests.exceptions.RequestException:
        # Backend not running - skip test
        pytest.skip("Backend not accessible")

def test_analytics_api_structure():
    """Test the analytics API test file structure"""
    
    # Verify test file exists
    import pathlib
    test_file = pathlib.Path(__file__).parent / "test_analytics_api.py"
    assert test_file.exists(), "Main analytics test file should exist"
    
    # Verify it contains expected test classes
    with open(test_file) as f:
        content = f.read()
        
    expected_classes = [
        "TestAnalyticsAuthentication",
        "TestTenantSummaryEndpoint", 
        "TestQueryHistoryEndpoint",
        "TestDocumentUsageEndpoint"
    ]
    
    for class_name in expected_classes:
        assert class_name in content, f"Test class {class_name} should exist"

def test_analytics_routes_in_main_test_runner():
    """Test that analytics tests are included in main test runner"""
    
    import pathlib
    runner_file = pathlib.Path(__file__).parent.parent / "run_all_tests.py"
    assert runner_file.exists(), "Main test runner should exist"
    
    with open(runner_file) as f:
        content = f.read()
    
    # Check analytics is included
    assert "analytics" in content, "Analytics should be in test categories"
    assert "test_analytics_api.py" in content, "Analytics test file should be listed"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])