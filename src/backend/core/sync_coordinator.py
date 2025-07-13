"""
Sync Coordinator - Orchestrates the Complete Sync Process
Combines discovery, embedding generation, and database operations
"""

from typing import Dict, Any
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.core.document_discovery import create_sync_plan, get_sync_summary, SyncPlan
from src.backend.core.embedding_engine import (
    EmbeddingConfig, 
    process_file_to_embeddings,
    EmbeddingModel,
    ChunkingStrategy
)
from src.backend.core.database_operations import (
    create_file_record,
    update_file_record,
    delete_file_record,
    save_embeddings,
    set_file_status,
    get_tenant_stats
)


class SyncCoordinator:
    """Main coordinator for sync operations"""
    
    def __init__(self, db: AsyncSession, upload_dir: str = "./data/uploads"):
        self.db = db
        self.upload_dir = upload_dir
        self.default_config = EmbeddingConfig()
    
    async def discover_changes(
        self, 
        tenant_slug: str, 
        force_full_sync: bool = False
    ) -> SyncPlan:
        """Discover what files need syncing"""
        return await create_sync_plan(self.db, tenant_slug, force_full_sync)
    
    async def process_single_file(
        self,
        tenant_slug: str,
        file_info,
        config: EmbeddingConfig,
        is_new_file: bool = True,
        existing_file_record = None
    ) -> Dict[str, Any]:
        """Process a single file: extract text, generate embeddings, save to DB"""
        
        file_path = Path(self.upload_dir) / file_info.path
        result = {
            "file_name": file_info.name,
            "success": False,
            "chunks_created": 0,
            "error": None
        }
        
        try:
            print(f"📄 Processing {file_info.name}...")
            
            # Create or update file record
            if is_new_file:
                file_record = await create_file_record(self.db, tenant_slug, file_info)
            else:
                file_record = await update_file_record(self.db, existing_file_record, file_info)
            
            # Generate embeddings
            embedded_chunks = process_file_to_embeddings(file_path, config)
            
            if not embedded_chunks:
                await set_file_status(self.db, file_record, "failed", "No embeddings generated")
                result["error"] = "No meaningful content or embeddings generated"
                return result
            
            # Save embeddings to database
            chunks_saved = await save_embeddings(self.db, file_record, embedded_chunks)
            
            # Mark as completed
            await set_file_status(self.db, file_record, "completed")
            
            result.update({
                "success": True,
                "chunks_created": chunks_saved
            })
            
            print(f"   ✅ Processed {file_info.name}: {chunks_saved} chunks")
            
        except Exception as e:
            error_msg = f"Error processing {file_info.name}: {str(e)}"
            print(f"   ❌ {error_msg}")
            
            if 'file_record' in locals():
                await set_file_status(self.db, file_record, "failed", str(e))
            
            result["error"] = str(e)
        
        return result
    
    async def execute_sync_plan(
        self,
        tenant_slug: str,
        plan: SyncPlan,
        config: EmbeddingConfig = None
    ) -> Dict[str, Any]:
        """Execute a complete sync plan"""
        
        if config is None:
            config = self.default_config
        
        results = {
            "tenant_slug": tenant_slug,
            "total_changes": plan.total_changes,
            "files_processed": 0,
            "total_chunks_created": 0,
            "new_files_processed": 0,
            "updated_files_processed": 0,
            "deleted_files_processed": 0,
            "successful_files": [],
            "failed_files": [],
            "config_used": {
                "model": config.model.value,
                "chunking": config.chunking.value,
                "chunk_size": config.chunk_size,
                "chunk_overlap": config.chunk_overlap
            }
        }
        
        try:
            # Process new files
            print(f"\n🔄 Processing {len(plan.new_files)} new files...")
            for file_info in plan.new_files:
                result = await self.process_single_file(
                    tenant_slug, file_info, config, is_new_file=True
                )
                
                results["files_processed"] += 1
                if result["success"]:
                    results["new_files_processed"] += 1
                    results["total_chunks_created"] += result["chunks_created"]
                    results["successful_files"].append(result["file_name"])
                else:
                    results["failed_files"].append({
                        "file_name": result["file_name"],
                        "error": result["error"]
                    })
            
            # Process updated files
            print(f"\n🔄 Processing {len(plan.updated_files)} updated files...")
            for db_file, file_info in plan.updated_files:
                result = await self.process_single_file(
                    tenant_slug, file_info, config, 
                    is_new_file=False, existing_file_record=db_file
                )
                
                results["files_processed"] += 1
                if result["success"]:
                    results["updated_files_processed"] += 1
                    results["total_chunks_created"] += result["chunks_created"]
                    results["successful_files"].append(result["file_name"])
                else:
                    results["failed_files"].append({
                        "file_name": result["file_name"],
                        "error": result["error"]
                    })
            
            # Process deleted files
            print(f"\n🗑️ Processing {len(plan.deleted_files)} deleted files...")
            for db_file in plan.deleted_files:
                try:
                    await delete_file_record(self.db, db_file)
                    results["deleted_files_processed"] += 1
                    print(f"   🗑️ Deleted {db_file.filename}")
                except Exception as e:
                    print(f"   ❌ Failed to delete {db_file.filename}: {e}")
                    results["failed_files"].append({
                        "file_name": db_file.filename,
                        "error": f"Delete failed: {str(e)}"
                    })
            
            print(f"\n✅ Sync completed for {tenant_slug}")
            print(f"   📊 Files processed: {results['files_processed']}")
            print(f"   📦 Chunks created: {results['total_chunks_created']}")
            print(f"   ✅ Successful: {len(results['successful_files'])}")
            print(f"   ❌ Failed: {len(results['failed_files'])}")
            
        except Exception as e:
            print(f"\n💥 Sync failed for {tenant_slug}: {e}")
            results["sync_error"] = str(e)
        
        return results
    
    async def quick_sync(
        self,
        tenant_slug: str,
        force_full_sync: bool = False,
        embedding_model: str = None,
        chunking_strategy: str = None
    ) -> Dict[str, Any]:
        """Complete sync operation in one call"""
        
        # Create config
        config = EmbeddingConfig()
        if embedding_model:
            try:
                config.model = EmbeddingModel(embedding_model)
            except ValueError:
                pass  # Use default
        
        if chunking_strategy:
            try:
                config.chunking = ChunkingStrategy(chunking_strategy)
            except ValueError:
                pass  # Use default
        
        # Discover changes
        plan = await self.discover_changes(tenant_slug, force_full_sync)
        
        if plan.total_changes == 0:
            stats = await get_tenant_stats(self.db, tenant_slug)
            return {
                "message": f"No changes detected for {tenant_slug}",
                "changes_detected": 0,
                "current_stats": stats
            }
        
        # Execute sync
        results = await self.execute_sync_plan(tenant_slug, plan, config)
        
        # Get final stats
        final_stats = await get_tenant_stats(self.db, tenant_slug)
        results["final_stats"] = final_stats
        
        return results
    
    async def get_sync_status(self, tenant_slug: str) -> Dict[str, Any]:
        """Get current sync status for tenant"""
        stats = await get_tenant_stats(self.db, tenant_slug)
        
        # Check if any files are currently processing
        processing_files = [f.filename for f in stats["files_by_status"]["processing"]]
        
        return {
            "tenant_slug": tenant_slug,
            "total_files": stats["total_files"],
            "total_chunks": stats["total_chunks"],
            "status_breakdown": stats["status_breakdown"],
            "currently_processing": processing_files,
            "is_syncing": len(processing_files) > 0
        }