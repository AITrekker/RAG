"""
Pytest configuration for API-only tests.
"""

import pytest
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Test configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")

@pytest.fixture(scope="session")
def backend_url():
    """Provide backend URL for tests."""
    return BACKEND_URL

@pytest.fixture(scope="session") 
def admin_api_key():
    """Provide admin API key for tests."""
    return ADMIN_API_KEY

@pytest.fixture(scope="session")
def tenant_keys():
    """Provide tenant API keys from demo_tenant_keys.json."""
    try:
        with open("demo_tenant_keys.json") as f:
            return json.load(f)
    except FileNotFoundError:
        pytest.skip("demo_tenant_keys.json not found - run setup script first")

@pytest.fixture
def sample_queries():
    """Provide sample queries for testing."""
    return [
        "What is the company's mission?",
        "Tell me about the financial performance",
        "What are the key products?",
        "Describe the team structure",
        "What is the technical architecture?",
        "Company policies and guidelines",
        "Marketing strategy overview",
        "Project timeline and milestones"
    ]

class TestConfig:
    """Test configuration constants."""
    MAX_RESPONSE_TIME = 5.0  # seconds
    MIN_CONFIDENCE = 0.0
    MAX_CONFIDENCE = 1.0
    DEFAULT_MAX_SOURCES = 5