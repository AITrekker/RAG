"""
Comprehensive error handling system for the Enterprise RAG Platform.

This module provides:
- Custom exception classes for different error types
- Standardized error responses
- Error logging and monitoring
- Error code management
"""

import logging
import traceback
from typing import Dict, Any, Optional, Union
from datetime import datetime
from enum import Enum
from fastapi import HTTPException, status
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class ErrorCode(str, Enum):
    """Standard error codes for the platform."""
    # Authentication & Authorization
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    INVALID_API_KEY = "INVALID_API_KEY"
    API_KEY_EXPIRED = "API_KEY_EXPIRED"
    
    # Validation Errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    
    # Resource Errors
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RESOURCE_ALREADY_EXISTS = "RESOURCE_ALREADY_EXISTS"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    
    # Document Processing
    DOCUMENT_UPLOAD_FAILED = "DOCUMENT_UPLOAD_FAILED"
    DOCUMENT_PROCESSING_FAILED = "DOCUMENT_PROCESSING_FAILED"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    
    # Embedding & Vector Store
    EMBEDDING_GENERATION_FAILED = "EMBEDDING_GENERATION_FAILED"
    VECTOR_STORE_ERROR = "VECTOR_STORE_ERROR"
    SIMILARITY_SEARCH_FAILED = "SIMILARITY_SEARCH_FAILED"
    
    # LLM & Generation
    LLM_GENERATION_FAILED = "LLM_GENERATION_FAILED"
    MODEL_NOT_LOADED = "MODEL_NOT_LOADED"
    GENERATION_TIMEOUT = "GENERATION_TIMEOUT"
    
    # RAG Pipeline
    RAG_PIPELINE_ERROR = "RAG_PIPELINE_ERROR"
    CONTEXT_RETRIEVAL_FAILED = "CONTEXT_RETRIEVAL_FAILED"
    NO_RELEVANT_CONTEXT = "NO_RELEVANT_CONTEXT"
    
    # Sync & Processing
    SYNC_FAILED = "SYNC_FAILED"
    SYNC_IN_PROGRESS = "SYNC_IN_PROGRESS"
    PROCESSING_TIMEOUT = "PROCESSING_TIMEOUT"
    
    # System & Infrastructure
    DATABASE_ERROR = "DATABASE_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    
    # Rate Limiting & Quotas
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    
    # Tenant Management
    TENANT_NOT_FOUND = "TENANT_NOT_FOUND"
    TENANT_SUSPENDED = "TENANT_SUSPENDED"
    TENANT_QUOTA_EXCEEDED = "TENANT_QUOTA_EXCEEDED"


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RAGPlatformException(Exception):
    """Base exception for RAG Platform errors."""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        details: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.severity = severity
        self.details = details or {}
        self.tenant_id = tenant_id
        self.timestamp = datetime.utcnow()
        
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API response."""
        return {
            "error": self.message,
            "code": self.error_code.value,
            "status_code": self.status_code,
            "severity": self.severity.value,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "tenant_id": self.tenant_id
        }


# Specific exception classes
class AuthenticationError(RAGPlatformException):
    """Authentication related errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.UNAUTHORIZED,
            status_code=status.HTTP_401_UNAUTHORIZED,
            severity=ErrorSeverity.HIGH,
            details=details
        )


class AuthorizationError(RAGPlatformException):
    """Authorization related errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.FORBIDDEN,
            status_code=status.HTTP_403_FORBIDDEN,
            severity=ErrorSeverity.HIGH,
            details=details
        )


class ValidationError(RAGPlatformException):
    """Input validation errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.VALIDATION_ERROR,
            status_code=status.HTTP_400_BAD_REQUEST,
            severity=ErrorSeverity.LOW,
            details=details
        )


class ResourceNotFoundError(RAGPlatformException):
    """Resource not found errors."""
    def __init__(self, resource_type: str, resource_id: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"{resource_type} with id '{resource_id}' not found",
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
            status_code=status.HTTP_404_NOT_FOUND,
            severity=ErrorSeverity.LOW,
            details=details or {"resource_type": resource_type, "resource_id": resource_id}
        )


class DocumentProcessingError(RAGPlatformException):
    """Document processing errors."""
    def __init__(self, message: str, document_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.DOCUMENT_PROCESSING_FAILED,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            severity=ErrorSeverity.MEDIUM,
            details=details or {"document_id": document_id}
        )


class EmbeddingError(RAGPlatformException):
    """Embedding generation errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.EMBEDDING_GENERATION_FAILED,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            severity=ErrorSeverity.HIGH,
            details=details
        )


class LLMError(RAGPlatformException):
    """LLM generation errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.LLM_GENERATION_FAILED,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            severity=ErrorSeverity.HIGH,
            details=details
        )


class RAGPipelineError(RAGPlatformException):
    """RAG pipeline errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.RAG_PIPELINE_ERROR,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            severity=ErrorSeverity.HIGH,
            details=details
        )


class SyncError(RAGPlatformException):
    """Document sync errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.SYNC_FAILED,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            severity=ErrorSeverity.MEDIUM,
            details=details
        )


