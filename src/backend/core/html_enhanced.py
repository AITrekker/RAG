"""
Enhanced HTML processing with BeautifulSoup integration.
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
        metadata = {}
        
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
        
        # Extract language from html tag
        html_tag = soup.find('html')
        if html_tag and html_tag.get('lang') and 'language' not in metadata:
            metadata['language'] = html_tag.get('lang')
        
        # Use first h1 as title fallback
        if 'title' not in metadata:
            h1_tag = soup.find('h1')
            if h1_tag:
                metadata['title'] = h1_tag.get_text().strip()
        
        # Extract clean text content
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
        
        text_content = text.strip()
        
        metadata['encoding'] = used_encoding
        metadata['extraction_method'] = 'beautifulsoup'
        
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


def extract_html_content_fallback(file_path: str) -> Dict[str, Any]:
    """Fallback HTML extraction using regex when BeautifulSoup is not available."""
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
        metadata = {}
        
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
        
        # Extract language from html tag
        lang_pattern = r'<html[^>]*lang=["\']([^"\']*)["\']'
        lang_match = re.search(lang_pattern, content, re.IGNORECASE)
        if lang_match:
            metadata['language'] = lang_match.group(1)
        
        # Clean content
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
        content = re.sub(r'\s+', ' ', content).strip()
        
        metadata['encoding'] = used_encoding
        metadata['extraction_method'] = 'regex_fallback'
        
        return {
            'success': True,
            'content': content,
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