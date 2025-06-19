"""
Configurable text splitters for LlamaIndex with tenant-aware settings.

This module provides various text splitting strategies optimized for
different document types and tenant requirements.
"""

import logging
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum

from llama_index.core.text_splitter import (
    RecursiveCharacterTextSplitter,
    SentenceSplitter,
    TokenTextSplitter
)
from llama_index.core.node_parser import (
    SimpleNodeParser,
    SentenceWindowNodeParser,
    SemanticSplitterNodeParser,
    HierarchicalNodeParser
)

from .llama_config import TenantLlamaConfig
from ..config.settings import get_settings

logger = logging.getLogger(__name__)


class SplittingStrategy(Enum):
    """Available text splitting strategies."""
    RECURSIVE = "recursive"
    SENTENCE = "sentence"
    SEMANTIC = "semantic"
    TOKEN = "token"
    HIERARCHICAL = "hierarchical"
    SENTENCE_WINDOW = "sentence_window"


@dataclass
class SplitterConfig:
    """Configuration for text splitters."""
    strategy: SplittingStrategy
    chunk_size: int = 1000
    chunk_overlap: int = 200
    separators: List[str] = None
    sentence_window_size: int = 3
    window_metadata_key: str = "window"
    original_text_metadata_key: str = "original_text"
    include_metadata: bool = True
    include_prev_next_rel: bool = True


