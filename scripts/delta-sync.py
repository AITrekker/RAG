#!/usr/bin/env python3
"""
Delta Sync Script - Trigger delta sync for all tenants with upload directories

This script:
1. Scans /data/uploads/ for tenant directories (UUID named)
2. Validates tenant exists in database
3. Runs delta sync detection and processing for each tenant
4. Reports results and statistics
"""

import os
import sys
import socket
import asyncio
from pathlib import Path
from typing import List, Dict, Any
from uuid import UUID
from dotenv import load_dotenv

# Set NLTK data path for Docker environment
os.environ['NLTK_DATA'] = '/tmp/nltk_data'

# Add project root to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Use direct path method for now
PROJECT_ROOT = Path(__file__).parent.parent

# Setup DATABASE_URL for local vs Docker execution
def setup_database_url():
    """Setup DATABASE_URL for current environment (Docker vs local)"""
    load_dotenv()
    
    # Get credentials from .env
    postgres_user = os.getenv("POSTGRES_USER")
    postgres_password = os.getenv("POSTGRES_PASSWORD") 
    rag_environment = os.getenv("RAG_ENVIRONMENT", "development")
    postgres_db = f"rag_db_{rag_environment}"
    
    if not postgres_user or not postgres_password:
        print("❌ Missing database credentials in .env file")
        print("   Required: POSTGRES_USER, POSTGRES_PASSWORD")
        sys.exit(1)
    
    # Detect environment
    if is_running_in_docker():
        # Use Docker network hostname
        database_url = f"postgresql://{postgres_user}:{postgres_password}@postgres:5432/{postgres_db}"
        print("🐳 Detected Docker environment")
    else:
        # Use localhost for local execution
        database_url = f"postgresql://{postgres_user}:{postgres_password}@localhost:5432/{postgres_db}"
        print("💻 Detected local environment")
    
    # Set the environment variable for database connections
    os.environ["DATABASE_URL"] = database_url
    print(f"📡 Database URL: {database_url}")

def is_running_in_docker() -> bool:
    """Detect if we're running inside a Docker container"""
    try:
        # Check for Docker-specific files/environments
        if os.path.exists("/.dockerenv"):
            return True
        
        # Check if hostname resolves to postgres (Docker network)
        try:
            socket.gethostbyname("postgres")
            return True
        except socket.gaierror:
            return False
            
    except Exception:
        return False

# Setup database URL BEFORE importing backend modules
setup_database_url()

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.database import AsyncSessionLocal, init_database
from src.backend.models.database import Tenant, User
from src.backend.services.file_service import FileService
from src.backend.services.embedding_service_pgvector import PgVectorEmbeddingService
from src.backend.services.sync_service import SyncService


async def get_tenant_directories() -> List[UUID]:
    """
    Get tenant directories from /data/uploads/ that are valid UUIDs
    
    Returns:
        List of tenant UUIDs found in upload directories
    """
    uploads_path = PROJECT_ROOT / "data" / "uploads"
    tenant_ids = []
    
    if not uploads_path.exists():
        return tenant_ids
    
    for directory in uploads_path.iterdir():
        if directory.is_dir():
            try:
                # Try to parse directory name as UUID
                tenant_id = UUID(directory.name)
                tenant_ids.append(tenant_id)
            except ValueError:
                # Skip non-UUID directory names
                print(f"⏩ Skipping non-UUID directory: {directory.name}")
    
    return tenant_ids


