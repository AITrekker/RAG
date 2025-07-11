"""
DEPRECATED: Consistency Checker Service - No Longer Needed

This module is deprecated and no longer needed with PostgreSQL + pgvector.
Data consistency is now maintained within PostgreSQL transactions.

Use PostgreSQL constraints and monitoring instead.
"""

import warnings
import logging
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from dataclasses import dataclass
from enum import Enum

warnings.warn(
    "consistency_checker is deprecated and no longer needed with pgvector. "
    "Data consistency is maintained within PostgreSQL transactions.", 
    DeprecationWarning, 
    stacklevel=2
)

logger = logging.getLogger(__name__)


class InconsistencyType(Enum):
    """DEPRECATED: Types of data inconsistencies"""
    MISSING_EMBEDDINGS = "missing_embeddings"
    ORPHANED_EMBEDDINGS = "orphaned_embeddings"
    MISSING_CHUNKS = "missing_chunks"
    ORPHANED_CHUNKS = "orphaned_chunks"
    QDRANT_POSTGRES_MISMATCH = "qdrant_postgres_mismatch"
    STUCK_PROCESSING = "stuck_processing"
    STALE_EMBEDDINGS = "stale_embeddings"


class Severity(Enum):
    """DEPRECATED: Severity levels for inconsistencies"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class InconsistencyReport:
    """DEPRECATED: Report of a detected inconsistency"""
    inconsistency_type: InconsistencyType
    severity: Severity
    tenant_id: UUID
    file_id: Optional[UUID]
    file_path: Optional[str]
    description: str
    details: Dict[str, Any]
    detected_at: object  # datetime
    repair_action: str
    estimated_impact: str


@dataclass
class ConsistencyStats:
    """DEPRECATED: Overall consistency statistics"""
    tenant_id: UUID
    total_files: int
    synced_files: int
    files_with_chunks: int
    total_chunks: int
    files_missing_embeddings: int
    orphaned_chunks: int
    stuck_processing_files: int
    stale_embeddings_files: int
    consistency_score: float
    last_checked: object  # datetime


class ConsistencyChecker:
    """
    DEPRECATED: No longer needed with unified PostgreSQL + pgvector architecture.
    
    This service was designed for checking consistency between PostgreSQL and Qdrant.
    With pgvector, all data is in PostgreSQL with ACID transactions.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize deprecated service."""
        logger.error("ConsistencyChecker is deprecated and no longer functional.")
        raise NotImplementedError(
            "ConsistencyChecker is deprecated. "
            "Data consistency is maintained automatically within PostgreSQL transactions."
        )
    
    async def check_tenant_consistency(self, *args, **kwargs):
        """DEPRECATED: Use PostgreSQL constraints and monitoring instead."""
        logger.error("check_tenant_consistency is deprecated.")
        raise NotImplementedError("Use PostgreSQL constraints and monitoring instead")
    
    async def check_all_tenants_consistency(self, *args, **kwargs):
        """DEPRECATED: Use PostgreSQL constraints and monitoring instead."""
        logger.error("check_all_tenants_consistency is deprecated.")
        raise NotImplementedError("Use PostgreSQL constraints and monitoring instead")
    
    async def generate_repair_plan(self, *args, **kwargs):
        """DEPRECATED: Use PostgreSQL constraints and monitoring instead."""
        logger.error("generate_repair_plan is deprecated.")
        raise NotImplementedError("Use PostgreSQL constraints and monitoring instead")


# Legacy factory function for backwards compatibility
async def get_consistency_checker(*args, **kwargs):
    """
    DEPRECATED: Get consistency checker.
    
    Use PostgreSQL constraints and monitoring instead.
    """
    logger.warning("get_consistency_checker is deprecated. Use PostgreSQL constraints and monitoring instead.")
    raise NotImplementedError("Use PostgreSQL constraints and monitoring instead")