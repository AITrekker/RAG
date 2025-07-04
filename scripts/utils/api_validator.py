#!/usr/bin/env python3
"""
API Validator for RAG System

Validates API calls against the OpenAPI schema to prevent script brittleness
due to API evolution without script updates.

Usage:
    from scripts.utils.api_validator import APIValidator
    
    validator = APIValidator()
    await validator.validate_endpoint("GET", "/api/v1/auth/tenants")
    await validator.validate_request("POST", "/api/v1/query", {"query": "test"})
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import aiohttp
import jsonschema
from jsonschema import validate, ValidationError

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from scripts.utils import get_paths
    paths = get_paths()
except ImportError:
    paths = None


class APIValidationError(Exception):
    """Raised when API validation fails."""
    pass


class APIValidator:
    """Validates API calls against OpenAPI schema."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self._schema: Optional[Dict[str, Any]] = None
        self._schema_cache_file = self._get_schema_cache_file()
    
    def _get_schema_cache_file(self) -> Path:
        """Get path to schema cache file."""
        if paths:
            cache_dir = paths.root / ".api_cache"
        else:
            cache_dir = Path(__file__).parent.parent.parent / ".api_cache"
        
        cache_dir.mkdir(exist_ok=True)
        return cache_dir / "openapi_schema.json"
    
    async def get_openapi_schema(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        Fetch current OpenAPI schema from backend.
        
        Args:
            use_cache: If True, try to use cached schema first
            
        Returns:
            OpenAPI schema as dictionary
        """
        # Try cache first if requested
        if use_cache and self._schema:
            return self._schema
        
        if use_cache and self._schema_cache_file.exists():
            try:
                with open(self._schema_cache_file, 'r') as f:
                    self._schema = json.load(f)
                    return self._schema
            except Exception:
                # Cache file corrupted, fetch fresh
                pass
        
        # Fetch from backend
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/openapi.json") as response:
                    response.raise_for_status()
                    self._schema = await response.json()
            
            # Cache the schema
            with open(self._schema_cache_file, 'w') as f:
                json.dump(self._schema, f, indent=2)
            
            return self._schema
            
        except Exception as e:
            raise APIValidationError(f"Failed to fetch OpenAPI schema: {e}")
    
    async def validate_endpoint_exists(self, method: str, path: str) -> bool:
        """
        Validate that endpoint exists in the API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., "/api/v1/auth/tenants")
            
        Returns:
            True if endpoint exists
            
        Raises:
            APIValidationError: If endpoint doesn't exist
        """
        schema = await self.get_openapi_schema()
        method = method.lower()
        
        # Check if path exists in OpenAPI spec
        paths_spec = schema.get("paths", {})
        if path not in paths_spec:
            available_paths = list(paths_spec.keys())
            raise APIValidationError(
                f"Endpoint {path} not found in API spec. "
                f"Available paths: {available_paths[:10]}{'...' if len(available_paths) > 10 else ''}"
            )
        
        # Check if method is supported
        path_spec = paths_spec[path]
        if method not in path_spec:
            available_methods = list(path_spec.keys())
            raise APIValidationError(
                f"Method {method.upper()} not supported for {path}. "
                f"Available methods: {[m.upper() for m in available_methods]}"
            )
        
        return True
    
    async def validate_request_body(self, method: str, path: str, data: Dict[str, Any]) -> bool:
        """
        Validate request body against OpenAPI schema.
        
        Args:
            method: HTTP method
            path: API path
            data: Request body data
            
        Returns:
            True if valid
            
        Raises:
            APIValidationError: If validation fails
        """
        schema = await self.get_openapi_schema()
        method = method.lower()
        
        # Get endpoint specification
        endpoint_spec = schema["paths"][path][method]
        
        # Check if endpoint expects a request body
        if "requestBody" not in endpoint_spec:
            if data:
                raise APIValidationError(f"{method.upper()} {path} does not expect a request body")
            return True
        
        request_body_spec = endpoint_spec["requestBody"]
        
        # Get JSON schema for application/json content type
        content = request_body_spec.get("content", {})
        json_content = content.get("application/json", {})
        
        if not json_content:
            # No JSON schema defined, skip validation
            return True
        
        request_schema = json_content.get("schema", {})
        
        if not request_schema:
            return True
        
        # Resolve $ref if present
        if "$ref" in request_schema:
            request_schema = self._resolve_ref(schema, request_schema["$ref"])
        
        # Validate data against schema
        try:
            validate(instance=data, schema=request_schema)
            return True
        except ValidationError as e:
            raise APIValidationError(f"Request body validation failed for {method.upper()} {path}: {e.message}")
    
    def _resolve_ref(self, schema: Dict[str, Any], ref: str) -> Dict[str, Any]:
        """Resolve OpenAPI $ref reference."""
        # Simple reference resolution for #/components/schemas/ModelName
        if ref.startswith("#/components/schemas/"):
            model_name = ref.split("/")[-1]
            components = schema.get("components", {})
            schemas = components.get("schemas", {})
            return schemas.get(model_name, {})
        return {}
    
    async def validate_response_format(self, method: str, path: str, status_code: int, 
                                     response_data: Any) -> bool:
        """
        Validate response format against OpenAPI schema.
        
        Args:
            method: HTTP method
            path: API path  
            status_code: HTTP status code
            response_data: Response data
            
        Returns:
            True if valid
        """
        schema = await self.get_openapi_schema()
        method = method.lower()
        
        # Get endpoint specification
        endpoint_spec = schema["paths"][path][method]
        responses_spec = endpoint_spec.get("responses", {})
        
        # Check for specific status code or default
        status_str = str(status_code)
        response_spec = responses_spec.get(status_str) or responses_spec.get("default")
        
        if not response_spec:
            return True  # No response schema defined
        
        # Get JSON schema for response
        content = response_spec.get("content", {})
        json_content = content.get("application/json", {})
        response_schema = json_content.get("schema", {})
        
        if not response_schema:
            return True
        
        # Resolve $ref if present
        if "$ref" in response_schema:
            response_schema = self._resolve_ref(schema, response_schema["$ref"])
        
        # Validate response against schema
        try:
            validate(instance=response_data, schema=response_schema)
            return True
        except ValidationError as e:
            raise APIValidationError(f"Response validation failed for {method.upper()} {path}: {e.message}")
    
    async def validate_full_request(self, method: str, path: str, 
                                  data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Validate complete API request (endpoint existence + request body).
        
        Args:
            method: HTTP method
            path: API path
            data: Request body data (optional)
            
        Returns:
            True if valid
            
        Raises:
            APIValidationError: If validation fails
        """
        # Validate endpoint exists
        await self.validate_endpoint_exists(method, path)
        
        # Validate request body if provided
        if data is not None:
            await self.validate_request_body(method, path, data)
        
        return True
    
    async def get_endpoint_info(self, method: str, path: str) -> Dict[str, Any]:
        """
        Get detailed information about an endpoint.
        
        Args:
            method: HTTP method
            path: API path
            
        Returns:
            Endpoint specification from OpenAPI schema
        """
        await self.validate_endpoint_exists(method, path)
        schema = await self.get_openapi_schema()
        return schema["paths"][path][method.lower()]
    
    async def list_all_endpoints(self) -> List[Tuple[str, str]]:
        """
        List all available endpoints.
        
        Returns:
            List of (method, path) tuples
        """
        schema = await self.get_openapi_schema()
        endpoints = []
        
        for path, methods in schema.get("paths", {}).items():
            for method in methods.keys():
                if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    endpoints.append((method.upper(), path))
        
        return sorted(endpoints)
    
    async def refresh_schema_cache(self) -> None:
        """Force refresh of cached OpenAPI schema."""
        self._schema = None
        if self._schema_cache_file.exists():
            self._schema_cache_file.unlink()
        await self.get_openapi_schema(use_cache=False)


