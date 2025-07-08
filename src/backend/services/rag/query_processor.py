"""Query processing and validation for RAG system."""

import re
from typing import Dict, Any, Optional, List
from uuid import UUID

from .base import Query, QueryProcessorInterface

class QueryProcessor(QueryProcessorInterface):
    """Processes and validates user queries for RAG system."""
    
    def __init__(self, max_query_length: int = 1000, min_query_length: int = 3):
        self.max_query_length = max_query_length
        self.min_query_length = min_query_length
        
        # Filter patterns
        self.file_type_patterns = {
            'pdf': r'\b(?:pdf|document)s?\b',
            'html': r'\b(?:html|web|page)s?\b', 
            'txt': r'\b(?:text|txt|file)s?\b'
        }
        
        self.date_patterns = {
            'recent': r'\b(?:recent|latest|new|current)\b',
            'old': r'\b(?:old|previous|earlier|past)\b'
        }
    
    def process_query(self, raw_query: str, tenant_id: UUID, user_id: Optional[UUID] = None) -> Query:
        """Process and validate user query."""
        # Clean the query
        cleaned_query = self._clean_query(raw_query)
        
        # Validate query
        self._validate_query(cleaned_query)
        
        # Extract filters
        query_text, filters = self.extract_filters(cleaned_query)
        
        # Create query object
        query = Query(
            text=query_text.strip(),
            tenant_id=tenant_id,
            user_id=user_id,
            filters=filters,
            original_text=raw_query
        )
        
        return query
    
    def extract_filters(self, query: str) -> tuple[str, Dict[str, Any]]:
        """Extract filters from query text."""
        filters = {}
        remaining_query = query.lower()
        
        # Extract file type filters
        file_types = []
        for file_type, pattern in self.file_type_patterns.items():
            if re.search(pattern, remaining_query, re.IGNORECASE):
                file_types.append(file_type)
                remaining_query = re.sub(pattern, '', remaining_query, flags=re.IGNORECASE)
        
        if file_types:
            filters['file_types'] = file_types
        
        # Extract temporal filters
        for time_filter, pattern in self.date_patterns.items():
            if re.search(pattern, remaining_query, re.IGNORECASE):
                filters['temporal'] = time_filter
                remaining_query = re.sub(pattern, '', remaining_query, flags=re.IGNORECASE)
                break
        
        # Extract specific filename mentions
        filename_pattern = r'\b(?:in|from|file)\s+["\']?([^"\'\\s]+\\.\\w+)["\']?'
        filename_match = re.search(filename_pattern, remaining_query, re.IGNORECASE)
        if filename_match:
            filters['filename'] = filename_match.group(1)
            remaining_query = re.sub(filename_pattern, '', remaining_query, flags=re.IGNORECASE)
        
        # Clean up remaining query
        cleaned_query = re.sub(r'\s+', ' ', remaining_query).strip()
        
        return cleaned_query, filters
    
    def _clean_query(self, query: str) -> str:
        """Clean and normalize query text."""
        if not query:
            return ""
        
        # Remove extra whitespace
        query = re.sub(r'\s+', ' ', query.strip())
        
        # Remove special characters that might interfere with search
        # Keep alphanumeric, spaces, basic punctuation
        query = re.sub(r'[^\w\s\.,!?\-\'"]', ' ', query)
        
        # Remove extra spaces again
        query = re.sub(r'\s+', ' ', query).strip()
        
        return query
    
    def _validate_query(self, query: str) -> None:
        """Validate query meets requirements."""
        if not query:
            raise ValueError("Query cannot be empty")
        
        if len(query) < self.min_query_length:
            raise ValueError(f"Query too short. Minimum length: {self.min_query_length}")
        
        if len(query) > self.max_query_length:
            raise ValueError(f"Query too long. Maximum length: {self.max_query_length}")
        
        # Check for potentially problematic queries
        if query.lower().strip() in ['test', 'hello', 'hi', '?']:
            raise ValueError("Query too generic or not specific enough")
    
    def expand_query(self, query: str) -> List[str]:
        """Generate query variations for better retrieval."""
        variations = [query]
        
        # Add variations with synonyms for common terms
        synonyms = {
            'policy': ['rule', 'guideline', 'procedure'],
            'benefit': ['perk', 'advantage', 'compensation'],
            'work': ['job', 'employment', 'position'],
            'remote': ['home', 'telework', 'virtual'],
            'vacation': ['time off', 'leave', 'holiday'],
            'salary': ['pay', 'compensation', 'wage']
        }
        
        for word, syns in synonyms.items():
            if word in query.lower():
                for syn in syns:
                    variation = re.sub(word, syn, query, flags=re.IGNORECASE)
                    if variation != query:
                        variations.append(variation)
        
        return variations[:5]  # Limit to 5 variations
    
    def get_query_intent(self, query: str) -> str:
        """Classify query intent."""
        query_lower = query.lower()
        
        # Question patterns
        if any(q in query_lower for q in ['what', 'how', 'when', 'where', 'why', 'who']):
            return 'question'
        
        # Policy/procedure requests
        if any(p in query_lower for p in ['policy', 'procedure', 'rule', 'guideline']):
            return 'policy_lookup'
        
        # Benefit inquiries
        if any(b in query_lower for b in ['benefit', 'vacation', 'leave', 'insurance', 'salary']):
            return 'benefits_inquiry'
        
        # General information
        return 'general_info'