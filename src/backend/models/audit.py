"""
Database model for auditing synchronization events.
"""

from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.sql import func
from src.backend.db.base import Base

class SyncEvent(Base):
    __tablename__ = 'sync_events'

    id = Column(Integer, primary_key=True, index=True)
    sync_run_id = Column(String, nullable=False, index=True)
    tenant_id = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    event_type = Column(String, nullable=False) # e.g., 'SYNC_START', 'FILE_ADDED', 'INGESTION_FAILURE'
    status = Column(String, nullable=False) # e.g., 'SUCCESS', 'FAILURE', 'IN_PROGRESS'
    
    message = Column(String, nullable=True)
    event_metadata = Column(JSON, nullable=True) # Renamed from 'metadata' to avoid SQLAlchemy conflict

    def __repr__(self):
        return f"<SyncEvent(id={self.id}, sync_run_id='{self.sync_run_id}', event_type='{self.event_type}', status='{self.status}')>" 