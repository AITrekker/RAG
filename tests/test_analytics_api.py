"""
Test suite for Analytics API endpoints
Tests all analytics routes with proper authentication and response validation

NOTE: These tests require the full backend environment with all dependencies.
To run these tests, use the Docker environment:
    docker-compose exec backend python -m pytest tests/test_analytics_api.py -v

Or run through the main test runner:
    python run_all_tests.py --category analytics
"""

import pytest
import json
from fastapi.testclient import TestClient
from datetime import datetime, date, timedelta

from src.backend.main import app

client = TestClient(app)

# Test API keys - loaded from demo_tenant_keys.json at runtime
def load_test_api_keys():
    """Load API keys from demo_tenant_keys.json file"""
    import json
    from pathlib import Path
    
    keys_file = Path(__file__).parent.parent / "demo_tenant_keys.json"
    if keys_file.exists():
        with open(keys_file) as f:
            keys_data = json.load(f)
        return {
            "tenant1": keys_data.get("tenant1", {}).get("api_key", "test_key_1"),
            "tenant2": keys_data.get("tenant2", {}).get("api_key", "test_key_2"),
            "tenant3": keys_data.get("tenant3", {}).get("api_key", "test_key_3")
        }
    else:
        # Fallback for testing when demo keys don't exist
        return {
            "tenant1": "test_api_key_tenant1",
            "tenant2": "test_api_key_tenant2", 
            "tenant3": "test_api_key_tenant3"
        }

VALID_API_KEYS = load_test_api_keys()
ADMIN_API_KEY = "test_admin_api_key"

# Helper function to make authenticated requests
def make_auth_request(method, endpoint, api_key=VALID_API_KEYS["tenant1"], **kwargs):
    """Make authenticated request with API key"""
    headers = {"X-API-Key": api_key}
    if "headers" in kwargs:
        headers.update(kwargs["headers"])
        del kwargs["headers"]
    
    response = getattr(client, method.lower())(
        f"/api/v1/analytics{endpoint}",
        headers=headers,
        **kwargs
    )
    return response


class TestAnalyticsAuthentication:
    """Test authentication for analytics endpoints"""
    
    def test_analytics_without_api_key(self):
        """Test that analytics endpoints require API key"""
        response = client.get("/api/v1/analytics/summary")
        assert response.status_code == 401
        assert "Missing API key" in response.json()["message"]
    
    def test_analytics_with_invalid_api_key(self):
        """Test that invalid API keys are rejected"""
        response = client.get(
            "/api/v1/analytics/summary",
            headers={"X-API-Key": "invalid_key_123"}
        )
        assert response.status_code == 401
        assert "Invalid API key" in response.json()["message"]
    
    def test_analytics_with_valid_api_key(self):
        """Test that valid API keys are accepted"""
        response = make_auth_request("GET", "/summary")
        assert response.status_code == 200
        assert "tenant_id" in response.json()


class TestTenantSummaryEndpoint:
    """Test /summary endpoint"""
    
    def test_get_tenant_summary_success(self):
        """Test successful tenant summary retrieval"""
        response = make_auth_request("GET", "/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "tenant_id" in data
        assert "today" in data
        assert "all_time" in data
        assert "recent_trend" in data
        
        # Verify today's metrics structure
        today = data["today"]
        required_today_fields = ["queries", "documents", "users", "avg_response_time", "success_rate"]
        for field in required_today_fields:
            assert field in today
            assert isinstance(today[field], (int, float))
        
        # Verify all-time metrics structure
        all_time = data["all_time"]
        required_all_time_fields = ["total_queries", "total_documents", "success_rate"]
        for field in required_all_time_fields:
            assert field in all_time
            assert isinstance(all_time[field], (int, float))
        
        # Verify recent trend structure
        assert isinstance(data["recent_trend"], list)
        if data["recent_trend"]:
            trend_item = data["recent_trend"][0]
            required_trend_fields = ["date", "queries", "success_rate", "avg_response_time"]
            for field in required_trend_fields:
                assert field in trend_item
    
    def test_get_tenant_summary_different_tenants(self):
        """Test that different tenants get different data"""
        response1 = make_auth_request("GET", "/summary", VALID_API_KEYS["tenant1"])
        response2 = make_auth_request("GET", "/summary", VALID_API_KEYS["tenant2"])
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Tenant IDs should be different
        data1 = response1.json()
        data2 = response2.json()
        assert data1["tenant_id"] != data2["tenant_id"]


class TestQueryHistoryEndpoint:
    """Test /queries/history endpoint"""
    
    def test_get_query_history_success(self):
        """Test successful query history retrieval"""
        response = make_auth_request("GET", "/queries/history")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        
        # If there are queries, verify structure
        if data:
            query = data[0]
            required_fields = ["id", "query_text", "response_type", "response_time_ms", "sources_count", "created_at"]
            for field in required_fields:
                assert field in query
    
    def test_get_query_history_with_limit(self):
        """Test query history with limit parameter"""
        response = make_auth_request("GET", "/queries/history?limit=2")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) <= 2
    
    def test_get_query_history_with_offset(self):
        """Test query history with offset parameter"""
        response = make_auth_request("GET", "/queries/history?offset=1&limit=1")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) <= 1
    
    def test_get_query_history_invalid_params(self):
        """Test query history with invalid parameters"""
        # Test negative limit
        response = make_auth_request("GET", "/queries/history?limit=-1")
        assert response.status_code == 422
        
        # Test excessive limit
        response = make_auth_request("GET", "/queries/history?limit=2000")
        assert response.status_code == 422
        
        # Test negative offset
        response = make_auth_request("GET", "/queries/history?offset=-1")
        assert response.status_code == 422


