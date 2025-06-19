"""
Node parsers for LlamaIndex with tenant-aware settings and advanced parsing strategies.

This module provides sophisticated node parsing capabilities with
tenant isolation, metadata extraction, and relationship tracking.
"""

import logging
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum

from llama_index.core import Document
from llama_index.core.node_parser import (
    SimpleNodeParser,
    SentenceWindowNodeParser,
    SemanticSplitterNodeParser,
    HierarchicalNodeParser,
    HTMLNodeParser,
    JSONNodeParser
)
from llama_index.core.schema import BaseNode

from .llama_config import TenantLlamaConfig
from .text_splitters import TenantAwareTextSplitterManager, SplittingStrategy
from ..config.settings import get_settings

logger = logging.getLogger(__name__)


class NodeParsingStrategy(Enum):
    """Available node parsing strategies."""
    SIMPLE = "simple"
    SENTENCE_WINDOW = "sentence_window"
    SEMANTIC = "semantic"
    HIERARCHICAL = "hierarchical"
    HTML = "html"
    JSON = "json"


@dataclass
class NodeParserConfig:
    """Configuration for node parsers."""
    strategy: NodeParsingStrategy
    chunk_size: int = 1000
    chunk_overlap: int = 200
    include_metadata: bool = True
    include_prev_next_rel: bool = True
    
    # Sentence window specific
    window_size: int = 3
    window_metadata_key: str = "window"
    original_text_metadata_key: str = "original_text"
    
    # Semantic specific
    buffer_size: int = 1
    breakpoint_percentile_threshold: int = 95
    
    # Hierarchical specific
    hierarchy_levels: List[int] = None
    
    # HTML specific
    tags: List[str] = None
    
    def __post_init__(self):
        """Set default values for complex fields."""
        if self.hierarchy_levels is None:
            self.hierarchy_levels = [2048, 512, 128]
        if self.tags is None:
            self.tags = ["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "b", "i", "u", "section"]


class TenantAwareNodeParserManager:
    """
    Manager for tenant-aware node parsing with multiple strategies.
    
    Features:
    - Multiple parsing strategies
    - Tenant-specific configurations
    - Advanced metadata extraction
    - Relationship tracking
    - Performance optimization
    """
    
    def __init__(self, tenant_config: TenantLlamaConfig, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the node parser manager.
        
        Args:
            tenant_config: Tenant-specific configuration
            config: Global configuration dictionary
        """
        self.tenant_config = tenant_config
        self.config = config or get_settings()
        self.tenant_id = tenant_config.tenant_id
        
        # Get metadata extraction configuration
        self.metadata_config = self.config.get("file_processing", {}).get("metadata_extraction", {})
        
        # Create parser configurations
        self.parser_configs = self._create_parser_configs()
        
        # Initialize text splitter manager
        self.text_splitter_manager = TenantAwareTextSplitterManager(tenant_config, config)
        
        # Initialize parsers
        self.parsers = self._initialize_parsers()
        
        logger.info(f"Initialized NodeParserManager for tenant {self.tenant_id} with {len(self.parsers)} strategies")
    
    def _create_parser_configs(self) -> Dict[NodeParsingStrategy, NodeParserConfig]:
        """Create parser configurations for different strategies."""
        base_chunk_size = self.tenant_config.chunk_size
        base_overlap = self.tenant_config.chunk_overlap
        include_metadata = self.tenant_config.enable_metadata_extraction
        
        configs = {
            NodeParsingStrategy.SIMPLE: NodeParserConfig(
                strategy=NodeParsingStrategy.SIMPLE,
                chunk_size=base_chunk_size,
                chunk_overlap=base_overlap,
                include_metadata=include_metadata,
                include_prev_next_rel=True
            ),
            
            NodeParsingStrategy.SENTENCE_WINDOW: NodeParserConfig(
                strategy=NodeParsingStrategy.SENTENCE_WINDOW,
                chunk_size=base_chunk_size,
                chunk_overlap=base_overlap,
                include_metadata=include_metadata,
                window_size=3,
                window_metadata_key="window_content",
                original_text_metadata_key="original_sentence"
            ),
            
            NodeParsingStrategy.SEMANTIC: NodeParserConfig(
                strategy=NodeParsingStrategy.SEMANTIC,
                chunk_size=base_chunk_size,
                chunk_overlap=base_overlap,
                include_metadata=include_metadata,
                buffer_size=1,
                breakpoint_percentile_threshold=95
            ),
            
            NodeParsingStrategy.HIERARCHICAL: NodeParserConfig(
                strategy=NodeParsingStrategy.HIERARCHICAL,
                chunk_size=base_chunk_size,
                chunk_overlap=base_overlap,
                include_metadata=include_metadata,
                hierarchy_levels=[2048, 512, 128]
            ),
            
            NodeParsingStrategy.HTML: NodeParserConfig(
                strategy=NodeParsingStrategy.HTML,
                chunk_size=base_chunk_size,
                chunk_overlap=base_overlap,
                include_metadata=include_metadata,
                tags=["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "b", "i", "u", "section"]
            ),
            
            NodeParsingStrategy.JSON: NodeParserConfig(
                strategy=NodeParsingStrategy.JSON,
                chunk_size=base_chunk_size,
                chunk_overlap=base_overlap,
                include_metadata=include_metadata
            )
        }
        
        return configs
    
    def _initialize_parsers(self) -> Dict[NodeParsingStrategy, Any]:
        """Initialize node parsers for each strategy."""
        parsers = {}
        
        try:
            # Simple Node Parser
            simple_config = self.parser_configs[NodeParsingStrategy.SIMPLE]
            text_splitter = self.text_splitter_manager.get_text_splitter(SplittingStrategy.RECURSIVE)
            parsers[NodeParsingStrategy.SIMPLE] = SimpleNodeParser(
                text_splitter=text_splitter,
                include_metadata=simple_config.include_metadata,
                include_prev_next_rel=simple_config.include_prev_next_rel
            )
            
            # Sentence Window Node Parser
            window_config = self.parser_configs[NodeParsingStrategy.SENTENCE_WINDOW]
            sentence_splitter = self.text_splitter_manager.get_text_splitter(SplittingStrategy.SENTENCE)
            parsers[NodeParsingStrategy.SENTENCE_WINDOW] = SentenceWindowNodeParser(
                text_splitter=sentence_splitter,
                window_size=window_config.window_size,
                window_metadata_key=window_config.window_metadata_key,
                original_text_metadata_key=window_config.original_text_metadata_key,
                include_metadata=window_config.include_metadata,
                include_prev_next_rel=window_config.include_prev_next_rel
            )
            
            # HTML Node Parser
            html_config = self.parser_configs[NodeParsingStrategy.HTML]
            parsers[NodeParsingStrategy.HTML] = HTMLNodeParser(
                tags=html_config.tags,
                include_metadata=html_config.include_metadata,
                include_prev_next_rel=html_config.include_prev_next_rel
            )
            
            # JSON Node Parser
            json_config = self.parser_configs[NodeParsingStrategy.JSON]
            parsers[NodeParsingStrategy.JSON] = JSONNodeParser(
                include_metadata=json_config.include_metadata,
                include_prev_next_rel=json_config.include_prev_next_rel
            )
            
            logger.info(f"Initialized {len(parsers)} node parsers for tenant {self.tenant_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize node parsers for tenant {self.tenant_id}: {e}")
            # Fallback to simple parser
            text_splitter = self.text_splitter_manager.get_text_splitter(SplittingStrategy.RECURSIVE)
            parsers[NodeParsingStrategy.SIMPLE] = SimpleNodeParser(
                text_splitter=text_splitter,
                include_metadata=True,
                include_prev_next_rel=True
            )
        
        return parsers
    
    def get_node_parser(self, strategy: Union[NodeParsingStrategy, str]) -> Any:
        """
        Get a node parser for the specified strategy.
        
        Args:
            strategy: Parsing strategy to use
            
        Returns:
            Node parser instance
        """
        if isinstance(strategy, str):
            try:
                strategy = NodeParsingStrategy(strategy.lower())
            except ValueError:
                logger.warning(f"Unknown strategy '{strategy}', falling back to simple")
                strategy = NodeParsingStrategy.SIMPLE
        
        parser = self.parsers.get(strategy)
        if not parser:
            logger.warning(f"Parser for strategy {strategy} not available, using simple")
            parser = self.parsers[NodeParsingStrategy.SIMPLE]
        
        return parser
    
    def parse_documents(
        self, 
        documents: List[Document], 
        strategy: Union[NodeParsingStrategy, str] = NodeParsingStrategy.SIMPLE
    ) -> List[BaseNode]:
        """
        Parse documents into nodes using the specified strategy.
        
        Args:
            documents: Documents to parse
            strategy: Parsing strategy to use
            
        Returns:
            List of parsed nodes
        """
        parser = self.get_node_parser(strategy)
        
        try:
            # Add tenant metadata to documents
            for doc in documents:
                self._enhance_document_metadata(doc)
            
            # Parse documents
            nodes = parser.get_nodes_from_documents(documents)
            
            # Post-process nodes
            nodes = self._post_process_nodes(nodes, strategy)
            
            logger.debug(f"Parsed {len(documents)} documents into {len(nodes)} nodes using {strategy} strategy")
            return nodes
            
        except Exception as e:
            logger.error(f"Error parsing documents with {strategy} strategy: {e}")
            # Fallback to simple parsing
            return self._fallback_parse(documents)
    
    def _enhance_document_metadata(self, document: Document):
        """Enhance document with tenant-specific metadata."""
        if not hasattr(document, 'metadata') or document.metadata is None:
            document.metadata = {}
        
        # Add tenant information
        document.metadata.update({
            "tenant_id": self.tenant_id,
            "processing_timestamp": self.config.get("app", {}).get("name", "Enterprise_RAG_Pipeline"),
            "parser_config": {
                "chunk_size": self.tenant_config.chunk_size,
                "chunk_overlap": self.tenant_config.chunk_overlap,
                "enable_metadata_extraction": self.tenant_config.enable_metadata_extraction
            }
        })
        
        # Extract additional metadata if enabled
        if self.metadata_config.get("extract_keywords", False):
            document.metadata["keywords"] = self._extract_keywords(document.text)
        
        if self.metadata_config.get("extract_summary", False):
            document.metadata["summary"] = self._extract_summary(document.text)
    
    def _post_process_nodes(self, nodes: List[BaseNode], strategy: Union[NodeParsingStrategy, str]) -> List[BaseNode]:
        """Post-process nodes after parsing."""
        processed_nodes = []
        
        for i, node in enumerate(nodes):
            # Ensure node has metadata
            if not hasattr(node, 'metadata') or node.metadata is None:
                node.metadata = {}
            
            # Add processing metadata
            node.metadata.update({
                "tenant_id": self.tenant_id,
                "node_index": i,
                "parsing_strategy": strategy.value if isinstance(strategy, NodeParsingStrategy) else strategy,
                "node_id": f"{self.tenant_id}_{i}_{hash(node.text[:100])}"
            })
            
            # Add node relationships if enabled
            if self.parser_configs[NodeParsingStrategy.SIMPLE].include_prev_next_rel:
                if i > 0:
                    node.metadata["prev_node_id"] = f"{self.tenant_id}_{i-1}_{hash(nodes[i-1].text[:100])}"
                if i < len(nodes) - 1:
                    node.metadata["next_node_id"] = f"{self.tenant_id}_{i+1}_{hash(nodes[i+1].text[:100])}"
            
            processed_nodes.append(node)
        
        return processed_nodes
    
    def _fallback_parse(self, documents: List[Document]) -> List[BaseNode]:
        """Fallback parsing method."""
        simple_parser = self.parsers[NodeParsingStrategy.SIMPLE]
        
        try:
            return simple_parser.get_nodes_from_documents(documents)
        except Exception as e:
            logger.error(f"Fallback parsing also failed: {e}")
            return []
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text (simple implementation)."""
        # Simple keyword extraction - in production, use more sophisticated methods
        words = text.lower().split()
        # Filter out common words and keep words longer than 3 characters
        stop_words = {"the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
        keywords = [word for word in words if len(word) > 3 and word not in stop_words]
        
        # Return top 10 most frequent keywords
        from collections import Counter
        return [word for word, count in Counter(keywords).most_common(10)]
    
    def _extract_summary(self, text: str) -> str:
        """Extract summary from text (simple implementation)."""
        # Simple summary - first 200 characters
        return text[:200] + "..." if len(text) > 200 else text
    
    def get_recommended_strategy(self, document_type: str, content_type: str = None) -> NodeParsingStrategy:
        """
        Get recommended parsing strategy based on document characteristics.
        
        Args:
            document_type: Type of document (pdf, txt, etc.)
            content_type: Type of content (html, json, etc.)
            
        Returns:
            Recommended parsing strategy
        """
        # Strategy recommendations based on document and content type
        if content_type:
            if content_type.lower() == "html":
                return NodeParsingStrategy.HTML
            elif content_type.lower() == "json":
                return NodeParsingStrategy.JSON
        
        if document_type.lower() in ["pdf", "docx", "doc"]:
            return NodeParsingStrategy.HIERARCHICAL
        
        elif document_type.lower() in ["txt", "md"]:
            return NodeParsingStrategy.SENTENCE_WINDOW
        
        elif document_type.lower() in ["html", "htm"]:
            return NodeParsingStrategy.HTML
        
        elif document_type.lower() in ["json"]:
            return NodeParsingStrategy.JSON
        
        else:
            # Default fallback
            return NodeParsingStrategy.SIMPLE
    
    def get_parser_config(self, strategy: Union[NodeParsingStrategy, str]) -> NodeParserConfig:
        """
        Get configuration for a specific parser strategy.
        
        Args:
            strategy: Parsing strategy
            
        Returns:
            Parser configuration
        """
        if isinstance(strategy, str):
            strategy = NodeParsingStrategy(strategy.lower())
        
        return self.parser_configs.get(strategy, self.parser_configs[NodeParsingStrategy.SIMPLE])
    
    def update_parser_config(self, strategy: Union[NodeParsingStrategy, str], **kwargs):
        """
        Update configuration for a specific parser strategy.
        
        Args:
            strategy: Parsing strategy to update
            **kwargs: Configuration parameters to update
        """
        if isinstance(strategy, str):
            strategy = NodeParsingStrategy(strategy.lower())
        
        if strategy in self.parser_configs:
            config = self.parser_configs[strategy]
            
            # Update configuration
            for key, value in kwargs.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            
            # Reinitialize the parser
            self._reinitialize_parser(strategy)
            
            logger.info(f"Updated configuration for {strategy} parser")
    
    def _reinitialize_parser(self, strategy: NodeParsingStrategy):
        """Reinitialize a specific parser with updated configuration."""
        config = self.parser_configs[strategy]
        
        try:
            if strategy == NodeParsingStrategy.SIMPLE:
                text_splitter = self.text_splitter_manager.get_text_splitter(SplittingStrategy.RECURSIVE)
                self.parsers[strategy] = SimpleNodeParser(
                    text_splitter=text_splitter,
                    include_metadata=config.include_metadata,
                    include_prev_next_rel=config.include_prev_next_rel
                )
            
            elif strategy == NodeParsingStrategy.SENTENCE_WINDOW:
                sentence_splitter = self.text_splitter_manager.get_text_splitter(SplittingStrategy.SENTENCE)
                self.parsers[strategy] = SentenceWindowNodeParser(
                    text_splitter=sentence_splitter,
                    window_size=config.window_size,
                    window_metadata_key=config.window_metadata_key,
                    original_text_metadata_key=config.original_text_metadata_key,
                    include_metadata=config.include_metadata,
                    include_prev_next_rel=config.include_prev_next_rel
                )
            
            elif strategy == NodeParsingStrategy.HTML:
                self.parsers[strategy] = HTMLNodeParser(
                    tags=config.tags,
                    include_metadata=config.include_metadata,
                    include_prev_next_rel=config.include_prev_next_rel
                )
            
            elif strategy == NodeParsingStrategy.JSON:
                self.parsers[strategy] = JSONNodeParser(
                    include_metadata=config.include_metadata,
                    include_prev_next_rel=config.include_prev_next_rel
                )
            
            logger.debug(f"Reinitialized {strategy} parser")
            
        except Exception as e:
            logger.error(f"Failed to reinitialize {strategy} parser: {e}")
    
    def get_available_strategies(self) -> List[str]:
        """Get list of available parsing strategies."""
        return [strategy.value for strategy in self.parsers.keys()]
    
    def get_parser_status(self) -> Dict[str, Any]:
        """Get status information for all parsers."""
        return {
            "tenant_id": self.tenant_id,
            "available_strategies": self.get_available_strategies(),
            "configurations": {
                strategy.value: {
                    "chunk_size": config.chunk_size,
                    "chunk_overlap": config.chunk_overlap,
                    "include_metadata": config.include_metadata,
                    "strategy": config.strategy.value
                }
                for strategy, config in self.parser_configs.items()
            },
            "metadata_extraction_enabled": self.tenant_config.enable_metadata_extraction
        }


def create_node_parser_manager(tenant_config: TenantLlamaConfig) -> TenantAwareNodeParserManager:
    """
    Factory function to create a node parser manager for a tenant.
    
    Args:
        tenant_config: Tenant-specific configuration
        
    Returns:
        TenantAwareNodeParserManager: Configured parser manager
    """
    return TenantAwareNodeParserManager(tenant_config)


def parse_documents_for_tenant(
    tenant_config: TenantLlamaConfig,
    documents: List[Document],
    strategy: Union[NodeParsingStrategy, str] = NodeParsingStrategy.SIMPLE
) -> List[BaseNode]:
    """
    Convenience function to parse documents for a tenant.
    
    Args:
        tenant_config: Tenant-specific configuration
        documents: Documents to parse
        strategy: Parsing strategy to use
        
    Returns:
        List of parsed nodes
    """
    manager = create_node_parser_manager(tenant_config)
    return manager.parse_documents(documents, strategy) 