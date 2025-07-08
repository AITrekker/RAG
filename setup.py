import sys
import subprocess
import shutil
from setuptools import setup, find_packages
from pathlib import Path

# --- Helper Functions ---

def is_in_virtual_env() -> bool:
    """Check if running in a virtual environment."""
    return sys.prefix != sys.base_prefix or hasattr(sys, 'real_prefix')

def install_requirements():
    """Install requirements from requirements.txt using the correct pip."""
    print("Installing requirements...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
        )
        print("Requirements installed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error installing requirements: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: 'pip' command not found. Is pip installed and in your PATH?")
        sys.exit(1)

def setup_environment_file():
    """Create .env file from .env.example if it doesn't exist."""
    env_example = Path(".env.example")
    env_file = Path(".env")
    
    if env_example.exists() and not env_file.exists():
        try:
            shutil.copy(env_example, env_file)
            print("Created .env file from .env.example")
        except Exception as e:
            print(f"Warning: Could not create .env file: {e}")
            print("   You may need to create it manually: copy .env.example .env")
    elif env_file.exists():
        print(".env file already exists")
    else:
        print("Warning: .env.example not found")
        print("   You may need to create .env file manually")

def create_directories():
    """Create essential directories if they don't exist."""
    directories = [
        "data/tenants",
        "logs",
        "cache/transformers",
        "cache/huggingface"
    ]
    
    for directory in directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                print(f"Created directory: {directory}")
            except Exception as e:
                print(f"Warning: Could not create {directory}: {e}")

def print_setup_summary():
    """Print setup completion summary."""
    print("\n" + "="*50)
    print("SETUP COMPLETE!")
    print("="*50)
    print("\nNext steps:")
    print("1. Start Qdrant: docker-compose up -d qdrant")
    print("2. Initialize database: python scripts/db-init.py")
    print("3. Start backend: python scripts/run_backend.py")
    print("\nOr run everything with Docker (backend may have ML library issues):")
    print("   docker-compose up -d")
    print("\nFor development setup with additional checks:")
    print("   python scripts/setup_dev.py")
    print("="*50)

# --- Main Setup Logic ---
# Check if running in a virtual environment
if not is_in_virtual_env():
    print("Error: This setup must be run within a virtual environment.")
    print("Please activate your virtual environment and try again.")
    print("To create a virtual environment:")
    print("  python -m venv .venv")
    print("  # On Windows:")
    print("  .venv\\Scripts\\activate")
    print("  # On Unix/MacOS:")
    print("  source .venv/bin/activate")
    sys.exit(1)

print("Running in a virtual environment. Proceeding with installation...")

# Step 1: Create essential directories
print("\nCreating directories...")
create_directories()

# Step 2: Setup environment file
print("\nSetting up environment...")
setup_environment_file()

# Step 3: Install requirements
print("\nInstalling dependencies...")
install_requirements()

# Step 4: Print summary
print_setup_summary()

setup(
    name="enterprise-rag-platform",
    version="1.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    author="Enterprise RAG Team",
    description="A multi-tenant RAG platform for enterprise document search and retrieval",
    long_description=Path("README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    url="https://github.com/AITrekker/RAG", 
    python_requires=">=3.11",
    entry_points={
        'console_scripts': [
            'rag-backend=backend.main:app', # Example if you have a main entry point
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
    ],
)
