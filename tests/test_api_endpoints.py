"""
Comprehensive API Endpoints Test Suite for Enterprise RAG Platform

Tests all REST API endpoints including:
- Document management (upload, list, get, update, delete, download)
- Query processing (query, history, specific query results)
- Health checks (basic, detailed, system status, readiness, liveness)
- Tenant management (create, list, get, update, delete, stats)
- Sync operations (trigger sync, get sync status)
- Audit logs (get audit events, query audit history)
"""

import pytest
import sys
import os
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
import tempfile
import json
from datetime import datetime
import uuid

# Update the path to ensure 'src' is in our import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.backend.main import app
from src.backend.models.api_models import *

class TestAPIEndpoints:
    """Comprehensive test suite for all API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_tenant_id(self):
        """Mock tenant ID."""
        return str(uuid.uuid4())
    
    @pytest.fixture
    def auth_headers(self, mock_tenant_id):
        """Mock authentication headers."""
        return {
            "Authorization": f"Bearer test-token-{mock_tenant_id}",
            "X-Tenant-ID": mock_tenant_id
        }

    # ======================
    # DOCUMENT ENDPOINTS
    # ======================
    
    @patch('src.backend.middleware.auth.get_current_tenant')
    @patch('src.backend.api.v1.routes.documents.DocumentIngestionPipeline')
    @patch('src.backend.api.v1.routes.documents.TenantFileSystemManager')
    def test_upload_document(self, mock_fs_manager, mock_ingestion, mock_auth, client, mock_tenant_id, auth_headers):
        """Test document upload endpoint."""
        # Setup mocks
        mock_auth.return_value = mock_tenant_id
        mock_fs_manager_instance = Mock()
        mock_fs_manager.return_value = mock_fs_manager_instance
        mock_fs_manager_instance.save_uploaded_file.return_value = "/path/to/file.pdf"
        
        mock_ingestion_instance = Mock()
        mock_ingestion.return_value = mock_ingestion_instance
        mock_result = Mock()
        mock_result.chunks_created = 10
        mock_result.processing_time = 2.5
        mock_ingestion_instance.process_document.return_value = mock_result
        
        # Test successful upload
        test_file_content = b"PDF file content"
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.pdf", test_file_content, "application/pdf")},
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "document_id" in data
        assert data["filename"] == "test.pdf"
        assert data["status"] == "processed"
        assert data["chunks_created"] == 10
    
    @patch('src.backend.middleware.auth.get_current_tenant')
    def test_upload_document_invalid_file(self, mock_auth, client, mock_tenant_id, auth_headers):
        """Test document upload with invalid file."""
        mock_auth.return_value = mock_tenant_id
        
        # Test without filename
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("", b"content", "application/pdf")},
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "Filename is required" in response.json()["detail"]
    
    @patch('src.backend.middleware.auth.get_current_tenant')
    def test_list_documents(self, mock_auth, client, mock_tenant_id, auth_headers):
        """Test list documents endpoint."""
        mock_auth.return_value = mock_tenant_id
        
        response = client.get("/api/v1/documents/", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert "total_count" in data
        assert "page" in data
        assert "page_size" in data
    
    @patch('src.backend.middleware.auth.get_current_tenant')
    def test_get_document(self, mock_auth, client, mock_tenant_id, auth_headers):
        """Test get specific document endpoint."""
        mock_auth.return_value = mock_tenant_id
        
        document_id = "doc-1"
        response = client.get(f"/api/v1/documents/{document_id}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == document_id
    
    @patch('src.backend.middleware.auth.get_current_tenant')
    def test_get_document_not_found(self, mock_auth, client, mock_tenant_id, auth_headers):
        """Test get non-existent document."""
        mock_auth.return_value = mock_tenant_id
        
        document_id = "non-existent"
        response = client.get(f"/api/v1/documents/{document_id}", headers=auth_headers)
        
        assert response.status_code == 404
    
    @patch('src.backend.middleware.auth.get_current_tenant')
    def test_delete_document(self, mock_auth, client, mock_tenant_id, auth_headers):
        """Test delete document endpoint."""
        mock_auth.return_value = mock_tenant_id
        
        document_id = "doc-1"
        response = client.delete(f"/api/v1/documents/{document_id}", headers=auth_headers)
        
        # Should return 204 No Content for successful deletion
        assert response.status_code == 204

    # ======================
    # QUERY ENDPOINTS
    # ======================
    
    @patch('src.backend.middleware.auth.get_current_tenant')
    @patch('src.backend.core.rag_pipeline.get_rag_pipeline')
    def test_process_query(self, mock_rag_pipeline, mock_auth, client, mock_tenant_id, auth_headers):
        """Test query processing endpoint."""
        mock_auth.return_value = mock_tenant_id
        
        # Setup mock RAG response
        mock_pipeline_instance = Mock()
        mock_rag_pipeline.return_value = mock_pipeline_instance
        mock_rag_response = Mock()
        mock_rag_response.query = "What is Python?"
        mock_rag_response.answer = "Python is a programming language."
        mock_rag_response.processing_time = 1.5
        mock_pipeline_instance.process_query.return_value = mock_rag_response
        
        query_data = {"query": "What is Python?"}
        response = client.post(
            "/api/v1/query/query",
            json=query_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "processing_time" in data
    
    @patch('src.backend.middleware.auth.get_current_tenant')
    def test_process_empty_query(self, mock_auth, client, mock_tenant_id, auth_headers):
        """Test query processing with empty query."""
        mock_auth.return_value = mock_tenant_id
        
        query_data = {"query": ""}
        response = client.post(
            "/api/v1/query/query",
            json=query_data,
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "Query cannot be empty" in response.json()["detail"]
    
    @patch('src.backend.middleware.auth.get_current_tenant')
    def test_get_query_history(self, mock_auth, client, mock_tenant_id, auth_headers):
        """Test query history endpoint."""
        mock_auth.return_value = mock_tenant_id
        
        response = client.get("/api/v1/query/history", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "queries" in data
        assert "total_count" in data

    # ======================
    # HEALTH ENDPOINTS
    # ======================
    
    def test_basic_health_check(self, client):
        """Test basic health check endpoint."""
        response = client.get("/api/v1/health/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "uptime_seconds" in data
    
    @patch('src.backend.api.v1.routes.health.check_database_health')
    @patch('src.backend.api.v1.routes.health.check_vector_store_health') 
    @patch('src.backend.api.v1.routes.health.check_embedding_service_health')
    def test_detailed_health_check(self, mock_embedding, mock_vector, mock_db, client):
        """Test detailed health check endpoint."""
        # Setup mock component responses
        mock_db.return_value = Mock(name="database", status="healthy")
        mock_vector.return_value = Mock(name="vector_store", status="healthy")
        mock_embedding.return_value = Mock(name="embedding_service", status="healthy")
        
        response = client.get("/api/v1/health/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        assert "components" in data
    
    def test_system_status(self, client):
        """Test system status endpoint."""
        response = client.get("/api/v1/health/status")
        
        assert response.status_code == 200
        data = response.json()
        assert "health" in data
        assert "metrics" in data
    
    def test_readiness_check(self, client):
        """Test readiness check endpoint."""
        response = client.get("/api/v1/health/readiness")
        
        assert response.status_code == 200
    
    def test_liveness_check(self, client):
        """Test liveness check endpoint."""
        response = client.get("/api/v1/health/liveness")
        
        assert response.status_code == 200

    # ======================
    # TENANT ENDPOINTS
    # ======================
    
    @patch('src.backend.middleware.auth.require_authentication')
    @patch('src.backend.api.v1.routes.tenants.TenantManager')
    def test_create_tenant(self, mock_tenant_manager, mock_auth, client):
        """Test create tenant endpoint."""
        # Setup mocks
        mock_auth.return_value = {"user": "admin"}
        mock_manager_instance = Mock()
        mock_tenant_manager.return_value = mock_manager_instance
        
        mock_tenant = Mock()
        mock_tenant.id = uuid.uuid4()
        mock_tenant.name = "Test Tenant"
        mock_tenant.description = "Test Description"
        mock_tenant.contact_email = "test@example.com"
        mock_tenant.status = "active"
        mock_tenant.created_at = datetime.utcnow()
        mock_tenant.updated_at = datetime.utcnow()
        mock_tenant.settings = {}
        
        mock_manager_instance.create_tenant.return_value = mock_tenant
        
        tenant_data = {
            "name": "Test Tenant",
            "description": "Test Description", 
            "contact_email": "test@example.com",
            "settings": {}
        }
        
        response = client.post(
            "/api/v1/tenants/",
            json=tenant_data,
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Tenant"
    
    @patch('src.backend.middleware.auth.require_authentication')
    @patch('src.backend.api.v1.routes.tenants.TenantManager')
    def test_list_tenants(self, mock_tenant_manager, mock_auth, client):
        """Test list tenants endpoint."""
        mock_auth.return_value = {"user": "admin"}
        mock_manager_instance = Mock()
        mock_tenant_manager.return_value = mock_manager_instance
        
        # Setup mock tenants
        mock_tenants = []
        mock_manager_instance.list_tenants.return_value = (mock_tenants, 0)
        mock_manager_instance.get_tenant_stats.return_value = {"document_count": 0, "storage_used": 0}
        
        response = client.get(
            "/api/v1/tenants/",
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "tenants" in data
        assert "total_count" in data

    # ======================
    # SYNC ENDPOINTS
    # ======================
    
    @patch('src.backend.middleware.auth.get_current_tenant')
    @patch('src.backend.api.v1.routes.sync.DeltaSyncService')
    def test_trigger_sync(self, mock_sync_service, mock_auth, client, mock_tenant_id, auth_headers):
        """Test trigger sync endpoint."""
        mock_auth.return_value = mock_tenant_id
        mock_service_instance = Mock()
        mock_sync_service.return_value = mock_service_instance
        
        mock_result = Mock()
        mock_result.sync_run_id = "sync-123"
        mock_result.files_processed = 5
        mock_result.duration = 10.5
        mock_service_instance.run_sync.return_value = mock_result
        
        response = client.post("/api/v1/sync/trigger", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "sync_run_id" in data
    
    @patch('src.backend.middleware.auth.get_current_tenant')
    def test_get_sync_status(self, mock_auth, client, mock_tenant_id, auth_headers):
        """Test get sync status endpoint."""
        mock_auth.return_value = mock_tenant_id
        
        response = client.get("/api/v1/sync/status", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    # ======================
    # AUDIT ENDPOINTS  
    # ======================
    
    @patch('src.backend.middleware.auth.get_current_tenant')
    def test_get_audit_events(self, mock_auth, client, mock_tenant_id, auth_headers):
        """Test get audit events endpoint."""
        mock_auth.return_value = mock_tenant_id
        
        response = client.get("/api/v1/audit/events", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "events" in data

    # ======================
    # AUTHENTICATION TESTS
    # ======================
    
    def test_unauthorized_access(self, client):
        """Test endpoints without authentication."""
        endpoints = [
            "/api/v1/documents/",
            "/api/v1/query/query",
            "/api/v1/sync/trigger"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code in [401, 403]  # Unauthorized or Forbidden
    
    def test_invalid_tenant_id(self, client):
        """Test endpoints with invalid tenant ID."""
        invalid_headers = {
            "Authorization": "Bearer invalid-token",
            "X-Tenant-ID": "invalid-uuid"
        }
        
        response = client.get("/api/v1/documents/", headers=invalid_headers)
        assert response.status_code in [400, 401, 403]

    # ======================
    # ERROR HANDLING TESTS
    # ======================
    
    @patch('src.backend.middleware.auth.get_current_tenant')
    def test_internal_server_error_handling(self, mock_auth, client, mock_tenant_id, auth_headers):
        """Test internal server error handling."""
        mock_auth.return_value = mock_tenant_id
        
        # This should trigger a 500 error due to missing implementation
        response = client.get("/api/v1/documents/non-existent-doc", headers=auth_headers)
        
        # Depending on implementation, this might be 404 or 500
        assert response.status_code in [404, 500]
    
    def test_request_validation_errors(self, client, auth_headers):
        """Test request validation errors."""
        # Test invalid JSON
        response = client.post(
            "/api/v1/query/query",
            data="invalid json",
            headers={**auth_headers, "Content-Type": "application/json"}
        )
        
        assert response.status_code == 422  # Unprocessable Entity

    # ======================
    # PAGINATION TESTS
    # ======================
    
    @patch('src.backend.middleware.auth.get_current_tenant')
    def test_pagination_parameters(self, mock_auth, client, mock_tenant_id, auth_headers):
        """Test pagination parameters in list endpoints."""
        mock_auth.return_value = mock_tenant_id
        
        # Test documents pagination
        response = client.get(
            "/api/v1/documents/?page=2&page_size=5",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 5
    
    def test_invalid_pagination_parameters(self, client, auth_headers):
        """Test invalid pagination parameters."""
        # Test negative page number
        response = client.get(
            "/api/v1/documents/?page=-1",
            headers=auth_headers
        )
        
        assert response.status_code in [400, 422]

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 