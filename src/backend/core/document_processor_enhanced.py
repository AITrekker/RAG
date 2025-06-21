"""
Enhanced document processor with BeautifulSoup-based HTML processing.

This module extends the DocumentProcessor with enhanced HTML processing capabilities
using BeautifulSoup for better content extraction and metadata parsing.
"""

import os
import re
import html
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pathlib import Path

# BeautifulSoup import
try:
    from bs4 import BeautifulSoup
    BEAUTIFULSOUP_AVAILABLE = True
except ImportError:
    BeautifulSoup = None
    BEAUTIFULSOUP_AVAILABLE = False

logger = logging.getLogger(__name__)


def extract_html_content_with_beautifulsoup(file_path: str) -> Dict[str, Any]:
    """
    Extract HTML content using BeautifulSoup for enhanced processing.
    
    Args:
        file_path: Path to the HTML file
        
    Returns:
        Dictionary containing extracted content and metadata
    """
    if not BEAUTIFULSOUP_AVAILABLE:
        return {
            'success': False,
            'error': "BeautifulSoup is not available. Install with: pip install beautifulsoup4"
        }
    
    try:
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
        metadata = _extract_html_metadata(soup)
        metadata['encoding'] = used_encoding
        metadata['extraction_method'] = 'beautifulsoup'
        
        # Extract clean text content
        text_content = _extract_html_text_content(soup)
        
        # Extract document structure
        structure = _extract_html_structure(soup)
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
        logger.error(f"BeautifulSoup HTML extraction error: {e}")
        return {
            'success': False,
            'error': f"HTML extraction error: {str(e)}"
        }


def _extract_html_metadata(soup) -> Dict[str, Any]:
    """Extract metadata from HTML using BeautifulSoup."""
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
        logger.warning(f"Error extracting HTML metadata: {e}")
    
    return metadata


def _extract_html_text_content(soup) -> str:
    """Extract clean text content from HTML using BeautifulSoup."""
    try:
        # Remove script and style elements
        for element in soup(["script", "style", "noscript", "head"]):
            element.decompose()
        
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
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        
        return text.strip()
        
    except Exception as e:
        logger.warning(f"Error extracting HTML text content: {e}")
        return soup.get_text() if soup else ""


def _extract_html_structure(soup) -> Dict[str, Any]:
    """Extract document structure information from HTML."""
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
                text = heading.get_text().strip()
                if text:  # Only include non-empty headings
                    structure['headings'].append({
                        'level': level,
                        'text': text,
                        'id': heading.get('id'),
                        'class': heading.get('class')
                    })
        
        # Extract links
        for link in soup.find_all('a', href=True):
            text = link.get_text().strip()
            href = link['href']
            if text and href:  # Only include links with text and href
                structure['links'].append({
                    'text': text,
                    'href': href,
                    'title': link.get('title')
                })
        
        # Extract images
        for img in soup.find_all('img'):
            src = img.get('src')
            if src:  # Only include images with src
                structure['images'].append({
                    'src': src,
                    'alt': img.get('alt', ''),
                    'title': img.get('title', '')
                })
        
        # Extract lists
        for list_tag in soup.find_all(['ul', 'ol']):
            list_items = []
            for li in list_tag.find_all('li'):
                item_text = li.get_text().strip()
                if item_text:
                    list_items.append(item_text)
            
            if list_items:  # Only include non-empty lists
                structure['lists'].append({
                    'type': list_tag.name,
                    'items': list_items
                })
        
        # Extract tables
        for table in soup.find_all('table'):
            rows = []
            for row in table.find_all('tr'):
                cells = []
                for cell in row.find_all(['td', 'th']):
                    cell_text = cell.get_text().strip()
                    cells.append(cell_text)
                if cells and any(cells):  # Only include rows with content
                    rows.append(cells)
            
            if rows:  # Only include non-empty tables
                structure['tables'].append({'rows': rows})
        
    except Exception as e:
        logger.warning(f"Error extracting HTML structure: {e}")
    
    return structure


def extract_html_content_fallback(file_path: str) -> Dict[str, Any]:
    """
    Fallback HTML extraction using regex when BeautifulSoup is not available.
    
    Args:
        file_path: Path to the HTML file
        
    Returns:
        Dictionary containing extracted content and metadata
    """
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
        metadata = _extract_html_metadata_regex(content)
        metadata['encoding'] = used_encoding
        metadata['extraction_method'] = 'regex_fallback'
        
        # Clean content
        clean_content = _clean_html_content_regex(content)
        
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
            'error': f"Regex HTML extraction error: {str(e)}"
        }


def _extract_html_metadata_regex(content: str) -> Dict[str, Any]:
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


def _clean_html_content_regex(content: str) -> str:
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


# Enhanced HTML extraction function that tries BeautifulSoup first, then fallback
def extract_html_content(file_path: str) -> Dict[str, Any]:
    """
    Extract content from HTML file with BeautifulSoup support.
    
    This function first tries to use BeautifulSoup for enhanced processing,
    then falls back to regex-based extraction if BeautifulSoup is not available.
    
    Args:
        file_path: Path to the HTML file
        
    Returns:
        Dictionary containing extracted content and metadata
    """
    if BEAUTIFULSOUP_AVAILABLE:
        logger.debug(f"Using BeautifulSoup for HTML extraction: {file_path}")
        result = extract_html_content_with_beautifulsoup(file_path)
        if result['success']:
            return result
        else:
            logger.warning(f"BeautifulSoup extraction failed, falling back to regex: {result.get('error')}")
    
    logger.debug(f"Using regex fallback for HTML extraction: {file_path}")
    return extract_html_content_fallback(file_path)


def validate_html_file(file_path: str) -> bool:
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