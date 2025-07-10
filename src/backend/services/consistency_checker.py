"""
Consistency Checker Service - Detects and reports data inconsistencies between PostgreSQL and Qdrant
Provides detailed analysis and repair recommendations for maintaining data integrity
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Set, Any, Optional, Tuple
from uuid import UUID
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from src.backend.models.database import File, EmbeddingChunk, SyncOperation
from src.backend.config.settings import get_settings

settings = get_settings()


class InconsistencyType(Enum):
    """Types of data inconsistencies"""
    MISSING_EMBEDDINGS = "missing_embeddings"  # File synced but no embeddings in Qdrant
    ORPHANED_EMBEDDINGS = "orphaned_embeddings"  # Embeddings in Qdrant but no file record
    MISSING_CHUNKS = "missing_chunks"  # File record exists but no chunk records in PostgreSQL
    ORPHANED_CHUNKS = "orphaned_chunks"  # Chunk records exist but no file record
    QDRANT_POSTGRES_MISMATCH = "qdrant_postgres_mismatch"  # Different chunk counts
    STUCK_PROCESSING = "stuck_processing"  # Files stuck in processing state
    STALE_EMBEDDINGS = "stale_embeddings"  # Embeddings older than file modification


class Severity(Enum):
    """Severity levels for inconsistencies"""
    CRITICAL = "critical"  # Data loss or corruption
    HIGH = "high"  # Functional impact on search
    MEDIUM = "medium"  # Performance or accuracy impact
    LOW = "low"  # Minor inconsistencies


@dataclass
class InconsistencyReport:
    """Report of a detected inconsistency"""
    inconsistency_type: InconsistencyType
    severity: Severity
    tenant_id: UUID
    file_id: Optional[UUID]
    file_path: Optional[str]
    description: str
    details: Dict[str, Any]
    detected_at: datetime
    repair_action: str
    estimated_impact: str


@dataclass
class ConsistencyStats:
    """Overall consistency statistics"""
    tenant_id: UUID
    total_files: int
    synced_files: int
    files_with_chunks: int
    total_chunks: int
    files_missing_embeddings: int
    orphaned_chunks: int
    stuck_processing_files: int
    stale_embeddings_files: int
    consistency_score: float  # 0-100%
    last_checked: datetime


class ConsistencyChecker:
    """Service for checking data consistency between PostgreSQL and Qdrant"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self._qdrant_client = None
        
    async def _ensure_qdrant_client(self):
        """Initialize Qdrant client if not already done"""
        if self._qdrant_client is None:
            try:
                from qdrant_client import QdrantClient
                self._qdrant_client = QdrantClient(
                    host=settings.qdrant_host,
                    port=settings.qdrant_port
                )
            except ImportError:
                print("⚠️ qdrant-client not available for consistency checking")
                self._qdrant_client = None
            except Exception as e:
                print(f"⚠️ Failed to connect to Qdrant: {e}")
                self._qdrant_client = None
    
    async def check_tenant_consistency(
        self, 
        tenant_id: UUID, 
        environment: str = None
    ) -> Tuple[ConsistencyStats, List[InconsistencyReport]]:
        """
        Perform comprehensive consistency check for a tenant
        
        Args:
            tenant_id: Tenant to check
            environment: Target environment (defaults to current)
            
        Returns:
            Tuple[ConsistencyStats, List[InconsistencyReport]]: Stats and detailed issues
        """
        import os
        
        current_env = environment or os.getenv("RAG_ENVIRONMENT", "development")
        collection_name = f"documents_{current_env}"
        
        await self._ensure_qdrant_client()
        
        # Gather basic statistics
        stats = await self._gather_consistency_stats(tenant_id)
        
        # Perform detailed consistency checks
        inconsistencies = []
        
        # Check for missing embeddings
        missing_embeddings = await self._check_missing_embeddings(tenant_id, collection_name)
        inconsistencies.extend(missing_embeddings)
        
        # Check for orphaned chunks
        orphaned_chunks = await self._check_orphaned_chunks(tenant_id)
        inconsistencies.extend(orphaned_chunks)
        
        # Check for files stuck in processing
        stuck_files = await self._check_stuck_processing_files(tenant_id)
        inconsistencies.extend(stuck_files)
        
        # Check for Qdrant/PostgreSQL mismatches
        if self._qdrant_client:
            qdrant_mismatches = await self._check_qdrant_postgres_mismatches(tenant_id, collection_name)
            inconsistencies.extend(qdrant_mismatches)
            
            # Check for orphaned embeddings in Qdrant
            orphaned_embeddings = await self._check_orphaned_embeddings(tenant_id, collection_name)
            inconsistencies.extend(orphaned_embeddings)
        
        # Update statistics with inconsistency counts
        stats.files_missing_embeddings = len([i for i in inconsistencies if i.inconsistency_type == InconsistencyType.MISSING_EMBEDDINGS])
        stats.orphaned_chunks = len([i for i in inconsistencies if i.inconsistency_type == InconsistencyType.ORPHANED_CHUNKS])
        stats.stuck_processing_files = len([i for i in inconsistencies if i.inconsistency_type == InconsistencyType.STUCK_PROCESSING])
        
        # Calculate consistency score
        stats.consistency_score = self._calculate_consistency_score(stats, inconsistencies)
        stats.last_checked = datetime.utcnow()
        
        return stats, inconsistencies
    
    async def _gather_consistency_stats(self, tenant_id: UUID) -> ConsistencyStats:
        """Gather basic consistency statistics"""
        
        # Count total files
        total_files_result = await self.db.execute(
            select(func.count(File.id)).where(File.tenant_id == tenant_id)
        )
        total_files = total_files_result.scalar() or 0
        
        # Count synced files
        synced_files_result = await self.db.execute(
            select(func.count(File.id)).where(
                and_(
                    File.tenant_id == tenant_id,
                    File.sync_status == 'synced'
                )
            )
        )
        synced_files = synced_files_result.scalar() or 0
        
        # Count files with chunks
        files_with_chunks_result = await self.db.execute(
            select(func.count(func.distinct(EmbeddingChunk.file_id))).where(
                EmbeddingChunk.tenant_id == tenant_id
            )
        )
        files_with_chunks = files_with_chunks_result.scalar() or 0
        
        # Count total chunks
        total_chunks_result = await self.db.execute(
            select(func.count(EmbeddingChunk.id)).where(
                EmbeddingChunk.tenant_id == tenant_id
            )
        )
        total_chunks = total_chunks_result.scalar() or 0
        
        return ConsistencyStats(
            tenant_id=tenant_id,
            total_files=total_files,
            synced_files=synced_files,
            files_with_chunks=files_with_chunks,
            total_chunks=total_chunks,
            files_missing_embeddings=0,  # Will be filled later
            orphaned_chunks=0,  # Will be filled later
            stuck_processing_files=0,  # Will be filled later
            stale_embeddings_files=0,  # Will be filled later
            consistency_score=0.0,  # Will be calculated later
            last_checked=datetime.utcnow()
        )
    
    async def _check_missing_embeddings(
        self, 
        tenant_id: UUID, 
        collection_name: str
    ) -> List[InconsistencyReport]:
        """Check for files marked as synced but missing embeddings"""
        
        inconsistencies = []
        
        # Find files marked as synced but with no embedding chunks
        result = await self.db.execute(
            select(File).outerjoin(
                EmbeddingChunk, File.id == EmbeddingChunk.file_id
            ).where(
                and_(
                    File.tenant_id == tenant_id,
                    File.sync_status == 'synced',
                    EmbeddingChunk.id.is_(None)
                )
            )
        )
        
        files_missing_embeddings = result.scalars().all()
        
        for file_record in files_missing_embeddings:
            inconsistencies.append(InconsistencyReport(
                inconsistency_type=InconsistencyType.MISSING_EMBEDDINGS,
                severity=Severity.HIGH,
                tenant_id=tenant_id,
                file_id=file_record.id,
                file_path=file_record.file_path,
                description=f"File '{file_record.filename}' is marked as synced but has no embedding chunks",
                details={
                    'file_size': file_record.file_size,
                    'sync_completed_at': file_record.sync_completed_at.isoformat() if file_record.sync_completed_at else None,
                    'file_hash': file_record.file_hash
                },
                detected_at=datetime.utcnow(),
                repair_action="Re-process file to generate embeddings",
                estimated_impact="File will not appear in search results"
            ))
        
        return inconsistencies
    
    async def _check_orphaned_chunks(self, tenant_id: UUID) -> List[InconsistencyReport]:
        """Check for embedding chunks without corresponding file records"""
        
        inconsistencies = []
        
        # Find chunks that don't have corresponding file records
        result = await self.db.execute(
            select(EmbeddingChunk).outerjoin(
                File, EmbeddingChunk.file_id == File.id
            ).where(
                and_(
                    EmbeddingChunk.tenant_id == tenant_id,
                    File.id.is_(None)
                )
            )
        )
        
        orphaned_chunks = result.scalars().all()
        
        # Group by file_id for reporting
        orphaned_by_file = {}
        for chunk in orphaned_chunks:
            if chunk.file_id not in orphaned_by_file:
                orphaned_by_file[chunk.file_id] = []
            orphaned_by_file[chunk.file_id].append(chunk)
        
        for file_id, chunks in orphaned_by_file.items():
            inconsistencies.append(InconsistencyReport(
                inconsistency_type=InconsistencyType.ORPHANED_CHUNKS,
                severity=Severity.MEDIUM,
                tenant_id=tenant_id,
                file_id=file_id,
                file_path=None,
                description=f"Found {len(chunks)} orphaned embedding chunks for deleted file",
                details={
                    'chunk_count': len(chunks),
                    'chunk_ids': [str(chunk.id) for chunk in chunks[:5]],  # Sample of chunk IDs
                    'qdrant_point_ids': [str(chunk.qdrant_point_id) for chunk in chunks[:5]]
                },
                detected_at=datetime.utcnow(),
                repair_action="Delete orphaned chunks from PostgreSQL and Qdrant",
                estimated_impact="Wastes storage space and may cause query inconsistencies"
            ))
        
        return inconsistencies
    
    async def _check_stuck_processing_files(self, tenant_id: UUID) -> List[InconsistencyReport]:
        """Check for files stuck in processing state"""
        
        inconsistencies = []
        
        # Find files that have been processing for more than 1 hour
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        
        result = await self.db.execute(
            select(File).where(
                and_(
                    File.tenant_id == tenant_id,
                    File.sync_status == 'processing',
                    or_(
                        File.sync_started_at.is_(None),
                        File.sync_started_at < cutoff_time
                    )
                )
            )
        )
        
        stuck_files = result.scalars().all()
        
        for file_record in stuck_files:
            processing_duration = None
            if file_record.sync_started_at:
                processing_duration = (datetime.utcnow() - file_record.sync_started_at).total_seconds()
            
            inconsistencies.append(InconsistencyReport(
                inconsistency_type=InconsistencyType.STUCK_PROCESSING,
                severity=Severity.HIGH,
                tenant_id=tenant_id,
                file_id=file_record.id,
                file_path=file_record.file_path,
                description=f"File '{file_record.filename}' has been stuck in processing state",
                details={
                    'sync_started_at': file_record.sync_started_at.isoformat() if file_record.sync_started_at else None,
                    'processing_duration_seconds': processing_duration,
                    'file_size': file_record.file_size,
                    'sync_error': file_record.sync_error
                },
                detected_at=datetime.utcnow(),
                repair_action="Reset file status to 'pending' and retry sync",
                estimated_impact="File is unavailable for search and may block other operations"
            ))
        
        return inconsistencies
    
    async def _check_qdrant_postgres_mismatches(
        self, 
        tenant_id: UUID, 
        collection_name: str
    ) -> List[InconsistencyReport]:
        """Check for mismatches between Qdrant and PostgreSQL chunk counts"""
        
        if not self._qdrant_client:
            return []
        
        inconsistencies = []
        
        try:
            # Get files with chunks from PostgreSQL
            result = await self.db.execute(
                select(
                    EmbeddingChunk.file_id,
                    func.count(EmbeddingChunk.id).label('pg_chunk_count')
                ).where(
                    EmbeddingChunk.tenant_id == tenant_id
                ).group_by(EmbeddingChunk.file_id)
            )
            
            postgres_counts = {row.file_id: row.pg_chunk_count for row in result.fetchall()}
            
            # Check each file in Qdrant
            for file_id, pg_count in postgres_counts.items():
                try:
                    # Count points in Qdrant for this file
                    qdrant_count = self._qdrant_client.count(
                        collection_name=collection_name,
                        count_filter={
                            "must": [
                                {"key": "file_id", "match": {"value": str(file_id)}},
                                {"key": "tenant_id", "match": {"value": str(tenant_id)}}
                            ]
                        }
                    ).count
                    
                    if qdrant_count != pg_count:
                        # Get file info for better reporting
                        file_result = await self.db.execute(
                            select(File).where(File.id == file_id)
                        )
                        file_record = file_result.scalar_one_or_none()
                        
                        inconsistencies.append(InconsistencyReport(
                            inconsistency_type=InconsistencyType.QDRANT_POSTGRES_MISMATCH,
                            severity=Severity.HIGH,
                            tenant_id=tenant_id,
                            file_id=file_id,
                            file_path=file_record.file_path if file_record else None,
                            description=f"Chunk count mismatch: PostgreSQL has {pg_count}, Qdrant has {qdrant_count}",
                            details={
                                'postgres_chunks': pg_count,
                                'qdrant_chunks': qdrant_count,
                                'filename': file_record.filename if file_record else 'Unknown'
                            },
                            detected_at=datetime.utcnow(),
                            repair_action="Re-process file to synchronize chunk counts",
                            estimated_impact="Search results may be incomplete or inconsistent"
                        ))
                        
                except Exception as e:
                    print(f"⚠️ Error checking file {file_id} in Qdrant: {e}")
                    continue
        
        except Exception as e:
            print(f"⚠️ Error during Qdrant consistency check: {e}")
        
        return inconsistencies
    
    async def _check_orphaned_embeddings(
        self, 
        tenant_id: UUID, 
        collection_name: str
    ) -> List[InconsistencyReport]:
        """Check for embeddings in Qdrant without corresponding PostgreSQL records"""
        
        if not self._qdrant_client:
            return []
        
        inconsistencies = []
        
        try:
            # This is a complex check that would require scanning all Qdrant points
            # For now, we'll do a simpler check by getting a sample and verifying
            # In production, this might be done as a background job
            
            # Get sample of points from Qdrant for this tenant
            scroll_result = self._qdrant_client.scroll(
                collection_name=collection_name,
                scroll_filter={
                    "must": [
                        {"key": "tenant_id", "match": {"value": str(tenant_id)}}
                    ]
                },
                limit=100,  # Sample size
                with_payload=True,
                with_vectors=False
            )
            
            points = scroll_result[0]
            orphaned_count = 0
            
            for point in points:
                file_id = point.payload.get('file_id')
                if file_id:
                    # Check if corresponding chunk exists in PostgreSQL
                    result = await self.db.execute(
                        select(EmbeddingChunk.id).where(
                            and_(
                                EmbeddingChunk.qdrant_point_id == UUID(point.id),
                                EmbeddingChunk.tenant_id == tenant_id
                            )
                        )
                    )
                    
                    if not result.scalar_one_or_none():
                        orphaned_count += 1
            
            if orphaned_count > 0:
                inconsistencies.append(InconsistencyReport(
                    inconsistency_type=InconsistencyType.ORPHANED_EMBEDDINGS,
                    severity=Severity.MEDIUM,
                    tenant_id=tenant_id,
                    file_id=None,
                    file_path=None,
                    description=f"Found {orphaned_count} orphaned embeddings in Qdrant (sample of 100 checked)",
                    details={
                        'orphaned_count_in_sample': orphaned_count,
                        'sample_size': len(points),
                        'collection_name': collection_name
                    },
                    detected_at=datetime.utcnow(),
                    repair_action="Run full Qdrant cleanup to remove orphaned embeddings",
                    estimated_impact="Wastes vector storage space and may return stale results"
                ))
        
        except Exception as e:
            print(f"⚠️ Error checking orphaned embeddings in Qdrant: {e}")
        
        return inconsistencies
    
    def _calculate_consistency_score(
        self, 
        stats: ConsistencyStats, 
        inconsistencies: List[InconsistencyReport]
    ) -> float:
        """Calculate overall consistency score (0-100%)"""
        
        if stats.total_files == 0:
            return 100.0
        
        # Weight different types of inconsistencies
        severity_weights = {
            Severity.CRITICAL: 1.0,
            Severity.HIGH: 0.8,
            Severity.MEDIUM: 0.5,
            Severity.LOW: 0.2
        }
        
        # Calculate penalty for each inconsistency
        total_penalty = 0.0
        for inconsistency in inconsistencies:
            weight = severity_weights.get(inconsistency.severity, 0.5)
            total_penalty += weight
        
        # Calculate score based on healthy files vs total files
        max_possible_penalty = stats.total_files
        if max_possible_penalty > 0:
            penalty_ratio = min(total_penalty / max_possible_penalty, 1.0)
            score = (1.0 - penalty_ratio) * 100.0
        else:
            score = 100.0
        
        return round(score, 2)
    
    async def generate_repair_plan(
        self, 
        inconsistencies: List[InconsistencyReport]
    ) -> List[Dict[str, Any]]:
        """Generate actionable repair plan for detected inconsistencies"""
        
        repair_actions = []
        
        # Group inconsistencies by type for batch operations
        by_type = {}
        for inconsistency in inconsistencies:
            if inconsistency.inconsistency_type not in by_type:
                by_type[inconsistency.inconsistency_type] = []
            by_type[inconsistency.inconsistency_type].append(inconsistency)
        
        # Generate repair actions
        for inconsistency_type, items in by_type.items():
            if inconsistency_type == InconsistencyType.MISSING_EMBEDDINGS:
                file_ids = [item.file_id for item in items if item.file_id]
                repair_actions.append({
                    'action_type': 'reprocess_files',
                    'description': f'Re-process {len(file_ids)} files to generate missing embeddings',
                    'file_ids': [str(fid) for fid in file_ids],
                    'priority': 'high',
                    'estimated_time': f'{len(file_ids) * 2} minutes'
                })
            
            elif inconsistency_type == InconsistencyType.ORPHANED_CHUNKS:
                chunk_counts = sum(len(item.details.get('chunk_ids', [])) for item in items)
                repair_actions.append({
                    'action_type': 'cleanup_orphaned_chunks',
                    'description': f'Delete {chunk_counts} orphaned chunks from PostgreSQL and Qdrant',
                    'affected_files': len(items),
                    'priority': 'medium',
                    'estimated_time': f'{chunk_counts // 100 + 1} minutes'
                })
            
            elif inconsistency_type == InconsistencyType.STUCK_PROCESSING:
                file_ids = [item.file_id for item in items if item.file_id]
                repair_actions.append({
                    'action_type': 'reset_stuck_files',
                    'description': f'Reset {len(file_ids)} stuck files to pending status',
                    'file_ids': [str(fid) for fid in file_ids],
                    'priority': 'high',
                    'estimated_time': '1 minute'
                })
            
            elif inconsistency_type == InconsistencyType.QDRANT_POSTGRES_MISMATCH:
                file_ids = [item.file_id for item in items if item.file_id]
                repair_actions.append({
                    'action_type': 'resync_mismatched_files',
                    'description': f'Re-sync {len(file_ids)} files with chunk count mismatches',
                    'file_ids': [str(fid) for fid in file_ids],
                    'priority': 'high',
                    'estimated_time': f'{len(file_ids) * 3} minutes'
                })
        
        return repair_actions
    
    async def check_all_tenants_consistency(
        self, 
        environment: str = None
    ) -> Dict[str, Tuple[ConsistencyStats, List[InconsistencyReport]]]:
        """Check consistency across all tenants"""
        
        # Get all tenant IDs
        result = await self.db.execute(
            select(func.distinct(File.tenant_id))
        )
        tenant_ids = [row[0] for row in result.fetchall()]
        
        all_results = {}
        
        for tenant_id in tenant_ids:
            try:
                stats, inconsistencies = await self.check_tenant_consistency(tenant_id, environment)
                all_results[str(tenant_id)] = (stats, inconsistencies)
            except Exception as e:
                print(f"⚠️ Error checking consistency for tenant {tenant_id}: {e}")
                continue
        
        return all_results


async def get_consistency_checker(db_session: AsyncSession) -> ConsistencyChecker:
    """Factory function to create consistency checker"""
    return ConsistencyChecker(db_session) 