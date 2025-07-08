#!/usr/bin/env python3
"""
RAG Configuration Manager

This script helps manage and test different RAG/LLM configurations.
It allows you to:
1. View current configuration
2. Apply different preset configurations
3. Test configuration changes
4. Export/import configurations

Usage:
    python scripts/rag_config_manager.py --show-current
    python scripts/rag_config_manager.py --apply-preset high-quality
    python scripts/rag_config_manager.py --test-query "What is the company mission?"
    python scripts/rag_config_manager.py --export config_backup.json
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import requests
import time

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.backend.config.settings import get_settings
from src.backend.config.rag_prompts import rag_prompts
from src.backend.config.config_loader import config_loader

class RAGConfigManager:
    """Manages RAG configuration and testing"""
    
    def __init__(self):
        self.settings = get_settings()
        self.backend_url = "http://localhost:8000"
        
        # Load presets from /config/presets/ directory
        try:
            self.presets = self._load_preset_definitions()
        except Exception as e:
            print(f"⚠️ Could not load presets from /config/presets/: {e}")
            print("Using built-in presets")
            self.presets = self._get_builtin_presets()
    
    def _load_preset_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Load preset definitions from config directory"""
        available_presets = config_loader.get_available_presets()
        presets = {}
        
        for preset_name, description in available_presets.items():
            # Load the actual config values for display
            try:
                config = config_loader.load_preset_config(preset_name)
                presets[preset_name] = {
                    "description": description,
                    "config": config
                }
            except Exception as e:
                print(f"⚠️ Could not load preset {preset_name}: {e}")
        
        return presets
    
    def _get_builtin_presets(self) -> Dict[str, Dict[str, Any]]:
        """Fallback built-in presets"""
        return {
            "high-quality": {
                "description": "Best quality responses (slower)",
                "config": {
                    "RAG_LLM_MODEL": "gpt2-large",
                    "RAG_TEMPERATURE": "0.2",
                    "RAG_MAX_NEW_TOKENS": "250",
                    "RAG_MAX_SOURCES": "7",
                    "RAG_TOP_P": "0.8",
                    "RAG_TOP_K": "30",
                    "RAG_REPETITION_PENALTY": "1.4"
                }
            },
            "fast": {
                "description": "Fast responses (lower quality)",
                "config": {
                    "RAG_LLM_MODEL": "distilgpt2",
                    "RAG_TEMPERATURE": "0.4",
                    "RAG_MAX_NEW_TOKENS": "150",
                    "RAG_MAX_SOURCES": "3",
                    "RAG_TOP_P": "0.9",
                    "RAG_TOP_K": "50"
                }
            },
            "creative": {
                "description": "More creative responses",
                "config": {
                    "RAG_LLM_MODEL": "gpt2-medium",
                    "RAG_TEMPERATURE": "0.6",
                    "RAG_MAX_NEW_TOKENS": "200",
                    "RAG_TOP_P": "0.9",
                    "RAG_TOP_K": "60",
                    "RAG_REPETITION_PENALTY": "1.1"
                }
            },
            "focused": {
                "description": "Very focused/factual responses",
                "config": {
                    "RAG_LLM_MODEL": "gpt2-medium",
                    "RAG_TEMPERATURE": "0.1",
                    "RAG_MAX_NEW_TOKENS": "180",
                    "RAG_TOP_P": "0.7",
                    "RAG_TOP_K": "20",
                    "RAG_REPETITION_PENALTY": "1.5"
                }
            },
            "balanced": {
                "description": "Balanced quality and speed (recommended)",
                "config": {
                    "RAG_LLM_MODEL": "gpt2-medium",
                    "RAG_TEMPERATURE": "0.3",
                    "RAG_MAX_NEW_TOKENS": "200",
                    "RAG_MAX_SOURCES": "5",
                    "RAG_TOP_P": "0.85",
                    "RAG_TOP_K": "40",
                    "RAG_REPETITION_PENALTY": "1.3"
                }
            }
        }
    
    def show_current_config(self):
        """Display current RAG configuration"""
        print("🎛️  Current RAG Configuration:")
        print("=" * 50)
        
        llm_config = self.settings.get_rag_llm_config()
        retrieval_config = self.settings.get_rag_retrieval_config()
        response_config = self.settings.get_rag_response_config()
        
        print(f"📋 LLM Settings:")
        print(f"   Model: {llm_config['model_name']}")
        print(f"   Temperature: {llm_config['temperature']}")
        print(f"   Max Tokens: {llm_config['max_new_tokens']}")
        print(f"   Top-p: {llm_config['top_p']}")
        print(f"   Top-k: {llm_config['top_k']}")
        print(f"   Repetition Penalty: {llm_config['repetition_penalty']}")
        
        print(f"\n🔍 Retrieval Settings:")
        print(f"   Max Sources: {retrieval_config['max_sources']}")
        print(f"   Confidence Threshold: {retrieval_config['confidence_threshold']}")
        print(f"   Max Context Length: {retrieval_config['max_context_length']}")
        
        print(f"\n📝 Response Settings:")
        print(f"   Max Sentences: {response_config['max_sentences']}")
        print(f"   Remove Artifacts: {response_config['remove_prompt_artifacts']}")
        print(f"   Ensure Punctuation: {response_config['ensure_punctuation']}")
        
        print(f"\n🎯 Available Prompt Templates:")
        for name, desc in rag_prompts.get_available_templates().items():
            marker = "👈 CURRENT" if name == rag_prompts.get_current_template() else ""
            external_marker = "🔄" if name in rag_prompts._loaded_templates else "📝"
            print(f"   {external_marker} {name}: {desc} {marker}")
        
        print(f"\n🔄 Hot-Reload Status:")
        reload_status = rag_prompts.get_reload_status()
        print(f"   Enabled: {reload_status['hot_reload_enabled']}")
        print(f"   Check Interval: {reload_status['check_interval']}s")
        print(f"   External Templates: {reload_status['loaded_templates_count']}")
        if reload_status['loaded_template_names']:
            print(f"   External Names: {', '.join(reload_status['loaded_template_names'])}")
    
    def list_presets(self):
        """List available configuration presets"""
        print("🎯 Available Configuration Presets:")
        print("=" * 40)
        
        for name, preset in self.presets.items():
            print(f"\n📦 {name.upper()}")
            print(f"   Description: {preset['description']}")
            print(f"   Key settings:")
            config = preset['config']
            print(f"     Model: {config.get('RAG_LLM_MODEL', 'default')}")
            print(f"     Temperature: {config.get('RAG_TEMPERATURE', 'default')}")
            print(f"     Max Tokens: {config.get('RAG_MAX_NEW_TOKENS', 'default')}")
            print(f"     Max Sources: {config.get('RAG_MAX_SOURCES', 'default')}")
    
    def apply_preset(self, preset_name: str):
        """Apply a configuration preset"""
        if preset_name not in self.presets:
            print(f"❌ Unknown preset: {preset_name}")
            print(f"Available presets: {', '.join(self.presets.keys())}")
            return False
        
        print(f"🎛️  Applying preset: {preset_name.upper()}")
        
        # Use config_loader to apply the preset
        success = config_loader.apply_preset_to_env(preset_name, str(project_root / ".env"))
        
        if success:
            preset = self.presets[preset_name]
            print(f"Description: {preset['description']}")
            print(f"\n✅ Preset '{preset_name}' applied to .env file")
            print("🔄 Restart the backend to apply changes: docker-compose restart backend")
            
            # Show what was applied
            config = preset.get('config', {})
            print(f"\n📝 Key settings applied:")
            for key, value in list(config.items())[:5]:  # Show first 5 settings
                print(f"   {key}={value}")
            if len(config) > 5:
                print(f"   ... and {len(config) - 5} more settings")
                
        else:
            print(f"❌ Failed to apply preset '{preset_name}'")
        
        return success
    
    def test_query(self, query: str, tenant_key: Optional[str] = None):
        """Test a query with current configuration"""
        if not tenant_key:
            # Try to load from demo keys
            try:
                with open(project_root / "demo_tenant_keys.json") as f:
                    keys = json.load(f)
                tenant_key = keys["tenant1"]["api_key"]
            except:
                print("❌ No tenant API key provided and couldn't load demo keys")
                return
        
        print(f"🧪 Testing query with current configuration:")
        print(f"Query: '{query}'")
        print(f"Backend: {self.backend_url}")
        
        headers = {
            "X-API-Key": tenant_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": query,
            "max_sources": 5
        }
        
        start_time = time.time()
        
        try:
            response = requests.post(
                f"{self.backend_url}/api/v1/query/",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                print(f"\n✅ Success! ({response_time:.2f}s)")
                print(f"📝 Answer ({len(data['answer'])} chars):")
                print(f"   {data['answer']}")
                print(f"\n📚 Sources ({len(data['sources'])}):")
                for i, source in enumerate(data['sources'], 1):
                    print(f"   {i}. {source['filename']} (score: {source['score']:.3f})")
                print(f"\n📊 Metadata:")
                print(f"   Confidence: {data['confidence']:.3f}")
                print(f"   Processing Time: {data['processing_time']:.3f}s")
                print(f"   Model: {data['model_used']}")
                
            else:
                print(f"❌ Query failed: {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")
    
    def export_config(self, filename: str):
        """Export current configuration to file"""
        config = {
            "llm_config": self.settings.get_rag_llm_config(),
            "retrieval_config": self.settings.get_rag_retrieval_config(),
            "response_config": self.settings.get_rag_response_config(),
            "current_template": rag_prompts.get_current_template(),
            "export_timestamp": time.time()
        }
        
        with open(filename, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"✅ Configuration exported to {filename}")
    
    def reload_templates(self):
        """Manually reload prompt templates"""
        print("🔄 Reloading prompt templates...")
        try:
            rag_prompts.force_reload()
            reload_status = rag_prompts.get_reload_status()
            print(f"✅ Reloaded {reload_status['loaded_templates_count']} external templates")
            if reload_status['loaded_template_names']:
                print(f"   Templates: {', '.join(reload_status['loaded_template_names'])}")
        except Exception as e:
            print(f"❌ Failed to reload templates: {e}")
    
    def list_templates(self):
        """List all available prompt templates"""
        print("📝 Available Prompt Templates:")
        print("=" * 40)
        
        templates = rag_prompts.get_available_templates()
        current = rag_prompts.get_current_template()
        
        for name, desc in templates.items():
            markers = []
            if name == current:
                markers.append("👈 CURRENT")
            if name in rag_prompts._loaded_templates:
                markers.append("🔄 EXTERNAL")
            else:
                markers.append("📝 BUILT-IN")
            
            marker_str = " ".join(markers)
            print(f"\n📋 {name.upper()}")
            print(f"   Description: {desc}")
            print(f"   Status: {marker_str}")
    
    def test_template(self, template_name: str):
        """Test a specific prompt template"""
        print(f"🧪 Testing template: {template_name}")
        
        try:
            # Get template
            template_content = rag_prompts.get_prompt_template(template_name)
            print(f"✅ Template found ({len(template_content)} characters)")
            
            # Test formatting
            sample_query = "What is the company's mission?"
            sample_context = "[Source 1 - company_overview.txt]: Our company mission is to provide excellent service."
            
            formatted = rag_prompts.build_prompt(sample_query, sample_context, template_name)
            print(f"✅ Template formatting successful ({len(formatted)} characters)")
            
            print(f"\n📋 Sample Output Preview:")
            preview = formatted[:300] + "..." if len(formatted) > 300 else formatted
            print(f"{preview}")
            
        except Exception as e:
            print(f"❌ Template test failed: {e}")
    
    def benchmark_presets(self, query: str = "What is the company's mission?"):
        """Benchmark all presets with a test query"""
        print(f"🏁 Benchmarking all presets with query: '{query}'")
        print("=" * 60)
        
        results = {}
        
        for preset_name in self.presets.keys():
            print(f"\n🧪 Testing preset: {preset_name.upper()}")
            
            # Apply preset
            self.apply_preset(preset_name)
            
            # Restart would be needed here in real usage
            print("   ⚠️  Note: Backend restart needed for changes to take effect")
            
            # For demo, just show what would happen
            preset = self.presets[preset_name]
            config = preset['config']
            
            estimated_quality = "High" if "gpt2-large" in config.get('RAG_LLM_MODEL', '') else \
                               "Medium" if "gpt2-medium" in config.get('RAG_LLM_MODEL', '') else "Low"
            
            estimated_speed = "Fast" if "distilgpt2" in config.get('RAG_LLM_MODEL', '') else \
                             "Medium" if "gpt2-medium" in config.get('RAG_LLM_MODEL', '') else "Slow"
            
            results[preset_name] = {
                "quality": estimated_quality,
                "speed": estimated_speed,
                "description": preset['description']
            }
            
            print(f"   Estimated Quality: {estimated_quality}")
            print(f"   Estimated Speed: {estimated_speed}")
        
        print(f"\n📊 Benchmark Summary:")
        print("-" * 40)
        for name, result in results.items():
            print(f"{name.ljust(12)}: {result['quality'].ljust(8)} quality, {result['speed'].ljust(8)} speed")

def main():
    parser = argparse.ArgumentParser(description="RAG Configuration Manager")
    parser.add_argument("--show-current", action="store_true", help="Show current configuration")
    parser.add_argument("--list-presets", action="store_true", help="List available presets")
    parser.add_argument("--apply-preset", help="Apply a configuration preset")
    parser.add_argument("--test-query", help="Test a query with current config")
    parser.add_argument("--tenant-key", help="API key for testing (optional)")
    parser.add_argument("--export", help="Export current config to file")
    parser.add_argument("--benchmark", action="store_true", help="Benchmark all presets")
    parser.add_argument("--reload-templates", action="store_true", help="Reload prompt templates")
    parser.add_argument("--list-templates", action="store_true", help="List all prompt templates")
    parser.add_argument("--test-template", help="Test a specific prompt template")
    
    args = parser.parse_args()
    
    manager = RAGConfigManager()
    
    if args.show_current:
        manager.show_current_config()
    elif args.list_presets:
        manager.list_presets()
    elif args.apply_preset:
        manager.apply_preset(args.apply_preset)
    elif args.test_query:
        manager.test_query(args.test_query, args.tenant_key)
    elif args.export:
        manager.export_config(args.export)
    elif args.benchmark:
        manager.benchmark_presets()
    elif args.reload_templates:
        manager.reload_templates()
    elif args.list_templates:
        manager.list_templates()
    elif args.test_template:
        manager.test_template(args.test_template)
    else:
        print("🎛️  RAG Configuration Manager")
        print("Use --help to see available commands")
        print("\nQuick commands:")
        print("  --show-current          Show current settings")
        print("  --list-presets          List available presets")
        print("  --apply-preset production Apply recommended preset")
        print("  --test-query 'question' Test with a query")
        print("  --reload-templates      Reload prompt templates")
        print("  --list-templates        List all templates")
        print("  --test-template NAME    Test specific template")

if __name__ == "__main__":
    main()