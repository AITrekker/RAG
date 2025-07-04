#!/usr/bin/env python3
"""
Comprehensive Script Validation for RAG System

Validates all scripts against the current API schema to detect potential
brittleness issues before they cause problems in production.

Usage:
    python scripts/validate_all_scripts.py                    # Full validation
    python scripts/validate_all_scripts.py --save-baseline    # Save API baseline
    python scripts/validate_all_scripts.py --check-compat     # Check compatibility
    python scripts/validate_all_scripts.py --test-endpoints   # Test live endpoints
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from scripts.utils import (
        get_paths, APIValidator, APIContractTester, ScriptTester,
        ValidatedAPIClient
    )
    paths = get_paths()
    validation_available = True
except ImportError as e:
    print(f"❌ Validation utilities not available: {e}")
    print("   Install dependencies: pip install aiohttp jsonschema")
    sys.exit(1)


class ComprehensiveValidator:
    """Comprehensive validation for all RAG system scripts."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.validator = APIValidator(base_url)
        self.contract_tester = APIContractTester(base_url)
        self.script_tester = ScriptTester(base_url)
        self.client = ValidatedAPIClient(base_url)
    
    def get_script_files(self) -> List[Path]:
        """Get all Python script files to validate."""
        script_files = []
        
        # Scripts directory
        scripts_dir = paths.scripts
        for script_file in scripts_dir.glob("**/*.py"):
            # Skip __pycache__ and utility modules
            if "__pycache__" not in str(script_file) and script_file.name != "__init__.py":
                script_files.append(script_file)
        
        return sorted(script_files)
    
    def load_api_keys(self) -> Dict[str, str]:
        """Load API keys for testing."""
        api_keys = {}
        
        # Load admin key from .env
        env_file = paths.env_file
        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    if line.startswith("ADMIN_API_KEY="):
                        api_keys["admin"] = line.split("=", 1)[1].strip()
                        break
        
        # Load tenant keys from demo file
        demo_keys_file = paths.demo_keys_file
        if demo_keys_file.exists():
            try:
                with open(demo_keys_file, 'r') as f:
                    tenant_keys = json.load(f)
                
                for tenant_name, tenant_info in tenant_keys.items():
                    api_key = tenant_info.get("api_key", "")
                    if api_key and "HIDDEN" not in api_key and api_key != "N/A":
                        api_keys[tenant_name] = api_key
                
                # Also add a generic tenant key (first available)
                if tenant_keys:
                    first_tenant = list(tenant_keys.values())[0]
                    api_key = first_tenant.get("api_key", "")
                    if api_key and "HIDDEN" not in api_key and api_key != "N/A":
                        api_keys["tenant1"] = api_key
            except Exception as e:
                print(f"⚠️ Could not load tenant keys: {e}")
        
        return api_keys
    
    async def validate_api_schema(self) -> bool:
        """Validate that we can fetch and parse the API schema."""
        print("🔍 Validating API schema accessibility...")
        
        try:
            schema = await self.validator.get_openapi_schema(use_cache=False)
            
            # Basic schema validation
            required_fields = ["openapi", "info", "paths"]
            for field in required_fields:
                if field not in schema:
                    print(f"  ❌ Missing required field: {field}")
                    return False
            
            paths_count = len(schema.get("paths", {}))
            print(f"  ✅ Schema valid - {paths_count} endpoints defined")
            
            # Check for common endpoints
            paths_spec = schema.get("paths", {})
            critical_paths = [
                "/api/v1/auth/tenants",
                "/api/v1/health/liveness",
                "/api/v1/files",
                "/api/v1/query"
            ]
            
            missing_paths = [path for path in critical_paths if path not in paths_spec]
            if missing_paths:
                print(f"  ⚠️ Missing critical paths: {missing_paths}")
            else:
                print(f"  ✅ All critical paths present")
            
            return True
            
        except Exception as e:
            print(f"  ❌ Schema validation failed: {e}")
            return False
    
    async def validate_all_scripts(self) -> Dict[str, List[str]]:
        """Validate all script files against the API schema."""
        print("\n📁 Validating script files against API schema...")
        
        script_files = self.get_script_files()
        all_errors = {}
        
        for script_file in script_files:
            errors = await self.script_tester.validate_script_endpoints(script_file)
            if errors:
                all_errors[str(script_file)] = errors
            else:
                print(f"  ✅ {script_file.name} - All endpoints valid")
        
        return all_errors
    
    async def test_live_endpoints(self) -> bool:
        """Test live API endpoints with actual requests."""
        print("\n🌐 Testing live API endpoints...")
        
        api_keys = self.load_api_keys()
        
        if not api_keys:
            print("  ⚠️ No API keys available - skipping live tests")
            print("  💡 Run setup_demo_tenants.py to generate API keys")
            return True
        
        print(f"  🔑 Using {len(api_keys)} API keys: {list(api_keys.keys())}")
        
        try:
            results = await self.script_tester.test_critical_endpoints(api_keys)
            
            success_count = sum(1 for success in results.values() if success)
            total_count = len(results)
            
            print(f"  📊 Results: {success_count}/{total_count} endpoints working")
            
            failed_endpoints = [endpoint for endpoint, success in results.items() if not success]
            if failed_endpoints:
                print(f"  ❌ Failed endpoints: {failed_endpoints}")
                return False
            else:
                print(f"  ✅ All critical endpoints working")
                return True
                
        except Exception as e:
            print(f"  ❌ Live testing failed: {e}")
            return False
    
    async def check_api_compatibility(self) -> bool:
        """Check API compatibility with baseline."""
        print("\n🔄 Checking API compatibility with baseline...")
        
        try:
            baseline_info = self.contract_tester.get_baseline_info()
            if not baseline_info:
                print("  ⚠️ No baseline schema found")
                print("  💡 Run with --save-baseline to create one")
                return True
            
            print(f"  📋 Baseline: {baseline_info['created']}")
            
            changes = await self.contract_tester.check_compatibility_with_baseline()
            has_breaking_changes = self.contract_tester.print_changes_report(changes)
            
            return not has_breaking_changes
            
        except Exception as e:
            print(f"  ❌ Compatibility check failed: {e}")
            return False
    
    async def run_full_validation(self) -> bool:
        """Run complete validation suite."""
        print("🚀 RAG System Script Validation")
        print("=" * 60)
        
        success = True
        
        # 1. Validate API schema
        if not await self.validate_api_schema():
            success = False
        
        # 2. Check API compatibility
        if not await self.check_api_compatibility():
            success = False
        
        # 3. Validate script files
        script_errors = await self.validate_all_scripts()
        if script_errors:
            success = False
            print(f"\n❌ Script validation errors found:")
            for script_file, errors in script_errors.items():
                print(f"  📄 {Path(script_file).name}:")
                for error in errors:
                    print(f"    • {error}")
        
        # 4. Test live endpoints
        if not await self.test_live_endpoints():
            success = False
        
        # Summary
        print(f"\n" + "=" * 60)
        if success:
            print("🎉 All validations passed!")
            print("✅ Scripts should work correctly with current API")
            print("\n📋 Recommendations:")
            print("  • Run this validation before deploying changes")
            print("  • Update baseline after intentional API changes")
            print("  • Monitor for breaking changes in CI/CD")
        else:
            print("❌ Validation failed!")
            print("⚠️ Some scripts may not work with current API")
            print("\n🔧 Next steps:")
            print("  • Update scripts to match current API")
            print("  • Check if API changes are intentional")
            print("  • Update baseline if API changes are expected")
        
        return success
    
    async def save_baseline(self) -> None:
        """Save current API schema as baseline."""
        print("💾 Saving current API schema as baseline...")
        await self.contract_tester.save_baseline_schema()
        print("✅ Baseline saved - use --check-compat to compare future changes")


async def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Comprehensive RAG System Script Validation")
    parser.add_argument("--save-baseline", action="store_true",
                       help="Save current API schema as baseline")
    parser.add_argument("--check-compat", action="store_true", 
                       help="Check API compatibility with baseline only")
    parser.add_argument("--test-endpoints", action="store_true",
                       help="Test live endpoints only")
    parser.add_argument("--validate-scripts", action="store_true",
                       help="Validate script files only")
    parser.add_argument("--base-url", default="http://localhost:8000",
                       help="Backend URL (default: http://localhost:8000)")
    
    args = parser.parse_args()
    
    validator = ComprehensiveValidator(args.base_url)
    
    try:
        if args.save_baseline:
            await validator.save_baseline()
            
        elif args.check_compat:
            success = await validator.check_api_compatibility()
            sys.exit(0 if success else 1)
            
        elif args.test_endpoints:
            success = await validator.test_live_endpoints()
            sys.exit(0 if success else 1)
            
        elif args.validate_scripts:
            errors = await validator.validate_all_scripts()
            sys.exit(0 if not errors else 1)
            
        else:
            # Full validation
            success = await validator.run_full_validation()
            sys.exit(0 if success else 1)
            
    except KeyboardInterrupt:
        print("\n⚠️ Validation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())