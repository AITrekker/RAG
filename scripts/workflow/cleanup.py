#!/usr/bin/env python3
"""
RAG System Cleanup Script - Pure Operational

Cleans up Docker containers, volumes, databases, and files without importing backend modules.
Uses subprocess calls for all operations to avoid dependency issues.

Usage:
    python scripts/workflow/cleanup.py                    # Interactive mode
    python scripts/workflow/cleanup.py --all              # Everything
    python scripts/workflow/cleanup.py --containers       # Docker only
    python scripts/workflow/cleanup.py --data             # Files + DB only
    python scripts/workflow/cleanup.py --env test         # Specific environment
    python scripts/workflow/cleanup.py --force            # Skip confirmations
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

# Add project root to Python path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from scripts.utils.project_paths import get_project_root
    PROJECT_ROOT = get_project_root()
except ImportError:
    # Fallback to old method
    SCRIPT_DIR = Path(__file__).parent.absolute()
    PROJECT_ROOT = SCRIPT_DIR.parent.parent

class CleanupManager:
    def __init__(self, force: bool = False, quiet: bool = False):
        self.force = force
        self.quiet = quiet
        self.environments = ["production", "staging", "test", "development"]
    
    def log(self, message: str, level: str = "INFO"):
        """Log message unless in quiet mode."""
        if not self.quiet:
            prefix = "🧹" if level == "INFO" else "⚠️" if level == "WARN" else "❌"
            print(f"{prefix} {message}")
    
    def confirm(self, message: str) -> bool:
        """Ask for user confirmation unless force mode."""
        if self.force:
            return True
        
        response = input(f"❓ {message} (y/N): ").strip().lower()
        return response in ['y', 'yes']
    
    def run_command(self, cmd: List[str], description: str, check: bool = True) -> bool:
        """Run shell command and return success status."""
        try:
            self.log(f"Running: {description}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                if not self.quiet and result.stdout:
                    print(f"  ✅ {result.stdout.strip()}")
                return True
            else:
                if not self.quiet and result.stderr:
                    print(f"  ❌ {result.stderr.strip()}")
                return not check
                
        except Exception as e:
            self.log(f"Command failed: {e}", "ERROR")
            return not check
    
    def cleanup_containers(self) -> bool:
        """Clean up Docker containers and volumes."""
        self.log("🐳 Cleaning up Docker containers and volumes...")
        
        success = True
        
        # Stop and remove containers
        if not self.run_command(
            ["docker-compose", "-f", str(PROJECT_ROOT / "docker-compose.yml"), "down"],
            "Stopping containers",
            check=False
        ):
            success = False
        
        # Remove volumes (excluding cache volumes by default)
        volumes = ["rag_postgres_data", "rag_qdrant_storage"]
        for volume in volumes:
            if not self.run_command(
                ["docker", "volume", "rm", volume],
                f"Removing volume {volume}",
                check=False
            ):
                self.log(f"Volume {volume} may not exist (this is normal)", "WARN")
        
        # Ask before removing cache volumes (they're expensive to rebuild)
        if self.confirm("Remove ML model cache volumes? (they take time to rebuild)"):
            cache_volumes = ["rag_huggingface_cache", "rag_transformers_cache"]
            for volume in cache_volumes:
                if not self.run_command(
                    ["docker", "volume", "rm", volume],
                    f"Removing cache volume {volume}",
                    check=False
                ):
                    self.log(f"Cache volume {volume} may not exist (this is normal)", "WARN")
        
        # Clean up images if requested
        if self.confirm("Remove RAG Docker images as well?"):
            self.run_command(
                ["docker", "image", "rm", "rag-backend", "rag-init"],
                "Removing RAG images",
                check=False
            )
        
        return success
    
    def cleanup_database(self, environment: Optional[str] = None) -> bool:
        """Clean up database entries."""
        self.log("🗃️ Cleaning up database entries...")
        
        success = True
        
        # Get database credentials
        env_file = PROJECT_ROOT / ".env"
        if not env_file.exists():
            self.log("No .env file found, skipping database cleanup", "WARN")
            return True
        
        try:
            # Read credentials from .env
            with open(env_file, 'r') as f:
                env_content = f.read()
            
            postgres_user = None
            postgres_password = None
            for line in env_content.split('\n'):
                if line.startswith('POSTGRES_USER='):
                    postgres_user = line.split('=', 1)[1]
                elif line.startswith('POSTGRES_PASSWORD='):
                    postgres_password = line.split('=', 1)[1]
            
            if not postgres_user or not postgres_password:
                self.log("Missing database credentials in .env", "ERROR")
                return False
            
            # Clean specific environment or all
            if environment:
                environments_to_clean = [environment]
            else:
                environments_to_clean = self.environments
            
            for env in environments_to_clean:
                db_name = f"rag_db_{env}"
                
                # Drop and recreate database (separate commands to avoid transaction issues)
                
                # First, terminate all connections to the database
                terminate_success = self.run_command([
                    "docker", "exec", "rag_postgres", "psql", 
                    "-U", postgres_user, "-d", "postgres", "-c",
                    f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{db_name}' AND pid <> pg_backend_pid();"
                ], f"Terminating connections to {db_name}", check=False)
                
                drop_success = self.run_command([
                    "docker", "exec", "rag_postgres", "psql", 
                    "-U", postgres_user, "-d", "postgres", "-c",
                    f"DROP DATABASE IF EXISTS {db_name};"
                ], f"Dropping database {db_name}", check=False)
                
                create_success = self.run_command([
                    "docker", "exec", "rag_postgres", "psql", 
                    "-U", postgres_user, "-d", "postgres", "-c",
                    f"CREATE DATABASE {db_name} OWNER {postgres_user};"
                ], f"Creating database {db_name}", check=False)
                
                if not (drop_success and create_success):
                    self.log(f"Failed to clean database {db_name}", "WARN")
                    success = False
        
        except Exception as e:
            self.log(f"Database cleanup failed: {e}", "ERROR")
            return False
        
        return success
    
    def cleanup_files(self, environment: Optional[str] = None) -> bool:
        """Clean up upload files and logs."""
        self.log("📁 Cleaning up files...")
        
        success = True
        
        # Clean upload files
        uploads_dir = PROJECT_ROOT / "data" / "uploads"
        if uploads_dir.exists():
            if environment:
                # Try to clean specific tenant directories for this environment
                # Since we don't have backend access, clean all tenant dirs
                self.log(f"Cleaning all upload files (environment-specific cleanup requires backend)", "WARN")
            
            if self.confirm(f"Remove all files in {uploads_dir}?"):
                try:
                    shutil.rmtree(uploads_dir)
                    uploads_dir.mkdir(parents=True, exist_ok=True)
                    self.log("Upload files cleaned")
                except Exception as e:
                    self.log(f"Failed to clean upload files: {e}", "ERROR")
                    success = False
        
        # Clean logs
        logs_dir = PROJECT_ROOT / "logs"
        if logs_dir.exists():
            if self.confirm(f"Remove log files in {logs_dir}?"):
                try:
                    shutil.rmtree(logs_dir)
                    logs_dir.mkdir(parents=True, exist_ok=True)
                    self.log("Log files cleaned")
                except Exception as e:
                    self.log(f"Failed to clean log files: {e}", "ERROR")
                    success = False
        
        # Clean demo tenant keys
        demo_keys_file = PROJECT_ROOT / "demo_tenant_keys.json"
        if demo_keys_file.exists():
            if self.confirm("Remove demo tenant keys file?"):
                try:
                    demo_keys_file.unlink()
                    self.log("Demo tenant keys file removed")
                except Exception as e:
                    self.log(f"Failed to remove demo keys: {e}", "ERROR")
                    success = False
        
        return success
    
    def cleanup_credentials(self) -> bool:
        """Clean up admin credentials from .env file."""
        self.log("🔑 Cleaning up credentials...")
        
        env_file = PROJECT_ROOT / ".env"
        if not env_file.exists():
            self.log("No .env file found", "WARN")
            return True
        
        try:
            with open(env_file, 'r') as f:
                lines = f.readlines()
            
            # Remove admin credentials and environment URLs
            cleaned_lines = []
            skip_next_empty = False
            
            for line in lines:
                if (line.strip().startswith('ADMIN_TENANT_ID=') or 
                    line.strip().startswith('ADMIN_API_KEY=') or
                    line.strip().startswith('RAG_ENVIRONMENT=') or
                    line.strip().startswith('DATABASE_URL_')):
                    continue
                elif line.strip() in ['# Admin credentials (auto-generated)', '# Environment-specific database URLs']:
                    skip_next_empty = True
                    continue
                elif skip_next_empty and line.strip() == '':
                    skip_next_empty = False
                    continue
                else:
                    cleaned_lines.append(line)
                    skip_next_empty = False
            
            # Write cleaned file
            with open(env_file, 'w') as f:
                f.writelines(cleaned_lines)
            
            self.log("Admin credentials removed from .env")
            return True
            
        except Exception as e:
            self.log(f"Failed to clean credentials: {e}", "ERROR")
            return False
    
    def cleanup_all(self, environment: Optional[str] = None, include_caches: bool = True) -> bool:
        """Clean up everything."""
        cleanup_type = "comprehensive cleanup (including caches)" if include_caches else "comprehensive cleanup (preserving caches)"
        self.log(f"🧹 Starting {cleanup_type}...")
        
        if environment:
            self.log(f"🌍 Targeting environment: {environment}")
        else:
            self.log("🌍 Targeting all environments")
        
        success = True
        
        # Confirm comprehensive cleanup
        scope = f"environment '{environment}'" if environment else "ALL ENVIRONMENTS"
        cache_warning = " (INCLUDING ML MODEL CACHES)" if include_caches else ""
        if not self.confirm(f"This will clean up {scope}{cache_warning}. Continue?"):
            self.log("Cleanup cancelled")
            return False
        
        # Clean in order: database -> containers -> files -> credentials
        # Database cleanup needs containers running, so do it first
        if not self.cleanup_database(environment):
            success = False
        
        if not self.cleanup_containers_with_caches(include_caches):
            success = False
        
        if not self.cleanup_files(environment):
            success = False
        
        if not self.cleanup_credentials():
            success = False
        
        if success:
            self.log("🎉 Cleanup completed successfully!")
        else:
            self.log("⚠️ Cleanup completed with some errors", "WARN")
        
        return success
    
    def cleanup_containers_with_caches(self, include_caches: bool = True) -> bool:
        """Clean up Docker containers and optionally volumes including caches."""
        self.log("🐳 Cleaning up Docker containers and volumes...")
        
        success = True
        
        # Stop and remove containers
        if not self.run_command(
            ["docker-compose", "-f", str(PROJECT_ROOT / "docker-compose.yml"), "down"],
            "Stopping containers",
            check=False
        ):
            success = False
        
        # Remove volumes (excluding cache volumes by default)
        volumes = ["rag_postgres_data", "rag_qdrant_storage"]
        for volume in volumes:
            if not self.run_command(
                ["docker", "volume", "rm", volume],
                f"Removing volume {volume}",
                check=False
            ):
                self.log(f"Volume {volume} may not exist (this is normal)", "WARN")
        
        # Handle cache volumes based on include_caches flag
        if include_caches:
            self.log("🗑️ Removing ML model cache volumes...")
            cache_volumes = ["rag_huggingface_cache", "rag_transformers_cache"]
            for volume in cache_volumes:
                if not self.run_command(
                    ["docker", "volume", "rm", volume],
                    f"Removing cache volume {volume}",
                    check=False
                ):
                    self.log(f"Cache volume {volume} may not exist (this is normal)", "WARN")
        else:
            self.log("💾 Preserving ML model cache volumes for faster restarts")
        
        # Clean up images if requested
        if self.confirm("Remove RAG Docker images as well?"):
            self.run_command(
                ["docker", "image", "rm", "rag-backend", "rag-init"],
                "Removing RAG images",
                check=False
            )
        
        return success

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='RAG System Cleanup')
    parser.add_argument('--all', action='store_true', help='Clean everything')
    parser.add_argument('--containers', action='store_true', help='Clean Docker containers only')
    parser.add_argument('--data', action='store_true', help='Clean files and database only')
    parser.add_argument('--env', choices=['production', 'staging', 'test', 'development'],
                       help='Clean specific environment only')
    parser.add_argument('--force', action='store_true', help='Skip confirmations')
    parser.add_argument('--quiet', action='store_true', help='Minimal output')
    
    args = parser.parse_args()
    
    # Create cleanup manager
    manager = CleanupManager(force=args.force, quiet=args.quiet)
    
    try:
        success = True
        
        if args.all:
            success = manager.cleanup_all(args.env, include_caches=True)
        elif args.containers:
            success = manager.cleanup_containers()
        elif args.data:
            success = manager.cleanup_database(args.env) and manager.cleanup_files(args.env)
        elif args.env or any([args.all, args.containers, args.data]):
            # Environment-specific cleanup
            success = manager.cleanup_all(args.env, include_caches=False)
        else:
            # Interactive mode
            manager.log("🧹 RAG System Cleanup - Interactive Mode")
            manager.log("=" * 50)
            
            print("\nCleanup Options:")
            print("1. Clean data only (database + files + credentials)")
            print("2. Clean containers only")
            print("3. Clean specific environment")
            print("4. Clean everything (containers + database + files + credentials + caches)")
            print("5. Cancel")
            
            choice = input("\nSelect option (1-5): ").strip()
            
            if choice == '1':
                success = manager.cleanup_database() and manager.cleanup_files() and manager.cleanup_credentials()
            elif choice == '2':
                success = manager.cleanup_containers()
            elif choice == '3':
                print("\nEnvironments:")
                for i, env in enumerate(manager.environments, 1):
                    print(f"{i}. {env}")
                
                env_choice = input("Select environment (1-4): ").strip()
                try:
                    env_index = int(env_choice) - 1
                    if 0 <= env_index < len(manager.environments):
                        selected_env = manager.environments[env_index]
                        success = manager.cleanup_all(selected_env, include_caches=False)
                    else:
                        manager.log("Invalid environment selection", "ERROR")
                        success = False
                except ValueError:
                    manager.log("Invalid input", "ERROR")
                    success = False
            elif choice == '4':
                success = manager.cleanup_all(include_caches=True)
            elif choice == '5':
                manager.log("Cleanup cancelled")
                success = True
            else:
                manager.log("Invalid option", "ERROR")
                success = False
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        manager.log("\nCleanup interrupted by user")
        sys.exit(1)
    except Exception as e:
        manager.log(f"Unexpected error: {e}", "ERROR")
        sys.exit(1)

if __name__ == "__main__":
    main()