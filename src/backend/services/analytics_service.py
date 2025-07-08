"""
Analytics Service for RAG Platform
Comprehensive tenant-separated metrics and analytics
"""

import hashlib
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any
from uuid import UUID, uuid4

from sqlalchemy import func, desc, and_, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..models.database import (
    QueryLog, QueryFeedback, TenantMetrics, DocumentAccessLog, 
    UserSession, Tenant, File, EmbeddingChunk, User
)


class AnalyticsService:
    """Service for analytics and metrics aggregation"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # =============================================
    # QUERY LOGGING & TRACKING
    # =============================================
    
    def log_query(
        self,
        tenant_id: UUID,
        query_text: str,
        response_text: Optional[str] = None,
        response_type: str = 'success',
        response_time_ms: int = 0,
        confidence_score: Optional[float] = None,
        sources_count: int = 0,
        chunks_retrieved: int = 0,
        user_id: Optional[UUID] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        embedding_model: str = 'all-MiniLM-L6-v2',
        llm_model: str = 'gpt-3.5-turbo',
        tokens_used: Optional[int] = None,
        cost_usd: Optional[float] = None,
        embedding_time_ms: Optional[int] = None,
        search_time_ms: Optional[int] = None,
        llm_time_ms: Optional[int] = None
    ) -> QueryLog:
        """Log a query with comprehensive metrics"""
        
        # Generate query hash for deduplication
        query_hash = hashlib.sha256(
            f"{tenant_id}:{query_text}".encode('utf-8')
        ).hexdigest()
        
        query_log = QueryLog(
            tenant_id=tenant_id,
            user_id=user_id,
            query_text=query_text,
            query_hash=query_hash,
            response_text=response_text,
            response_type=response_type,
            confidence_score=confidence_score,
            sources_count=sources_count,
            chunks_retrieved=chunks_retrieved,
            response_time_ms=response_time_ms,
            embedding_time_ms=embedding_time_ms,
            search_time_ms=search_time_ms,
            llm_time_ms=llm_time_ms,
            embedding_model=embedding_model,
            llm_model=llm_model,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        self.db.add(query_log)
        self.db.flush()  # Get the ID without committing
        
        return query_log
    
    def log_document_access(
        self,
        query_log_id: UUID,
        file_id: UUID,
        tenant_id: UUID,
        relevance_score: float,
        rank_position: int,
        chunks_used: int = 1,
        included_in_response: bool = True
    ) -> DocumentAccessLog:
        """Log document access for a query"""
        
        access_log = DocumentAccessLog(
            query_log_id=query_log_id,
            file_id=file_id,
            tenant_id=tenant_id,
            chunks_used=chunks_used,
            relevance_score=relevance_score,
            rank_position=rank_position,
            included_in_response=included_in_response
        )
        
        self.db.add(access_log)
        return access_log
    
    def add_query_feedback(
        self,
        query_log_id: UUID,
        tenant_id: UUID,
        rating: int,
        feedback_type: str = 'rating',
        feedback_text: Optional[str] = None,
        helpful: Optional[bool] = None,
        user_id: Optional[UUID] = None,
        accuracy_rating: Optional[int] = None,
        relevance_rating: Optional[int] = None,
        completeness_rating: Optional[int] = None
    ) -> QueryFeedback:
        """Add feedback for a query"""
        
        feedback = QueryFeedback(
            query_log_id=query_log_id,
            tenant_id=tenant_id,
            user_id=user_id,
            rating=rating,
            feedback_type=feedback_type,
            feedback_text=feedback_text,
            helpful=helpful,
            accuracy_rating=accuracy_rating,
            relevance_rating=relevance_rating,
            completeness_rating=completeness_rating
        )
        
        self.db.add(feedback)
        return feedback
    
    # =============================================
    # SESSION TRACKING
    # =============================================
    
    def start_session(
        self,
        tenant_id: UUID,
        session_id: str,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> UserSession:
        """Start tracking a user session"""
        
        session = UserSession(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        self.db.add(session)
        return session
    
    def update_session_activity(
        self,
        session_id: str,
        query_count_increment: int = 1
    ) -> Optional[UserSession]:
        """Update session last activity and query count"""
        
        session = self.db.query(UserSession).filter(
            UserSession.session_id == session_id
        ).first()
        
        if session:
            session.last_activity_at = datetime.utcnow()
            session.query_count += query_count_increment
            
        return session
    
    def end_session(self, session_id: str) -> Optional[UserSession]:
        """End a user session"""
        
        session = self.db.query(UserSession).filter(
            UserSession.session_id == session_id
        ).first()
        
        if session:
            session.ended_at = datetime.utcnow()
            if session.started_at:
                session.duration_seconds = int(
                    (session.ended_at - session.started_at).total_seconds()
                )
        
        return session
    
    # =============================================
    # METRICS AGGREGATION
    # =============================================
    
    def calculate_daily_metrics(
        self, 
        tenant_id: UUID, 
        target_date: date
    ) -> TenantMetrics:
        """Calculate and store daily metrics for a tenant"""
        
        # Check if metrics already exist for this date
        existing = self.db.query(TenantMetrics).filter(
            and_(
                TenantMetrics.tenant_id == tenant_id,
                TenantMetrics.metric_date == target_date
            )
        ).first()
        
        if existing:
            return existing
        
        # Date range for queries
        start_datetime = datetime.combine(target_date, datetime.min.time())
        end_datetime = datetime.combine(target_date + timedelta(days=1), datetime.min.time())
        
        # Query metrics
        query_stats = self.db.query(
            func.count(QueryLog.id).label('total_queries'),
            func.sum(func.case([(QueryLog.response_type == 'success', 1)], else_=0)).label('successful_queries'),
            func.sum(func.case([(QueryLog.response_type == 'no_answer', 1)], else_=0)).label('no_answer_queries'),
            func.sum(func.case([(QueryLog.response_type == 'error', 1)], else_=0)).label('error_queries'),
            func.avg(QueryLog.response_time_ms).label('avg_response_time'),
            func.avg(QueryLog.confidence_score).label('avg_confidence_score'),
            func.percentile_cont(0.95).within_group(QueryLog.response_time_ms).label('p95_response_time'),
            func.sum(QueryLog.tokens_used).label('tokens_used'),
            func.sum(QueryLog.cost_usd).label('total_cost_usd')
        ).filter(
            and_(
                QueryLog.tenant_id == tenant_id,
                QueryLog.created_at >= start_datetime,
                QueryLog.created_at < end_datetime
            )
        ).first()
        
        # User activity metrics
        user_stats = self.db.query(
            func.count(func.distinct(QueryLog.user_id)).label('unique_users'),
            func.count(func.distinct(UserSession.session_id)).label('active_sessions')
        ).outerjoin(
            UserSession, 
            and_(
                UserSession.tenant_id == tenant_id,
                UserSession.started_at >= start_datetime,
                UserSession.started_at < end_datetime
            )
        ).filter(
            and_(
                QueryLog.tenant_id == tenant_id,
                QueryLog.created_at >= start_datetime,
                QueryLog.created_at < end_datetime
            )
        ).first()
        
        # Document metrics
        doc_stats = self.db.query(
            func.count(File.id).label('total_documents'),
            func.count(EmbeddingChunk.id).label('total_chunks')
        ).outerjoin(EmbeddingChunk).filter(
            and_(
                File.tenant_id == tenant_id,
                File.deleted_at.is_(None)
            )
        ).first()
        
        # Document changes for the day
        doc_changes = self.db.query(
            func.sum(func.case([(File.created_at >= start_datetime, 1)], else_=0)).label('documents_added'),
            func.sum(func.case([(File.updated_at >= start_datetime, 1)], else_=0)).label('documents_updated'),
            func.sum(func.case([(File.deleted_at >= start_datetime, 1)], else_=0)).label('documents_deleted')
        ).filter(
            File.tenant_id == tenant_id
        ).first()
        
        # Storage calculation
        storage_stats = self.db.query(
            func.sum(File.file_size).label('total_bytes')
        ).filter(
            and_(
                File.tenant_id == tenant_id,
                File.deleted_at.is_(None)
            )
        ).first()
        
        storage_mb = (storage_stats.total_bytes or 0) / (1024 * 1024)
        
        # Feedback metrics
        feedback_stats = self.db.query(
            func.avg(QueryFeedback.rating).label('avg_rating'),
            func.count(QueryFeedback.id).label('feedback_count'),
            func.sum(func.case([(QueryFeedback.helpful == True, 1)], else_=0)).label('thumbs_up_count'),
            func.sum(func.case([(QueryFeedback.helpful == False, 1)], else_=0)).label('thumbs_down_count')
        ).join(QueryLog).filter(
            and_(
                QueryLog.tenant_id == tenant_id,
                QueryFeedback.created_at >= start_datetime,
                QueryFeedback.created_at < end_datetime
            )
        ).first()
        
        # Create metrics record
        metrics = TenantMetrics(
            tenant_id=tenant_id,
            metric_date=target_date,
            total_queries=query_stats.total_queries or 0,
            successful_queries=query_stats.successful_queries or 0,
            no_answer_queries=query_stats.no_answer_queries or 0,
            error_queries=query_stats.error_queries or 0,
            unique_users=user_stats.unique_users or 0,
            active_sessions=user_stats.active_sessions or 0,
            avg_response_time=query_stats.avg_response_time,
            avg_confidence_score=query_stats.avg_confidence_score,
            p95_response_time=query_stats.p95_response_time,
            total_documents=doc_stats.total_documents or 0,
            documents_added=doc_changes.documents_added or 0,
            documents_updated=doc_changes.documents_updated or 0,
            documents_deleted=doc_changes.documents_deleted or 0,
            total_chunks=doc_stats.total_chunks or 0,
            storage_used_mb=storage_mb,
            tokens_used=query_stats.tokens_used or 0,
            total_cost_usd=query_stats.total_cost_usd or 0,
            avg_user_rating=feedback_stats.avg_rating,
            feedback_count=feedback_stats.feedback_count or 0,
            thumbs_up_count=feedback_stats.thumbs_up_count or 0,
            thumbs_down_count=feedback_stats.thumbs_down_count or 0
        )
        
        self.db.add(metrics)
        return metrics
    
    # =============================================
    # ANALYTICS QUERIES
    # =============================================
    
    def get_tenant_summary(self, tenant_id: UUID) -> Dict[str, Any]:
        """Get current tenant summary metrics"""
        
        # Today's metrics
        today = date.today()
        today_metrics = self.calculate_daily_metrics(tenant_id, today)
        
        # All-time totals
        all_time_queries = self.db.query(func.count(QueryLog.id)).filter(
            QueryLog.tenant_id == tenant_id
        ).scalar() or 0
        
        all_time_documents = self.db.query(func.count(File.id)).filter(
            and_(
                File.tenant_id == tenant_id,
                File.deleted_at.is_(None)
            )
        ).scalar() or 0
        
        # Success rate calculation
        total_queries = self.db.query(func.count(QueryLog.id)).filter(
            QueryLog.tenant_id == tenant_id
        ).scalar() or 0
        
        successful_queries = self.db.query(func.count(QueryLog.id)).filter(
            and_(
                QueryLog.tenant_id == tenant_id,
                QueryLog.response_type == 'success'
            )
        ).scalar() or 0
        
        success_rate = (successful_queries / total_queries * 100) if total_queries > 0 else 0
        
        # Recent activity (last 7 days)
        seven_days_ago = today - timedelta(days=7)
        recent_metrics = self.db.query(TenantMetrics).filter(
            and_(
                TenantMetrics.tenant_id == tenant_id,
                TenantMetrics.metric_date >= seven_days_ago
            )
        ).all()
        
        return {
            'tenant_id': str(tenant_id),
            'today': {
                'queries': today_metrics.total_queries,
                'documents': today_metrics.total_documents,
                'users': today_metrics.unique_users,
                'avg_response_time': today_metrics.avg_response_time,
                'success_rate': (today_metrics.successful_queries / today_metrics.total_queries * 100) if today_metrics.total_queries > 0 else 0
            },
            'all_time': {
                'total_queries': all_time_queries,
                'total_documents': all_time_documents,
                'success_rate': success_rate
            },
            'recent_trend': [
                {
                    'date': m.metric_date.isoformat(),
                    'queries': m.total_queries,
                    'success_rate': (m.successful_queries / m.total_queries * 100) if m.total_queries > 0 else 0,
                    'avg_response_time': m.avg_response_time
                }
                for m in recent_metrics
            ]
        }
    
    def get_query_history(
        self, 
        tenant_id: UUID, 
        limit: int = 50, 
        offset: int = 0,
        user_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """Get paginated query history for tenant"""
        
        query = self.db.query(QueryLog).filter(
            QueryLog.tenant_id == tenant_id
        )
        
        if user_id:
            query = query.filter(QueryLog.user_id == user_id)
        
        queries = query.order_by(desc(QueryLog.created_at)).offset(offset).limit(limit).all()
        
        return [
            {
                'id': str(q.id),
                'query_text': q.query_text,
                'response_type': q.response_type,
                'confidence_score': q.confidence_score,
                'response_time_ms': q.response_time_ms,
                'sources_count': q.sources_count,
                'created_at': q.created_at.isoformat(),
                'user_id': str(q.user_id) if q.user_id else None
            }
            for q in queries
        ]
    
    def get_document_usage_stats(self, tenant_id: UUID) -> List[Dict[str, Any]]:
        """Get document usage statistics"""
        
        stats = self.db.query(
            File.id,
            File.filename,
            func.count(DocumentAccessLog.id).label('access_count'),
            func.avg(DocumentAccessLog.relevance_score).label('avg_relevance'),
            func.max(DocumentAccessLog.created_at).label('last_accessed')
        ).outerjoin(DocumentAccessLog).filter(
            and_(
                File.tenant_id == tenant_id,
                File.deleted_at.is_(None)
            )
        ).group_by(File.id, File.filename).order_by(
            desc('access_count')
        ).limit(20).all()
        
        return [
            {
                'file_id': str(s.id),
                'filename': s.filename,
                'access_count': s.access_count or 0,
                'avg_relevance': float(s.avg_relevance) if s.avg_relevance else 0,
                'last_accessed': s.last_accessed.isoformat() if s.last_accessed else None
            }
            for s in stats
        ]
    
    def get_performance_metrics(
        self, 
        tenant_id: UUID, 
        days: int = 30
    ) -> Dict[str, Any]:
        """Get performance metrics over time"""
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        metrics = self.db.query(TenantMetrics).filter(
            and_(
                TenantMetrics.tenant_id == tenant_id,
                TenantMetrics.metric_date >= start_date,
                TenantMetrics.metric_date <= end_date
            )
        ).order_by(TenantMetrics.metric_date).all()
        
        return {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': days
            },
            'metrics': [
                {
                    'date': m.metric_date.isoformat(),
                    'total_queries': m.total_queries,
                    'success_rate': (m.successful_queries / m.total_queries * 100) if m.total_queries > 0 else 0,
                    'avg_response_time': m.avg_response_time,
                    'avg_confidence': m.avg_confidence_score,
                    'unique_users': m.unique_users,
                    'documents': m.total_documents,
                    'storage_mb': m.storage_used_mb
                }
                for m in metrics
            ]
        }
    
    # =============================================
    # UTILITY METHODS
    # =============================================
    
    def generate_session_id(self) -> str:
        """Generate a unique session ID"""
        return str(uuid4())
    
    def commit(self):
        """Commit all pending database changes"""
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise