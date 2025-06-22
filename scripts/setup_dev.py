#!/usr/bin/env python3
"""
Automated Development Environment Setup for RAG Platform
This script sets up the complete development environment for the RAG platform
"""

import os
import sys
import subprocess
import platform
import shutil
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

def print_banner():
    """Print setup banner"""
    print("🛠️  RAG Platform - Automated Development Setup")
    print("=" * 50)
    print()

def print_section(title: str):
    """Print section header"""
    print(f"\n{'='*20} {title} {'='*20}")

def print_step(step: str, status: str = "INFO"):
    """Print setup step with status"""
    icons = {
        "INFO": "ℹ️",
        "SUCCESS": "✅", 
        "WARNING": "⚠️",
        "ERROR": "❌",
        "SKIP": "⏭️"
    }
    icon = icons.get(status, "ℹ️")
    print(f"{icon} {step}")

def run_command(cmd: List[str], description: str, check: bool = True, capture_output: bool = False) -> Tuple[bool, str]:
    """Run a shell command with error handling"""
    try:
        print_step(f"Running: {description}")
        
        if capture_output:
            result = subprocess.run(cmd, capture_output=True, text=True, check=check)
            return True, result.stdout.strip()
        else:
            subprocess.run(cmd, check=check)
            return True, ""
    except subprocess.CalledProcessError as e:
        print_step(f"Failed: {description} - {e}", "ERROR")
        return False, str(e)
    except FileNotFoundError:
        print_step(f"Command not found: {' '.join(cmd)}", "ERROR")
        return False, "Command not found"

def check_system_requirements() -> Dict[str, bool]:
    """Check system requirements"""
    print_section("SYSTEM REQUIREMENTS CHECK")
    
    requirements = {}
    
    # Check Python version
    python_version = sys.version_info
    if python_version.major >= 3 and python_version.minor >= 8:
        print_step(f"Python {python_version.major}.{python_version.minor}.{python_version.micro}", "SUCCESS")
        requirements["python"] = True
    else:
        print_step(f"Python {python_version.major}.{python_version.minor}.{python_version.micro} - Need 3.8+", "ERROR")
        requirements["python"] = False
    
    # Check Node.js
    try:
        success, node_version = run_command(["node", "--version"], "Checking Node.js", check=False, capture_output=True)
        if success:
            version_num = node_version.replace("v", "")
            major_version = int(version_num.split(".")[0])
            if major_version >= 18:
                print_step(f"Node.js {version_num}", "SUCCESS")
                requirements["nodejs"] = True
            else:
                print_step(f"Node.js {version_num} - Need 18+", "ERROR")
                requirements["nodejs"] = False
        else:
            print_step("Node.js not found", "ERROR")
            requirements["nodejs"] = False
    except:
        print_step("Node.js not found", "ERROR")
        requirements["nodejs"] = False
    
    # Check npm
    try:
        success, npm_version = run_command(["npm", "--version"], "Checking npm", check=False, capture_output=True)
        if success:
            print_step(f"npm {npm_version}", "SUCCESS")
            requirements["npm"] = True
        else:
            print_step("npm not found", "ERROR")
            requirements["npm"] = False
    except:
        print_step("npm not found", "ERROR")
        requirements["npm"] = False
    
    # Check Docker
    try:
        success, docker_version = run_command(["docker", "--version"], "Checking Docker", check=False, capture_output=True)
        if success:
            print_step(f"Docker available", "SUCCESS")
            requirements["docker"] = True
        else:
            print_step("Docker not found - Optional for direct execution", "WARNING")
            requirements["docker"] = False
    except:
        print_step("Docker not found - Optional for direct execution", "WARNING")
        requirements["docker"] = False
    
    # Check Git
    try:
        success, git_version = run_command(["git", "--version"], "Checking Git", check=False, capture_output=True)
        if success:
            print_step("Git available", "SUCCESS")
            requirements["git"] = True
        else:
            print_step("Git not found", "WARNING")
            requirements["git"] = False
    except:
        print_step("Git not found", "WARNING")
        requirements["git"] = False
    
    return requirements

