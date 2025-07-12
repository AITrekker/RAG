#!/usr/bin/env python3
"""
Simplified Delta Sync Script - Works with new simplified architecture

This script uses the new simplified services to process tenant documents:
1. Uses UnifiedDocumentProcessor for all file types
2. Uses MultiTenantRAGService for LlamaIndex integration  
3. Uses SimplifiedEmbeddingService for tracking

Much simpler than the old complex dual-path approach.
"""

import os
import sys
import asyncio
from pathlib import Path
from typing import List, Dict, Any
from uuid import UUID
from dotenv import load_dotenv

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

async def simplified_delta_sync():
    """Run delta sync using the new simplified architecture"""
    try:
        # Import new simplified services
        from src.backend.dependencies import get_db_session
        from src.backend.services.multitenant_rag_service import MultiTenantRAGService
        from src.backend.services.unified_document_processor import UnifiedDocumentProcessor
        from src.backend.services.simplified_embedding_service import SimplifiedEmbeddingService
        from src.backend.services.file_service import FileService
        from src.backend.dependencies import get_embedding_model
        from src.backend.models.database import Tenant, File
        from sqlalchemy import select
        from src.backend.config.settings import get_settings
        
        settings = get_settings()
        embedding_model = get_embedding_model()
        
        print("🚀 Starting Simplified Delta Sync")
        print("=" * 50)
        
        # Get database session
        async with get_db_session() as db:
            # Initialize services
            file_service = FileService(db)
            rag_service = MultiTenantRAGService(db, file_service, embedding_model)
            await rag_service.initialize()
            
            document_processor = UnifiedDocumentProcessor(db, rag_service)
            await document_processor.initialize()
            
            embedding_service = SimplifiedEmbeddingService(
                db=db,
                embedding_model=embedding_model,
                document_processor=document_processor,
                rag_service=rag_service
            )
            
            # Get all active tenants
            result = await db.execute(
                select(Tenant).where(Tenant.is_active == True)
            )
            tenants = result.scalars().all()
            
            if not tenants:
                print("⚠️ No active tenants found")
                return
            
            print(f"Found {len(tenants)} active tenants")
            
            total_stats = {
                'tenants_processed': 0,
                'files_processed': 0,
                'files_successful': 0,
                'files_failed': 0
            }
            
            # Process each tenant
            for tenant in tenants:
                print(f"\n📁 Processing tenant: {tenant.name} ({tenant.slug})")
                
                # Get files that need processing
                result = await db.execute(
                    select(File).where(
                        File.tenant_id == tenant.id,
                        File.sync_status.in_(['pending', 'failed']),
                        File.deleted_at.is_(None)
                    )
                )
                files_to_process = result.scalars().all()
                
                if not files_to_process:
                    print("  ✓ No files need processing")
                    continue
                
                print(f"  Found {len(files_to_process)} files to process")
                
                # Process files using simplified service
                stats = await embedding_service.process_multiple_files(files_to_process)
                
                print(f"  Results: {stats['successful']} successful, {stats['failed']} failed")
                
                total_stats['tenants_processed'] += 1
                total_stats['files_processed'] += stats['total_files']
                total_stats['files_successful'] += stats['successful']
                total_stats['files_failed'] += stats['failed']
            
            # Print summary
            print("\n" + "=" * 50)
            print("📊 Delta Sync Complete")
            print(f"Tenants processed: {total_stats['tenants_processed']}")
            print(f"Files processed: {total_stats['files_processed']}")
            print(f"Successful: {total_stats['files_successful']}")
            print(f"Failed: {total_stats['files_failed']}")
            
            success_rate = (total_stats['files_successful'] / max(1, total_stats['files_processed'])) * 100
            print(f"Success rate: {success_rate:.1f}%")
            
            if total_stats['files_failed'] > 0:
                print("⚠️ Some files failed processing - check logs for details")
                return False
            else:
                print("✅ All files processed successfully!")
                return True
                
    except Exception as e:
        print(f"❌ Delta sync failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def get_processing_stats():
    """Get current processing statistics"""
    try:
        from src.backend.dependencies import get_db_session
        from src.backend.services.multitenant_rag_service import MultiTenantRAGService
        from src.backend.services.file_service import FileService
        from src.backend.dependencies import get_embedding_model
        from src.backend.models.database import Tenant, File
        from sqlalchemy import select, func
        
        embedding_model = get_embedding_model()
        
        async with get_db_session() as db:
            file_service = FileService(db)
            rag_service = MultiTenantRAGService(db, file_service, embedding_model)
            
            # Get file status counts
            result = await db.execute(
                select(
                    File.sync_status,
                    func.count(File.id).label('count')
                ).where(
                    File.deleted_at.is_(None)
                ).group_by(File.sync_status)
            )
            
            status_counts = {row.sync_status: row.count for row in result.fetchall()}
            
            print("\n📊 Current File Status:")
            for status, count in status_counts.items():
                print(f"  {status}: {count}")
            
            return status_counts
            
    except Exception as e:
        print(f"❌ Error getting stats: {e}")
        return {}

def main():
    """Main entry point"""
    load_dotenv()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--stats":
        print("📊 Getting current processing statistics...")
        asyncio.run(get_processing_stats())
        return
    
    print("🚀 Simplified Delta Sync using new architecture")
    print("Uses: MultiTenantRAGService + UnifiedDocumentProcessor + SimplifiedEmbeddingService")
    print()
    
    success = asyncio.run(simplified_delta_sync())
    
    if success:
        print("\n✅ Delta sync completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Delta sync failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()