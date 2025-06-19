"""
Query parsing and normalization module.

This module handles parsing and normalizing user queries to improve search quality
and ensure consistent query processing.
"""

import re
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class QueryType(Enum):
    """Types of queries that can be identified."""
    QUESTION = "question"
    KEYWORD = "keyword"
    COMPARISON = "comparison"
    DEFINITION = "definition"
    EXAMPLE = "example"
    HOW_TO = "how_to"
    UNKNOWN = "unknown"

@dataclass
class ParsedQuery:
    """Structured representation of a parsed query."""
    original_query: str
    normalized_query: str
    query_type: QueryType
    keywords: List[str]
    metadata: Dict[str, Any]
    
    # Optional extracted components
    subject: Optional[str] = None
    action: Optional[str] = None
    context: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "original_query": self.original_query,
            "normalized_query": self.normalized_query,
            "query_type": self.query_type.value,
            "keywords": self.keywords,
            "metadata": self.metadata,
            "subject": self.subject,
            "action": self.action,
            "context": self.context
        }

class QueryParser:
    """
    Parses and normalizes user queries.
    
    Features:
    - Query type classification
    - Keyword extraction
    - Query component extraction (subject, action, context)
    - Query normalization
    - Metadata enrichment
    """
    
    # Common question starters
    QUESTION_STARTERS = {
        'what': QueryType.QUESTION,
        'who': QueryType.QUESTION,
        'where': QueryType.QUESTION,
        'when': QueryType.QUESTION,
        'why': QueryType.QUESTION,
        'how': QueryType.HOW_TO,
        'can': QueryType.QUESTION,
        'could': QueryType.QUESTION,
        'should': QueryType.QUESTION,
        'is': QueryType.QUESTION,
        'are': QueryType.QUESTION,
        'will': QueryType.QUESTION,
        'do': QueryType.QUESTION,
        'does': QueryType.QUESTION
    }
    
    # Common patterns for different query types
    QUERY_PATTERNS = {
        QueryType.DEFINITION: [
            r"^(?:what|who|define|explain|describe)\s+(?:is|are|does)\s+.*[?]?$",
            r"^(?:meaning|definition)\s+of\s+.*$"
        ],
        QueryType.EXAMPLE: [
            r"^(?:show|give|provide)\s+(?:me\s+)?(?:an?\s+)?example\s+of\s+.*$",
            r"^example\s+of\s+.*$"
        ],
        QueryType.HOW_TO: [
            r"^how\s+(?:to|do|can|should)\s+.*[?]?$",
            r"^(?:steps?|guide|tutorial)\s+(?:to|for)\s+.*$"
        ],
        QueryType.COMPARISON: [
            r"^(?:compare|difference\s+between|vs\.?|versus)\s+.*$",
            r"^.*\s+(?:vs\.?|versus|compared\s+to)\s+.*$"
        ]
    }
    
    def __init__(self):
        """Initialize the query parser."""
        # Compile regex patterns
        self.compiled_patterns = {
            qtype: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
            for qtype, patterns in self.QUERY_PATTERNS.items()
        }
    
    def parse_and_normalize(self, query: str, tenant_id: str) -> ParsedQuery:
        """
        Parse and normalize a query.
        
        Args:
            query: The user's query string
            tenant_id: The tenant's ID for logging
            
        Returns:
            ParsedQuery: Structured representation of the parsed query
        """
        try:
            # Normalize query
            normalized = self._normalize_query(query)
            
            # Identify query type
            query_type = self._identify_query_type(normalized)
            
            # Extract components
            components = self._extract_components(normalized, query_type)
            
            # Extract keywords
            keywords = self._extract_keywords(normalized)
            
            # Create metadata
            metadata = {
                "tenant_id": tenant_id,
                "original_length": len(query),
                "normalized_length": len(normalized),
                "has_question_mark": "?" in query,
                "keyword_count": len(keywords)
            }
            
            parsed = ParsedQuery(
                original_query=query,
                normalized_query=normalized,
                query_type=query_type,
                keywords=keywords,
                metadata=metadata,
                **components
            )
            
            logger.info(
                f"Parsed query for tenant {tenant_id}: "
                f"type={query_type.value}, keywords={len(keywords)}"
            )
            
            return parsed
            
        except Exception as e:
            logger.error(f"Failed to parse query for tenant {tenant_id}: {str(e)}")
            raise
    
    def _normalize_query(self, query: str) -> str:
        """
        Normalize a query string.
        
        Performs:
        1. Convert to lowercase
        2. Remove extra whitespace
        3. Remove punctuation except question marks
        4. Standardize quotation marks
        5. Remove unnecessary words
        """
        # Convert to lowercase
        normalized = query.lower()
        
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        
        # Remove unnecessary punctuation but keep question marks
        normalized = re.sub(r'[^\w\s?]', ' ', normalized)
        
        # Standardize whitespace again
        normalized = ' '.join(normalized.split())
        
        # Remove common filler words
        filler_words = {'please', 'could', 'would', 'you', 'tell', 'me', 'about', 'the', 'a', 'an'}
        normalized = ' '.join(
            word for word in normalized.split()
            if word not in filler_words
        )
        
        return normalized.strip()
    
    def _identify_query_type(self, query: str) -> QueryType:
        """Identify the type of query."""
        # Check for exact question starters
        first_word = query.split()[0] if query else ''
        if first_word in self.QUESTION_STARTERS:
            return self.QUESTION_STARTERS[first_word]
        
        # Check patterns for each query type
        for qtype, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                if pattern.match(query):
                    return qtype
        
        # Default to keyword search if no patterns match
        return QueryType.KEYWORD if query else QueryType.UNKNOWN
    
    def _extract_components(self, query: str, query_type: QueryType) -> Dict[str, str]:
        """Extract subject, action, and context from query."""
        components = {"subject": None, "action": None, "context": None}
        
        words = query.split()
        if not words:
            return components
        
        if query_type == QueryType.HOW_TO and len(words) > 2:
            # For "how to" queries, action is after "how to"
            action_start = 2 if words[0] == "how" and words[1] == "to" else 1
            components["action"] = " ".join(words[action_start:])
        
        elif query_type == QueryType.DEFINITION and len(words) > 2:
            # For definition queries, subject is after "what is" or similar
            subject_start = 2 if words[0] in ["what", "who"] and words[1] in ["is", "are"] else 1
            components["subject"] = " ".join(words[subject_start:])
        
        elif query_type == QueryType.COMPARISON and len(words) > 1:
            # For comparison queries, try to extract both subjects
            parts = re.split(r'\s+(?:vs\.?|versus|compared\s+to)\s+', query)
            if len(parts) == 2:
                components["subject"] = parts[0].strip()
                components["context"] = parts[1].strip()
        
        return components
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Extract important keywords from query."""
        # Split into words
        words = query.split()
        
        # Remove very common words
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
            'for', 'of', 'with', 'by', 'from', 'up', 'about', 'into', 'over',
            'after', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'shall', 'should', 'may', 'might', 'must', 'can', 'could'
        }
        
        keywords = [
            word for word in words
            if word not in stopwords and len(word) > 2
        ]
        
        return keywords 