async def validate_tenant_exists(tenant_id: UUID) -> Dict[str, Any]:
    """
    Validate that a tenant exists in the database
    
    Returns:
        Dict with tenant info if exists, None if not found
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Tenant).where(
                Tenant.id == tenant_id,
                Tenant.is_active == True
            )
        )
        tenant = result.scalar_one_or_none()
        
        if tenant:
            return {
                'id': tenant.id,
                'name': tenant.name,
                'slug': tenant.slug,
                'plan_tier': tenant.plan_tier
            }
        return None


async def get_or_create_system_user() -> UUID:
    """
    Get or create a system user for auto-discovered files
    
    Returns:
        UUID of the system user
    """
    async with AsyncSessionLocal() as session:
        # Try to find existing system user
        result = await session.execute(
            select(User).where(User.email == 'system@delta-sync.local')
        )
        system_user = result.scalar_one_or_none()
        
        if not system_user:
            # Create system user
            system_user = User(
                email='system@delta-sync.local',
                password_hash='system_user_no_login',
                full_name='Delta Sync System User',
                is_active=True
            )
            session.add(system_user)
            await session.commit()
            await session.refresh(system_user)
            print(f"✅ Created system user: {system_user.id}")
        
        return system_user.id


async def run_tenant_sync(tenant_id: UUID, tenant_info: Dict[str, Any], system_user_id: UUID) -> Dict[str, Any]:
    """
    Run delta sync for a specific tenant
    
    Returns:
        Dict with sync results
    """
    print(f"\n🚀 Running delta sync for {tenant_info['name']}")
    print(f"   Tenant ID: {tenant_id}")
    print(f"   Plan: {tenant_info['plan_tier']}")
    
    async with AsyncSessionLocal() as session:
        # Initialize services with singleton embedding model
        file_service = FileService(session)
        
        # Get singleton embedding model to avoid multiple loads
        try:
            from src.backend.dependencies import get_embedding_model
            embedding_model = get_embedding_model()
            embedding_service = PgVectorEmbeddingService(session, embedding_model)
            print(f"  🤖 Using singleton embedding model")
        except Exception as e:
            print(f"  ⚠️ Failed to load embedding model: {e}")
            embedding_service = PgVectorEmbeddingService(session)
            await embedding_service.initialize()
        
        sync_service = SyncService(session, file_service, embedding_service)
        
        try:
            # 1. Scan files
            print(f"  📁 Scanning files...")
            files = await file_service.scan_tenant_files(tenant_id)
            print(f"     Found {len(files)} files")
            
            # 2. Detect changes
            print(f"  🔍 Detecting changes...")
            sync_plan = await sync_service.detect_file_changes(tenant_id)
            
            changes_summary = {
                'total': sync_plan.total_changes,
                'new': len(sync_plan.new_files),
                'updated': len(sync_plan.updated_files),
                'deleted': len(sync_plan.deleted_files)
            }
            
            print(f"     Changes detected: {changes_summary['total']}")
            print(f"       New: {changes_summary['new']}")
            print(f"       Updated: {changes_summary['updated']}")
            print(f"       Deleted: {changes_summary['deleted']}")
            
            # 3. Execute sync if there are changes
            sync_operation = None
            if sync_plan.total_changes > 0:
                print(f"  ⚡ Executing sync...")
                
                try:
                    # Execute the sync plan using the service
                    sync_operation = await sync_service.execute_sync_plan(sync_plan, system_user_id)
                    
                    # Get results from sync operation
                    files_processed = sync_operation.files_processed or 0
                    files_failed = 0  # TODO: Track failed files in sync operation
                    
                    print(f"     Sync completed: {files_processed} processed, {files_failed} failed")
                    
                    return {
                        'tenant_id': str(tenant_id),
                        'tenant_name': tenant_info['name'],
                        'files_found': len(files),
                        'changes_detected': changes_summary,
                        'files_processed': files_processed,
                        'files_failed': files_failed,
                        'status': 'completed' if files_failed == 0 else 'partial',
                        'error': None
                    }
                    
                except Exception as e:
                    await session.rollback()
                    print(f"     ❌ Sync failed: {e}")
                    return {
                        'tenant_id': str(tenant_id),
                        'tenant_name': tenant_info['name'],
                        'files_found': len(files),
                        'changes_detected': changes_summary,
                        'files_processed': 0,
                        'files_failed': sync_plan.total_changes,
                        'status': 'failed',
                        'error': str(e)
                    }
            else:
                print(f"     ⏩ No changes detected, sync not needed")
                return {
                    'tenant_id': str(tenant_id),
                    'tenant_name': tenant_info['name'],
                    'files_found': len(files),
                    'changes_detected': changes_summary,
                    'files_processed': 0,
                    'files_failed': 0,
                    'status': 'no_changes',
                    'error': None
                }
                
        except Exception as e:
            print(f"     ❌ Error during sync: {e}")
            return {
                'tenant_id': str(tenant_id),
                'tenant_name': tenant_info['name'],
                'files_found': 0,
                'changes_detected': {'total': 0, 'new': 0, 'updated': 0, 'deleted': 0},
                'files_processed': 0,
                'files_failed': 0,
                'status': 'error',
                'error': str(e)
            }


async def main():
    """Main function to orchestrate delta sync across all tenants"""
    print("🚀 Delta Sync Script")
    print("=" * 50)
    
    try:
        # Initialize database
        print("\n🔧 Initializing database...")
        await init_database()
        print("✅ Database initialized")
        
        # Get system user
        print("\n👤 Setting up system user...")
        system_user_id = await get_or_create_system_user()
        print(f"✅ System user ready: {system_user_id}")
        
        # 1. Scan for tenant directories
        print("\n📁 Scanning for tenant directories...")
        tenant_ids = await get_tenant_directories()
        
        if not tenant_ids:
            print("❌ No tenant directories found in /data/uploads/")
            print("💡 Run scripts/rename-tenants.py first to set up directories")
            return
        
        print(f"✅ Found {len(tenant_ids)} tenant directories")
        
        # 2. Validate tenants exist in database
        print(f"\n🔍 Validating tenants in database...")
        valid_tenants = []
        
        for tenant_id in tenant_ids:
            tenant_info = await validate_tenant_exists(tenant_id)
            if tenant_info:
                valid_tenants.append((tenant_id, tenant_info))
                print(f"  ✅ {tenant_info['name']} ({tenant_id})")
            else:
                print(f"  ❌ Tenant not found in database: {tenant_id}")
        
        if not valid_tenants:
            print("❌ No valid tenants found")
            return
        
        print(f"✅ {len(valid_tenants)} valid tenants ready for sync")
        
        # 3. Run delta sync for each tenant
        print(f"\n⚡ Starting delta sync operations...")
        sync_results = []
        
        for tenant_id, tenant_info in valid_tenants:
            result = await run_tenant_sync(tenant_id, tenant_info, system_user_id)
            sync_results.append(result)
        
        # 4. Generate summary report
        print(f"\n🎉 Delta Sync Complete!")
        print("=" * 50)
        
        total_files_found = sum(r['files_found'] for r in sync_results)
        total_processed = sum(r['files_processed'] for r in sync_results)
        total_failed = sum(r['files_failed'] for r in sync_results)
        total_changes = sum(r['changes_detected']['total'] for r in sync_results)
        
        print(f"📊 Overall Summary:")
        print(f"  🏢 Tenants processed: {len(sync_results)}")
        print(f"  📁 Total files found: {total_files_found}")
        print(f"  🔄 Total changes detected: {total_changes}")
        print(f"  ✅ Files processed successfully: {total_processed}")
        print(f"  ❌ Files failed: {total_failed}")
        
        print(f"\n📋 Detailed Results:")
        for result in sync_results:
            status_emoji = {
                'completed': '✅',
                'partial': '⚠️',
                'no_changes': '⏩',
                'failed': '❌',
                'error': '💥'
            }.get(result['status'], '❓')
            
            print(f"  {status_emoji} {result['tenant_name']}: {result['files_processed']} processed")
            if result['error']:
                print(f"      Error: {result['error']}")
        
        # 5. Next steps
        if total_processed > 0:
            print(f"\n🚀 Success! Your files are now:")
            print(f"  📊 Indexed in PostgreSQL")
            print(f"  🔢 Embedded and stored in Qdrant")
            print(f"  🔍 Ready for RAG queries")
            print(f"\n💡 Test your RAG system with queries about your company data!")
        else:
            print(f"\n💡 No files were processed. This could mean:")
            print(f"  • All files were already synced")
            print(f"  • No supported file types found")
            print(f"  • Check the detailed error messages above")
        
    except Exception as e:
        print(f"❌ Critical error during delta sync: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())