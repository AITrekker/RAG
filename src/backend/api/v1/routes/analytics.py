"""
Analytics API Routes
Tenant-separated metrics and analytics endpoints
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.backend.dependencies import get_db, get_current_tenant
from src.backend.services.analytics_service import AnalyticsService
from src.backend.models.api_models import TenantResponse


# =============================================
# RESPONSE MODELS
# =============================================

class QueryLogResponse(BaseModel):
    """Query log response model"""
    id: str
    query_text: str
    response_type: str
    confidence_score: Optional[float]
    response_time_ms: int
    sources_count: int
    created_at: str
    user_id: Optional[str]

class TenantSummaryResponse(BaseModel):
    """Tenant summary metrics response"""
    tenant_id: str
    today: Dict[str, Any]
    all_time: Dict[str, Any]
    recent_trend: List[Dict[str, Any]]

class DocumentUsageResponse(BaseModel):
    """Document usage statistics response"""
    file_id: str
    filename: str
    access_count: int
    avg_relevance: float
    last_accessed: Optional[str]

class PerformanceMetricsResponse(BaseModel):
    """Performance metrics response"""
    period: Dict[str, Any]
    metrics: List[Dict[str, Any]]

class QueryFeedbackRequest(BaseModel):
    """Query feedback request model"""
    query_log_id: UUID
    rating: int = Field(..., ge=1, le=5, description="Rating from 1-5")
    feedback_type: str = Field(default="rating", description="Type of feedback")
    feedback_text: Optional[str] = Field(None, description="Optional feedback text")
    helpful: Optional[bool] = Field(None, description="Whether response was helpful")
    accuracy_rating: Optional[int] = Field(None, ge=1, le=5, description="Accuracy rating 1-5")
    relevance_rating: Optional[int] = Field(None, ge=1, le=5, description="Relevance rating 1-5")
    completeness_rating: Optional[int] = Field(None, ge=1, le=5, description="Completeness rating 1-5")

class MetricsFilterParams(BaseModel):
    """Parameters for filtering metrics"""
    start_date: Optional[date] = Field(None, description="Start date for metrics")
    end_date: Optional[date] = Field(None, description="End date for metrics")
    user_id: Optional[UUID] = Field(None, description="Filter by specific user")
    query_type: Optional[str] = Field(None, description="Filter by query type")
    response_type: Optional[str] = Field(None, description="Filter by response type")

# =============================================
# ROUTER SETUP
# =============================================

router = APIRouter(tags=["Analytics"])


# =============================================
# TENANT SUMMARY ENDPOINTS
# =============================================

@router.get("/summary", response_model=TenantSummaryResponse)
async def get_tenant_summary(
    tenant: TenantResponse = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive tenant summary metrics
    
    Returns:
    - Today's metrics (queries, documents, users, performance)
    - All-time totals 
    - Recent 7-day trend data
    """
    # Temporary fallback to mock data while analytics service is being converted to async
    mock_summary = {
        "tenant_id": str(tenant.id),
        "today": {
            "queries": 47,
            "documents": 156,
            "users": 12,
            "avg_response_time": 850,
            "success_rate": 94.2
        },
        "all_time": {
            "total_queries": 3247,
            "total_documents": 156,
            "success_rate": 91.8
        },
        "recent_trend": [
            {"date": "2025-07-01", "queries": 35, "success_rate": 92.1, "avg_response_time": 920},
            {"date": "2025-07-02", "queries": 42, "success_rate": 94.3, "avg_response_time": 780},
            {"date": "2025-07-03", "queries": 38, "success_rate": 91.2, "avg_response_time": 890},
            {"date": "2025-07-04", "queries": 51, "success_rate": 95.1, "avg_response_time": 720},
            {"date": "2025-07-05", "queries": 44, "success_rate": 93.8, "avg_response_time": 810},
            {"date": "2025-07-06", "queries": 39, "success_rate": 92.7, "avg_response_time": 870},
            {"date": "2025-07-07", "queries": 47, "success_rate": 94.2, "avg_response_time": 850}
        ]
    }
    
    try:
        return TenantSummaryResponse(**mock_summary)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tenant summary: {str(e)}"
        )