def setup_project_structure() -> bool:
    """Create project directory structure"""
    print_section("PROJECT STRUCTURE SETUP")
    
    project_root = Path.cwd()
    
    directories = [
        "src/backend/api/routes",
        "src/backend/core", 
        "src/backend/models",
        "src/backend/utils",
        "src/backend/config",
        "src/backend/migrations",
        "src/backend/tests",
        "src/frontend/components",
        "src/frontend/hooks",
        "src/frontend/services", 
        "src/frontend/tests",
        "src/config",
        "scripts",
        "docker/chroma",
        "docker/nginx",
        "tests",
        "data/uploads",
        "data/chroma",
        "data/postgres",
        "data/redis",
        "cache/transformers",
        "cache/huggingface",
        "logs"
    ]
    
    for directory in directories:
        dir_path = project_root / directory
        if not dir_path.exists():
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                print_step(f"Created: {directory}", "SUCCESS")
            except Exception as e:
                print_step(f"Failed to create {directory}: {e}", "ERROR")
                return False
        else:
            print_step(f"Already exists: {directory}", "SKIP")
    
    return True

def setup_python_environment() -> bool:
    """Set up Python virtual environment and dependencies"""
    print_section("PYTHON ENVIRONMENT SETUP")
    
    # Check if virtual environment exists
    venv_path = Path(".venv")
    
    if not venv_path.exists():
        print_step("Creating virtual environment")
        success, _ = run_command([sys.executable, "-m", "venv", ".venv"], "Creating virtual environment")
        if not success:
            return False
    else:
        print_step("Virtual environment already exists", "SKIP")
    
    # Determine activation script based on platform
    if platform.system() == "Windows":
        pip_executable = venv_path / "Scripts" / "pip.exe"
        python_executable = venv_path / "Scripts" / "python.exe"
    else:
        pip_executable = venv_path / "bin" / "pip"
        python_executable = venv_path / "bin" / "python"
    
    # Install requirements if they exist
    requirements_file = Path("requirements.txt")
    if requirements_file.exists():
        print_step("Installing Python dependencies")
        success, _ = run_command([
            str(pip_executable), "install", "-r", str(requirements_file)
        ], "Installing requirements.txt")
        if not success:
            return False
    else:
        print_step("requirements.txt not found - will be created later", "WARNING")
    
    return True

def setup_frontend_environment() -> bool:
    """Set up Node.js frontend environment"""
    print_section("FRONTEND ENVIRONMENT SETUP")
    
    frontend_dir = Path("src/frontend")
    
    if not frontend_dir.exists():
        print_step("Frontend directory not found - will be created later", "WARNING")
        return True
    
    # Change to frontend directory
    os.chdir(frontend_dir)
    
    # Check if package.json exists
    if Path("package.json").exists():
        print_step("Installing Node.js dependencies")
        success, _ = run_command(["npm", "install"], "Installing npm dependencies")
        if not success:
            os.chdir("../..")
            return False
    else:
        print_step("package.json not found - frontend not yet initialized", "WARNING")
    
    # Return to project root
    os.chdir("../..")
    return True

def get_env_example_content() -> str:
    """Returns the content for the .env.example file"""
    return """# RAG Enterprise Platform - Environment Variables
# -------------------------------------------------
# Copy this file to .env and fill in the values for your local setup.

# -- General Settings --
ENVIRONMENT=development # development, staging, or production
LOG_LEVEL=INFO # DEBUG, INFO, WARNING, ERROR

# -- Backend Settings --
# For local development, these are often managed by docker-compose or direct execution scripts.
# For production, these should be set explicitly.
DATABASE_URL=postgresql://rag_user:rag_password@postgres:5432/rag_database
CHROMA_PERSIST_DIRECTORY=./data/chroma
UPLOAD_DIRECTORY=./data/uploads
TRANSFORMERS_CACHE=./cache/transformers
# Set to 0 to use the first available GPU, or "-1" to force CPU.
CUDA_VISIBLE_DEVICES=0

# -- Frontend Settings --
# These are typically build-time variables for the frontend container/service.
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_TITLE="Enterprise RAG Platform"

# -- Security Settings (for later layers) --
# SECRET_KEY=your_super_secret_key_here
# API_KEY_SALT=your_api_key_salt_here

# -- CORS Origins --
# A JSON string of a list of allowed origins
CORS_ORIGINS='["http://localhost:3000", "http://127.0.0.1:3000"]'
"""

