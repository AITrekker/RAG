#!/usr/bin/env python3
"""
Script Validator for RAG System

Validates API calls in scripts against the current OpenAPI schema to prevent
brittleness from API evolution. Provides decorators and utilities for robust
API interactions.

Usage:
    from scripts.utils.script_validator import validated_api_call, APIClient
    
    # Using decorator
    @validated_api_call("GET", "/api/v1/auth/tenants")
    async def get_tenants(api_key: str):
        # Function will be validated before execution
        pass
    
    # Using client
    client = APIClient()
    response = await client.validated_request("GET", "/api/v1/auth/tenants", api_key="key")
"""

import asyncio
import json
import re
import sys
from typing import List, Dict, Any, Optional, Union, Callable
from pathlib import Path
from dataclasses import dataclass, field
from functools import wraps
import logging

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from scripts.utils.api_validator import APIValidator, APIValidationError
except ImportError:
    # Create dummy classes for when dependencies are missing
    class APIValidator:
        def __init__(self, *args, **kwargs):
            raise ImportError("APIValidator requires aiohttp and jsonschema dependencies")
    
    class APIValidationError(Exception):
        pass


class ValidatedAPIClient:
    """HTTP client with built-in API validation."""
    
    def __init__(self, base_url: str = "http://localhost:8000", validate_requests: bool = True,
                 validate_responses: bool = False):
        self.base_url = base_url.rstrip("/")
        self.validate_requests = validate_requests
        self.validate_responses = validate_responses
        self.validator = APIValidator(base_url) if validate_requests or validate_responses else None
        
    async def validated_request(self, method: str, path: str, api_key: str,
                              data: Optional[Dict[str, Any]] = None, 
                              timeout: int = 30) -> Dict[str, Any]:
        """
        Make an API request with validation.
        
        Args:
            method: HTTP method
            path: API path
            api_key: API key for authentication
            data: Request body data (for POST/PUT)
            timeout: Request timeout in seconds
            
        Returns:
            API response as dictionary
            
        Raises:
            APIValidationError: If validation fails
            aiohttp.ClientError: If request fails
        """
        # Validate request before making it
        if self.validate_requests and self.validator:
            try:
                await self.validator.validate_full_request(method, path, data)
            except APIValidationError as e:
                print(f"❌ Request validation failed: {e}")
                raise
        
        # Make the actual request
        url = f"{self.base_url}{path}"
        headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                if method.upper() == "GET":
                    async with session.get(url, headers=headers, timeout=timeout) as response:
                        response_data = await response.json()
                        status_code = response.status
                elif method.upper() == "POST":
                    async with session.post(url, headers=headers, json=data, timeout=timeout) as response:
                        response_data = await response.json()
                        status_code = response.status
                elif method.upper() == "PUT":
                    async with session.put(url, headers=headers, json=data, timeout=timeout) as response:
                        response_data = await response.json()
                        status_code = response.status
                elif method.upper() == "DELETE":
                    async with session.delete(url, headers=headers, timeout=timeout) as response:
                        response_data = await response.json()
                        status_code = response.status
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                # Validate response format
                if self.validate_responses and self.validator:
                    try:
                        await self.validator.validate_response_format(method, path, status_code, response_data)
                    except APIValidationError as e:
                        print(f"⚠️ Response validation failed: {e}")
                        # Don't raise for response validation failures, just warn
                
                # Check for HTTP errors
                if status_code >= 400:
                    error_msg = response_data.get("detail", f"HTTP {status_code} error")
                    raise aiohttp.ClientResponseError(
                        request_info=aiohttp.RequestInfo(
                            url=response.url,
                            method=method,
                            headers=headers
                        ),
                        history=(),
                        status=status_code,
                        message=error_msg
                    )
                
                return {
                    "status": status_code,
                    "data": response_data
                }
                
            except aiohttp.ClientError as e:
                print(f"❌ HTTP request failed: {e}")
                raise
            except json.JSONDecodeError as e:
                print(f"❌ Invalid JSON response: {e}")
                raise
    
    async def get(self, path: str, api_key: str, **kwargs) -> Dict[str, Any]:
        """Convenience method for GET requests."""
        return await self.validated_request("GET", path, api_key, **kwargs)
    
    async def post(self, path: str, api_key: str, data: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """Convenience method for POST requests."""
        return await self.validated_request("POST", path, api_key, data, **kwargs)
    
    async def put(self, path: str, api_key: str, data: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """Convenience method for PUT requests."""
        return await self.validated_request("PUT", path, api_key, data, **kwargs)
    
    async def delete(self, path: str, api_key: str, **kwargs) -> Dict[str, Any]:
        """Convenience method for DELETE requests."""
        return await self.validated_request("DELETE", path, api_key, **kwargs)


def validated_api_call(method: str, path: str, base_url: str = "http://localhost:8000"):
    """
    Decorator to validate API calls before execution.
    
    Args:
        method: HTTP method
        path: API path
        base_url: Backend URL
        
    Usage:
        @validated_api_call("GET", "/api/v1/auth/tenants")
        async def get_tenants():
            # This function will only execute if the API endpoint exists
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Validate the API endpoint exists
            validator = APIValidator(base_url)
            try:
                await validator.validate_endpoint_exists(method, path)
            except APIValidationError as e:
                print(f"❌ API validation failed for {func.__name__}: {e}")
                raise
            
            # Call the original function
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


class ScriptTester:
    """Test script API calls against current schema."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.validator = APIValidator(base_url)
        self.client = ValidatedAPIClient(base_url, validate_requests=True, validate_responses=True)
    
    async def test_critical_endpoints(self, api_keys: Dict[str, str]) -> Dict[str, bool]:
        """
        Test critical endpoints that scripts depend on.
        
        Args:
            api_keys: Dictionary mapping key names to API keys
                     e.g., {"admin": "admin_key", "tenant1": "tenant_key"}
        
        Returns:
            Dictionary mapping endpoint to success status
        """
        results = {}
        
        # Define critical endpoints used by scripts
        critical_endpoints = [
            ("GET", "/api/v1/auth/tenants", "admin"),
            ("GET", "/api/v1/auth/tenant", "tenant1"),
            ("GET", "/api/v1/files", "tenant1"),
            ("POST", "/api/v1/query", "tenant1"),
            ("POST", "/api/v1/sync/trigger", "admin"),
            ("GET", "/api/v1/health/liveness", "admin"),
        ]
        
        print("🧪 Testing critical endpoints...")
        
        for method, path, key_name in critical_endpoints:
            endpoint_name = f"{method} {path}"
            
            if key_name not in api_keys:
                print(f"  ⚠️ {endpoint_name} - Missing API key '{key_name}'")
                results[endpoint_name] = False
                continue
            
            try:
                # Validate endpoint exists
                await self.validator.validate_endpoint_exists(method, path)
                
                # Test actual request for safe endpoints
                if method == "GET" and not any(x in path for x in ["/query", "/sync"]):
                    try:
                        response = await self.client.validated_request(
                            method, path, api_keys[key_name], timeout=10
                        )
                        print(f"  ✅ {endpoint_name} - OK (status: {response['status']})")
                        results[endpoint_name] = True
                    except Exception as e:
                        print(f"  ❌ {endpoint_name} - Request failed: {e}")
                        results[endpoint_name] = False
                else:
                    # Just validate schema for potentially destructive endpoints
                    print(f"  ✅ {endpoint_name} - Schema OK")
                    results[endpoint_name] = True
                    
            except APIValidationError as e:
                print(f"  ❌ {endpoint_name} - {e}")
                results[endpoint_name] = False
        
        return results
    
    async def validate_script_endpoints(self, script_file: Path) -> list[str]:
        """
        Parse a script file and validate all API endpoints it uses.
        
        Args:
            script_file: Path to Python script file
            
        Returns:
            List of validation errors (empty if all valid)
        """
        errors = []
        
        try:
            with open(script_file, 'r') as f:
                content = f.read()
            
            # Simple regex-based endpoint extraction
            import re
            
            # Look for common API call patterns
            patterns = [
                r'["\']([A-Z]+)["\'].*?["\'](/api/v\d+/[^"\']*)["\']',  # method, path in separate strings
                r'(GET|POST|PUT|DELETE)\s+["\'](/api/v\d+/[^"\']*)["\']',  # method path
                r'["\'](/api/v\d+/[^"\']*)["\']',  # just paths
            ]
            
            endpoints_found = set()
            
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple) and len(match) == 2:
                        method, path = match
                        endpoints_found.add((method.upper(), path))
                    elif isinstance(match, str) and match.startswith('/api/'):
                        # Assume GET for path-only matches
                        endpoints_found.add(("GET", match))
            
            print(f"\n🔍 Found {len(endpoints_found)} API endpoints in {script_file.name}:")
            
            for method, path in sorted(endpoints_found):
                try:
                    await self.validator.validate_endpoint_exists(method, path)
                    print(f"  ✅ {method} {path}")
                except APIValidationError as e:
                    error_msg = f"{script_file.name}: {method} {path} - {e}"
                    errors.append(error_msg)
                    print(f"  ❌ {method} {path} - {e}")
        
        except Exception as e:
            errors.append(f"Failed to parse {script_file.name}: {e}")
        
        return errors


# Convenience function for easy importing
APIClient = ValidatedAPIClient


if __name__ == "__main__":
    # Test the script validator
    async def test_script_validator():
        print("🧪 Testing Script Validator")
        print("=" * 50)
        
        # Test API client
        client = APIClient()
        
        try:
            # Test with a simple endpoint (this might fail if backend is not running)
            print("\n📡 Testing API client...")
            try:
                response = await client.get("/api/v1/health/liveness", "dummy_key")
                print(f"  ✅ Health check response: {response}")
            except Exception as e:
                print(f"  ⚠️ Health check failed (backend may not be running): {e}")
            
            # Test decorator
            print("\n🎯 Testing validation decorator...")
            
            @validated_api_call("GET", "/api/v1/health/liveness")
            async def test_decorated_function():
                return "Function executed after validation"
            
            try:
                result = await test_decorated_function()
                print(f"  ✅ Decorated function: {result}")
            except Exception as e:
                print(f"  ❌ Decorated function failed: {e}")
            
            # Test script analysis
            print("\n📁 Testing script analysis...")
            tester = ScriptTester()
            
            # Analyze a few script files
            script_files = [
                Path(__file__).parent.parent / "test_demo_tenants.py",
                Path(__file__).parent.parent / "test_query.py",
            ]
            
            for script_file in script_files:
                if script_file.exists():
                    errors = await tester.validate_script_endpoints(script_file)
                    if not errors:
                        print(f"  ✅ {script_file.name} - All endpoints valid")
                    else:
                        print(f"  ⚠️ {script_file.name} - {len(errors)} issues found")
            
            print(f"\n🎉 Script validator test completed!")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(test_script_validator())