@router.get("/metrics/daily")
async def get_daily_metrics(
    days: int = Query(30, ge=1, le=365, description="Number of days to fetch"),
    tenant: TenantResponse = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get daily aggregated metrics for the specified period"""
    # Temporary mock data while analytics service is being converted to async
    from datetime import datetime, timedelta
    import random
    
    mock_performance = {
        "period": {
            "start_date": (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d"),
            "end_date": datetime.now().strftime("%Y-%m-%d"), 
            "days": days
        },
        "metrics": []
    }
    
    # Generate mock daily metrics
    for i in range(min(days, 30)):  # Limit to 30 days for demo
        date_val = datetime.now() - timedelta(days=days-1-i)
        mock_performance["metrics"].append({
            "date": date_val.strftime("%Y-%m-%d"),
            "total_queries": random.randint(20, 70),
            "success_rate": random.uniform(80, 95),
            "avg_response_time": random.uniform(500, 1200),
            "avg_confidence": random.uniform(0.7, 0.95),
            "unique_users": random.randint(5, 20),
            "documents": 156,
            "storage_mb": 1247.5
        })
    
    try:
        return mock_performance
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch daily metrics: {str(e)}"
        )

@router.post("/metrics/calculate")
async def calculate_metrics_for_date(
    target_date: date = Query(..., description="Date to calculate metrics for"),
    tenant: TenantResponse = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Manually trigger metrics calculation for a specific date"""
    analytics = AnalyticsService(db)
    
    try:
        metrics = analytics.calculate_daily_metrics(tenant.id, target_date)
        analytics.commit()
        
        return {
            "message": f"Metrics calculated for {target_date}",
            "metrics": {
                "total_queries": metrics.total_queries,
                "total_documents": metrics.total_documents,
                "unique_users": metrics.unique_users,
                "avg_response_time": metrics.avg_response_time,
                "storage_used_mb": metrics.storage_used_mb
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate metrics: {str(e)}"
        )

# =============================================
# QUERY ANALYTICS ENDPOINTS
# =============================================

@router.get("/queries/history", response_model=List[QueryLogResponse])
async def get_query_history(
    limit: int = Query(50, ge=1, le=1000, description="Number of queries to return"),
    offset: int = Query(0, ge=0, description="Number of queries to skip"),
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    tenant: TenantResponse = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get paginated query history for the tenant"""
    # Temporary mock data while analytics service is being converted to async
    mock_queries = [
        {
            "id": "q1",
            "query_text": "What are the key features of our new product?",
            "response_type": "success",
            "confidence_score": 0.92,
            "response_time_ms": 750,
            "sources_count": 3,
            "created_at": "2025-07-07T15:30:00Z",
            "user_id": "user1"
        },
        {
            "id": "q2", 
            "query_text": "How do we handle customer complaints?",
            "response_type": "success",
            "confidence_score": 0.88,
            "response_time_ms": 920,
            "sources_count": 2,
            "created_at": "2025-07-07T15:15:00Z",
            "user_id": "user2"
        },
        {
            "id": "q3",
            "query_text": "What is the pricing structure?",
            "response_type": "no_answer",
            "confidence_score": 0.45,
            "response_time_ms": 1200,
            "sources_count": 1,
            "created_at": "2025-07-07T14:45:00Z",
            "user_id": "user1"
        }
    ]
    
    try:
        # Apply limit and offset to mock data
        start = offset
        end = offset + limit
        paginated_queries = mock_queries[start:end]
        return [QueryLogResponse(**q) for q in paginated_queries]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch query history: {str(e)}"
        )

@router.post("/queries/feedback")
async def submit_query_feedback(
    feedback: QueryFeedbackRequest,
    tenant: TenantResponse = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Submit feedback for a query response"""
    analytics = AnalyticsService(db)
    
    try:
        feedback_record = analytics.add_query_feedback(
            query_log_id=feedback.query_log_id,
            tenant_id=tenant.id,
            rating=feedback.rating,
            feedback_type=feedback.feedback_type,
            feedback_text=feedback.feedback_text,
            helpful=feedback.helpful,
            accuracy_rating=feedback.accuracy_rating,
            relevance_rating=feedback.relevance_rating,
            completeness_rating=feedback.completeness_rating
        )
        analytics.commit()
        
        return {
            "message": "Feedback submitted successfully",
            "feedback_id": str(feedback_record.id)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit feedback: {str(e)}"
        )

@router.get("/queries/stats")
async def get_query_statistics(
    days: int = Query(30, ge=1, le=365, description="Number of days for statistics"),
    tenant: TenantResponse = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get detailed query statistics and performance metrics"""
    analytics = AnalyticsService(db)
    
    try:
        # Get recent metrics
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        performance_data = analytics.get_performance_metrics(tenant.id, days)
        
        # Calculate additional statistics
        total_queries = sum(m['total_queries'] for m in performance_data['metrics'])
        avg_success_rate = sum(m['success_rate'] for m in performance_data['metrics']) / len(performance_data['metrics']) if performance_data['metrics'] else 0
        avg_response_time = sum(m['avg_response_time'] or 0 for m in performance_data['metrics']) / len(performance_data['metrics']) if performance_data['metrics'] else 0
        
        return {
            "period": performance_data['period'],
            "summary": {
                "total_queries": total_queries,
                "avg_success_rate": round(avg_success_rate, 2),
                "avg_response_time": round(avg_response_time, 2)
            },
            "daily_breakdown": performance_data['metrics']
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch query statistics: {str(e)}"
        )

# =============================================
# DOCUMENT ANALYTICS ENDPOINTS
# =============================================

@router.get("/documents/usage", response_model=List[DocumentUsageResponse])
async def get_document_usage_stats(
    tenant: TenantResponse = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get document usage statistics showing most accessed documents"""
    # Temporary mock data while analytics service is being converted to async
    mock_document_usage = [
        {
            "file_id": "doc1",
            "filename": "Product_Specifications_v2.pdf",
            "access_count": 23,
            "avg_relevance": 0.89,
            "last_accessed": "2025-07-07T15:30:00Z"
        },
        {
            "file_id": "doc2",
            "filename": "Customer_Service_Guide.md",
            "access_count": 18,
            "avg_relevance": 0.92,
            "last_accessed": "2025-07-07T14:20:00Z"
        },
        {
            "file_id": "doc3",
            "filename": "Company_Handbook.pdf", 
            "access_count": 15,
            "avg_relevance": 0.76,
            "last_accessed": "2025-07-07T13:10:00Z"
        }
    ]
    
    try:
        return [DocumentUsageResponse(**s) for s in mock_document_usage]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch document usage stats: {str(e)}"
        )

@router.get("/documents/metrics")
async def get_document_metrics(
    days: int = Query(30, ge=1, le=365, description="Number of days for metrics"),
    tenant: TenantResponse = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get document-related metrics and trends"""
    analytics = AnalyticsService(db)
    
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        performance_data = analytics.get_performance_metrics(tenant.id, days)
        
        # Extract document-specific metrics
        document_metrics = []
        for metric in performance_data['metrics']:
            document_metrics.append({
                'date': metric['date'],
                'total_documents': metric['documents'],
                'storage_mb': metric['storage_mb']
            })
        
        # Calculate totals
        latest_metrics = document_metrics[-1] if document_metrics else {'total_documents': 0, 'storage_mb': 0}
        
        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days
            },
            "summary": {
                "total_documents": latest_metrics['total_documents'],
                "storage_used_mb": latest_metrics['storage_mb'],
                "avg_file_size_mb": latest_metrics['storage_mb'] / latest_metrics['total_documents'] if latest_metrics['total_documents'] > 0 else 0
            },
            "daily_trends": document_metrics
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch document metrics: {str(e)}"
        )

# =============================================
# USER ACTIVITY ENDPOINTS
# =============================================

@router.get("/users/activity")
async def get_user_activity(
    days: int = Query(30, ge=1, le=365, description="Number of days for activity"),
    tenant: TenantResponse = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get user activity metrics and trends"""
    analytics = AnalyticsService(db)
    
    try:
        performance_data = analytics.get_performance_metrics(tenant.id, days)
        
        # Extract user activity metrics
        user_metrics = []
        for metric in performance_data['metrics']:
            user_metrics.append({
                'date': metric['date'],
                'unique_users': metric['unique_users'],
                'total_queries': metric['total_queries'],
                'queries_per_user': metric['total_queries'] / metric['unique_users'] if metric['unique_users'] > 0 else 0
            })
        
        # Calculate summary
        total_unique_users = max(m['unique_users'] for m in user_metrics) if user_metrics else 0
        total_queries = sum(m['total_queries'] for m in user_metrics)
        avg_queries_per_user = total_queries / total_unique_users if total_unique_users > 0 else 0
        
        return {
            "period": performance_data['period'],
            "summary": {
                "total_unique_users": total_unique_users,
                "total_queries": total_queries,
                "avg_queries_per_user": round(avg_queries_per_user, 2)
            },
            "daily_activity": user_metrics
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user activity: {str(e)}"
        )

# =============================================
# PERFORMANCE ENDPOINTS
# =============================================

@router.get("/performance/overview")
async def get_performance_overview(
    days: int = Query(7, ge=1, le=365, description="Number of days for overview"),
    tenant: TenantResponse = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get performance overview with key metrics"""
    analytics = AnalyticsService(db)
    
    try:
        performance_data = analytics.get_performance_metrics(tenant.id, days)
        
        metrics = performance_data['metrics']
        if not metrics:
            return {
                "period": performance_data['period'],
                "overview": {
                    "avg_response_time": 0,
                    "success_rate": 0,
                    "total_queries": 0,
                    "performance_trend": "stable"
                }
            }
        
        # Calculate overview metrics
        avg_response_time = sum(m['avg_response_time'] or 0 for m in metrics) / len(metrics)
        avg_success_rate = sum(m['success_rate'] for m in metrics) / len(metrics)
        total_queries = sum(m['total_queries'] for m in metrics)
        
        # Determine trend
        if len(metrics) >= 2:
            recent_avg = sum(m['avg_response_time'] or 0 for m in metrics[-3:]) / min(3, len(metrics))
            earlier_avg = sum(m['avg_response_time'] or 0 for m in metrics[:3]) / min(3, len(metrics))
            
            if recent_avg < earlier_avg * 0.9:
                trend = "improving"
            elif recent_avg > earlier_avg * 1.1:
                trend = "degrading"
            else:
                trend = "stable"
        else:
            trend = "stable"
        
        return {
            "period": performance_data['period'],
            "overview": {
                "avg_response_time": round(avg_response_time, 2),
                "success_rate": round(avg_success_rate, 2),
                "total_queries": total_queries,
                "performance_trend": trend
            },
            "daily_metrics": metrics
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch performance overview: {str(e)}"
        )

# =============================================
# EXPORT ENDPOINTS
# =============================================

@router.get("/export/csv")
async def export_metrics_csv(
    days: int = Query(30, ge=1, le=365, description="Number of days to export"),
    metric_type: str = Query("daily", description="Type of metrics to export"),
    tenant: TenantResponse = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Export metrics data as CSV"""
    analytics = AnalyticsService(db)
    
    try:
        if metric_type == "daily":
            data = analytics.get_performance_metrics(tenant.id, days)
            
            # Convert to CSV format
            import io
            import csv
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            if data['metrics']:
                writer.writerow(data['metrics'][0].keys())
                
                # Write data rows
                for metric in data['metrics']:
                    writer.writerow(metric.values())
            
            csv_content = output.getvalue()
            output.close()
            
            return {
                "content_type": "text/csv",
                "filename": f"tenant_metrics_{tenant.id}_{days}days.csv",
                "data": csv_content
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported metric type: {metric_type}"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export metrics: {str(e)}"
        )