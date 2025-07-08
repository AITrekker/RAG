"""
RAG Prompt Templates Configuration

This file manages prompt templates used in the RAG pipeline.
Templates are loaded from /config/prompts/ directory with hot-reloading support.
"""

import os
import time
from typing import Dict, Any
from dataclasses import dataclass
from pathlib import Path
from .config_loader import config_loader, PromptTemplate


@dataclass
class RAGPromptTemplates:
    """Container for all RAG prompt templates"""
    
    # Main RAG answer generation prompt
    rag_answer_prompt: str = """You are a professional AI assistant providing accurate information based on company documents.

CONTEXT FROM COMPANY DOCUMENTS:
{context}

USER QUESTION: {query}

INSTRUCTIONS:
- Provide a clear, well-structured answer based ONLY on the context above
- Use professional language and complete sentences
- If information is missing from the context, state this clearly
- Cite specific sources when making claims
- Structure your response with proper paragraphs
- Be comprehensive but concise

PROFESSIONAL ANSWER:"""

    # Alternative more conversational prompt
    rag_conversational_prompt: str = """Based on the following company documents, please answer the user's question in a helpful and professional manner.

Company Documents:
{context}

Question: {query}

Please provide a clear answer based on the information in these documents. If the documents don't contain enough information to fully answer the question, please mention this."""

    # Focused/technical prompt for detailed queries
    rag_technical_prompt: str = """You are a technical documentation assistant. Answer the question using only the provided context.

DOCUMENTATION CONTEXT:
{context}

QUESTION: {query}

REQUIREMENTS:
- Answer using only information from the context
- Be precise and technical when appropriate
- Include specific details and examples when available
- If context is insufficient, explain what information is missing

TECHNICAL ANSWER:"""

    # Executive summary style prompt
    rag_executive_prompt: str = """You are an executive assistant providing concise, business-focused answers.

BUSINESS CONTEXT:
{context}

EXECUTIVE QUESTION: {query}

DIRECTIVE:
- Provide a concise, business-focused answer
- Highlight key metrics, outcomes, and strategic implications
- Use professional business language
- Focus on actionable insights

EXECUTIVE SUMMARY:"""

    # Q&A style prompt
    rag_qa_prompt: str = """Answer the following question based on the provided information:

Information:
{context}

Question: {query}

Answer:"""

    # Default fallback prompt
    rag_fallback_prompt: str = """Context: {context}

Question: {query}

Answer:"""


