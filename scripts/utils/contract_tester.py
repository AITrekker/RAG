#!/usr/bin/env python3
"""
API Contract Testing for RAG System

Compares API schemas over time to detect breaking changes and ensure
backward compatibility. Helps prevent script brittleness from API evolution.

Usage:
    # Save current schema as baseline
    python scripts/utils/contract_tester.py --save-baseline
    
    # Compare current API with baseline
    python scripts/utils/contract_tester.py --check-compatibility
    
    # Compare two specific schema files
    python scripts/utils/contract_tester.py --compare old_schema.json new_schema.json
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from scripts.utils import get_paths
    from scripts.utils.api_validator import APIValidator
    paths = get_paths()
except ImportError:
    paths = None


class APIContractTester:
    """Tests API contract compatibility over time."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.validator = APIValidator(base_url)
        self.schemas_dir = self._get_schemas_dir()
        
    def _get_schemas_dir(self) -> Path:
        """Get directory for storing API schemas."""
        if paths:
            schemas_dir = paths.root / "schemas"
        else:
            schemas_dir = Path(__file__).parent.parent.parent / "schemas"
        
        schemas_dir.mkdir(exist_ok=True)
        return schemas_dir
    
    async def save_current_schema(self, filename: Optional[str] = None) -> Path:
        """
        Save current API schema to file.
        
        Args:
            filename: Optional filename, defaults to timestamped name
            
        Returns:
            Path to saved schema file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"api_schema_{timestamp}.json"
        
        schema_file = self.schemas_dir / filename
        schema = await self.validator.get_openapi_schema(use_cache=False)
        
        with open(schema_file, 'w') as f:
            json.dump(schema, f, indent=2)
        
        print(f"✅ Schema saved to {schema_file}")
        return schema_file
    
    async def save_baseline_schema(self) -> Path:
        """Save current schema as baseline for comparisons."""
        return await self.save_current_schema("baseline.json")
    
    def load_schema(self, schema_file: Path) -> Dict[str, Any]:
        """Load schema from file."""
        with open(schema_file, 'r') as f:
            return json.load(f)
    
    def compare_schemas(self, old_schema: Dict[str, Any], new_schema: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Compare two API schemas and detect changes.
        
        Args:
            old_schema: Previous API schema
            new_schema: Current API schema
            
        Returns:
            Dictionary with change categories and lists of changes
        """
        changes = {
            "breaking_changes": [],
            "new_endpoints": [],
            "deprecated_endpoints": [],
            "modified_endpoints": [],
            "non_breaking_changes": []
        }
        
        old_paths = old_schema.get("paths", {})
        new_paths = new_schema.get("paths", {})
        
        # Check for removed endpoints (breaking changes)
        for path, methods in old_paths.items():
            if path not in new_paths:
                changes["breaking_changes"].append(f"Removed endpoint: {path}")
            else:
                # Check for removed methods
                new_methods = new_paths[path]
                for method in methods:
                    if method not in new_methods:
                        changes["breaking_changes"].append(f"Removed method: {method.upper()} {path}")
                    else:
                        # Check for parameter changes
                        method_changes = self._compare_endpoint_methods(
                            old_paths[path][method], 
                            new_paths[path][method],
                            f"{method.upper()} {path}"
                        )
                        changes["breaking_changes"].extend(method_changes["breaking"])
                        changes["modified_endpoints"].extend(method_changes["modified"])
                        changes["non_breaking_changes"].extend(method_changes["non_breaking"])
        
        # Check for new endpoints
        for path, methods in new_paths.items():
            if path not in old_paths:
                changes["new_endpoints"].append(f"New endpoint: {path}")
            else:
                # Check for new methods
                old_methods = old_paths[path]
                for method in methods:
                    if method not in old_methods:
                        changes["new_endpoints"].append(f"New method: {method.upper()} {path}")
        
        # Check for deprecated endpoints
        for path, methods in new_paths.items():
            for method, spec in methods.items():
                if spec.get("deprecated", False):
                    endpoint = f"{method.upper()} {path}"
                    if endpoint not in [change.split(": ", 1)[1] for change in changes["deprecated_endpoints"]]:
                        changes["deprecated_endpoints"].append(f"Deprecated: {endpoint}")
        
        return changes
    
    def _compare_endpoint_methods(self, old_spec: Dict[str, Any], new_spec: Dict[str, Any], 
                                endpoint: str) -> Dict[str, List[str]]:
        """Compare individual endpoint method specifications."""
        changes = {
            "breaking": [],
            "modified": [],
            "non_breaking": []
        }
        
        # Check required parameters
        old_params = {p["name"]: p for p in old_spec.get("parameters", []) if p.get("required", False)}
        new_params = {p["name"]: p for p in new_spec.get("parameters", []) if p.get("required", False)}
        
        # Removed required parameters = breaking change
        for param_name in old_params:
            if param_name not in new_params:
                changes["breaking"].append(f"Removed required parameter '{param_name}' from {endpoint}")
        
        # Added required parameters = breaking change  
        for param_name in new_params:
            if param_name not in old_params:
                changes["breaking"].append(f"Added required parameter '{param_name}' to {endpoint}")
        
        # Check request body changes
        old_body = old_spec.get("requestBody", {})
        new_body = new_spec.get("requestBody", {})
        
        if old_body and not new_body:
            changes["breaking"].append(f"Removed request body from {endpoint}")
        elif not old_body and new_body and new_body.get("required", False):
            changes["breaking"].append(f"Added required request body to {endpoint}")
        
        # Check response format changes
        old_responses = old_spec.get("responses", {})
        new_responses = new_spec.get("responses", {})
        
        for status_code in old_responses:
            if status_code not in new_responses:
                changes["breaking"].append(f"Removed response {status_code} from {endpoint}")
        
        # Check for description/summary changes (non-breaking)
        if old_spec.get("summary") != new_spec.get("summary"):
            changes["non_breaking"].append(f"Updated summary for {endpoint}")
        
        if old_spec.get("description") != new_spec.get("description"):
            changes["non_breaking"].append(f"Updated description for {endpoint}")
        
        return changes
    
    async def check_compatibility_with_baseline(self) -> Dict[str, List[str]]:
        """Check current API compatibility with saved baseline."""
        baseline_file = self.schemas_dir / "baseline.json"
        
        if not baseline_file.exists():
            raise FileNotFoundError(
                f"Baseline schema not found at {baseline_file}. "
                f"Run with --save-baseline first."
            )
        
        baseline_schema = self.load_schema(baseline_file)
        current_schema = await self.validator.get_openapi_schema(use_cache=False)
        
        return self.compare_schemas(baseline_schema, current_schema)
    
    def print_changes_report(self, changes: Dict[str, List[str]], title: str = "API Changes") -> bool:
        """
        Print formatted changes report.
        
        Returns:
            True if there are breaking changes, False otherwise
        """
        print(f"\n📊 {title}")
        print("=" * 50)
        
        has_breaking_changes = bool(changes["breaking_changes"])
        
        if changes["breaking_changes"]:
            print(f"\n❌ Breaking Changes ({len(changes['breaking_changes'])}):")
            for change in changes["breaking_changes"]:
                print(f"  • {change}")
        
        if changes["deprecated_endpoints"]:
            print(f"\n⚠️ Deprecated Endpoints ({len(changes['deprecated_endpoints'])}):")
            for change in changes["deprecated_endpoints"]:
                print(f"  • {change}")
        
        if changes["new_endpoints"]:
            print(f"\n✅ New Endpoints ({len(changes['new_endpoints'])}):")
            for change in changes["new_endpoints"]:
                print(f"  • {change}")
        
        if changes["modified_endpoints"]:
            print(f"\n🔄 Modified Endpoints ({len(changes['modified_endpoints'])}):")
            for change in changes["modified_endpoints"]:
                print(f"  • {change}")
        
        if changes["non_breaking_changes"]:
            print(f"\n📝 Documentation Changes ({len(changes['non_breaking_changes'])}):")
            for change in changes["non_breaking_changes"]:
                print(f"  • {change}")
        
        # Summary
        total_changes = sum(len(changes[key]) for key in changes)
        if total_changes == 0:
            print(f"\n🎉 No changes detected - API is stable!")
        else:
            print(f"\n📈 Total changes: {total_changes}")
            if has_breaking_changes:
                print(f"⚠️ ATTENTION: {len(changes['breaking_changes'])} breaking changes detected!")
                print(f"Scripts may need updates to handle these changes.")
            else:
                print(f"✅ No breaking changes - scripts should continue working.")
        
        return has_breaking_changes
    
    def get_baseline_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the baseline schema."""
        baseline_file = self.schemas_dir / "baseline.json"
        
        if not baseline_file.exists():
            return None
        
        stat = baseline_file.stat()
        return {
            "file": str(baseline_file),
            "created": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
            "size": stat.st_size
        }


async def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="API Contract Testing for RAG System")
    parser.add_argument("--save-baseline", action="store_true", 
                       help="Save current API schema as baseline")
    parser.add_argument("--check-compatibility", action="store_true",
                       help="Check current API compatibility with baseline")
    parser.add_argument("--compare", nargs=2, metavar=("OLD", "NEW"),
                       help="Compare two specific schema files")
    parser.add_argument("--save-current", metavar="FILENAME",
                       help="Save current schema to specific filename")
    parser.add_argument("--list-schemas", action="store_true",
                       help="List saved schema files")
    parser.add_argument("--base-url", default="http://localhost:8000",
                       help="Backend URL (default: http://localhost:8000)")
    
    args = parser.parse_args()
    
    tester = APIContractTester(args.base_url)
    
    try:
        if args.save_baseline:
            print("💾 Saving current API schema as baseline...")
            await tester.save_baseline_schema()
            
        elif args.check_compatibility:
            print("🔍 Checking API compatibility with baseline...")
            
            baseline_info = tester.get_baseline_info()
            if baseline_info:
                print(f"📋 Baseline: {baseline_info['file']}")
                print(f"   Created: {baseline_info['created']}")
            
            changes = await tester.check_compatibility_with_baseline()
            has_breaking_changes = tester.print_changes_report(changes, "Compatibility Check")
            
            # Exit with error code if breaking changes found
            if has_breaking_changes:
                sys.exit(1)
            
        elif args.compare:
            old_file, new_file = args.compare
            print(f"🔍 Comparing schemas: {old_file} → {new_file}")
            
            old_schema = tester.load_schema(Path(old_file))
            new_schema = tester.load_schema(Path(new_file))
            changes = tester.compare_schemas(old_schema, new_schema)
            tester.print_changes_report(changes, "Schema Comparison")
            
        elif args.save_current:
            print(f"💾 Saving current API schema to {args.save_current}...")
            await tester.save_current_schema(args.save_current)
            
        elif args.list_schemas:
            print("📁 Saved schema files:")
            schemas_dir = tester.schemas_dir
            schema_files = list(schemas_dir.glob("*.json"))
            
            if not schema_files:
                print("   No schema files found.")
            else:
                for schema_file in sorted(schema_files):
                    stat = schema_file.stat()
                    created = datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
                    size_kb = stat.st_size / 1024
                    print(f"   {schema_file.name} ({size_kb:.1f} KB, {created})")
            
        else:
            parser.print_help()
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())