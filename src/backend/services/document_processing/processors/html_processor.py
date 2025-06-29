"""HTML file processor using selectolax."""

from typing import List, Dict, Any
from pathlib import Path
import re
from ..base import DocumentProcessor

try:
    from selectolax.parser import HTMLParser
    SELECTOLAX_AVAILABLE = True
except ImportError:
    SELECTOLAX_AVAILABLE = False

class HTMLProcessor(DocumentProcessor):
    """Processor for HTML files using selectolax."""
    
    def __init__(self):
        if not SELECTOLAX_AVAILABLE:
            raise ImportError("selectolax is required for HTML processing. Install with: pip install selectolax")
    
    def supported_extensions(self) -> List[str]:
        return ['.html', '.htm']
    
    def extract_text(self, file_path: str) -> str:
        """Extract text from HTML file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                html_content = f.read()
            
            return self._parse_html_content(html_content)
            
        except Exception as e:
            raise ValueError(f"Error processing HTML {file_path}: {e}")
    
    def _parse_html_content(self, html_content: str) -> str:
        """Parse HTML content and extract structured text."""
        tree = HTMLParser(html_content)
        
        # Remove unwanted elements
        for selector in ['script', 'style', 'meta', 'link', 'noscript']:
            for elem in tree.css(selector):
                elem.decompose()
        
        text_parts = []
        
        # Extract title
        title = tree.css_first('title')
        if title and title.text().strip():
            text_parts.append(f"Title: {title.text().strip()}")
        
        # Extract headers with hierarchy
        for header in tree.css('h1, h2, h3, h4, h5, h6'):
            if header.text().strip():
                text_parts.append(f"[{header.tag.upper()}] {header.text().strip()}")
        
        # Extract main content areas
        content_selectors = [
            'main', 'article', '[role="main"]',
            '.content', '.post-content', '.entry-content'
        ]
        
        found_main_content = False
        for selector in content_selectors:
            for elem in tree.css(selector):
                text = self._clean_text(elem.text())
                if text and len(text) > 50:
                    text_parts.append(text)
                    found_main_content = True
        
        # If no main content found, extract from paragraphs and divs
        if not found_main_content:
            for elem in tree.css('p, div'):
                text = self._clean_text(elem.text())
                if text and len(text) > 30:
                    text_parts.append(text)
        
        # Extract lists
        for list_elem in tree.css('ul, ol'):
            items = []
            for li in list_elem.css('li'):
                item_text = self._clean_text(li.text())
                if item_text:
                    items.append(item_text)
            
            if items:
                text_parts.append('• ' + '\n• '.join(items))
        
        return '\n\n'.join(text_parts)
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text."""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Filter very short or meaningless content
        if len(text) < 10 or text.lower() in ['read more', 'click here', 'learn more', 'continue reading']:
            return ""
        
        return text
    
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract metadata from HTML file."""
        path = Path(file_path)
        stat = path.stat()
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                html_content = f.read()
            
            tree = HTMLParser(html_content)
            
            # Extract meta tags
            meta_data = {}
            for meta in tree.css('meta[name], meta[property]'):
                name = meta.attributes.get('name') or meta.attributes.get('property')
                content = meta.attributes.get('content', '')
                if name and content:
                    meta_data[name.lower()] = content
            
            return {
                'file_type': 'html',
                'title': tree.css_first('title').text() if tree.css_first('title') else '',
                'description': meta_data.get('description', ''),
                'keywords': meta_data.get('keywords', ''),
                'author': meta_data.get('author', ''),
                'og_title': meta_data.get('og:title', ''),
                'og_description': meta_data.get('og:description', ''),
                'viewport': meta_data.get('viewport', ''),
                'charset': meta_data.get('charset', ''),
                'size_bytes': stat.st_size,
                'modified_time': stat.st_mtime,
                'created_time': stat.st_ctime,
                'links_count': len(tree.css('a')),
                'images_count': len(tree.css('img')),
                'headings_count': len(tree.css('h1, h2, h3, h4, h5, h6')),
                'paragraphs_count': len(tree.css('p')),
                'meta_tags': meta_data
            }
            
        except Exception as e:
            # Fallback metadata if HTML parsing fails
            return {
                'file_type': 'html',
                'size_bytes': stat.st_size,
                'modified_time': stat.st_mtime,
                'created_time': stat.st_ctime,
                'error': str(e)
            }