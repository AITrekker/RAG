"""
Utilities for RAG project scripts.
"""

from .project_paths import get_project_root, get_paths, paths

# Import validation utilities (optional, may fail if dependencies missing)
try:
    from .api_validator import APIValidator, validate_api_endpoint, validate_api_request
    from .script_validator import ValidatedAPIClient, APIClient, validated_api_call, ScriptTester
    from .contract_tester import APIContractTester
    
    __all__ = [
        'get_project_root', 'get_paths', 'paths',
        'APIValidator', 'validate_api_endpoint', 'validate_api_request',
        'ValidatedAPIClient', 'APIClient', 'validated_api_call', 'ScriptTester',
        'APIContractTester'
    ]
except ImportError:
    # Validation utilities not available (missing aiohttp, jsonschema, etc.)
    __all__ = ['get_project_root', 'get_paths', 'paths']