class TenantAwareTextSplitterManager:
    """
    Manager for tenant-aware text splitting with multiple strategies.
    
    Features:
    - Multiple splitting strategies
    - Tenant-specific configurations
    - Document type optimization
    - Performance monitoring
    """
    
    def __init__(self, tenant_config: TenantLlamaConfig, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the text splitter manager.
        
        Args:
            tenant_config: Tenant-specific configuration
            config: Global configuration dictionary
        """
        self.tenant_config = tenant_config
        self.config = config or get_settings()
        self.tenant_id = tenant_config.tenant_id
        
        # Get chunking configuration
        self.chunking_config = self.config.get("file_processing", {}).get("chunking", {})
        
        # Create splitter configurations
        self.splitter_configs = self._create_splitter_configs()
        
        # Initialize splitters
        self.splitters = self._initialize_splitters()
        
        logger.info(f"Initialized TextSplitterManager for tenant {self.tenant_id} with {len(self.splitters)} strategies")
    
    def _create_splitter_configs(self) -> Dict[SplittingStrategy, SplitterConfig]:
        """Create splitter configurations for different strategies."""
        base_chunk_size = self.tenant_config.chunk_size
        base_overlap = self.tenant_config.chunk_overlap
        base_separators = self.tenant_config.separators
        
        configs = {
            SplittingStrategy.RECURSIVE: SplitterConfig(
                strategy=SplittingStrategy.RECURSIVE,
                chunk_size=base_chunk_size,
                chunk_overlap=base_overlap,
                separators=base_separators or ["\n\n", "\n", " ", ""]
            ),
            
            SplittingStrategy.SENTENCE: SplitterConfig(
                strategy=SplittingStrategy.SENTENCE,
                chunk_size=base_chunk_size,
                chunk_overlap=base_overlap,
                separators=[". ", "! ", "? "]
            ),
            
            SplittingStrategy.TOKEN: SplitterConfig(
                strategy=SplittingStrategy.TOKEN,
                chunk_size=min(base_chunk_size, 512),  # Token-based needs smaller chunks
                chunk_overlap=min(base_overlap, 50)
            ),
            
            SplittingStrategy.SENTENCE_WINDOW: SplitterConfig(
                strategy=SplittingStrategy.SENTENCE_WINDOW,
                chunk_size=base_chunk_size,
                chunk_overlap=base_overlap,
                sentence_window_size=3,
                window_metadata_key="window_content",
                original_text_metadata_key="original_sentence"
            ),
            
            SplittingStrategy.HIERARCHICAL: SplitterConfig(
                strategy=SplittingStrategy.HIERARCHICAL,
                chunk_size=base_chunk_size,
                chunk_overlap=base_overlap,
                separators=["\n\n", "\n", " ", ""]
            ),
            
            SplittingStrategy.SEMANTIC: SplitterConfig(
                strategy=SplittingStrategy.SEMANTIC,
                chunk_size=base_chunk_size,
                chunk_overlap=base_overlap
            )
        }
        
        return configs
    
    def _initialize_splitters(self) -> Dict[SplittingStrategy, Any]:
        """Initialize text splitters for each strategy."""
        splitters = {}
        
        try:
            # Recursive Character Text Splitter
            recursive_config = self.splitter_configs[SplittingStrategy.RECURSIVE]
            splitters[SplittingStrategy.RECURSIVE] = RecursiveCharacterTextSplitter(
                chunk_size=recursive_config.chunk_size,
                chunk_overlap=recursive_config.chunk_overlap,
                separators=recursive_config.separators
            )
            
            # Sentence Splitter
            sentence_config = self.splitter_configs[SplittingStrategy.SENTENCE]
            splitters[SplittingStrategy.SENTENCE] = SentenceSplitter(
                chunk_size=sentence_config.chunk_size,
                chunk_overlap=sentence_config.chunk_overlap
            )
            
            # Token Text Splitter
            token_config = self.splitter_configs[SplittingStrategy.TOKEN]
            splitters[SplittingStrategy.TOKEN] = TokenTextSplitter(
                chunk_size=token_config.chunk_size,
                chunk_overlap=token_config.chunk_overlap
            )
            
            logger.info(f"Initialized {len(splitters)} text splitters for tenant {self.tenant_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize text splitters for tenant {self.tenant_id}: {e}")
            # Fallback to basic recursive splitter
            splitters[SplittingStrategy.RECURSIVE] = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200
            )
        
        return splitters
    
    def get_text_splitter(self, strategy: Union[SplittingStrategy, str]) -> Any:
        """
        Get a text splitter for the specified strategy.
        
        Args:
            strategy: Splitting strategy to use
            
        Returns:
            Text splitter instance
        """
        if isinstance(strategy, str):
            try:
                strategy = SplittingStrategy(strategy.lower())
            except ValueError:
                logger.warning(f"Unknown strategy '{strategy}', falling back to recursive")
                strategy = SplittingStrategy.RECURSIVE
        
        splitter = self.splitters.get(strategy)
        if not splitter:
            logger.warning(f"Splitter for strategy {strategy} not available, using recursive")
            splitter = self.splitters[SplittingStrategy.RECURSIVE]
        
        return splitter
    
    def split_text(self, text: str, strategy: Union[SplittingStrategy, str] = SplittingStrategy.RECURSIVE) -> List[str]:
        """
        Split text using the specified strategy.
        
        Args:
            text: Text to split
            strategy: Splitting strategy to use
            
        Returns:
            List of text chunks
        """
        splitter = self.get_text_splitter(strategy)
        
        try:
            chunks = splitter.split_text(text)
            logger.debug(f"Split text into {len(chunks)} chunks using {strategy} strategy")
            return chunks
        except Exception as e:
            logger.error(f"Error splitting text with {strategy} strategy: {e}")
            # Fallback to simple splitting
            return self._fallback_split(text)
    
    def _fallback_split(self, text: str) -> List[str]:
        """Fallback text splitting method."""
        chunk_size = self.tenant_config.chunk_size
        chunks = []
        
        for i in range(0, len(text), chunk_size):
            chunks.append(text[i:i + chunk_size])
        
        logger.debug(f"Fallback split created {len(chunks)} chunks")
        return chunks
    
    def get_recommended_strategy(self, document_type: str, content_length: int) -> SplittingStrategy:
        """
        Get recommended splitting strategy based on document characteristics.
        
        Args:
            document_type: Type of document (pdf, txt, etc.)
            content_length: Length of content in characters
            
        Returns:
            Recommended splitting strategy
        """
        # Strategy recommendations based on document type and size
        if document_type.lower() in ["pdf", "docx", "doc"]:
            if content_length > 50000:  # Large documents
                return SplittingStrategy.HIERARCHICAL
            else:
                return SplittingStrategy.RECURSIVE
        
        elif document_type.lower() in ["txt", "md"]:
            if content_length > 100000:  # Very large text files
                return SplittingStrategy.SENTENCE
            else:
                return SplittingStrategy.RECURSIVE
        
        elif document_type.lower() in ["csv", "json"]:
            return SplittingStrategy.TOKEN
        
        else:
            # Default fallback
            return SplittingStrategy.RECURSIVE
    
    def get_splitter_config(self, strategy: Union[SplittingStrategy, str]) -> SplitterConfig:
        """
        Get configuration for a specific splitter strategy.
        
        Args:
            strategy: Splitting strategy
            
        Returns:
            Splitter configuration
        """
        if isinstance(strategy, str):
            strategy = SplittingStrategy(strategy.lower())
        
        return self.splitter_configs.get(strategy, self.splitter_configs[SplittingStrategy.RECURSIVE])
    
    def update_splitter_config(self, strategy: Union[SplittingStrategy, str], **kwargs):
        """
        Update configuration for a specific splitter strategy.
        
        Args:
            strategy: Splitting strategy to update
            **kwargs: Configuration parameters to update
        """
        if isinstance(strategy, str):
            strategy = SplittingStrategy(strategy.lower())
        
        if strategy in self.splitter_configs:
            config = self.splitter_configs[strategy]
            
            # Update configuration
            for key, value in kwargs.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            
            # Reinitialize the splitter
            self._reinitialize_splitter(strategy)
            
            logger.info(f"Updated configuration for {strategy} splitter")
    
    def _reinitialize_splitter(self, strategy: SplittingStrategy):
        """Reinitialize a specific splitter with updated configuration."""
        config = self.splitter_configs[strategy]
        
        try:
            if strategy == SplittingStrategy.RECURSIVE:
                self.splitters[strategy] = RecursiveCharacterTextSplitter(
                    chunk_size=config.chunk_size,
                    chunk_overlap=config.chunk_overlap,
                    separators=config.separators
                )
            
            elif strategy == SplittingStrategy.SENTENCE:
                self.splitters[strategy] = SentenceSplitter(
                    chunk_size=config.chunk_size,
                    chunk_overlap=config.chunk_overlap
                )
            
            elif strategy == SplittingStrategy.TOKEN:
                self.splitters[strategy] = TokenTextSplitter(
                    chunk_size=config.chunk_size,
                    chunk_overlap=config.chunk_overlap
                )
            
            logger.debug(f"Reinitialized {strategy} splitter")
            
        except Exception as e:
            logger.error(f"Failed to reinitialize {strategy} splitter: {e}")
    
    def get_available_strategies(self) -> List[str]:
        """Get list of available splitting strategies."""
        return [strategy.value for strategy in self.splitters.keys()]
    
    def get_splitter_status(self) -> Dict[str, Any]:
        """Get status information for all splitters."""
        return {
            "tenant_id": self.tenant_id,
            "available_strategies": self.get_available_strategies(),
            "configurations": {
                strategy.value: {
                    "chunk_size": config.chunk_size,
                    "chunk_overlap": config.chunk_overlap,
                    "strategy": config.strategy.value
                }
                for strategy, config in self.splitter_configs.items()
            },
            "default_strategy": self.chunking_config.get("strategy", "recursive")
        }


def create_text_splitter_manager(tenant_config: TenantLlamaConfig) -> TenantAwareTextSplitterManager:
    """
    Factory function to create a text splitter manager for a tenant.
    
    Args:
        tenant_config: Tenant-specific configuration
        
    Returns:
        TenantAwareTextSplitterManager: Configured splitter manager
    """
    return TenantAwareTextSplitterManager(tenant_config)


def split_text_for_tenant(
    tenant_config: TenantLlamaConfig,
    text: str,
    strategy: Union[SplittingStrategy, str] = SplittingStrategy.RECURSIVE
) -> List[str]:
    """
    Convenience function to split text for a tenant.
    
    Args:
        tenant_config: Tenant-specific configuration
        text: Text to split
        strategy: Splitting strategy to use
        
    Returns:
        List of text chunks
    """
    manager = create_text_splitter_manager(tenant_config)
    return manager.split_text(text, strategy) 