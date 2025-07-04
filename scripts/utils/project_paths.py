#!/usr/bin/env python3
"""
Project Path Detection Utility

Provides robust project root detection and consistent path resolution
for all scripts in the RAG system.
"""

from pathlib import Path
from typing import Optional
import os
import sys


class ProjectPaths:
    """Centralized project path management."""
    
    _instance = None
    _project_root = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._project_root is None:
            self._project_root = self._find_project_root()
    
    def _find_project_root(self) -> Path:
        """
        Find project root by looking for marker files.
        Searches upward from current file location.
        """
        # Start from the current file's directory
        current = Path(__file__).resolve().parent
        
        # Project markers (files that indicate project root)
        markers = [
            "docker-compose.yml",
            "Makefile", 
            "CLAUDE.md",
            ".git",
            "requirements.txt"
        ]
        
        # Search upward through directory tree
        while current != current.parent:  # Stop at filesystem root
            # Check if any marker files exist in current directory
            for marker in markers:
                if (current / marker).exists():
                    return current
            current = current.parent
        
        # Fallback: assume we're in a subdirectory of the project
        # This handles cases where the script is deep in the project
        fallback = Path(__file__).resolve().parent.parent.parent
        if (fallback / "docker-compose.yml").exists():
            return fallback
            
        raise RuntimeError(
            f"Could not find project root. Searched from {Path(__file__).resolve()} "
            f"looking for markers: {markers}"
        )
    
    @property
    def root(self) -> Path:
        """Project root directory."""
        return self._project_root
    
    @property
    def scripts(self) -> Path:
        """Scripts directory."""
        return self._project_root / "scripts"
    
    @property
    def src(self) -> Path:
        """Source code directory."""
        return self._project_root / "src"
    
    @property
    def backend(self) -> Path:
        """Backend source directory."""
        return self.src / "backend"
    
    @property
    def frontend(self) -> Path:
        """Frontend source directory."""
        return self.src / "frontend"
    
    @property
    def data(self) -> Path:
        """Data directory."""
        return self._project_root / "data"
    
    @property
    def uploads(self) -> Path:
        """Uploads directory."""
        return self.data / "uploads"
    
    @property
    def logs(self) -> Path:
        """Logs directory."""
        return self._project_root / "logs"
    
    @property
    def config(self) -> Path:
        """Config directory."""
        return self._project_root / "config"
    
    @property
    def docs(self) -> Path:
        """Documentation directory."""
        return self._project_root / "docs"
    
    @property
    def tests(self) -> Path:
        """Tests directory."""
        return self._project_root / "tests"
    
    @property
    def env_file(self) -> Path:
        """Main .env file."""
        return self._project_root / ".env"
    
    @property
    def demo_keys_file(self) -> Path:
        """Demo tenant keys JSON file."""
        return self._project_root / "demo_tenant_keys.json"
    
    @property
    def docker_compose_file(self) -> Path:
        """Docker compose file."""
        return self._project_root / "docker-compose.yml"
    
    def tenant_upload_dir(self, tenant_id: str) -> Path:
        """Get upload directory for specific tenant."""
        return self.uploads / tenant_id
    
    def ensure_dir(self, path: Path) -> Path:
        """Ensure directory exists, create if needed."""
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def add_to_python_path(self):
        """Add project root to Python path for imports."""
        root_str = str(self._project_root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)


# Global instance for easy importing
paths = ProjectPaths()


def get_project_root() -> Path:
    """Get project root directory."""
    return paths.root


def get_paths() -> ProjectPaths:
    """Get project paths instance."""
    return paths


if __name__ == "__main__":
    # Test the path detection
    print(f"Project root: {paths.root}")
    print(f"Scripts dir: {paths.scripts}")
    print(f"Backend dir: {paths.backend}")
    print(f"Env file: {paths.env_file}")
    print(f"Demo keys: {paths.demo_keys_file}")
    
    # Verify key files exist
    key_files = [
        ("docker-compose.yml", paths.docker_compose_file),
        (".env", paths.env_file),
        ("scripts directory", paths.scripts),
        ("src directory", paths.src)
    ]
    
    print("\nVerifying key project files:")
    for name, path in key_files:
        status = "✅" if path.exists() else "❌"
        print(f"{status} {name}: {path}")