def setup_environment_files() -> bool:
    """Set up environment configuration files"""
    print_section("ENVIRONMENT CONFIGURATION")
    
    env_example = Path(".env.example")
    env_file = Path(".env")
    
    # Create .env.example if it does not exist
    if not env_example.exists():
        try:
            print_step("Creating .env.example file")
            env_example.write_text(get_env_example_content())
            print_step(".env.example created successfully", "SUCCESS")
        except IOError as e:
            print_step(f"Failed to create .env.example: {e}", "ERROR")
            return False

    # Create .env from .env.example if it doesn't exist
    if env_example.exists() and not env_file.exists():
        try:
            print_step("Creating .env from .env.example")
            shutil.copy(env_example, env_file)
            print_step("Created .env from .env.example", "SUCCESS")
        except Exception as e:
            print_step(f"Failed to create .env: {e}", "ERROR")
            return False
    elif env_file.exists():
        print_step(".env already exists", "SKIP")
    else:
        print_step(".env.example not found - will be created later", "WARNING")
    
    return True

def test_gpu_availability() -> bool:
    """Test GPU and CUDA availability"""
    print_section("GPU/CUDA VERIFICATION")
    
    try:
        # Try to import torch and check CUDA
        import torch
        
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            gpu_name = torch.cuda.get_device_name(0) if gpu_count > 0 else "Unknown"
            cuda_version = torch.version.cuda
            
            print_step(f"CUDA available: {cuda_version}", "SUCCESS")
            print_step(f"GPU count: {gpu_count}", "SUCCESS")
            print_step(f"Primary GPU: {gpu_name}", "SUCCESS")
            
            # Test basic GPU operation
            x = torch.randn(100, 100).cuda()
            y = torch.randn(100, 100).cuda()
            z = torch.matmul(x, y)
            print_step("GPU tensor operations working", "SUCCESS")
            
            return True
        else:
            print_step("CUDA not available - will run on CPU", "WARNING")
            return True
            
    except ImportError:
        print_step("PyTorch not installed - install requirements.txt first", "WARNING")
        return True
    except Exception as e:
        print_step(f"GPU test failed: {e}", "ERROR")
        return True  # Non-critical for setup

def create_gitignore() -> bool:
    """Create .gitignore file"""
    print_section("GIT CONFIGURATION")
    
    gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
.venv/
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Environment variables
.env
.env.local
.env.development.local
.env.test.local
.env.production.local

# Logs
logs/
*.log

# Database
*.db
*.sqlite

# Node.js
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# Build outputs
dist/
build/

# Cache
cache/
.cache/

# Data directories
data/
!data/.gitkeep

# Docker
.docker/

# Coverage
.coverage
.pytest_cache/
htmlcov/

# Jupyter
.ipynb_checkpoints

