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
from unittest.mock import Mock, patch, MagicMock, AsyncMock
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
    
    @patch('src.backend.api.v1.routes.documents.DocumentIngestionPipeline')
    @patch('src.backend.api.v1.routes.documents.TenantFileSystemManager')
    def test_upload_document(self, mock_fs_manager, mock_ingestion, authenticated_client, auth_headers):
        """Test document upload endpoint."""
        # Setup mocks
        mock_fs_manager_instance = Mock()
        mock_fs_manager.return_value = mock_fs_manager_instance
        
        # Make the mock awaitable
        async def save_file_mock(*args, **kwargs):
            return "/path/to/file.pdf"
        mock_fs_manager_instance.save_uploaded_file = save_file_mock

        mock_ingestion_instance = Mock()
        mock_ingestion.return_value = mock_ingestion_instance
        mock_result = Mock()
        mock_result.chunks_created = 10
        mock_result.processing_time = 2.5
        mock_ingestion_instance.process_document.return_value = mock_result
        
        # Test successful upload
        test_file_content = b"PDF file content"
        response = authenticated_client.post(
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
    
    def test_upload_document_invalid_file(self, authenticated_client, auth_headers):
        """Test document upload with invalid file."""
        # Test without filename
        response = authenticated_client.post(
            "/api/v1/documents/upload",
            files={"file": ("", b"content", "application/pdf")},
            headers=auth_headers
        )
        assert response.status_code == 422
    
    def test_list_documents(self, authenticated_client, auth_headers):
        """Test list documents endpoint."""
        response = authenticated_client.get("/api/v1/documents/", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert "total_count" in data
        assert "page" in data
        assert "page_size" in data
    
    def test_get_document(self, authenticated_client, auth_headers):
        """Test get specific document endpoint."""
        document_id = "doc-1"
        response = authenticated_client.get(f"/api/v1/documents/{document_id}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == document_id
    
    def test_get_document_not_found(self, authenticated_client, auth_headers):
        """Test get non-existent document."""
        document_id = "non-existent"
        response = authenticated_client.get(f"/api/v1/documents/{document_id}", headers=auth_headers)
        
        assert response.status_code == 404
    
    @patch('src.backend.api.v1.routes.documents.DocumentIngestionPipeline')
    def test_delete_document(self, mock_ingestion, authenticated_client, auth_headers):
        """Test document deletion endpoint."""
        mock_pipeline_instance = Mock()
        mock_ingestion.return_value = mock_pipeline_instance

        # Make the mock awaitable
        async def delete_doc_mock(*args, **kwargs):
            return True
        mock_pipeline_instance.delete_document = delete_doc_mock

        doc_id = str(uuid.uuid4())
        response = authenticated_client.delete(f"/api/v1/documents/{doc_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["message"] == "Document deleted successfully"

    # ======================
    # QUERY ENDPOINTS
    # ======================
    
    @patch('src.backend.core.rag_pipeline.get_rag_pipeline')
    def test_process_query(self, mock_rag_pipeline, authenticated_client, auth_headers):
        """Test query processing endpoint."""
        # Setup mock RAG response
        mock_pipeline_instance = Mock()
        mock_rag_pipeline.return_value = mock_pipeline_instance

        # Make the process_query mock awaitable
        async def process_query_mock(*args, **kwargs):
            response_mock = Mock()
            response_mock.query = "What is Python?"
            response_mock.answer = "Python is a programming language."
            response_mock.processing_time = 1.5
            response_mock.sources = []
            return response_mock
        mock_pipeline_instance.process_query = process_query_mock

        query_data = {"query": "What is Python?"}
        response = authenticated_client.post(
            "/api/v1/query/",
            json=query_data,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Python is a programming language."
    
    def test_process_empty_query(self, authenticated_client, auth_headers):
        """Test query processing with empty query."""
        query_data = {"query": ""}
        response = authenticated_client.post(
            "/api/v1/query/",
            json=query_data,
            headers=auth_headers
        )
        assert response.status_code == 422
    
    def test_get_query_history(self, authenticated_client, auth_headers):
        """Test query history endpoint."""
        response = authenticated_client.get("/api/v1/query/history", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "queries" in data

    # ======================
    # HEALTH ENDPOINTS
    # ======================
    
    def test_basic_health_check(self, client):
        """Test basic health check endpoint."""
        response = client.get("/api/v1/health/")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "service" in data
    
    @patch('src.backend.api.v1.routes.health.check_database_health', new_callable=AsyncMock)
    @patch('src.backend.api.v1.routes.health.check_vector_store_health', new_callable=AsyncMock)
    @patch('src.backend.api.v1.routes.health.check_embedding_service_health', new_callable=AsyncMock)
    def test_detailed_health_check(self, mock_embedding, mock_vector, mock_db, client):
        """Test detailed health check endpoint."""
        mock_db.return_value = {"name": "database", "status": "healthy"}
        mock_vector.return_value = {"name": "vector_store", "status": "healthy"}
        mock_embedding.return_value = {"name": "embedding_service", "status": "healthy"}
        
        response = client.get("/api/v1/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
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
    
    @patch('src.backend.api.v1.routes.tenants.TenantManager')
    def test_create_tenant(self, mock_tenant_manager, authenticated_client):
        """Test create tenant endpoint."""
        mock_manager_instance = Mock()
        mock_tenant_manager.return_value = mock_manager_instance

        # Make the mock awaitable
        async def create_tenant_mock(*args, **kwargs):
            tenant_mock = Mock()
            tenant_mock.id = uuid.uuid4()
            tenant_mock.name = "Test Tenant"
            tenant_mock.description = "Test Description"
            tenant_mock.contact_email = "test@example.com"
            tenant_mock.status = "active"
            tenant_mock.created_at = datetime.utcnow()
            tenant_mock.updated_at = datetime.utcnow()
            tenant_mock.settings = {}
            return tenant_mock
        mock_manager_instance.create_tenant = create_tenant_mock

        tenant_data = {
            "name": "Test Tenant",
            "description": "Test Description"
        }

        response = authenticated_client.post(
            "/api/v1/tenants/",
            json=tenant_data,
        )
        assert response.status_code == 201
        assert "id" in response.json()
    
    @patch('src.backend.api.v1.routes.tenants.TenantManager')
    def test_list_tenants(self, mock_tenant_manager, authenticated_client):
        """Test list tenants endpoint."""
        mock_manager_instance = Mock()
        mock_tenant_manager.return_value = mock_manager_instance

        # Make the mock awaitable
        async def list_tenants_mock(*args, **kwargs):
            return ([], 0)
        async def get_stats_mock(*args, **kwargs):
            return {"document_count": 0, "storage_used": 0}

        mock_manager_instance.list_tenants = list_tenants_mock
        mock_manager_instance.get_tenant_stats = get_stats_mock

        response = authenticated_client.get(
            "/api/v1/tenants/",
        )
        assert response.status_code == 200
        assert "tenants" in response.json()

    # ======================
    # SYNC ENDPOINTS
    # ======================
    
    @patch('src.backend.api.v1.routes.sync.DeltaSync')
    def test_trigger_sync(self, mock_delta_sync, authenticated_client, auth_headers):
        """Test trigger sync endpoint."""
        mock_service_instance = Mock()
        mock_delta_sync.return_value = mock_service_instance
        
        async def run_sync_mock(*args, **kwargs):
            mock_result = Mock()
            mock_result.sync_run_id = "sync-123"
            return mock_result
        mock_service_instance.run_sync = run_sync_mock

        response = authenticated_client.post(
            "/api/v1/sync/trigger", 
            json={"force_full_sync": False}, 
            headers=auth_headers
        )
        assert response.status_code == 200
        assert "message" in response.json()

    def test_get_sync_status(self, authenticated_client, auth_headers):
        """Test get sync status endpoint."""
        response = authenticated_client.get("/api/v1/sync/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "current_status" in data

    # ======================
    # AUDIT ENDPOINTS
    # ======================
    
    def test_get_audit_events(self, authenticated_client, auth_headers):
        """Test get audit events endpoint."""
        response = authenticated_client.get("/api/v1/audit/events", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    # ======================
    # SECURITY & VALIDATION
    # ======================
    
    def test_unauthorized_access(self, client):
        """Test endpoints without authentication."""
        # Use a POST for endpoints that require it
        response = client.post("/api/v1/documents/upload", files={"file": ("test.pdf", b"c")})
        assert response.status_code in [401, 403]
        
        response = client.post("/api/v1/query/", json={"query": "test"})
        assert response.status_code in [401, 403]

        response = client.post("/api/v1/sync/trigger", json={})
        assert response.status_code in [401, 403]

    def test_invalid_tenant_id(self, client):
        """Test endpoints with invalid tenant ID."""
        invalid_headers = {"X-Tenant-ID": "invalid-uuid"}
        response = client.get("/api/v1/documents/", headers=invalid_headers)
        assert response.status_code in [401, 403]

    @patch('src.backend.middleware.auth.APIKeyValidator.validate_api_key')
    def test_request_validation_errors(self, mock_validate, authenticated_client, auth_headers):
        """Test request validation errors."""
        mock_validate.return_value = True # Mock auth for this test
        
        # Test invalid JSON for a POST endpoint
        response = authenticated_client.post(
            "/api/v1/tenants/",
            data="invalid json",
            headers={**auth_headers, "Content-Type": "application/json"}
        )
        assert response.status_code == 422

    def test_pagination_parameters(self, authenticated_client, auth_headers):
        """Test valid pagination parameters."""
        response = authenticated_client.get("/api/v1/documents/?page=2&page_size=5", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 5

    def test_invalid_pagination_parameters(self, authenticated_client, auth_headers):
        """Test invalid pagination parameters."""
        response = authenticated_client.get("/api/v1/documents/?page=-1", headers=auth_headers)
        assert response.status_code == 422

if __name__ == "__main__":
    pytest.main()