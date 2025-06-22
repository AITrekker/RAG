"""
Pytest configuration and fixtures for the entire test suite.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

from src.backend.main import app
from src.backend.config.settings import get_settings

@pytest.fixture(scope="module")
def test_app():
    """
    Creates a FastAPI app instance for testing, ensuring that 'testserver'
    is in the trusted hosts list to bypass TrustedHostMiddleware during tests.
    """
    # Get the application settings
    settings = get_settings()
    
    # Add 'testserver' to the list of allowed hosts for the test environment
    if "testserver" not in settings.allowed_hosts:
        settings.allowed_hosts.append("testserver")
    
    # Use a patch to ensure the modified settings are used by the app
    with patch('src.backend.main.settings', settings):
        yield app

@pytest.fixture(scope="module")
def client(test_app):
    """
    Provides a TestClient instance for making API requests in tests.
    This client is configured to work with the test_app fixture.
    """
    with TestClient(test_app) as test_client:
        yield test_client

@pytest.fixture(scope="module")
def authenticated_client(test_app):
    """
    Provides a TestClient that is pre-authenticated for API requests.

    This fixture patches the API key validation to bypass the database check
    and returns a client that can be used for testing protected endpoints.
    """
    with patch('src.backend.middleware.auth.APIKeyValidator.validate_api_key') as mock_validate:
        # Configure the mock to return a valid TenantApiKey object
        mock_api_key = MagicMock()
        mock_api_key.tenant_id = "test-tenant"
        mock_api_key.scopes = ["*"] # Full access for testing
        mock_api_key.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_validate.return_value = mock_api_key
        
        with TestClient(test_app) as test_client:
            # Set default headers for authenticated requests
            test_client.headers['Authorization'] = 'Bearer test-token'
            yield test_client 