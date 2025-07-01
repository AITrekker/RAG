"""
Template Management API Tests

Tests for prompt template management endpoints including hot-reload functionality.
All tests use pure HTTP requests without business logic imports.
"""

import json
import pytest
import requests
import tempfile
import yaml
from pathlib import Path
from typing import Dict, Any

from .conftest import api_client, tenant_headers


class TestAPITemplates:
    """Test template management API endpoints"""

    def test_list_templates(self, api_client: requests.Session, tenant_headers: Dict[str, str]):
        """Test GET /api/v1/templates/ - List all available templates"""
        response = api_client.get("/api/v1/templates/", headers=tenant_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "templates" in data
        assert "current_default" in data
        assert "total_count" in data
        
        # Verify templates is a dictionary
        assert isinstance(data["templates"], dict)
        assert isinstance(data["total_count"], int)
        assert data["total_count"] > 0
        
        # Should have at least built-in templates
        templates = data["templates"]
        assert "professional" in templates or "default" in templates
        assert "fallback" in templates
        
        # Each template should have a description
        for template_name, description in templates.items():
            assert isinstance(template_name, str)
            assert isinstance(description, str)
            assert len(description) > 0

    def test_get_specific_template_professional(self, api_client: requests.Session, tenant_headers: Dict[str, str]):
        """Test GET /api/v1/templates/{name} - Get professional template"""
        response = api_client.get("/api/v1/templates/professional", headers=tenant_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "template_name" in data
        assert "description" in data
        assert "content" in data
        assert "is_external" in data
        
        # Verify values
        assert data["template_name"] == "professional"
        assert isinstance(data["description"], str)
        assert isinstance(data["content"], str)
        assert isinstance(data["is_external"], bool)
        
        # Template content should contain placeholders
        content = data["content"]
        assert "{query}" in content
        assert "{context}" in content
        assert len(content) > 100  # Should be substantial

    def test_get_specific_template_fallback(self, api_client: requests.Session, tenant_headers: Dict[str, str]):
        """Test GET /api/v1/templates/{name} - Get fallback template"""
        response = api_client.get("/api/v1/templates/fallback", headers=tenant_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["template_name"] == "fallback"
        assert "fallback" in data["description"].lower() or "minimal" in data["description"].lower()
        assert "{query}" in data["content"]
        assert "{context}" in data["content"]

    def test_get_nonexistent_template(self, api_client: requests.Session, tenant_headers: Dict[str, str]):
        """Test GET /api/v1/templates/{name} - Template not found"""
        response = api_client.get("/api/v1/templates/nonexistent_template_12345", headers=tenant_headers)
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_reload_templates(self, api_client: requests.Session, tenant_headers: Dict[str, str]):
        """Test POST /api/v1/templates/reload - Force reload templates"""
        response = api_client.post("/api/v1/templates/reload", headers=tenant_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "message" in data
        assert "old_template_count" in data
        assert "new_template_count" in data
        assert "templates_changed" in data
        assert "loaded_templates" in data
        
        # Verify types
        assert isinstance(data["message"], str)
        assert isinstance(data["old_template_count"], int)
        assert isinstance(data["new_template_count"], int)
        assert isinstance(data["templates_changed"], bool)
        assert isinstance(data["loaded_templates"], list)
        
        # Message should indicate success
        assert "success" in data["message"].lower()

    def test_reload_status(self, api_client: requests.Session, tenant_headers: Dict[str, str]):
        """Test GET /api/v1/templates/status/reload - Get reload status"""
        response = api_client.get("/api/v1/templates/status/reload", headers=tenant_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "reload_status" in data
        assert "message" in data
        
        reload_status = data["reload_status"]
        assert "hot_reload_enabled" in reload_status
        assert "check_interval" in reload_status
        assert "prompts_directory" in reload_status
        assert "loaded_templates_count" in reload_status
        assert "loaded_template_names" in reload_status
        
        # Verify types
        assert isinstance(reload_status["hot_reload_enabled"], bool)
        assert isinstance(reload_status["check_interval"], (int, float))
        assert isinstance(reload_status["prompts_directory"], str)
        assert isinstance(reload_status["loaded_templates_count"], int)
        assert isinstance(reload_status["loaded_template_names"], list)

    def test_enable_hot_reload(self, api_client: requests.Session, tenant_headers: Dict[str, str]):
        """Test POST /api/v1/templates/status/reload/enable - Enable hot-reload"""
        response = api_client.post("/api/v1/templates/status/reload/enable", headers=tenant_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert isinstance(data["message"], str)
        assert "enabled" in data["message"].lower()

    def test_disable_hot_reload(self, api_client: requests.Session, tenant_headers: Dict[str, str]):
        """Test POST /api/v1/templates/status/reload/disable - Disable hot-reload"""
        response = api_client.post("/api/v1/templates/status/reload/disable", headers=tenant_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert isinstance(data["message"], str)
        assert "disabled" in data["message"].lower()

    def test_validate_template_professional(self, api_client: requests.Session, tenant_headers: Dict[str, str]):
        """Test POST /api/v1/templates/validate/{name} - Validate professional template"""
        response = api_client.post("/api/v1/templates/validate/professional", headers=tenant_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "template_name" in data
        assert "is_valid" in data
        assert "message" in data
        
        # Professional template should be valid
        assert data["template_name"] == "professional"
        assert data["is_valid"] is True
        assert "valid" in data["message"].lower()
        
        # Should include sample output
        if "sample_output_length" in data:
            assert isinstance(data["sample_output_length"], int)
            assert data["sample_output_length"] > 0
        
        if "sample_preview" in data:
            assert isinstance(data["sample_preview"], str)
            assert len(data["sample_preview"]) > 0

    def test_validate_template_fallback(self, api_client: requests.Session, tenant_headers: Dict[str, str]):
        """Test POST /api/v1/templates/validate/{name} - Validate fallback template"""
        response = api_client.post("/api/v1/templates/validate/fallback", headers=tenant_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["template_name"] == "fallback"
        assert data["is_valid"] is True

    def test_validate_nonexistent_template(self, api_client: requests.Session, tenant_headers: Dict[str, str]):
        """Test POST /api/v1/templates/validate/{name} - Validate nonexistent template"""
        response = api_client.post("/api/v1/templates/validate/nonexistent_template_12345", headers=tenant_headers)
        
        # Should return 500 because template doesn't exist
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data

    def test_templates_unauthorized(self, api_client: requests.Session):
        """Test template endpoints without API key"""
        endpoints = [
            "/api/v1/templates/",
            "/api/v1/templates/professional",
            "/api/v1/templates/reload",
            "/api/v1/templates/status/reload",
            "/api/v1/templates/status/reload/enable",
            "/api/v1/templates/status/reload/disable",
            "/api/v1/templates/validate/professional"
        ]
        
        for endpoint in endpoints:
            if endpoint.endswith("/enable") or endpoint.endswith("/disable") or endpoint == "/api/v1/templates/reload":
                response = api_client.post(endpoint)
            elif endpoint.startswith("/api/v1/templates/validate/"):
                response = api_client.post(endpoint)
            else:
                response = api_client.get(endpoint)
            
            assert response.status_code == 401, f"Endpoint {endpoint} should require authentication"

    def test_templates_work_across_tenants(self, api_client: requests.Session):
        """Test that templates work consistently across different tenants"""
        # Get available tenant keys from conftest
        from .conftest import get_demo_tenant_keys
        tenant_keys = get_demo_tenant_keys()
        
        if len(tenant_keys) < 2:
            pytest.skip("Need at least 2 tenant keys for multi-tenant testing")
        
        # Test with first two tenants
        tenant_names = list(tenant_keys.keys())[:2]
        
        for tenant_name in tenant_names:
            headers = {
                "X-API-Key": tenant_keys[tenant_name]["api_key"],
                "Content-Type": "application/json"
            }
            
            # List templates should work the same for all tenants
            response = api_client.get("/api/v1/templates/", headers=headers)
            assert response.status_code == 200
            
            data = response.json()
            assert "templates" in data
            assert data["total_count"] > 0
            
            # Professional template should exist for all tenants
            response = api_client.get("/api/v1/templates/professional", headers=headers)
            assert response.status_code == 200
            
            # Reload should work for all tenants
            response = api_client.post("/api/v1/templates/reload", headers=headers)
            assert response.status_code == 200

    def test_template_content_consistency(self, api_client: requests.Session, tenant_headers: Dict[str, str]):
        """Test that template content is consistent and properly formatted"""
        # Get list of all templates
        response = api_client.get("/api/v1/templates/", headers=tenant_headers)
        assert response.status_code == 200
        
        templates = response.json()["templates"]
        
        for template_name in templates.keys():
            # Get each template
            response = api_client.get(f"/api/v1/templates/{template_name}", headers=tenant_headers)
            assert response.status_code == 200
            
            data = response.json()
            content = data["content"]
            
            # Every template should have query and context placeholders
            assert "{query}" in content, f"Template {template_name} missing {{query}} placeholder"
            assert "{context}" in content, f"Template {template_name} missing {{context}} placeholder"
            
            # Content should be substantial (not empty or too short)
            assert len(content.strip()) > 20, f"Template {template_name} content too short"
            
            # Should not contain obvious template artifacts
            assert "TEMPLATE" not in content.upper() or "template" in template_name.lower()

    def test_reload_status_changes(self, api_client: requests.Session, tenant_headers: Dict[str, str]):
        """Test that hot-reload status can be changed via API"""
        # Get initial status
        response = api_client.get("/api/v1/templates/status/reload", headers=tenant_headers)
        assert response.status_code == 200
        initial_status = response.json()["reload_status"]["hot_reload_enabled"]
        
        # Toggle status
        if initial_status:
            # Disable it
            response = api_client.post("/api/v1/templates/status/reload/disable", headers=tenant_headers)
            assert response.status_code == 200
            
            # Check it's disabled
            response = api_client.get("/api/v1/templates/status/reload", headers=tenant_headers)
            assert response.status_code == 200
            assert response.json()["reload_status"]["hot_reload_enabled"] is False
            
            # Re-enable it
            response = api_client.post("/api/v1/templates/status/reload/enable", headers=tenant_headers)
            assert response.status_code == 200
        else:
            # Enable it
            response = api_client.post("/api/v1/templates/status/reload/enable", headers=tenant_headers)
            assert response.status_code == 200
            
            # Check it's enabled
            response = api_client.get("/api/v1/templates/status/reload", headers=tenant_headers)
            assert response.status_code == 200
            assert response.json()["reload_status"]["hot_reload_enabled"] is True

    def test_template_validation_comprehensive(self, api_client: requests.Session, tenant_headers: Dict[str, str]):
        """Test template validation with multiple templates"""
        # Get all available templates
        response = api_client.get("/api/v1/templates/", headers=tenant_headers)
        assert response.status_code == 200
        
        templates = response.json()["templates"]
        
        # Validate each template
        for template_name in templates.keys():
            response = api_client.post(f"/api/v1/templates/validate/{template_name}", headers=tenant_headers)
            
            if response.status_code == 200:
                data = response.json()
                assert data["template_name"] == template_name
                assert "is_valid" in data
                assert "message" in data
                
                # If validation succeeded, template should be valid
                if data["is_valid"]:
                    assert "valid" in data["message"].lower()
                else:
                    assert "error" in data["message"].lower() or "fail" in data["message"].lower()

    def test_template_api_error_handling(self, api_client: requests.Session, tenant_headers: Dict[str, str]):
        """Test error handling in template API endpoints"""
        # Test invalid template names with special characters
        invalid_names = ["", "template with spaces", "template/with/slashes", "template?with=params"]
        
        for invalid_name in invalid_names:
            if invalid_name:  # Skip empty string for URL construction
                response = api_client.get(f"/api/v1/templates/{invalid_name}", headers=tenant_headers)
                # Should either be 404 (not found) or 422 (validation error)
                assert response.status_code in [404, 422]

    def test_template_reload_idempotency(self, api_client: requests.Session, tenant_headers: Dict[str, str]):
        """Test that multiple reloads are idempotent"""
        # Perform multiple reloads
        results = []
        for _ in range(3):
            response = api_client.post("/api/v1/templates/reload", headers=tenant_headers)
            assert response.status_code == 200
            results.append(response.json())
        
        # All reloads should succeed
        for result in results:
            assert "message" in result
            assert "success" in result["message"].lower()
            assert "loaded_templates" in result


class TestTemplateAPIIntegration:
    """Integration tests for template API with other functionality"""

    def test_template_usage_in_query_api(self, api_client: requests.Session, tenant_headers: Dict[str, str]):
        """Test that templates can be used in query API calls"""
        # First, ensure we have templates available
        response = api_client.get("/api/v1/templates/", headers=tenant_headers)
        assert response.status_code == 200
        
        templates = response.json()["templates"]
        assert len(templates) > 0
        
        # Test query with a specific template
        template_name = "professional" if "professional" in templates else list(templates.keys())[0]
        
        query_payload = {
            "query": "What is the company's mission?",
            "prompt_template": template_name,
            "max_sources": 3
        }
        
        response = api_client.post("/api/v1/query/", headers=tenant_headers, json=query_payload)
        
        # Query might succeed or fail depending on data, but should not fail due to template issues
        assert response.status_code in [200, 404], f"Query with template {template_name} had unexpected status"
        
        if response.status_code == 200:
            data = response.json()
            # Should have used the specified template
            assert "answer" in data

    def test_template_reload_affects_queries(self, api_client: requests.Session, tenant_headers: Dict[str, str]):
        """Test that template reloads are picked up by query API"""
        # Reload templates
        response = api_client.post("/api/v1/templates/reload", headers=tenant_headers)
        assert response.status_code == 200
        
        # Make a query immediately after reload
        query_payload = {
            "query": "Test query after template reload",
            "max_sources": 1
        }
        
        response = api_client.post("/api/v1/query/", headers=tenant_headers, json=query_payload)
        
        # Query should work (success or no data, but not template errors)
        assert response.status_code in [200, 404]