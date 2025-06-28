"""
HTML document processor utility for the Enterprise RAG Platform.

This module provides enhanced HTML processing capabilities including:
- Advanced HTML content extraction and cleaning
- Metadata extraction from HTML head tags
- Structure preservation and analysis
- Fallback processing for various HTML formats
"""

import re
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import html

logger = logging.getLogger(__name__)


class HTMLProcessor:
    """
    Enhanced HTML document processor.
    
    Provides robust HTML content extraction with metadata preservation,
    structure analysis, and multiple fallback methods.
    """
    
    def __init__(self):
        """Initialize HTML processor."""
        self.use_beautifulsoup = self._check_beautifulsoup_availability()
        logger.info(f"HTMLProcessor initialized (BeautifulSoup available: {self.use_beautifulsoup})")
    
    def _check_beautifulsoup_availability(self) -> bool:
        """Check if BeautifulSoup is available for enhanced parsing."""
        try:
            from bs4 import BeautifulSoup
            return True
        except ImportError:
            logger.warning("BeautifulSoup not available, using fallback HTML parsing")
            return False
    
    def extract_content(self, file_path: str) -> Dict[str, Any]:
        """
        Extract content and metadata from HTML file.
        
        Args:
            file_path: Path to the HTML file
            
        Returns:
            Dictionary containing extracted content and metadata
        """
        try:
            if self.use_beautifulsoup:
                return self._extract_with_beautifulsoup(file_path)
            else:
                return self._extract_with_regex(file_path)
        except Exception as e:
            logger.error(f"Error extracting HTML content from {file_path}: {e}")
            return {
                'success': False,
                'error': f"HTML extraction error: {str(e)}"
            }
    
    def _extract_with_beautifulsoup(self, file_path: str) -> Dict[str, Any]:
        """Extract content using BeautifulSoup for better parsing."""
        try:
            from bs4 import BeautifulSoup
            
            # Try multiple encodings
            encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
            soup = None
            used_encoding = None
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    soup = BeautifulSoup(content, 'html.parser')
                    used_encoding = encoding
                    break
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    logger.warning(f"Error with encoding {encoding}: {e}")
                    continue
            
            if not soup:
                return {
                    'success': False,
                    'error': "Could not parse HTML with any supported encoding"
                }
            
            # Extract metadata
            metadata = self._extract_metadata_beautifulsoup(soup)
            metadata['encoding'] = used_encoding
            
            # Extract main content
            text_content = self._extract_text_content_beautifulsoup(soup)
            
            # Extract structure information
            structure = self._extract_structure_beautifulsoup(soup)
            metadata['structure'] = structure
            
            return {
                'success': True,
                'content': text_content,
                'title': metadata.get('title'),
                'page_count': 1,
                'language': metadata.get('language', 'en'),
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"BeautifulSoup extraction error: {e}")
            # Fallback to regex method
            return self._extract_with_regex(file_path)
    
    def _extract_metadata_beautifulsoup(self, soup) -> Dict[str, Any]:
        """Extract metadata using BeautifulSoup."""
        metadata = {}
        
        try:
            # Extract title
            title_tag = soup.find('title')
            if title_tag:
                metadata['title'] = title_tag.get_text().strip()
            
            # Extract meta tags
            meta_tags = soup.find_all('meta')
            for meta in meta_tags:
                name = meta.get('name') or meta.get('property') or meta.get('http-equiv')
                content = meta.get('content')
                
                if name and content:
                    name_lower = name.lower()
                    if name_lower == 'description':
                        metadata['description'] = content
                    elif name_lower == 'keywords':
                        metadata['keywords'] = content
                    elif name_lower == 'author':
                        metadata['author'] = content
                    elif name_lower in ['language', 'lang']:
                        metadata['language'] = content
                    elif name_lower == 'robots':
                        metadata['robots'] = content
                    elif name_lower.startswith('og:'):  # Open Graph
                        metadata[name_lower] = content
                    elif name_lower.startswith('twitter:'):  # Twitter Cards
                        metadata[name_lower] = content
            
            # Extract language from html tag
            html_tag = soup.find('html')
            if html_tag and html_tag.get('lang') and 'language' not in metadata:
                metadata['language'] = html_tag.get('lang')
            
            # Use first h1 as title fallback
            if 'title' not in metadata:
                h1_tag = soup.find('h1')
                if h1_tag:
                    metadata['title'] = h1_tag.get_text().strip()
            
        except Exception as e:
            logger.warning(f"Error extracting metadata: {e}")
        
        return metadata
    
    def _extract_text_content_beautifulsoup(self, soup) -> str:
        """Extract clean text content using BeautifulSoup."""
        try:
            # Remove script and style elements
            for script in soup(["script", "style", "noscript"]):
                script.decompose()
            
            # Remove comments
            from bs4 import Comment
            comments = soup.findAll(text=lambda text: isinstance(text, Comment))
            for comment in comments:
                comment.extract()
            
            # Get text content
            text = soup.get_text()
            
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text
            
        except Exception as e:
            logger.warning(f"Error extracting text content: {e}")
            return soup.get_text() if soup else ""
    
    def _extract_structure_beautifulsoup(self, soup) -> Dict[str, Any]:
        """Extract document structure information."""
        structure = {
            'headings': [],
            'links': [],
            'images': [],
            'lists': [],
            'tables': []
        }
        
        try:
            # Extract headings
            for level in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                for heading in soup.find_all(level):
                    structure['headings'].append({
                        'level': level,
                        'text': heading.get_text().strip(),
                        'id': heading.get('id'),
                        'class': heading.get('class')
                    })
            
            # Extract links
            for link in soup.find_all('a', href=True):
                structure['links'].append({
                    'text': link.get_text().strip(),
                    'href': link['href'],
                    'title': link.get('title')
                })
            
            # Extract images
            for img in soup.find_all('img'):
                structure['images'].append({
                    'src': img.get('src'),
                    'alt': img.get('alt'),
                    'title': img.get('title')
                })
            
            # Extract lists
            for list_tag in soup.find_all(['ul', 'ol']):
                list_items = [li.get_text().strip() for li in list_tag.find_all('li')]
                structure['lists'].append({
                    'type': list_tag.name,
                    'items': list_items
                })
            
            # Extract tables
            for table in soup.find_all('table'):
                rows = []
                for row in table.find_all('tr'):
                    cells = [cell.get_text().strip() for cell in row.find_all(['td', 'th'])]
                    if cells:
                        rows.append(cells)
                if rows:
                    structure['tables'].append({'rows': rows})
            
        except Exception as e:
            logger.warning(f"Error extracting structure: {e}")
        
        return structure
    
    def _extract_with_regex(self, file_path: str) -> Dict[str, Any]:
        """Extract content using regex patterns as fallback."""
        try:
            # Try multiple encodings
            encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
            content = None
            used_encoding = None
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    used_encoding = encoding
                    break
                except UnicodeDecodeError:
                    continue
            
            if not content:
                return {
                    'success': False,
                    'error': "Could not read HTML file with any supported encoding"
                }
            
            # Extract metadata using regex
            metadata = self._extract_metadata_regex(content)
            metadata['encoding'] = used_encoding
            metadata['extraction_method'] = 'regex_fallback'
            
            # Clean content
            clean_content = self._clean_html_content_regex(content)
            
            return {
                'success': True,
                'content': clean_content,
                'title': metadata.get('title'),
                'page_count': 1,
                'language': metadata.get('language', 'en'),
                'metadata': metadata
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Regex extraction error: {str(e)}"
            }
    
    def _extract_metadata_regex(self, content: str) -> Dict[str, Any]:
        """Extract metadata using regex patterns."""
        metadata = {}
        
        try:
            # Extract title
            title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
            if title_match:
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
                title = html.unescape(title)
                metadata['title'] = title
            
            # Extract meta description
            desc_pattern = r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']'
            desc_match = re.search(desc_pattern, content, re.IGNORECASE)
            if desc_match:
                metadata['description'] = html.unescape(desc_match.group(1))
            
            # Extract meta keywords
            keywords_pattern = r'<meta[^>]*name=["\']keywords["\'][^>]*content=["\']([^"\']*)["\']'
            keywords_match = re.search(keywords_pattern, content, re.IGNORECASE)
            if keywords_match:
                metadata['keywords'] = html.unescape(keywords_match.group(1))
            
            # Extract language from html tag
            lang_pattern = r'<html[^>]*lang=["\']([^"\']*)["\']'
            lang_match = re.search(lang_pattern, content, re.IGNORECASE)
            if lang_match:
                metadata['language'] = lang_match.group(1)
            
            # Extract first h1 as fallback title
            if 'title' not in metadata:
                h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', content, re.IGNORECASE | re.DOTALL)
                if h1_match:
                    h1_title = re.sub(r'<[^>]+>', '', h1_match.group(1)).strip()
                    h1_title = html.unescape(h1_title)
                    metadata['title'] = h1_title
            
        except Exception as e:
            logger.warning(f"Error extracting metadata with regex: {e}")
        
        return metadata
    
    def _clean_html_content_regex(self, content: str) -> str:
        """Clean HTML content using regex patterns."""
        try:
            # Remove script and style tags and their content
            content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
            content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
            content = re.sub(r'<noscript[^>]*>.*?</noscript>', '', content, flags=re.DOTALL | re.IGNORECASE)
            
            # Remove HTML comments
            content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
            
            # Remove all HTML tags
            content = re.sub(r'<[^>]+>', ' ', content)
            
            # Decode HTML entities
            content = html.unescape(content)
            
            # Clean up whitespace
            content = re.sub(r'\s+', ' ', content)
            content = content.strip()
            
            return content
            
        except Exception as e:
            logger.warning(f"Error cleaning HTML content: {e}")
            return content
    
    def validate_html(self, file_path: str) -> bool:
        """Validate if file is a proper HTML file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(1024)  # Read first 1KB
            
            # Check for HTML indicators
            content_lower = content.lower()
            html_indicators = ['<html', '<head', '<body', '<!doctype html', '<title']
            
            return any(indicator in content_lower for indicator in html_indicators)
            
        except Exception:
            return False
    
    def extract_links(self, file_path: str) -> List[Dict[str, str]]:
        """Extract all links from HTML file."""
        try:
            result = self.extract_content(file_path)
            if result['success'] and 'structure' in result['metadata']:
                return result['metadata']['structure'].get('links', [])
            return []
        except Exception as e:
            logger.error(f"Error extracting links: {e}")
            return []
    
    def extract_headings(self, file_path: str) -> List[Dict[str, str]]:
        """Extract all headings from HTML file."""
        try:
            result = self.extract_content(file_path)
            if result['success'] and 'structure' in result['metadata']:
                return result['metadata']['structure'].get('headings', [])
            return []
        except Exception as e:
            logger.error(f"Error extracting headings: {e}")
            return []


# Utility functions
def create_html_processor() -> HTMLProcessor:
    """Create HTML processor instance."""
    return HTMLProcessor()


def extract_html_content(file_path: str) -> Dict[str, Any]:
    """Quick function to extract HTML content."""
    processor = HTMLProcessor()
    return processor.extract_content(file_path)


def validate_html_file(file_path: str) -> bool:
    """Quick function to validate HTML file."""
    processor = HTMLProcessor()
    return processor.validate_html(file_path) 