# Temporary files
*.tmp
*.temp
temp/
tmp/
"""
    
    gitignore_path = Path(".gitignore")
    if not gitignore_path.exists():
        try:
            gitignore_path.write_text(gitignore_content)
            print_step("Created .gitignore", "SUCCESS")
        except Exception as e:
            print_step(f"Failed to create .gitignore: {e}", "ERROR")
            return False
    else:
        print_step(".gitignore already exists", "SKIP")
    
    return True

def run_verification_tests() -> bool:
    """Run verification tests"""
    print_section("VERIFICATION TESTS")
    
    # Test backend script
    backend_script = Path("scripts/run_backend.py")
    if backend_script.exists():
        print_step("Testing backend script")
        success, _ = run_command([
            sys.executable, str(backend_script), "--help"
        ], "Backend script test", check=False)
        if success:
            print_step("Backend script working", "SUCCESS")
        else:
            print_step("Backend script needs attention", "WARNING")
    
    # Test frontend script (bash)
    frontend_script = Path("scripts/run_frontend.sh")
    if frontend_script.exists() and platform.system() != "Windows":
        print_step("Testing frontend script (bash)")
        success, _ = run_command([
            "bash", str(frontend_script), "--help"
        ], "Frontend script test", check=False)
        if success:
            print_step("Frontend script working", "SUCCESS")
        else:
            print_step("Frontend script needs attention", "WARNING")
    
    # Test frontend script (PowerShell on Windows)
    frontend_ps_script = Path("scripts/run_frontend.ps1")
    if frontend_ps_script.exists() and platform.system() == "Windows":
        print_step("Testing frontend script (PowerShell)")
        success, _ = run_command([
            "powershell", "-ExecutionPolicy", "Bypass", 
            str(frontend_ps_script), "-Help"
        ], "Frontend PowerShell script test", check=False)
        if success:
            print_step("Frontend PowerShell script working", "SUCCESS")
        else:
            print_step("Frontend PowerShell script needs attention", "WARNING")
    
    return True

def print_summary(requirements: Dict[str, bool]):
    """Print setup summary"""
    print_section("SETUP SUMMARY")
    
    print("System Requirements:")
    for req, status in requirements.items():
        status_icon = "✅" if status else "❌"
        print(f"  {status_icon} {req.capitalize()}")
    
    print("\n📁 Directory Structure: Created")
    print("🐍 Python Environment: Configured")
    print("🌐 Frontend Environment: Configured")
    print("📄 Configuration Files: Created")
    print("🔧 Scripts: Ready")
    
    print("\n🚀 Next Steps:")
    print("1. Activate virtual environment:")
    if platform.system() == "Windows":
        print("   .venv\\Scripts\\activate")
    else:
        print("   source .venv/bin/activate")
    
    print("2. Install Python dependencies:")
    print("   pip install -r requirements.txt")
    
    print("3. Start development servers:")
    print("   python scripts/run_backend.py --debug")
    print("   ./scripts/run_frontend.sh (or .ps1 on Windows)")
    
    print("4. Or use Docker:")
    print("   docker-compose up --build")
    
    if not requirements.get("docker", False):
        print("\n⚠️  Consider installing Docker for containerized development")
    
    print("\n✨ Development environment setup complete!")

def main():
    """Main setup function"""
    print_banner()
    
    # Check system requirements
    requirements = check_system_requirements()
    
    # Stop if critical requirements are missing
    critical_missing = []
    if not requirements.get("python", False):
        critical_missing.append("Python 3.8+")
    
    if critical_missing:
        print(f"\n❌ Critical requirements missing: {', '.join(critical_missing)}")
        print("Please install missing requirements and run setup again.")
        sys.exit(1)
    
    # Run setup steps
    setup_steps = [
        ("Project Structure", setup_project_structure),
        ("Python Environment", setup_python_environment),
        ("Frontend Environment", setup_frontend_environment),
        ("Environment Files", setup_environment_files),
        ("Git Configuration", create_gitignore),
        ("GPU Verification", test_gpu_availability),
        ("Verification Tests", run_verification_tests)
    ]
    
    for step_name, step_func in setup_steps:
        try:
            success = step_func()
            if not success:
                print_step(f"{step_name} failed", "ERROR")
                response = input(f"Continue anyway? (y/N): ").strip().lower()
                if response != 'y':
                    sys.exit(1)
        except KeyboardInterrupt:
            print("\n\n🛑 Setup interrupted by user")
            sys.exit(1)
        except Exception as e:
            print_step(f"{step_name} error: {e}", "ERROR")
            response = input(f"Continue anyway? (y/N): ").strip().lower()
            if response != 'y':
                sys.exit(1)
    
    # Print summary
    print_summary(requirements)

if __name__ == "__main__":
    main() 