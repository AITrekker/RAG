import sys
import subprocess
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

# When setup.py is run for installation, install dependencies first.
install_requirements()

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
