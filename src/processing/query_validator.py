"""
Query input validation and sanitization with basic prompt injection defense.

This module provides validation and sanitization for user queries to prevent
prompt injection attacks and ensure query quality.
"""

import re
import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)

class QueryValidationError(Exception):
    """Raised when query validation fails."""
    pass

class QuerySanitizationConfig(BaseModel):
    """Configuration for query sanitization."""
    max_query_length: int = Field(default=500, description="Maximum allowed query length")
    min_query_length: int = Field(default=3, description="Minimum required query length")
    max_special_chars_ratio: float = Field(default=0.3, description="Maximum ratio of special characters allowed")
    blocked_patterns: list[str] = Field(
        default=[
            r"system:", r"assistant:", r"user:",  # Block role prompts
            r"```", r"'''",  # Block code blocks
            r"<\/?[a-z]+>",  # Block HTML/XML tags
            r"\{\{.*?\}\}",  # Block template expressions
            r"\[\[.*?\]\]",  # Block special brackets
        ],
        description="Regex patterns to block"
    )
    max_consecutive_chars: int = Field(default=10, description="Maximum consecutive identical characters")
    max_newlines: int = Field(default=5, description="Maximum number of newlines allowed")

class QueryValidator:
    """
    Validates and sanitizes user queries to prevent prompt injection and ensure quality.
    
    Features:
    - Length validation
    - Special character ratio checking
    - Pattern blocking (prompt injection prevention)
    - Character repetition limits
    - Basic structural validation
    """
    
    def __init__(self, config: Optional[QuerySanitizationConfig] = None):
        """Initialize validator with optional custom config."""
        self.config = config or QuerySanitizationConfig()
    
    def validate_and_sanitize(self, query: str, tenant_id: str) -> Tuple[str, Dict[str, Any]]:
        """
        Validate and sanitize a query.
        
        Args:
            query: The user's query string
            tenant_id: The tenant's ID for logging
            
        Returns:
            Tuple[str, Dict[str, Any]]: (sanitized query, validation info)
            
        Raises:
            QueryValidationError: If validation fails
        """
        validation_info = {
            "original_length": len(query),
            "warnings": [],
            "modifications": []
        }
        
        try:
            # Basic validation
            self._validate_length(query)
            self._validate_special_chars(query, validation_info)
            self._validate_patterns(query, validation_info)
            self._validate_structure(query, validation_info)
            
            # Sanitize
            sanitized = self._sanitize_query(query, validation_info)
            
            # Final validation
            self._validate_length(sanitized)
            
            validation_info["final_length"] = len(sanitized)
            logger.info(
                f"Query validated and sanitized for tenant {tenant_id}: "
                f"original_length={validation_info['original_length']}, "
                f"final_length={validation_info['final_length']}"
            )
            
            return sanitized, validation_info
            
        except QueryValidationError as e:
            logger.warning(f"Query validation failed for tenant {tenant_id}: {str(e)}")
            raise
    
    def _validate_length(self, query: str):
        """Validate query length."""
        if len(query) > self.config.max_query_length:
            raise QueryValidationError(
                f"Query too long: {len(query)} chars (max {self.config.max_query_length})"
            )
        if len(query) < self.config.min_query_length:
            raise QueryValidationError(
                f"Query too short: {len(query)} chars (min {self.config.min_query_length})"
            )
    
    def _validate_special_chars(self, query: str, validation_info: Dict[str, Any]):
        """Validate special character ratio."""
        special_chars = sum(1 for c in query if not c.isalnum() and not c.isspace())
        ratio = special_chars / len(query) if len(query) > 0 else 0
        
        if ratio > self.config.max_special_chars_ratio:
            validation_info["warnings"].append(
                f"High special character ratio: {ratio:.2f}"
            )
    
    def _validate_patterns(self, query: str, validation_info: Dict[str, Any]):
        """Check for blocked patterns."""
        for pattern in self.config.blocked_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                raise QueryValidationError(f"Query contains blocked pattern: {pattern}")
    
    def _validate_structure(self, query: str, validation_info: Dict[str, Any]):
        """Validate query structure."""
        # Check for character repetition
        for match in re.finditer(r'(.)\1{' + str(self.config.max_consecutive_chars) + ',}', query):
            validation_info["warnings"].append(
                f"Excessive character repetition: {match.group(0)}"
            )
        
        # Check newlines
        newlines = query.count('\n')
        if newlines > self.config.max_newlines:
            validation_info["warnings"].append(
                f"Excessive newlines: {newlines} (max {self.config.max_newlines})"
            )
    
    def _sanitize_query(self, query: str, validation_info: Dict[str, Any]) -> str:
        """
        Sanitize the query.
        
        Performs the following:
        1. Normalize whitespace
        2. Remove control characters
        3. Limit consecutive characters
        4. Remove potentially dangerous patterns
        """
        # Normalize whitespace
        sanitized = ' '.join(query.split())
        if sanitized != query:
            validation_info["modifications"].append("normalized_whitespace")
        
        # Remove control characters
        sanitized = ''.join(char for char in sanitized if char.isprintable())
        if sanitized != query:
            validation_info["modifications"].append("removed_control_chars")
        
        # Limit consecutive characters
        pattern = r'(.)\1{' + str(self.config.max_consecutive_chars) + ',}'
        sanitized = re.sub(pattern, lambda m: m.group(1) * self.config.max_consecutive_chars, sanitized)
        if sanitized != query:
            validation_info["modifications"].append("limited_consecutive_chars")
        
        return sanitized 