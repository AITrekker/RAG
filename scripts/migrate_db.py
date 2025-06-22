#!/usr/bin/env python3
"""
Database Migration Management Script

This script provides utilities for managing database migrations,
including running migrations, creating backups, and database maintenance.
"""

import os
import sys
import subprocess
import argparse
import logging
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backend.config.settings import get_settings
from src.backend.db.session import engine
from sqlalchemy import text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()


def create_backup(backup_dir: str = "backups") -> str:
    """Create a database backup."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(exist_ok=True)
    
    # Parse database URL for pg_dump
    db_url = settings.database_url
    # Extract components (simplified for localhost)
    backup_file = backup_dir / f"rag_backup_{timestamp}.sql"
    
    logger.info(f"Creating backup: {backup_file}")
    
    try:
        # Use pg_dump to create backup
        cmd = [
            "pg_dump",
            "--verbose",
            "--clean",
            "--no-acl",
            "--no-owner",
            db_url,
            "--file", str(backup_file)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"Backup created successfully: {backup_file}")
            return str(backup_file)
        else:
            logger.error(f"Backup failed: {result.stderr}")
            return None
            
    except Exception as e:
        logger.error(f"Backup failed with exception: {e}")
        return None


def run_migrations(target_revision: str = "head") -> bool:
    """Run database migrations."""
    logger.info(f"Running migrations to {target_revision}")
    
    try:
        # Change to backend directory for alembic
        backend_dir = Path(__file__).parent.parent / "src" / "backend"
        
        cmd = [
            "alembic", 
            "-c", "migrations/alembic.ini",
            "upgrade", target_revision
        ]
        
        result = subprocess.run(
            cmd, 
            cwd=backend_dir,
            capture_output=True, 
            text=True
        )
        
        if result.returncode == 0:
            logger.info("Migrations completed successfully")
            logger.info(result.stdout)
            return True
        else:
            logger.error(f"Migration failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Migration failed with exception: {e}")
        return False


def check_database_connection() -> bool:
    """Check database connectivity."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info("Database connection successful")
            return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


def create_test_tenant() -> bool:
    """Create a test tenant for validation."""
    try:
        with engine.connect() as conn:
            # Check if test tenant exists
            result = conn.execute(
                text("SELECT COUNT(*) FROM tenants WHERE tenant_id = 'test-tenant'")
            )
            
            if result.scalar() == 0:
                # Create test tenant
                conn.execute(text("""
                    INSERT INTO tenants (
                        id, tenant_id, name, tier, isolation_level, status,
                        created_at, updated_at, max_documents, max_storage_mb,
                        max_api_calls_per_day, max_concurrent_queries
                    ) VALUES (
                        gen_random_uuid(), 'test-tenant', 'Test Tenant', 'basic', 'logical', 'active',
                        NOW(), NOW(), 1000, 5000, 10000, 10
                    )
                """))
                conn.commit()
                logger.info("Test tenant created successfully")
            else:
                logger.info("Test tenant already exists")
            
        return True
        
    except Exception as e:
        logger.error(f"Failed to create test tenant: {e}")
        return False


def cleanup_old_backups(backup_dir: str = "backups", keep_count: int = 10):
    """Clean up old backup files, keeping only the most recent ones."""
    backup_dir = Path(backup_dir)
    
    if not backup_dir.exists():
        return
    
    # Get all backup files
    backup_files = list(backup_dir.glob("rag_backup_*.sql"))
    backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    # Remove old backups
    for backup_file in backup_files[keep_count:]:
        backup_file.unlink()
        logger.info(f"Removed old backup: {backup_file}")


def show_migration_status():
    """Show current migration status."""
    try:
        backend_dir = Path(__file__).parent.parent / "src" / "backend"
        
        cmd = ["alembic", "-c", "migrations/alembic.ini", "current"]
        
        result = subprocess.run(
            cmd,
            cwd=backend_dir,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("Current migration status:")
            logger.info(result.stdout)
        else:
            logger.error(f"Failed to get migration status: {result.stderr}")
            
    except Exception as e:
        logger.error(f"Failed to get migration status: {e}")


def main():
    parser = argparse.ArgumentParser(description="Database Migration Management")
    parser.add_argument("action", choices=[
        "migrate", "backup", "check", "status", "create-test-tenant", "cleanup-backups"
    ], help="Action to perform")
    
    parser.add_argument("--target", default="head", help="Migration target (default: head)")
    parser.add_argument("--backup-dir", default="backups", help="Backup directory")
    parser.add_argument("--keep-backups", type=int, default=10, help="Number of backups to keep")
    
    args = parser.parse_args()
    
    if args.action == "check":
        success = check_database_connection()
        sys.exit(0 if success else 1)
        
    elif args.action == "migrate":
        # Create backup before migration
        logger.info("Creating backup before migration...")
        backup_file = create_backup(args.backup_dir)
        
        if backup_file:
            success = run_migrations(args.target)
            sys.exit(0 if success else 1)
        else:
            logger.error("Backup failed, aborting migration")
            sys.exit(1)
            
    elif args.action == "backup":
        backup_file = create_backup(args.backup_dir)
        sys.exit(0 if backup_file else 1)
        
    elif args.action == "status":
        show_migration_status()
        
    elif args.action == "create-test-tenant":
        success = create_test_tenant()
        sys.exit(0 if success else 1)
        
    elif args.action == "cleanup-backups":
        cleanup_old_backups(args.backup_dir, args.keep_backups)
        

if __name__ == "__main__":
    main() 