# Convenience functions for easy importing
async def validate_api_endpoint(method: str, path: str, base_url: str = "http://localhost:8000") -> bool:
    """Quick validation of API endpoint existence."""
    validator = APIValidator(base_url)
    return await validator.validate_endpoint_exists(method, path)


async def validate_api_request(method: str, path: str, data: Optional[Dict] = None,
                             base_url: str = "http://localhost:8000") -> bool:
    """Quick validation of complete API request."""
    validator = APIValidator(base_url)
    return await validator.validate_full_request(method, path, data)


if __name__ == "__main__":
    # Test the validator
    async def test_validator():
        print("🧪 Testing API Validator")
        print("=" * 50)
        
        validator = APIValidator()
        
        try:
            # Test endpoint listing
            print("\n📋 Available endpoints:")
            endpoints = await validator.list_all_endpoints()
            for method, path in endpoints[:10]:  # Show first 10
                print(f"  {method} {path}")
            if len(endpoints) > 10:
                print(f"  ... and {len(endpoints) - 10} more")
            
            # Test endpoint validation
            print(f"\n✅ Testing endpoint validation:")
            test_endpoints = [
                ("GET", "/api/v1/auth/tenants"),
                ("POST", "/api/v1/query"),
                ("GET", "/api/v1/health/liveness"),
                ("POST", "/api/v1/sync/trigger")
            ]
            
            for method, path in test_endpoints:
                try:
                    await validator.validate_endpoint_exists(method, path)
                    print(f"  ✅ {method} {path} - OK")
                except APIValidationError as e:
                    print(f"  ❌ {method} {path} - {e}")
            
            # Test invalid endpoint
            print(f"\n❌ Testing invalid endpoint:")
            try:
                await validator.validate_endpoint_exists("GET", "/api/v1/nonexistent")
                print("  ⚠️ Should have failed!")
            except APIValidationError as e:
                print(f"  ✅ Correctly caught invalid endpoint: {e}")
            
            print(f"\n🎉 API Validator test completed!")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(test_validator())