class DatabaseError(RAGPlatformException):
    """Database operation errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.DATABASE_ERROR,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            severity=ErrorSeverity.CRITICAL,
            details=details
        )


class ConfigurationError(RAGPlatformException):
    """Configuration errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.CONFIGURATION_ERROR,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            severity=ErrorSeverity.CRITICAL,
            details=details
        )


class RateLimitError(RAGPlatformException):
    """Rate limiting errors."""
    def __init__(self, message: str, retry_after: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            severity=ErrorSeverity.MEDIUM,
            details=details or {"retry_after": retry_after}
        )


def handle_exception(
    exc: Exception,
    tenant_id: Optional[str] = None,
    endpoint: Optional[str] = None
) -> HTTPException:
    """
    Convert any exception to a standardized HTTPException.
    
    Args:
        exc: The exception to handle
        tenant_id: Optional tenant ID for context
        endpoint: Optional endpoint for context
        
    Returns:
        HTTPException with standardized error response
    """
    # Log the exception
    log_error(exc, tenant_id, endpoint)
    
    # Handle known exceptions
    if isinstance(exc, RAGPlatformException):
        return HTTPException(
            status_code=exc.status_code,
            detail=exc.to_dict()
        )
    
    # Handle Pydantic validation errors
    if isinstance(exc, ValidationError):
        validation_error = ValidationError(
            message="Input validation failed",
            details={"validation_errors": exc.errors()}
        )
        return HTTPException(
            status_code=validation_error.status_code,
            detail=validation_error.to_dict()
        )
    
    # Handle FastAPI HTTPException
    if isinstance(exc, HTTPException):
        return exc
    
    # Handle unknown exceptions
    internal_error = RAGPlatformException(
        message="An unexpected error occurred",
        error_code=ErrorCode.INTERNAL_ERROR,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        severity=ErrorSeverity.CRITICAL,
        details={"original_error": str(exc)},
        tenant_id=tenant_id
    )
    
    return HTTPException(
        status_code=internal_error.status_code,
        detail=internal_error.to_dict()
    )


def log_error(
    exc: Exception,
    tenant_id: Optional[str] = None,
    endpoint: Optional[str] = None
) -> None:
    """
    Log an error with context information.
    
    Args:
        exc: The exception to log
        tenant_id: Optional tenant ID
        endpoint: Optional endpoint
    """
    error_info = {
        "error_type": type(exc).__name__,
        "error_message": str(exc),
        "tenant_id": tenant_id,
        "endpoint": endpoint,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    if isinstance(exc, RAGPlatformException):
        error_info.update({
            "error_code": exc.error_code.value,
            "severity": exc.severity.value,
            "status_code": exc.status_code,
            "details": exc.details
        })
        log_level = _get_log_level_for_severity(exc.severity)
    else:
        log_level = logging.ERROR
    
    logger.log(log_level, f"Error occurred: {error_info}")
    
    # Log full traceback for debugging
    if log_level >= logging.ERROR:
        logger.error(f"Full traceback: {traceback.format_exc()}")


def _get_log_level_for_severity(severity: ErrorSeverity) -> int:
    """Get log level for error severity."""
    severity_levels = {
        ErrorSeverity.LOW: logging.INFO,
        ErrorSeverity.MEDIUM: logging.WARNING,
        ErrorSeverity.HIGH: logging.ERROR,
        ErrorSeverity.CRITICAL: logging.CRITICAL
    }
    return severity_levels.get(severity, logging.ERROR)


def create_error_response(
    message: str,
    error_code: ErrorCode,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    details: Optional[Dict[str, Any]] = None,
    tenant_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a standardized error response.
    
    Args:
        message: Error message
        error_code: Error code
        status_code: HTTP status code
        details: Additional error details
        tenant_id: Optional tenant ID
        
    Returns:
        Standardized error response dictionary
    """
    return {
        "error": message,
        "code": error_code.value,
        "status_code": status_code,
        "timestamp": datetime.utcnow().isoformat(),
        "details": details or {},
        "tenant_id": tenant_id
    }


# Convenience functions for common errors
def not_found_error(resource_type: str, resource_id: str) -> HTTPException:
    """Create a not found error."""
    error = ResourceNotFoundError(resource_type, resource_id)
    return HTTPException(status_code=error.status_code, detail=error.to_dict())


def validation_error(message: str, details: Optional[Dict[str, Any]] = None) -> HTTPException:
    """Create a validation error."""
    error = ValidationError(message, details)
    return HTTPException(status_code=error.status_code, detail=error.to_dict())


def authentication_error(message: str = "Authentication required") -> HTTPException:
    """Create an authentication error."""
    error = AuthenticationError(message)
    return HTTPException(status_code=error.status_code, detail=error.to_dict())


def authorization_error(message: str = "Insufficient permissions") -> HTTPException:
    """Create an authorization error."""
    error = AuthorizationError(message)
    return HTTPException(status_code=error.status_code, detail=error.to_dict())


def internal_error(message: str = "Internal server error", details: Optional[Dict[str, Any]] = None) -> HTTPException:
    """Create an internal error."""
    error = RAGPlatformException(
        message=message,
        error_code=ErrorCode.INTERNAL_ERROR,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        severity=ErrorSeverity.CRITICAL,
        details=details
    )
    return HTTPException(status_code=error.status_code, detail=error.to_dict()) 