"""
Query metadata extraction module.

This module extracts and enriches metadata from queries to improve search relevance
and provide additional context for query processing.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime
import spacy
from spacy.tokens import Doc
from spacy.language import Language

logger = logging.getLogger(__name__)

@dataclass
class QueryMetadata:
    """Structured representation of query metadata."""
    # Basic metadata
    timestamp: datetime
    tenant_id: str
    session_id: Optional[str]
    
    # Query characteristics
    query_length: int
    word_count: int
    avg_word_length: float
    
    # Extracted entities
    named_entities: Dict[str, List[str]]
    temporal_references: List[str]
    numerical_values: List[str]
    
    # Context hints
    domain_specific_terms: List[str]
    technical_terms: List[str]
    
    # Query structure
    has_quotes: bool
    quote_contents: List[str]
    has_special_chars: bool
    special_chars: Set[str]
    
    # Additional context
    source_context: Optional[Dict[str, Any]] = None
    user_context: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "tenant_id": self.tenant_id,
            "session_id": self.session_id,
            "query_characteristics": {
                "length": self.query_length,
                "word_count": self.word_count,
                "avg_word_length": self.avg_word_length
            },
            "entities": {
                "named_entities": self.named_entities,
                "temporal_references": self.temporal_references,
                "numerical_values": self.numerical_values
            },
            "context_hints": {
                "domain_terms": self.domain_specific_terms,
                "technical_terms": self.technical_terms
            },
            "structure": {
                "has_quotes": self.has_quotes,
                "quote_contents": self.quote_contents,
                "has_special_chars": self.has_special_chars,
                "special_chars": list(self.special_chars)
            },
            "additional_context": {
                "source": self.source_context,
                "user": self.user_context
            }
        }

class QueryMetadataExtractor:
    """
    Extracts and enriches metadata from queries.
    
    Features:
    - Basic query statistics
    - Named entity recognition
    - Temporal reference extraction
    - Technical term identification
    - Quote and special character analysis
    - Context enrichment
    """
    
    # Technical term indicators
    TECHNICAL_PATTERNS = [
        r"\b[A-Z][A-Za-z]*(?:Exception|Error|Warning)\b",  # Exception names
        r"\b(?:function|method|class|module|package)\s+[a-zA-Z_]\w*\b",  # Code elements
        r"\b[A-Z][A-Z0-9_]*\b",  # Constants
        r"\b(?:v\d+(?:\.\d+)*|\d+\.\d+\.\d+)\b",  # Versions
        r"\b[a-zA-Z_]\w*\([^)]*\)",  # Function calls
        r"\b(?:http|https|ftp|sftp|ssh)://\S+",  # URLs
        r"\b(?:GET|POST|PUT|DELETE|PATCH)\b",  # HTTP methods
        r"\b\d+\s*(?:ms|[GMK]B|Hz|px|em|rem)\b"  # Technical measurements
    ]
    
    # Domain-specific term patterns (customizable per tenant)
    DEFAULT_DOMAIN_PATTERNS = [
        r"\b(?:api|sdk|cli|gui|ui|ux)\b",  # Tech abbreviations
        r"\b(?:database|server|client|cache|proxy)\b",  # Infrastructure terms
        r"\b(?:async|sync|concurrent|parallel)\b",  # Programming concepts
        r"\b(?:deploy|build|test|debug|profile)\b",  # Development activities
        r"\b(?:config|settings?|preferences?)\b"  # Configuration terms
    ]
    
    def __init__(self, nlp: Optional[Language] = None):
        """
        Initialize the metadata extractor.
        
        Args:
            nlp: Optional spaCy language model (will load en_core_web_sm if None)
        """
        # Load spaCy model if not provided
        self.nlp = nlp or spacy.load("en_core_web_sm")
        
        # Compile regex patterns
        self.technical_patterns = [
            re.compile(pattern, re.IGNORECASE) 
            for pattern in self.TECHNICAL_PATTERNS
        ]
        self.domain_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.DEFAULT_DOMAIN_PATTERNS
        ]
    
    def extract_metadata(
        self,
        query: str,
        tenant_id: str,
        session_id: Optional[str] = None,
        source_context: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> QueryMetadata:
        """
        Extract metadata from a query.
        
        Args:
            query: The query string
            tenant_id: Tenant identifier
            session_id: Optional session identifier
            source_context: Optional source context
            user_context: Optional user context
            
        Returns:
            QueryMetadata: Extracted metadata
        """
        try:
            # Process with spaCy
            doc = self.nlp(query)
            
            # Extract basic statistics
            words = query.split()
            word_lengths = [len(word) for word in words if word.strip()]
            avg_word_length = (
                sum(word_lengths) / len(word_lengths)
                if word_lengths else 0.0
            )
            
            # Extract named entities
            named_entities = self._extract_named_entities(doc)
            
            # Extract temporal references
            temporal_refs = self._extract_temporal_references(doc)
            
            # Extract numerical values
            numerical_values = self._extract_numerical_values(doc)
            
            # Identify technical and domain terms
            technical_terms = self._identify_technical_terms(query)
            domain_terms = self._identify_domain_terms(query)
            
            # Analyze structure
            quotes = self._extract_quotes(query)
            special_chars = self._identify_special_chars(query)
            
            metadata = QueryMetadata(
                timestamp=datetime.now(),
                tenant_id=tenant_id,
                session_id=session_id,
                query_length=len(query),
                word_count=len(words),
                avg_word_length=avg_word_length,
                named_entities=named_entities,
                temporal_references=temporal_refs,
                numerical_values=numerical_values,
                domain_specific_terms=domain_terms,
                technical_terms=technical_terms,
                has_quotes=bool(quotes),
                quote_contents=quotes,
                has_special_chars=bool(special_chars),
                special_chars=special_chars,
                source_context=source_context,
                user_context=user_context
            )
            
            logger.info(
                f"Extracted metadata for query from tenant {tenant_id}: "
                f"{len(named_entities)} entities, {len(technical_terms)} technical terms"
            )
            
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to extract metadata: {str(e)}")
            raise
    
    def _extract_named_entities(self, doc: Doc) -> Dict[str, List[str]]:
        """Extract named entities using spaCy."""
        entities = {}
        for ent in doc.ents:
            if ent.label_ not in entities:
                entities[ent.label_] = []
            entities[ent.label_].append(ent.text)
        return entities
    
    def _extract_temporal_references(self, doc: Doc) -> List[str]:
        """Extract temporal references from the query."""
        temporal_refs = []
        
        # Extract date entities
        date_entities = [
            ent.text for ent in doc.ents
            if ent.label_ in {"DATE", "TIME"}
        ]
        
        # Extract temporal expressions
        temporal_patterns = [
            r"\b(?:today|yesterday|tomorrow)\b",
            r"\b(?:last|next|this)\s+(?:week|month|year|quarter)\b",
            r"\b\d+\s+(?:second|minute|hour|day|week|month|year)s?\s+(?:ago|from\s+now)\b"
        ]
        
        for pattern in temporal_patterns:
            matches = re.finditer(pattern, doc.text, re.IGNORECASE)
            temporal_refs.extend(match.group() for match in matches)
        
        return list(set(date_entities + temporal_refs))
    
    def _extract_numerical_values(self, doc: Doc) -> List[str]:
        """Extract numerical values and measurements."""
        numerical_patterns = [
            r"\b\d+(?:\.\d+)?\s*(?:[GMK]B|ms|Hz|px|em|rem|%|seconds?|minutes?|hours?|days?)\b",
            r"\b\d+(?:\.\d+)?\b"
        ]
        
        values = []
        for pattern in numerical_patterns:
            matches = re.finditer(pattern, doc.text)
            values.extend(match.group() for match in matches)
        
        return list(set(values))
    
    def _identify_technical_terms(self, query: str) -> List[str]:
        """Identify technical terms using patterns."""
        technical_terms = set()
        for pattern in self.technical_patterns:
            matches = pattern.finditer(query)
            technical_terms.update(match.group() for match in matches)
        return list(technical_terms)
    
    def _identify_domain_terms(self, query: str) -> List[str]:
        """Identify domain-specific terms."""
        domain_terms = set()
        for pattern in self.domain_patterns:
            matches = pattern.finditer(query)
            domain_terms.update(match.group() for match in matches)
        return list(domain_terms)
    
    def _extract_quotes(self, query: str) -> List[str]:
        """Extract quoted content from query."""
        quotes = []
        # Match both single and double quotes
        for pattern in [r'"([^"]+)"', r"'([^']+)'"]:
            matches = re.finditer(pattern, query)
            quotes.extend(match.group(1) for match in matches)
        return quotes
    
    def _identify_special_chars(self, query: str) -> Set[str]:
        """Identify special characters in query."""
        # Exclude common punctuation and whitespace
        special_chars = set()
        for char in query:
            if not (char.isalnum() or char.isspace() or char in {'.', ',', '!', '?', '"', "'"}):
                special_chars.add(char)
        return special_chars 