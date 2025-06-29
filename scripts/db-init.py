#!/usr/bin/env python3
"""
Hybrid Database Initialization Script

This script initializes both PostgreSQL and Qdrant databases with:
1. PostgreSQL schema and tables
2. System admin tenant with API key
3. Qdrant connection verification
4. Proper configuration for the RAG platform

Usage:
    python scripts/db-init.py
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.backend.database import init_database, AsyncSessionLocal
from src.backend.services.tenant_service import TenantService
from src.backend.models.database import User
from sqlalchemy import select

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HybridDatabaseInitializer:
    """Handles hybrid PostgreSQL + Qdrant database initialization."""
    
    def print_banner(self):
        """Print initialization banner."""
        print("🚀 Hybrid Database Initialization (PostgreSQL + Qdrant)")
        print("=" * 60)
        print("PostgreSQL: Control plane, tenant management, file metadata")
        print("Qdrant: Vector storage for embeddings")
        print()
    
    async def check_postgresql_connection(self) -> bool:
        """Check if PostgreSQL is accessible and initialize schema."""
        try:
            logger.info("Initializing PostgreSQL database...")
            
            # Initialize database schema
            await init_database()
            
            # Test connection with a simple query
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(1))
                result.scalar()
            
            logger.info("✅ PostgreSQL connected and schema initialized")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to PostgreSQL: {e}")
            logger.error("   Please ensure PostgreSQL is running and accessible")
            return False
    
    def check_qdrant_connection(self) -> bool:
        """Check if Qdrant is accessible."""
        try:
            import requests
            
            logger.info("Checking Qdrant connection...")
            
            # Test basic connection
            response = requests.get("http://localhost:6333/collections", timeout=5)
            response.raise_for_status()
            
            collections = response.json()
            logger.info(f"✅ Successfully connected to Qdrant")
            logger.info(f"   Found {len(collections.get('result', {}).get('collections', []))} existing collections")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Qdrant: {e}")
            logger.error("   Please ensure Qdrant is running and accessible")
            return False
    
    async def create_system_user(self) -> Dict[str, Any]:
        """Create or get the system user for file uploads."""
        logger.info("Creating/getting system user...")
        
        try:
            async with AsyncSessionLocal() as session:
                # Check if system user exists
                result = await session.execute(
                    select(User).where(User.email == 'system@rag-platform.local')
                )
                system_user = result.scalar_one_or_none()
                
                if system_user:
                    logger.info(f"✅ System user already exists: {system_user.id}")
                    return {
                        "user_id": system_user.id,
                        "email": system_user.email,
                        "full_name": system_user.full_name
                    }
                
                # Create system user
                system_user = User(
                    email='system@rag-platform.local',
                    password_hash='system_user_no_login',
                    full_name='System User for File Operations',
                    is_active=True
                )
                session.add(system_user)
                await session.commit()
                await session.refresh(system_user)
                
                logger.info(f"✅ Created system user: {system_user.id}")
                return {
                    "user_id": system_user.id,
                    "email": system_user.email,
                    "full_name": system_user.full_name
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to create system user: {e}")
            raise
    
    async def create_admin_tenant(self) -> Dict[str, Any]:
        """Create the admin tenant with API key."""
        logger.info("Creating admin tenant...")
        
        try:
            async with AsyncSessionLocal() as session:
                tenant_service = TenantService(session)
                
                # Check if admin tenant already exists
                tenants = await tenant_service.list_tenants()
                admin_tenant = next((t for t in tenants if t.get("slug") == "system-admin"), None)
                
                if admin_tenant:
                    logger.info(f"✅ Admin tenant already exists: {admin_tenant['name']}")
                    logger.info(f"   Tenant ID: {admin_tenant['id']}")
                    return {
                        "tenant_id": admin_tenant["id"],
                        "name": admin_tenant["name"],
                        "api_key": "EXISTING_KEY"  # We can't retrieve the actual key
                    }
                
                # Create new admin tenant
                result = await tenant_service.create_tenant(
                    name="System Admin",
                    description="Default administrative tenant for the RAG platform",
                    auto_sync=True,
                    sync_interval=60
                )
                
                logger.info(f"✅ Successfully created admin tenant")
                logger.info(f"   Tenant ID: {result['id']}")
                logger.info(f"   API Key: {result['api_key']}")
                
                return {
                    "tenant_id": result["id"],
                    "name": "System Admin",
                    "api_key": result["api_key"]
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to create admin tenant: {e}")
            raise
    
    async def verify_initialization(self, admin_tenant: Dict[str, Any], system_user: Dict[str, Any]) -> bool:
        """Verify that initialization was successful."""
        try:
            logger.info("Verifying initialization...")
            
            async with AsyncSessionLocal() as session:
                tenant_service = TenantService(session)
                
                # Check admin tenant exists
                tenants = await tenant_service.list_tenants()
                admin_exists = any(str(t["id"]) == str(admin_tenant["tenant_id"]) for t in tenants)
                
                if not admin_exists:
                    logger.error("❌ Admin tenant not found in verification")
                    return False
                
                # Check system user exists
                result = await session.execute(
                    select(User).where(User.id == system_user["user_id"])
                )
                user_exists = result.scalar_one_or_none() is not None
                
                if not user_exists:
                    logger.error("❌ System user not found in verification")
                    return False
                
                logger.info("✅ All verifications passed")
                return True
                
        except Exception as e:
            logger.error(f"❌ Verification failed: {e}")
            return False
    
    def print_summary(self, admin_tenant: Dict[str, Any], system_user: Dict[str, Any]):
        """Print initialization summary."""
        print("\n" + "=" * 60)
        print("🎉 HYBRID DATABASE INITIALIZATION COMPLETE")
        print("=" * 60)
        print(f"PostgreSQL: ✅ Schema created, ready for metadata")
        print(f"Qdrant: ✅ Connected, ready for vectors")
        print()
        print(f"System User ID: {system_user['user_id']}")
        print(f"System User Email: {system_user['email']}")
        print()
        print(f"Admin Tenant ID: {admin_tenant['tenant_id']}")
        print(f"Admin Tenant Name: {admin_tenant['name']}")
        
        if admin_tenant['api_key'] != "EXISTING_KEY":
            print(f"Admin API Key: {admin_tenant['api_key']}")
            print("\n⚠️  IMPORTANT: Save this API key securely!")
            print("   You'll need it to access the admin tenant.")
        
        print("\nNext Steps:")
        print("  1. Use the admin API key in your API requests")
        print("  2. Start the backend server with Docker Compose")
        print("  3. Upload documents using scripts/delta-sync.py")
        print("  4. Test with scripts/test_ml_pipeline.py")
        print("=" * 60)
    
    async def run(self) -> bool:
        """Run the complete initialization process."""
        self.print_banner()
        
        # Step 1: Check PostgreSQL connection and initialize schema
        if not await self.check_postgresql_connection():
            return False
        
        # Step 2: Check Qdrant connection
        if not self.check_qdrant_connection():
            return False
        
        # Step 3: Create system user
        try:
            system_user = await self.create_system_user()
        except Exception as e:
            logger.error(f"Failed to create system user: {e}")
            return False
        
        # Step 4: Create admin tenant
        try:
            admin_tenant = await self.create_admin_tenant()
        except Exception as e:
            logger.error(f"Failed to create admin tenant: {e}")
            return False
        
        # Step 5: Verify initialization
        if not await self.verify_initialization(admin_tenant, system_user):
            return False
        
        # Step 6: Print summary
        self.print_summary(admin_tenant, system_user)
        
        return True

async def main():
    """Main entry point."""
    try:
        initializer = HybridDatabaseInitializer()
        success = await initializer.run()
        
        if success:
            logger.info("✅ Database initialization completed successfully")
            sys.exit(0)
        else:
            logger.error("❌ Database initialization failed")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("\n🛑 Initialization interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error during initialization: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())