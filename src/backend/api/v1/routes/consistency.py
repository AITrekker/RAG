"""
Consistency and Recovery API Routes
Provides endpoints for checking data consistency and performing recovery operations
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime

from src.backend.dependencies import get_db_session, get_current_tenant_id
from src.backend.services.consistency_checker import (
    get_consistency_checker,
    ConsistencyChecker,
    ConsistencyStats,
    InconsistencyReport
)
from src.backend.services.recovery_service import (
    get_recovery_service,
    RecoveryService,
    RecoveryPlan,
    RecoveryAction
)
from src.backend.services.embedding_service import get_embedding_service
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/consistency", tags=["consistency"])


@router.get("/check/{tenant_id}", response_model=Dict[str, Any])
async def check_tenant_consistency(
    tenant_id: UUID,
    environment: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Perform comprehensive consistency check for a tenant
    
    Returns detailed statistics and list of detected inconsistencies
    """
    try:
        consistency_checker = await get_consistency_checker(db)
        
        stats, inconsistencies = await consistency_checker.check_tenant_consistency(
            tenant_id, environment
        )
        
        # Convert to API response format
        return {
            "tenant_id": str(tenant_id),
            "environment": environment,
            "stats": {
                "total_files": stats.total_files,
                "synced_files": stats.synced_files,
                "files_with_chunks": stats.files_with_chunks,
                "total_chunks": stats.total_chunks,
                "files_missing_embeddings": stats.files_missing_embeddings,
                "orphaned_chunks": stats.orphaned_chunks,
                "stuck_processing_files": stats.stuck_processing_files,
                "consistency_score": stats.consistency_score,
                "last_checked": stats.last_checked.isoformat()
            },
            "inconsistencies": [
                {
                    "type": inc.inconsistency_type.value,
                    "severity": inc.severity.value,
                    "file_id": str(inc.file_id) if inc.file_id else None,
                    "file_path": inc.file_path,
                    "description": inc.description,
                    "details": inc.details,
                    "detected_at": inc.detected_at.isoformat(),
                    "repair_action": inc.repair_action,
                    "estimated_impact": inc.estimated_impact
                }
                for inc in inconsistencies
            ],
            "summary": {
                "total_inconsistencies": len(inconsistencies),
                "critical_issues": len([i for i in inconsistencies if i.severity.value == "critical"]),
                "high_issues": len([i for i in inconsistencies if i.severity.value == "high"]),
                "medium_issues": len([i for i in inconsistencies if i.severity.value == "medium"]),
                "low_issues": len([i for i in inconsistencies if i.severity.value == "low"])
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Consistency check failed: {str(e)}")


@router.get("/check-all", response_model=Dict[str, Any])
async def check_all_tenants_consistency(
    environment: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Check consistency across all tenants
    
    Returns aggregated results for all tenants
    """
    try:
        consistency_checker = await get_consistency_checker(db)
        
        all_results = await consistency_checker.check_all_tenants_consistency(environment)
        
        # Aggregate statistics
        total_tenants = len(all_results)
        total_inconsistencies = 0
        tenants_with_issues = 0
        overall_score = 0.0
        
        tenant_summaries = {}
        
        for tenant_id, (stats, inconsistencies) in all_results.items():
            inconsistency_count = len(inconsistencies)
            total_inconsistencies += inconsistency_count
            
            if inconsistency_count > 0:
                tenants_with_issues += 1
            
            overall_score += stats.consistency_score
            
            tenant_summaries[tenant_id] = {
                "consistency_score": stats.consistency_score,
                "total_files": stats.total_files,
                "inconsistencies": inconsistency_count,
                "critical_issues": len([i for i in inconsistencies if i.severity.value == "critical"]),
                "high_issues": len([i for i in inconsistencies if i.severity.value == "high"]),
                "last_checked": stats.last_checked.isoformat()
            }
        
        average_score = overall_score / total_tenants if total_tenants > 0 else 100.0
        
        return {
            "environment": environment,
            "summary": {
                "total_tenants": total_tenants,
                "tenants_with_issues": tenants_with_issues,
                "total_inconsistencies": total_inconsistencies,
                "average_consistency_score": round(average_score, 2),
                "checked_at": datetime.utcnow().isoformat()
            },
            "tenant_results": tenant_summaries
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Multi-tenant consistency check failed: {str(e)}")


@router.post("/recovery/plan/{tenant_id}", response_model=Dict[str, Any])
async def create_recovery_plan(
    tenant_id: UUID,
    environment: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Create a recovery plan for a tenant based on consistency issues
    
    Returns a detailed plan with prioritized recovery actions
    """
    try:
        embedding_service = await get_embedding_service(db)
        recovery_service = await get_recovery_service(db, embedding_service)
        
        recovery_plan = await recovery_service.create_recovery_plan(tenant_id, environment)
        
        return {
            "plan_id": recovery_plan.plan_id,
            "tenant_id": str(recovery_plan.tenant_id),
            "created_at": recovery_plan.created_at.isoformat(),
            "total_estimated_duration": recovery_plan.total_estimated_duration,
            "total_actions": len(recovery_plan.actions),
            "actions": [
                {
                    "action_id": action.action_id,
                    "action_type": action.action_type.value,
                    "file_id": str(action.file_id) if action.file_id else None,
                    "description": action.description,
                    "priority": action.priority,
                    "estimated_duration_seconds": action.estimated_duration_seconds,
                    "status": action.status.value,
                    "details": action.details
                }
                for action in recovery_plan.actions
            ],
            "execution_order": recovery_plan.priority_order,
            "summary": {
                "high_priority_actions": len([a for a in recovery_plan.actions if a.priority <= 2]),
                "estimated_total_time": f"{recovery_plan.total_estimated_duration // 60} minutes {recovery_plan.total_estimated_duration % 60} seconds"
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recovery plan creation failed: {str(e)}")


@router.post("/recovery/execute/{tenant_id}", response_model=Dict[str, Any])
async def execute_recovery_plan(
    tenant_id: UUID,
    background_tasks: BackgroundTasks,
    environment: Optional[str] = None,
    max_concurrent: int = 3,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Execute a recovery plan for a tenant
    
    Creates and executes recovery actions in the background
    """
    try:
        embedding_service = await get_embedding_service(db)
        recovery_service = await get_recovery_service(db, embedding_service)
        
        # Create recovery plan
        recovery_plan = await recovery_service.create_recovery_plan(tenant_id, environment)
        
        if not recovery_plan.actions:
            return {
                "plan_id": recovery_plan.plan_id,
                "tenant_id": str(tenant_id),
                "status": "no_actions_needed",
                "message": "No recovery actions required - tenant is consistent"
            }
        
        # Execute recovery plan in background
        async def execute_plan():
            try:
                result = await recovery_service.execute_recovery_plan(recovery_plan, max_concurrent)
                print(f"✓ Recovery plan {recovery_plan.plan_id} completed: {result}")
            except Exception as e:
                print(f"⚠️ Recovery plan {recovery_plan.plan_id} failed: {str(e)}")
        
        background_tasks.add_task(execute_plan)
        
        return {
            "plan_id": recovery_plan.plan_id,
            "tenant_id": str(tenant_id),
            "status": "executing",
            "total_actions": len(recovery_plan.actions),
            "estimated_duration_seconds": recovery_plan.total_estimated_duration,
            "message": f"Recovery plan started with {len(recovery_plan.actions)} actions"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recovery execution failed: {str(e)}")


@router.post("/recovery/quick-fix/{tenant_id}", response_model=Dict[str, Any])
async def quick_fix_tenant(
    tenant_id: UUID,
    environment: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Perform quick fixes for common issues (non-destructive operations only)
    
    Resets stuck files and operations without data loss
    """
    try:
        embedding_service = await get_embedding_service(db)
        recovery_service = await get_recovery_service(db, embedding_service)
        
        results = await recovery_service.quick_fix_tenant(tenant_id, environment)
        
        return {
            "tenant_id": results["tenant_id"],
            "fixes_applied": results["fixes_applied"],
            "errors": results["errors"],
            "success": len(results["errors"]) == 0,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quick fix failed: {str(e)}")


@router.get("/recovery/status", response_model=Dict[str, Any])
async def get_recovery_status(
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get status of currently active recovery operations
    
    Returns information about ongoing recovery actions
    """
    try:
        embedding_service = await get_embedding_service(db)
        recovery_service = await get_recovery_service(db, embedding_service)
        
        active_recoveries = await recovery_service.get_active_recoveries()
        
        return {
            "active_recoveries": len(active_recoveries),
            "recoveries": active_recoveries,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get recovery status: {str(e)}")


@router.post("/repair-recommendations/{tenant_id}", response_model=Dict[str, Any])
async def get_repair_recommendations(
    tenant_id: UUID,
    environment: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get actionable repair recommendations for detected inconsistencies
    
    Returns detailed repair plan without executing it
    """
    try:
        consistency_checker = await get_consistency_checker(db)
        
        stats, inconsistencies = await consistency_checker.check_tenant_consistency(
            tenant_id, environment
        )
        
        if not inconsistencies:
            return {
                "tenant_id": str(tenant_id),
                "status": "healthy",
                "message": "No inconsistencies detected",
                "recommendations": []
            }
        
        repair_plan = await consistency_checker.generate_repair_plan(inconsistencies)
        
        return {
            "tenant_id": str(tenant_id),
            "consistency_score": stats.consistency_score,
            "total_inconsistencies": len(inconsistencies),
            "repair_recommendations": repair_plan,
            "total_estimated_time": sum(
                action.get("estimated_time_minutes", 0) 
                for action in repair_plan
            ),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate repair recommendations: {str(e)}")


@router.get("/health-summary", response_model=Dict[str, Any])
async def get_system_health_summary(
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get overall system health summary
    
    Returns high-level health metrics across all tenants
    """
    try:
        consistency_checker = await get_consistency_checker(db)
        
        # Get basic database statistics
        from sqlalchemy import func, select
        from src.backend.models.database import File, EmbeddingChunk, SyncOperation
        
        # Total files across all tenants
        total_files_result = await db.execute(select(func.count(File.id)))
        total_files = total_files_result.scalar() or 0
        
        # Files by status
        synced_files_result = await db.execute(
            select(func.count(File.id)).where(File.sync_status == 'synced')
        )
        synced_files = synced_files_result.scalar() or 0
        
        processing_files_result = await db.execute(
            select(func.count(File.id)).where(File.sync_status == 'processing')
        )
        processing_files = processing_files_result.scalar() or 0
        
        failed_files_result = await db.execute(
            select(func.count(File.id)).where(File.sync_status == 'failed')
        )
        failed_files = failed_files_result.scalar() or 0
        
        # Total chunks
        total_chunks_result = await db.execute(select(func.count(EmbeddingChunk.id)))
        total_chunks = total_chunks_result.scalar() or 0
        
        # Active sync operations
        active_syncs_result = await db.execute(
            select(func.count(SyncOperation.id)).where(SyncOperation.status == 'running')
        )
        active_syncs = active_syncs_result.scalar() or 0
        
        # Calculate health score
        if total_files > 0:
            health_score = (synced_files / total_files) * 100
        else:
            health_score = 100.0
        
        return {
            "system_health": {
                "overall_score": round(health_score, 2),
                "status": "healthy" if health_score >= 95 else "warning" if health_score >= 80 else "critical"
            },
            "file_statistics": {
                "total_files": total_files,
                "synced_files": synced_files,
                "processing_files": processing_files,
                "failed_files": failed_files,
                "sync_rate": round(synced_files / total_files * 100, 2) if total_files > 0 else 0
            },
            "embedding_statistics": {
                "total_chunks": total_chunks,
                "average_chunks_per_file": round(total_chunks / synced_files, 2) if synced_files > 0 else 0
            },
            "sync_operations": {
                "active_syncs": active_syncs
            },
            "recommendations": [
                "Consider running consistency check if sync rate is below 95%",
                "Monitor processing files - they may be stuck if count is high",
                "Investigate failed files for common error patterns"
            ] if health_score < 95 else ["System is healthy"],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get system health summary: {str(e)}") 