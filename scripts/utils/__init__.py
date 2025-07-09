"""
Utilities for RAG project scripts.
"""

from .project_paths import get_project_root, get_paths, paths

# Core utilities that should always be available
__all__ = ['get_project_root', 'get_paths', 'paths']

# Try to import API validation utilities with fallback
try:
    from .api_validator import APIValidator, APIValidationError
    __all__.extend(['APIValidator', 'APIValidationError'])
except ImportError as e:
    # Create dummy classes for when dependencies are missing
    class APIValidator:
        def __init__(self, *args, **kwargs):
            raise ImportError(f"APIValidator requires aiohttp and jsonschema: {e}")
    
    class APIValidationError(Exception):
        pass
    
    __all__.extend(['APIValidator', 'APIValidationError'])

# Try to import other utilities
try:
    from .script_validator import ValidatedAPIClient, ScriptTester
    __all__.extend(['ValidatedAPIClient', 'ScriptTester'])
except ImportError:
    class ValidatedAPIClient:
        def __init__(self, *args, **kwargs):
            raise ImportError("ValidatedAPIClient requires aiohttp")
    
    class ScriptTester:
        def __init__(self, *args, **kwargs):
            raise ImportError("ScriptTester requires aiohttp")
    
    __all__.extend(['ValidatedAPIClient', 'ScriptTester'])

try:
    from .contract_tester import APIContractTester
    __all__.extend(['APIContractTester'])
except ImportError:
    class APIContractTester:
        def __init__(self, *args, **kwargs):
            raise ImportError("APIContractTester requires aiohttp and jsonschema")
    
    __all__.extend(['APIContractTester'])

# Simple HTTP client fallback that works with just requests
class SimpleAPIClient:
    """Simple API client using requests library as fallback"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        try:
            import requests
            self.requests = requests
        except ImportError:
            raise ImportError("SimpleAPIClient requires requests library")
    
    def get(self, endpoint: str, api_key: str):
        """Make GET request"""
        headers = {"Authorization": f"Bearer {api_key}"}
        response = self.requests.get(f"{self.base_url}{endpoint}", headers=headers)
        return response.json()
    
    def post(self, endpoint: str, api_key: str, data: dict = None):
        """Make POST request"""
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        response = self.requests.post(f"{self.base_url}{endpoint}", headers=headers, json=data or {})
        return response.json()

__all__.append('SimpleAPIClient')