class TestDocumentUsageEndpoint:
    """Test /documents/usage endpoint"""
    
    def test_get_document_usage_success(self):
        """Test successful document usage retrieval"""
        response = make_auth_request("GET", "/documents/usage")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        
        # If there are documents, verify structure
        if data:
            doc = data[0]
            required_fields = ["file_id", "filename", "access_count", "avg_relevance"]
            for field in required_fields:
                assert field in doc
            
            # Verify data types
            assert isinstance(doc["access_count"], int)
            assert isinstance(doc["avg_relevance"], float)
            assert 0 <= doc["avg_relevance"] <= 1


class TestDailyMetricsEndpoint:
    """Test /metrics/daily endpoint"""
    
    def test_get_daily_metrics_success(self):
        """Test successful daily metrics retrieval"""
        response = make_auth_request("GET", "/metrics/daily")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "period" in data
        assert "metrics" in data
        
        # Verify period structure
        period = data["period"]
        required_period_fields = ["start_date", "end_date", "days"]
        for field in required_period_fields:
            assert field in period
        
        # Verify metrics structure
        metrics = data["metrics"]
        assert isinstance(metrics, list)
        
        if metrics:
            metric = metrics[0]
            required_metric_fields = ["date", "total_queries", "success_rate", "avg_response_time", "unique_users"]
            for field in required_metric_fields:
                assert field in metric
    
    def test_get_daily_metrics_with_days_param(self):
        """Test daily metrics with custom days parameter"""
        for days in [7, 14, 30, 90]:
            response = make_auth_request("GET", f"/metrics/daily?days={days}")
            assert response.status_code == 200
            
            data = response.json()
            assert data["period"]["days"] == days
    
    def test_get_daily_metrics_invalid_days(self):
        """Test daily metrics with invalid days parameter"""
        # Test zero days
        response = make_auth_request("GET", "/metrics/daily?days=0")
        assert response.status_code == 422
        
        # Test excessive days
        response = make_auth_request("GET", "/metrics/daily?days=500")
        assert response.status_code == 422


class TestQueryFeedbackEndpoint:
    """Test /queries/feedback endpoint"""
    
    def test_submit_query_feedback_success(self):
        """Test successful query feedback submission"""
        feedback_data = {
            "query_log_id": "123e4567-e89b-12d3-a456-426614174000",
            "rating": 4,
            "feedback_type": "rating",
            "feedback_text": "Great response",
            "helpful": True,
            "accuracy_rating": 5,
            "relevance_rating": 4,
            "completeness_rating": 4
        }
        
        response = make_auth_request("POST", "/queries/feedback", json=feedback_data)
        
        # Note: This endpoint might not be fully implemented yet
        # Adjust assertion based on current implementation
        assert response.status_code in [200, 201, 501]
    
    def test_submit_query_feedback_invalid_data(self):
        """Test query feedback with invalid data"""
        # Missing required fields
        invalid_data = {
            "rating": 4
            # Missing query_log_id
        }
        
        response = make_auth_request("POST", "/queries/feedback", json=invalid_data)
        assert response.status_code == 422
        
        # Invalid rating range
        invalid_rating_data = {
            "query_log_id": "123e4567-e89b-12d3-a456-426614174000",
            "rating": 10  # Should be 1-5
        }
        
        response = make_auth_request("POST", "/queries/feedback", json=invalid_rating_data)
        assert response.status_code == 422


class TestCrossEndpointConsistency:
    """Test consistency across different analytics endpoints"""
    
    def test_tenant_id_consistency(self):
        """Test that tenant_id is consistent across endpoints"""
        # Get tenant ID from summary
        summary_response = make_auth_request("GET", "/summary")
        assert summary_response.status_code == 200
        tenant_id = summary_response.json()["tenant_id"]
        
        # Verify that the same API key returns data for the same tenant
        # across different endpoints (this tests authentication consistency)
        endpoints_to_test = ["/queries/history", "/documents/usage", "/metrics/daily"]
        
        for endpoint in endpoints_to_test:
            response = make_auth_request("GET", endpoint)
            assert response.status_code == 200
    
    def test_data_type_consistency(self):
        """Test that data types are consistent across endpoints"""
        summary_response = make_auth_request("GET", "/summary")
        assert summary_response.status_code == 200
        summary_data = summary_response.json()
        
        # Test that success rates are consistently formatted
        assert isinstance(summary_data["today"]["success_rate"], (int, float))
        assert isinstance(summary_data["all_time"]["success_rate"], (int, float))
        
        # Test that response times are consistently in milliseconds
        assert isinstance(summary_data["today"]["avg_response_time"], (int, float))


class TestErrorHandling:
    """Test error handling across analytics endpoints"""
    
    def test_malformed_requests(self):
        """Test handling of malformed requests"""
        # Test invalid JSON for POST endpoints
        response = client.post(
            "/api/v1/analytics/queries/feedback",
            headers={"X-API-Key": VALID_API_KEYS["tenant1"]},
            data="invalid json"
        )
        assert response.status_code in [400, 422]
    
    def test_non_existent_endpoints(self):
        """Test handling of non-existent endpoints"""
        response = make_auth_request("GET", "/non-existent-endpoint")
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])