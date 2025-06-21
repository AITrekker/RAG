import os
import subprocess
import sys
from pathlib import Path

def in_virtualenv():
    return (
        hasattr(sys, 'real_prefix') or
        (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    )

def create_venv(venv_path):
    print(f"Creating virtual environment at {venv_path}...")
    subprocess.check_call([sys.executable, '-m', 'venv', str(venv_path)])

def activate_and_install(venv_path, requirements_file='requirements.txt'):
    pip_executable = venv_path / ('Scripts' if os.name == 'nt' else 'bin') / 'pip'
    print(f"Using pip at: {pip_executable}")
    subprocess.check_call([str(pip_executable), 'install', '--upgrade', 'pip'])
    subprocess.check_call([str(pip_executable), 'install', '-r', requirements_file])

def main():
    venv_path = Path('.venv')
    if not in_virtualenv():
        if not venv_path.exists():
            create_venv(venv_path)
        print(f"Activating virtual environment in {venv_path}...")
        activate_and_install(venv_path)
        print("""
✅ Setup complete.
To activate the environment manually:

  source .venv/bin/activate  (on macOS/Linux)
  .venv\Scripts\activate   (on Windows)
""")
    else:
        print("Already in a virtual environment. Installing requirements...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])

if __name__ == '__main__':
    main()
