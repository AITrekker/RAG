# Script Validation System

## Overview

The RAG system now includes a comprehensive script validation system that prevents brittleness from API evolution. This addresses the core issue where scripts break when APIs change without corresponding script updates.

## Components

### 1. **API Validator** (`scripts/utils/api_validator.py`)
- Validates API endpoints against OpenAPI schema
- Checks request/response formats
- Caches schema for performance
- Provides detailed error messages

```python
from scripts.utils import APIValidator

validator = APIValidator()
await validator.validate_endpoint_exists("GET", "/api/v1/auth/tenants")
await validator.validate_request_body("POST", "/api/v1/query", {"query": "test"})
```

### 2. **Contract Tester** (`scripts/utils/contract_tester.py`)
- Compares API schemas over time
- Detects breaking changes
- Saves baseline schemas
- Reports compatibility issues

```bash
# Save current API as baseline
python scripts/utils/contract_tester.py --save-baseline

# Check for breaking changes
python scripts/utils/contract_tester.py --check-compatibility
```

### 3. **Script Validator** (`scripts/utils/script_validator.py`)
- Validates API calls in scripts
- Provides robust HTTP client with validation
- Decorator for endpoint validation
- Automatic fallback for compatibility

```python
from scripts.utils import APIClient, validated_api_call

# Validated HTTP client
client = APIClient()
response = await client.get("/api/v1/auth/tenants", api_key)

# Validation decorator
@validated_api_call("GET", "/api/v1/auth/tenants")
async def get_tenants():
    pass
```

### 4. **Comprehensive Validator** (`scripts/validate_all_scripts.py`)
- Full system validation
- Tests all scripts against current API
- Live endpoint testing
- Compatibility checking

```bash
# Full validation
python scripts/validate_all_scripts.py

# Test specific aspects
python scripts/validate_all_scripts.py --test-endpoints
python scripts/validate_all_scripts.py --check-compat
```

## Key Features

### **Schema Validation**
- Validates endpoints exist in OpenAPI spec
- Checks HTTP methods are supported
- Validates request/response formats using JSON Schema
- Resolves OpenAPI `$ref` references

### **Breaking Change Detection**
- Removed endpoints/methods
- Added required parameters
- Changed response formats
- Deprecated endpoints

### **Robust Path Detection**
All scripts now use the project path detection system:
```python
from scripts.utils import get_paths
paths = get_paths()
PROJECT_ROOT = paths.root
```

### **Graceful Fallbacks**
Scripts work even without validation dependencies:
```python
try:
    from scripts.utils import APIClient
    use_validation = True
except ImportError:
    use_validation = False
```

## Usage Examples

### **In Scripts**
```python
# Enhanced test_demo_tenants.py
try:
    from scripts.utils import APIClient
    client = APIClient(validate_requests=True)
    response = await client.get("/api/v1/auth/tenants", api_key)
except ImportError:
    # Fallback to manual requests
    pass
```

### **CI/CD Integration**
```bash
# In your CI pipeline
python scripts/validate_all_scripts.py
if [ $? -ne 0 ]; then
    echo "API validation failed - scripts may be broken"
    exit 1
fi
```

### **Development Workflow**
```bash
# Before making API changes
python scripts/utils/contract_tester.py --save-baseline

# After API changes
python scripts/validate_all_scripts.py --check-compat
```

## Installation

### **Required Dependencies**
```bash
pip install -r scripts/requirements-validation.txt
```

### **Dependencies**
- `aiohttp>=3.8.0` - Async HTTP client
- `jsonschema>=4.0.0` - JSON Schema validation

## Benefits

### **Prevents Script Brittleness**
- Scripts validate API calls before execution
- Early detection of API compatibility issues
- Automatic fallback for missing endpoints

### **Development Safety**
- Catch breaking changes before deployment
- Ensure scripts work with current API
- Documentation of API evolution

### **Production Reliability**
- Validated API calls reduce runtime failures
- Better error messages for debugging
- Graceful degradation when APIs change

## Integration Status

### **Updated Scripts**
✅ `scripts/test_demo_tenants.py` - Uses validated API client
✅ `scripts/workflow/setup_demo_tenants.py` - Robust path detection
✅ `scripts/workflow/cleanup.py` - Robust path detection  
✅ `scripts/delta-sync.py` - Robust path detection
✅ `scripts/setup_environment_databases.py` - Robust path detection
✅ `scripts/test_system.py` - Robust path detection
✅ `scripts/test_query.py` - Robust path detection
✅ `scripts/test_sync.py` - Robust path detection

### **Available Tools**
✅ API endpoint validation
✅ Request/response validation
✅ Breaking change detection
✅ Schema compatibility checking
✅ Live endpoint testing
✅ Comprehensive script validation

## Next Steps

### **Immediate**
1. Install validation dependencies: `pip install -r scripts/requirements-validation.txt`
2. Save API baseline: `python scripts/utils/contract_tester.py --save-baseline`
3. Run full validation: `python scripts/validate_all_scripts.py`

### **Ongoing**
1. Add validation to remaining scripts
2. Integrate into CI/CD pipeline
3. Monitor for breaking changes
4. Update baselines after intentional API changes

### **Advanced**
1. Generate client SDKs from OpenAPI spec
2. Automatic script updates from schema changes
3. Performance monitoring for validation overhead
4. Custom validation rules for domain-specific constraints

## Troubleshooting

### **Common Issues**

**"Validation utilities not available"**
```bash
pip install aiohttp jsonschema
```

**"No baseline schema found"**
```bash
python scripts/utils/contract_tester.py --save-baseline
```

**"Backend not running"**
- Start backend: `docker-compose up -d`
- Check health: `curl http://localhost:8000/api/v1/health/liveness`

**"API keys missing"**
```bash
python scripts/workflow/setup_demo_tenants.py
```

This validation system eliminates the "API evolution without script updates" problem and makes the RAG system much more robust and maintainable.