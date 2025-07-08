#!/usr/bin/env python3
"""
Setup git hooks for secret scanning
"""

import subprocess
import sys
from pathlib import Path

class Colors:
    GREEN = '\033[0;32m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

def print_colored(message, color):
    print(f"{color}{message}{Colors.NC}")

def main():
    print_colored("🔧 Setting up git hooks for secret scanning...", Colors.BLUE)
    
    project_root = Path(__file__).parent.parent.parent
    
    # Configure git to use custom hooks directory
    try:
        subprocess.run(['git', 'config', 'core.hooksPath', '.githooks'], 
                      cwd=project_root, check=True)
        
        print_colored("✅ Git hooks configured!", Colors.GREEN)
        print()
        print("Hooks enabled:")
        print("  • pre-push: Secret scanning with gitleaks")
        print()
        print("To test manually:")
        print("  python scripts/security/check_secrets.py")
        print()
        print("To disable hooks temporarily:")
        print("  git push --no-verify")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to configure git hooks: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()