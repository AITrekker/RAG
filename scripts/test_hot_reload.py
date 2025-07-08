#!/usr/bin/env python3
"""
Hot-Reload Testing Script

This script demonstrates and tests the hot-reloading functionality for prompt templates.
It can create test templates, modify them, and verify that changes are picked up automatically.

Usage:
    python scripts/test_hot_reload.py --demo
    python scripts/test_hot_reload.py --test-api
    python scripts/test_hot_reload.py --create-test-template
"""

import argparse
import json
import requests
import sys
import time
import yaml
from pathlib import Path
from typing import Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.backend.config.rag_prompts import rag_prompts

class HotReloadTester:
    """Tests hot-reloading functionality for prompt templates"""
    
    def __init__(self):
        self.backend_url = "http://localhost:8000"
        self.config_dir = project_root / "config"
        self.prompts_dir = self.config_dir / "prompts"
        
        # Ensure prompts directory exists
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        
        # Load API key for testing
        try:
            with open(project_root / "demo_tenant_keys.json") as f:
                keys = json.load(f)
            self.api_key = keys["tenant1"]["api_key"]
        except:
            print("⚠️ Could not load API key - API testing will be limited")
            self.api_key = None
    
    def create_test_template(self):
        """Create a test template file for hot-reload testing"""
        test_template_content = {
            "test_basic": {
                "name": "Test Basic Template",
                "description": "Simple test template for hot-reload testing",
                "template": """This is a test template for hot-reload testing.

CONTEXT: {context}

QUESTION: {query}

TEST ANSWER:"""
            },
            "test_advanced": {
                "name": "Test Advanced Template",
                "description": "Advanced test template with more formatting",
                "template": """🧪 HOT-RELOAD TEST TEMPLATE

DOCUMENT CONTEXT:
{context}

USER QUESTION: {query}

INSTRUCTIONS:
- This template was loaded via hot-reload
- Current timestamp: {timestamp}
- Template version: 1.0

RESPONSE:"""
            }
        }
        
        test_file = self.prompts_dir / "test_templates.yaml"
        
        with open(test_file, 'w') as f:
            yaml.dump(test_template_content, f, default_flow_style=False)
        
        print(f"✅ Created test template file: {test_file}")
        return test_file
    
    def modify_test_template(self, version: int = 2):
        """Modify the test template to trigger hot-reload"""
        test_file = self.prompts_dir / "test_templates.yaml"
        
        if not test_file.exists():
            print("❌ Test template file doesn't exist. Create it first.")
            return False
        
        # Read current content
        with open(test_file, 'r') as f:
            content = yaml.safe_load(f)
        
        # Modify the template
        content["test_basic"]["template"] = f"""🔄 MODIFIED TEST TEMPLATE (Version {version})

CONTEXT: {{context}}

QUESTION: {{query}}

MODIFIED AT: {time.strftime('%Y-%m-%d %H:%M:%S')}

UPDATED ANSWER:"""
        
        content["test_advanced"]["description"] = f"Advanced test template (modified version {version})"
        content["test_advanced"]["template"] = content["test_advanced"]["template"].replace(
            "Template version: 1.0", 
            f"Template version: {version}.0"
        ).replace(
            "Current timestamp: {timestamp}",
            f"Modified timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # Write back
        with open(test_file, 'w') as f:
            yaml.dump(content, f, default_flow_style=False)
        
        print(f"✅ Modified test template (version {version})")
        return True
    
    def test_direct_hot_reload(self):
        """Test hot-reload functionality directly (no API)"""
        print("🧪 Testing Direct Hot-Reload Functionality")
        print("=" * 50)
        
        # 1. Create test template
        print("\n1. Creating test template...")
        test_file = self.create_test_template()
        
        # 2. Wait a moment for file system
        time.sleep(1)
        
        # 3. Force reload to pick up new file
        print("\n2. Force reloading templates...")
        rag_prompts.force_reload()
        
        # 4. Check if template is available
        print("\n3. Checking available templates...")
        templates = rag_prompts.get_available_templates()
        
        if "test_basic" in templates:
            print("✅ test_basic template found")
            print(f"   Description: {templates['test_basic']}")
        else:
            print("❌ test_basic template not found")
        
        # 5. Test template content
        print("\n4. Testing template content...")
        try:
            template_content = rag_prompts.get_prompt_template("test_basic")
            print("✅ Template content retrieved successfully")
            print(f"   Length: {len(template_content)} characters")
            
            # Test formatting
            formatted = rag_prompts.build_prompt(
                "What is hot-reload?", 
                "Hot-reload allows updating templates without restart.", 
                "test_basic"
            )
            print(f"   Formatted length: {len(formatted)} characters")
            
        except Exception as e:
            print(f"❌ Template content retrieval failed: {e}")
        
        # 6. Modify template and test hot-reload
        print("\n5. Testing automatic hot-reload...")
        print("   Modifying template file...")
        self.modify_test_template(version=2)
        
        # 7. Wait for hot-reload check interval
        print("   Waiting for hot-reload detection (3 seconds)...")
        time.sleep(3)
        
        # 8. Get template again (should trigger hot-reload check)
        print("   Retrieving template (should trigger reload check)...")
        try:
            new_template_content = rag_prompts.get_prompt_template("test_basic")
            
            if "MODIFIED TEST TEMPLATE" in new_template_content:
                print("✅ Hot-reload successful! Template was updated automatically")
            else:
                print("❌ Hot-reload failed - template content unchanged")
                
        except Exception as e:
            print(f"❌ Hot-reload test failed: {e}")
        
        # 9. Cleanup
        print("\n6. Cleanup...")
        try:
            test_file.unlink()
            print("✅ Test template file removed")
        except:
            print("⚠️ Could not remove test template file")
    
    def test_api_hot_reload(self):
        """Test hot-reload functionality via API"""
        if not self.api_key:
            print("❌ No API key available for API testing")
            return
        
        print("🌐 Testing API Hot-Reload Functionality")
        print("=" * 50)
        
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
        
        # 1. Check API status
        print("\n1. Checking API status...")
        try:
            response = requests.get(f"{self.backend_url}/api/v1/health/")
            if response.status_code == 200:
                print("✅ API is accessible")
            else:
                print(f"❌ API not accessible: {response.status_code}")
                return
        except Exception as e:
            print(f"❌ API connection failed: {e}")
            return
        
        # 2. Get current templates via API
        print("\n2. Getting current templates via API...")
        try:
            response = requests.get(f"{self.backend_url}/api/v1/templates/", headers=headers)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Found {data['total_count']} templates")
                print(f"   Current default: {data['current_default']}")
            else:
                print(f"❌ Failed to get templates: {response.status_code}")
                return
        except Exception as e:
            print(f"❌ API request failed: {e}")
            return
        
        # 3. Create test template
        print("\n3. Creating test template...")
        test_file = self.create_test_template()
        time.sleep(1)
        
        # 4. Trigger manual reload via API
        print("\n4. Triggering manual reload via API...")
        try:
            response = requests.post(f"{self.backend_url}/api/v1/templates/reload", headers=headers)
            if response.status_code == 200:
                data = response.json()
                print("✅ Manual reload successful")
                print(f"   Message: {data['message']}")
                print(f"   Template count: {data['old_template_count']} → {data['new_template_count']}")
            else:
                print(f"❌ Manual reload failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Reload API request failed: {e}")
        
        # 5. Check if new template is available
        print("\n5. Checking for new template via API...")
        try:
            response = requests.get(f"{self.backend_url}/api/v1/templates/test_basic", headers=headers)
            if response.status_code == 200:
                data = response.json()
                print("✅ Test template found via API")
                print(f"   Name: {data['template_name']}")
                print(f"   Description: {data['description']}")
                print(f"   Is external: {data['is_external']}")
            else:
                print(f"❌ Test template not found: {response.status_code}")
        except Exception as e:
            print(f"❌ Template API request failed: {e}")
        
        # 6. Test automatic hot-reload
        print("\n6. Testing automatic hot-reload...")
        self.modify_test_template(version=3)
        print("   Waiting 3 seconds for hot-reload...")
        time.sleep(3)
        
        # 7. Query template again to trigger hot-reload
        try:
            response = requests.get(f"{self.backend_url}/api/v1/templates/test_basic", headers=headers)
            if response.status_code == 200:
                data = response.json()
                if "MODIFIED TEST TEMPLATE (Version 3)" in data['content']:
                    print("✅ API Hot-reload successful!")
                else:
                    print("❌ API Hot-reload failed - content not updated")
            else:
                print(f"❌ Failed to retrieve updated template: {response.status_code}")
        except Exception as e:
            print(f"❌ Hot-reload verification failed: {e}")
        
        # 8. Check reload status
        print("\n7. Checking reload status...")
        try:
            response = requests.get(f"{self.backend_url}/api/v1/templates/status/reload", headers=headers)
            if response.status_code == 200:
                data = response.json()
                status = data['reload_status']
                print("✅ Reload status retrieved")
                print(f"   Hot-reload enabled: {status['hot_reload_enabled']}")
                print(f"   Check interval: {status['check_interval']}s")
                print(f"   Loaded templates: {status['loaded_templates_count']}")
            else:
                print(f"❌ Failed to get reload status: {response.status_code}")
        except Exception as e:
            print(f"❌ Status API request failed: {e}")
        
        # 9. Cleanup
        print("\n8. Cleanup...")
        try:
            test_file.unlink()
            print("✅ Test template file removed")
        except:
            print("⚠️ Could not remove test template file")
    
    def demo_workflow(self):
        """Demonstrate the complete hot-reload workflow"""
        print("🎬 Hot-Reload Demo Workflow")
        print("=" * 50)
        
        print("\nThis demo shows how prompt templates can be updated without restarting the backend.")
        print("You can edit YAML files in /config/prompts/ and see changes immediately!")
        
        # Run both tests
        self.test_direct_hot_reload()
        print("\n" + "="*50)
        self.test_api_hot_reload()
        
        print("\n🎉 Demo Complete!")
        print("\nTo test hot-reload manually:")
        print("1. Edit files in /config/prompts/")
        print("2. Wait 2-3 seconds")
        print("3. Make API calls - templates will auto-reload")
        print("4. Or call POST /api/v1/templates/reload for immediate reload")

def main():
    parser = argparse.ArgumentParser(description="Test hot-reload functionality")
    parser.add_argument("--demo", action="store_true", help="Run complete demo workflow")
    parser.add_argument("--test-api", action="store_true", help="Test API hot-reload only")
    parser.add_argument("--test-direct", action="store_true", help="Test direct hot-reload only")
    parser.add_argument("--create-test-template", action="store_true", help="Create test template file")
    
    args = parser.parse_args()
    
    tester = HotReloadTester()
    
    if args.demo:
        tester.demo_workflow()
    elif args.test_api:
        tester.test_api_hot_reload()
    elif args.test_direct:
        tester.test_direct_hot_reload()
    elif args.create_test_template:
        tester.create_test_template()
    else:
        print("🔄 Hot-Reload Tester")
        print("Use --help to see available commands")
        print("\nQuick commands:")
        print("  --demo                   Run complete demo")
        print("  --test-api               Test API hot-reload")
        print("  --test-direct            Test direct hot-reload")
        print("  --create-test-template   Create test template")

if __name__ == "__main__":
    main()