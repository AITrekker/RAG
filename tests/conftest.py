"""
Pytest configuration and fixtures for the entire test suite.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
import uuid
import hashlib

from src.backend.main import app
from src.backend.config.settings import get_settings
from src.backend.db.session import get_db
from src.backend.models.tenant import Tenant, TenantApiKey


@pytest.fixture(scope="session")
def db_session():
    """Provides a database session for the test suite."""
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()


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
    Provides a non-authenticated TestClient instance.
    """
    with TestClient(test_app) as test_client:
        yield test_client

@pytest.fixture(scope="module")
def authenticated_client(test_app):
    """
    Provides an authenticated TestClient instance.
    - Creates a real tenant and API key in the database.
    - Adds the API key to the client's headers.
    - Cleans up the tenant and key after tests.
    """
    db = next(get_db())
    
    tenant_id_str = f"test-tenant-{uuid.uuid4()}"
    api_key_str = f"test-token-{uuid.uuid4()}"
    key_hash = hashlib.sha256(api_key_str.encode('utf-8')).hexdigest()

    # Create tenant and API key in a single transaction
    tenant = Tenant(tenant_id=tenant_id_str, name=tenant_id_str, status="active")
    db.add(tenant)
    db.flush()  # Ensure tenant gets an ID

    api_key = TenantApiKey(
        tenant_id=tenant.id,
        key_name="Test Key",
        key_hash=key_hash,
        key_prefix="test",
        is_active=True,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
    )
    db.add(api_key)
    db.commit()

    with TestClient(test_app) as test_client:
        test_client.headers['Authorization'] = f'Bearer {api_key_str}'
        yield test_client
    
    # Cleanup
    db.delete(api_key)
    db.delete(tenant)
    db.commit()
    db.close()

@pytest.fixture
def auth_headers(authenticated_client):
    """Provides authentication headers for manual requests if needed."""
    return authenticated_client.headers 