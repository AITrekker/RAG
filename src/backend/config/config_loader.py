"""
Configuration Loader

Loads configuration from /config directory (project root)
Bridges between user-facing configs and backend settings
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"

@dataclass
class PromptTemplate:
    """Prompt template data structure"""
    name: str
    description: str
    template: str

class ConfigLoader:
    """Loads configuration from /config directory"""
    
    def __init__(self):
        self.config_dir = CONFIG_DIR
        self._prompt_cache = {}
    
    def load_preset_config(self, preset_name: str) -> Dict[str, Any]:
        """Load configuration preset from /config/presets/"""
        preset_file = self.config_dir / "presets" / f"{preset_name}.env"
        
        if not preset_file.exists():
            available = [f.stem for f in (self.config_dir / "presets").glob("*.env")]
            raise FileNotFoundError(f"Preset '{preset_name}' not found. Available: {available}")
        
        config = {}
        with open(preset_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = self._parse_env_value(value.strip())
        
        return config
    
    def load_prompt_templates(self, category: str = "business") -> Dict[str, PromptTemplate]:
        """Load prompt templates from /config/prompts/"""
        if category in self._prompt_cache:
            return self._prompt_cache[category]
        
        prompt_file = self.config_dir / "prompts" / f"{category}.yaml"
        
        if not prompt_file.exists():
            available = [f.stem for f in (self.config_dir / "prompts").glob("*.yaml")]
            raise FileNotFoundError(f"Prompt category '{category}' not found. Available: {available}")
        
        with open(prompt_file, 'r') as f:
            data = yaml.safe_load(f)
        
        templates = {}
        for template_id, template_data in data.items():
            templates[template_id] = PromptTemplate(
                name=template_data['name'],
                description=template_data['description'],
                template=template_data['template']
            )
        
        self._prompt_cache[category] = templates
        return templates
    
    def get_all_prompt_templates(self) -> Dict[str, Dict[str, PromptTemplate]]:
        """Get all prompt templates organized by category"""
        templates = {}
        
        prompt_dir = self.config_dir / "prompts"
        if not prompt_dir.exists():
            return templates
        
        for prompt_file in prompt_dir.glob("*.yaml"):
            category = prompt_file.stem
            templates[category] = self.load_prompt_templates(category)
        
        return templates
    
    def get_available_presets(self) -> Dict[str, str]:
        """Get list of available configuration presets"""
        presets = {}
        preset_dir = self.config_dir / "presets"
        
        if not preset_dir.exists():
            return presets
        
        for preset_file in preset_dir.glob("*.env"):
            preset_name = preset_file.stem
            
            # Read description from first comment line
            description = f"Configuration preset: {preset_name}"
            try:
                with open(preset_file, 'r') as f:
                    first_line = f.readline().strip()
                    if first_line.startswith('#'):
                        description = first_line[1:].strip()
            except:
                pass
            
            presets[preset_name] = description
        
        return presets
    
    def apply_preset_to_env(self, preset_name: str, env_file: str = ".env") -> bool:
        """Apply a preset configuration to an environment file"""
        try:
            config = self.load_preset_config(preset_name)
            env_path = Path(env_file)
            
            # Read existing .env file
            env_lines = []
            if env_path.exists():
                with open(env_path, 'r') as f:
                    env_lines = f.readlines()
            
            # Update with preset values
            updated_keys = set()
            
            for i, line in enumerate(env_lines):
                for key, value in config.items():
                    if line.startswith(f"{key}="):
                        env_lines[i] = f"{key}={value}\n"
                        updated_keys.add(key)
                        break
            
            # Add new keys that weren't found
            for key, value in config.items():
                if key not in updated_keys:
                    env_lines.append(f"{key}={value}\n")
            
            # Write back to file
            with open(env_path, 'w') as f:
                f.writelines(env_lines)
            
            return True
            
        except Exception as e:
            print(f"Error applying preset: {e}")
            return False
    
    def _parse_env_value(self, value: str) -> Any:
        """Parse environment variable value to appropriate type"""
        # Remove quotes
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        
        # Parse boolean
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # Parse integer
        try:
            if '.' not in value:
                return int(value)
        except ValueError:
            pass
        
        # Parse float
        try:
            return float(value)
        except ValueError:
            pass
        
        # Return as string
        return value

# Global config loader instance
config_loader = ConfigLoader()

# Export main functions for easy import
def load_preset(preset_name: str) -> Dict[str, Any]:
    """Load a configuration preset"""
    return config_loader.load_preset_config(preset_name)

def load_prompts(category: str = "business") -> Dict[str, PromptTemplate]:
    """Load prompt templates for a category"""
    return config_loader.load_prompt_templates(category)

def get_available_presets() -> Dict[str, str]:
    """Get available configuration presets"""
    return config_loader.get_available_presets()

def apply_preset(preset_name: str, env_file: str = ".env") -> bool:
    """Apply preset to environment file"""
    return config_loader.apply_preset_to_env(preset_name, env_file)

__all__ = [
    "ConfigLoader",
    "PromptTemplate", 
    "config_loader",
    "load_preset",
    "load_prompts",
    "get_available_presets",
    "apply_preset"
]