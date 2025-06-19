"""
Query intent classification module.

This module provides advanced intent classification for user queries to help
route them to the most appropriate processing pipeline.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class IntentCategory(Enum):
    """High-level intent categories."""
    INFORMATIONAL = "informational"  # Seeking information/facts
    PROCEDURAL = "procedural"        # How to do something
    NAVIGATIONAL = "navigational"    # Finding specific content/location
    TRANSACTIONAL = "transactional"  # Performing an action
    ANALYTICAL = "analytical"        # Analysis or comparison
    CLARIFICATION = "clarification"  # Seeking clarification
    UNKNOWN = "unknown"              # Cannot determine intent

class IntentSpecificity(Enum):
    """How specific the intent is."""
    BROAD = "broad"           # General topic
    MODERATE = "moderate"     # Somewhat specific
    SPECIFIC = "specific"     # Very specific
    UNKNOWN = "unknown"       # Cannot determine

@dataclass
class QueryIntent:
    """Structured representation of query intent."""
    category: IntentCategory
    specificity: IntentSpecificity
    confidence: float
    sub_intents: List[str]
    features: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "category": self.category.value,
            "specificity": self.specificity.value,
            "confidence": self.confidence,
            "sub_intents": self.sub_intents,
            "features": self.features
        }

class IntentClassifier:
    """
    Classifies query intent using rule-based and pattern matching approaches.
    
    Features:
    - Intent category classification
    - Intent specificity assessment
    - Confidence scoring
    - Sub-intent identification
    - Feature extraction
    """
    
    # Intent patterns for each category
    INTENT_PATTERNS = {
        IntentCategory.INFORMATIONAL: [
            (r"^(?:what|who|where|when|why)\s+(?:is|are|was|were)\s+.*[?]?$", 0.8),
            (r"^(?:explain|describe|tell\s+me\s+about)\s+.*$", 0.7),
            (r"^(?:definition|meaning)\s+of\s+.*$", 0.9),
            (r"^information\s+(?:about|on)\s+.*$", 0.7)
        ],
        IntentCategory.PROCEDURAL: [
            (r"^how\s+(?:to|do|can|should|would)\s+.*[?]?$", 0.9),
            (r"^(?:steps?|guide|tutorial|instructions?)\s+(?:to|for)\s+.*$", 0.8),
            (r"^(?:show|tell)\s+me\s+how\s+to\s+.*$", 0.8),
            (r"^what(?:'s|\s+is)\s+the\s+(?:best|right)\s+way\s+to\s+.*[?]?$", 0.7)
        ],
        IntentCategory.NAVIGATIONAL: [
            (r"^(?:where|how)\s+(?:can|do)\s+I\s+find\s+.*[?]?$", 0.8),
            (r"^(?:locate|find|search\s+for)\s+.*$", 0.7),
            (r"^(?:navigate|go)\s+to\s+.*$", 0.9),
            (r"^(?:link|path|route)\s+(?:to|for)\s+.*$", 0.8)
        ],
        IntentCategory.TRANSACTIONAL: [
            (r"^(?:how\s+(?:to|do\s+I)|can\s+I)\s+(?:create|update|delete|remove|add)\s+.*[?]?$", 0.9),
            (r"^(?:create|update|delete|remove|add)\s+.*$", 0.8),
            (r"^(?:execute|run|perform|do)\s+.*$", 0.7),
            (r"^(?:change|modify|alter)\s+.*$", 0.7)
        ],
        IntentCategory.ANALYTICAL: [
            (r"^(?:compare|analyze|evaluate|assess)\s+.*$", 0.9),
            (r"^(?:what(?:'s|\s+is)\s+the\s+difference\s+between)\s+.*[?]?$", 0.8),
            (r"^.*\s+(?:vs\.?|versus|compared\s+to)\s+.*$", 0.9),
            (r"^(?:pros\s+and\s+cons|advantages|disadvantages)\s+of\s+.*$", 0.8)
        ],
        IntentCategory.CLARIFICATION: [
            (r"^(?:what\s+do\s+you\s+mean\s+by|could\s+you\s+clarify|please\s+explain)\s+.*[?]?$", 0.9),
            (r"^(?:I\s+(?:don't\s+understand|am\s+confused\s+about))\s+.*[?]?$", 0.8),
            (r"^(?:clarify|explain)\s+.*[?]?$", 0.7),
            (r"^(?:can\s+you\s+(?:elaborate|provide\s+more\s+details)\s+(?:on|about))\s+.*[?]?$", 0.8)
        ]
    }
    
    # Specificity indicators
    SPECIFICITY_INDICATORS = {
        IntentSpecificity.SPECIFIC: [
            r"\b\d+(?:\.\d+)?\s*(?:px|em|rem|%|vh|vw|seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b",
            r"\b(?:specific|exact|precise|particular|certain)\b",
            r'"[^"]{10,}"',  # Quoted phrases of significant length
            r"\b(?:version|v)\s*\d+(?:\.\d+)*\b",  # Version numbers
            r"\b(?:step|phase|stage)\s+\d+\b",
            r"\b(?:section|chapter|page)\s+\d+\b"
        ],
        IntentSpecificity.MODERATE: [
            r"\b(?:recent|latest|current|modern|new)\b",
            r"\b(?:common|typical|standard|normal|regular)\b",
            r"\b(?:recommended|suggested|preferred)\b",
            r"\b(?:alternative|different|other)\b"
        ],
        IntentSpecificity.BROAD: [
            r"\b(?:general|basic|fundamental|overview|introduction)\b",
            r"\b(?:any|some|most|many|various)\b",
            r"\b(?:about|around|approximately)\b"
        ]
    }
    
    def __init__(self):
        """Initialize the intent classifier."""
        # Compile regex patterns
        self.compiled_patterns = {
            category: [(re.compile(pattern, re.IGNORECASE), confidence)
                      for pattern, confidence in patterns]
            for category, patterns in self.INTENT_PATTERNS.items()
        }
        
        self.compiled_specificity = {
            level: [re.compile(pattern, re.IGNORECASE)
                   for pattern in patterns]
            for level, patterns in self.SPECIFICITY_INDICATORS.items()
        }
    
    def classify_intent(self, query: str, parsed_query: Dict[str, Any]) -> QueryIntent:
        """
        Classify the intent of a query.
        
        Args:
            query: The original query string
            parsed_query: The parsed query information
            
        Returns:
            QueryIntent: Structured intent classification
        """
        # Find matching intent patterns
        category_matches = []
        for category, patterns in self.compiled_patterns.items():
            for pattern, base_confidence in patterns:
                if pattern.search(query):
                    category_matches.append((category, base_confidence))
        
        # Determine primary intent category and confidence
        if category_matches:
            # Use highest confidence match
            category, confidence = max(category_matches, key=lambda x: x[1])
        else:
            # Default to informational with low confidence
            category = IntentCategory.INFORMATIONAL
            confidence = 0.3
        
        # Assess specificity
        specificity = self._assess_specificity(query)
        
        # Extract features that contributed to classification
        features = self._extract_intent_features(query, parsed_query)
        
        # Identify sub-intents
        sub_intents = self._identify_sub_intents(query, category, parsed_query)
        
        # Adjust confidence based on features and sub-intents
        confidence = self._adjust_confidence(confidence, features, sub_intents)
        
        return QueryIntent(
            category=category,
            specificity=specificity,
            confidence=confidence,
            sub_intents=sub_intents,
            features=features
        )
    
    def _assess_specificity(self, query: str) -> IntentSpecificity:
        """Assess how specific the query is."""
        # Count matches for each specificity level
        matches = {
            level: sum(1 for pattern in patterns if pattern.search(query))
            for level, patterns in self.compiled_specificity.items()
        }
        
        # Find level with most matches
        if matches:
            max_matches = max(matches.values())
            if max_matches > 0:
                for level, count in matches.items():
                    if count == max_matches:
                        return level
        
        # Default to moderate if no clear indicators
        return IntentSpecificity.MODERATE
    
    def _extract_intent_features(self, query: str, parsed_query: Dict[str, Any]) -> Dict[str, Any]:
        """Extract features that helped determine intent."""
        features = {
            "query_length": len(query),
            "has_question_mark": query.endswith("?"),
            "word_count": len(query.split()),
            "contains_numbers": bool(re.search(r"\d+", query)),
            "contains_quotes": bool(re.search(r'"[^"]+"', query)),
            "query_type": parsed_query.get("query_type", "unknown"),
            "keyword_count": len(parsed_query.get("keywords", [])),
            "has_subject": parsed_query.get("subject") is not None,
            "has_action": parsed_query.get("action") is not None
        }
        
        return features
    
    def _identify_sub_intents(
        self, 
        query: str, 
        primary_intent: IntentCategory,
        parsed_query: Dict[str, Any]
    ) -> List[str]:
        """Identify additional sub-intents in the query."""
        sub_intents = []
        
        # Check for comparison aspects
        if re.search(r"\b(?:compare|vs\.?|versus|difference|similarities?|differences?)\b", query, re.IGNORECASE):
            sub_intents.append("comparison")
        
        # Check for temporal aspects
        if re.search(r"\b(?:when|time|schedule|duration|period|frequency)\b", query, re.IGNORECASE):
            sub_intents.append("temporal")
        
        # Check for quantity/measurement aspects
        if re.search(r"\b(?:how\s+(?:much|many|long|often)|quantity|amount|number)\b", query, re.IGNORECASE):
            sub_intents.append("quantitative")
        
        # Check for requirement aspects
        if re.search(r"\b(?:require(?:d|ments?)?|need(?:ed)?|must|should|mandatory)\b", query, re.IGNORECASE):
            sub_intents.append("requirements")
        
        # Check for example/illustration aspects
        if re.search(r"\b(?:example|illustration|show|demonstrate|sample)\b", query, re.IGNORECASE):
            sub_intents.append("examples")
        
        return sub_intents
    
    def _adjust_confidence(
        self, 
        base_confidence: float,
        features: Dict[str, Any],
        sub_intents: List[str]
    ) -> float:
        """Adjust confidence score based on features and sub-intents."""
        confidence = base_confidence
        
        # Adjust based on features
        if features["has_question_mark"]:
            confidence += 0.1
        if features["has_subject"] and features["has_action"]:
            confidence += 0.1
        if features["word_count"] < 3:
            confidence -= 0.2
        if features["contains_quotes"]:
            confidence += 0.1
        
        # Adjust based on sub-intents
        if len(sub_intents) > 0:
            confidence += 0.05 * len(sub_intents)
        
        # Ensure confidence stays in [0, 1] range
        return max(0.0, min(1.0, confidence)) 