class RAGPromptManager:
    """Manages RAG prompt templates and selection with hot-reloading support"""
    
    def __init__(self, enable_hot_reload: bool = True):
        self.templates = RAGPromptTemplates()
        self._current_template = "professional"
        self._loaded_templates = {}
        self._file_timestamps = {}
        self._enable_hot_reload = enable_hot_reload
        self._last_check_time = 0
        self._check_interval = 2.0  # Check for file changes every 2 seconds
        
        # Get prompts directory
        self._prompts_dir = config_loader.config_dir / "prompts"
        
        self._load_external_templates()
    
    def _load_external_templates(self):
        """Load templates from /config/prompts/ directory"""
        try:
            # Load all prompt template categories
            all_templates = config_loader.get_all_prompt_templates()
            
            # Clear existing templates
            self._loaded_templates = {}
            
            # Flatten templates from all categories
            for category, templates in all_templates.items():
                for template_id, template in templates.items():
                    self._loaded_templates[template_id] = template
            
            # Update file timestamps for hot-reloading
            if self._enable_hot_reload:
                self._update_file_timestamps()
                    
        except Exception as e:
            print(f"⚠️ Could not load external prompt templates: {e}")
            print("Using built-in templates only")
    
    def _update_file_timestamps(self):
        """Update file modification timestamps for hot-reload detection"""
        if not self._prompts_dir.exists():
            return
        
        for yaml_file in self._prompts_dir.glob("*.yaml"):
            try:
                self._file_timestamps[str(yaml_file)] = yaml_file.stat().st_mtime
            except Exception as e:
                print(f"⚠️ Could not get timestamp for {yaml_file}: {e}")
    
    def _check_for_file_changes(self) -> bool:
        """Check if any prompt template files have been modified"""
        if not self._enable_hot_reload or not self._prompts_dir.exists():
            return False
        
        current_time = time.time()
        
        # Only check periodically to avoid excessive file system calls
        if current_time - self._last_check_time < self._check_interval:
            return False
        
        self._last_check_time = current_time
        
        # Check each YAML file for modifications
        for yaml_file in self._prompts_dir.glob("*.yaml"):
            file_path = str(yaml_file)
            try:
                current_mtime = yaml_file.stat().st_mtime
                last_mtime = self._file_timestamps.get(file_path, 0)
                
                if current_mtime > last_mtime:
                    print(f"🔄 Detected change in prompt template file: {yaml_file.name}")
                    return True
                    
            except Exception as e:
                print(f"⚠️ Error checking file {yaml_file}: {e}")
        
        return False
    
    def _hot_reload_templates(self):
        """Reload templates from disk without restart"""
        print("🔄 Hot-reloading prompt templates...")
        try:
            # Clear config loader cache
            config_loader._prompt_cache = {}
            
            # Reload templates
            self._load_external_templates()
            
            print(f"✅ Reloaded {len(self._loaded_templates)} prompt templates")
            
        except Exception as e:
            print(f"❌ Failed to hot-reload templates: {e}")
    
    def get_prompt_template(self, template_name: str = "default") -> str:
        """Get a specific prompt template with hot-reload support"""
        # Check for file changes and reload if necessary
        if self._check_for_file_changes():
            self._hot_reload_templates()
        
        # Check external templates first
        if template_name in self._loaded_templates:
            return self._loaded_templates[template_name].template
        
        # Fallback to built-in templates
        template_map = {
            "default": self.templates.rag_answer_prompt,
            "professional": self.templates.rag_answer_prompt,
            "conversational": self.templates.rag_conversational_prompt,
            "technical": self.templates.rag_technical_prompt,
            "executive": self.templates.rag_executive_prompt,
            "qa": self.templates.rag_qa_prompt,
            "fallback": self.templates.rag_fallback_prompt
        }
        
        return template_map.get(template_name, self.templates.rag_answer_prompt)
    
    def build_prompt(self, query: str, context: str, template_name: str = "default") -> str:
        """Build a complete prompt from template"""
        template = self.get_prompt_template(template_name)
        return template.format(query=query, context=context)
    
    def get_available_templates(self) -> Dict[str, str]:
        """Get list of available prompt templates with descriptions"""
        # Check for file changes and reload if necessary
        if self._check_for_file_changes():
            self._hot_reload_templates()
        
        templates = {}
        
        # Add external templates
        for template_id, template in self._loaded_templates.items():
            templates[template_id] = template.description
        
        # Add built-in templates (if not overridden)
        builtin_templates = {
            "default": "Professional business assistant (recommended)",
            "professional": "Same as default - professional business language", 
            "conversational": "More casual, conversational tone",
            "technical": "Technical documentation style with precise details",
            "executive": "Concise executive summary style",
            "qa": "Simple question-answer format",
            "fallback": "Minimal prompt for basic responses"
        }
        
        for template_id, description in builtin_templates.items():
            if template_id not in templates:
                templates[template_id] = description
        
        return templates
    
    def set_default_template(self, template_name: str):
        """Set the default template to use"""
        available = self.get_available_templates()
        if template_name in available:
            self._current_template = template_name
        else:
            raise ValueError(f"Unknown template: {template_name}. Available: {list(available.keys())}")
    
    def get_current_template(self) -> str:
        """Get the current default template name"""
        return self._current_template
    
    def reload_external_templates(self):
        """Manually reload templates from config directory"""
        print("🔄 Manually reloading prompt templates...")
        config_loader._prompt_cache = {}  # Clear config loader cache
        self._loaded_templates = {}
        self._load_external_templates()
        print(f"✅ Manually reloaded {len(self._loaded_templates)} prompt templates")
    
    def force_reload(self):
        """Force reload all templates regardless of file timestamps"""
        self._hot_reload_templates()
    
    def get_reload_status(self) -> Dict[str, Any]:
        """Get status information about template reloading"""
        return {
            "hot_reload_enabled": self._enable_hot_reload,
            "check_interval": self._check_interval,
            "prompts_directory": str(self._prompts_dir),
            "loaded_templates_count": len(self._loaded_templates),
            "loaded_template_names": list(self._loaded_templates.keys()),
            "tracked_files": list(self._file_timestamps.keys()),
            "last_check_time": self._last_check_time
        }
    
    def enable_hot_reload(self):
        """Enable hot-reloading of prompt templates"""
        self._enable_hot_reload = True
        self._update_file_timestamps()
        print("✅ Hot-reload enabled for prompt templates")
    
    def disable_hot_reload(self):
        """Disable hot-reloading of prompt templates"""
        self._enable_hot_reload = False
        print("❌ Hot-reload disabled for prompt templates")


# Global prompt manager instance
rag_prompts = RAGPromptManager()


# Prompt configuration that can be loaded from environment or config file
class PromptConfig:
    """Configuration for prompt behavior"""
    
    # Which prompt template to use by default
    DEFAULT_TEMPLATE: str = "default"
    
    # Context formatting settings
    MAX_CONTEXT_SOURCES: int = 5
    SOURCE_SEPARATOR: str = "\n\n"
    SOURCE_PREFIX_FORMAT: str = "[Source {index} - {filename}]: "
    
    # Response formatting settings
    INCLUDE_SOURCE_CITATIONS: bool = True
    REQUIRE_CONTEXT_GROUNDING: bool = True
    
    # Quality control settings
    MIN_CONTEXT_LENGTH: int = 50  # Minimum context length to generate answer
    MAX_CONTEXT_LENGTH: int = 2000  # Maximum context to avoid token limits
    
    @classmethod
    def format_context_sources(cls, search_results) -> str:
        """Format search results into context string"""
        context_parts = []
        
        for i, result in enumerate(search_results[:cls.MAX_CONTEXT_SOURCES]):
            source_prefix = cls.SOURCE_PREFIX_FORMAT.format(
                index=i + 1,
                filename=result.filename
            )
            context_parts.append(f"{source_prefix}{result.content}")
        
        context = cls.SOURCE_SEPARATOR.join(context_parts)
        
        # Truncate if too long
        if len(context) > cls.MAX_CONTEXT_LENGTH:
            context = context[:cls.MAX_CONTEXT_LENGTH] + "..."
        
        return context


# Export the main components
__all__ = [
    "RAGPromptTemplates",
    "RAGPromptManager", 
    "rag_prompts",
    "PromptConfig"
]