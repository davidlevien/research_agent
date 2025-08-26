"""
Unified text extraction module.
Consolidates HTML parsing, text extraction, and metadata extraction
from both parse_tools.py and content_processor.py.
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def extract_text(html_content: str, preserve_structure: bool = False) -> str:
    """
    Extract clean text from HTML content.
    
    Args:
        html_content: HTML string to parse
        preserve_structure: If True, preserve paragraph/line structure
    
    Returns:
        Extracted text content
    """
    if not html_content:
        return ""
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for element in soup(['script', 'style', 'noscript']):
            element.decompose()
        
        if preserve_structure:
            # Get text with structure preserved
            text = soup.get_text(separator='\n', strip=True)
            # Clean up excessive newlines
            text = re.sub(r'\n{3,}', '\n\n', text)
        else:
            # Get plain text with spaces between elements
            text = soup.get_text(separator=' ', strip=True)
            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
        
    except Exception as e:
        logger.error(f"Text extraction failed: {e}")
        return ""


def clean_html(html_content: str) -> str:
    """
    Clean and sanitize HTML content by removing dangerous tags and attributes.
    
    Args:
        html_content: Raw HTML string
    
    Returns:
        Sanitized HTML string
    """
    if not html_content:
        return ""
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove dangerous tags
        dangerous_tags = ['script', 'style', 'iframe', 'object', 'embed', 
                         'form', 'input', 'button', 'select', 'textarea']
        for tag in dangerous_tags:
            for element in soup.find_all(tag):
                element.decompose()
        
        # Remove dangerous attributes
        dangerous_attrs = ['onclick', 'onload', 'onerror', 'onmouseover', 
                          'onmouseout', 'onkeypress', 'onkeydown', 'onkeyup']
        for tag in soup.find_all():
            for attr in dangerous_attrs:
                if attr in tag.attrs:
                    del tag.attrs[attr]
        
        return str(soup)
        
    except Exception as e:
        logger.error(f"HTML cleaning failed: {e}")
        return ""


def remove_html_tags(text: str) -> str:
    """
    Remove all HTML tags from text.
    
    Args:
        text: Text that may contain HTML tags
    
    Returns:
        Text with HTML tags removed
    """
    if not text:
        return ""
    
    # Check if text contains HTML
    if '<' not in text or '>' not in text:
        return text
    
    try:
        soup = BeautifulSoup(text, 'html.parser')
        return soup.get_text(separator=' ', strip=True)
    except:
        # Fallback to regex if BeautifulSoup fails
        return re.sub(r'<[^>]+>', '', text)


def extract_metadata(html_content: str) -> Dict[str, Any]:
    """
    Extract metadata from HTML including title, description, dates, etc.
    
    Args:
        html_content: HTML string to parse
    
    Returns:
        Dictionary of metadata fields
    """
    metadata = {
        "title": "",
        "description": "",
        "keywords": [],
        "author": "",
        "published_date": "",
        "modified_date": "",
        "language": "",
        "publisher": ""
    }
    
    if not html_content:
        return metadata
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract title
        title_tag = soup.find('title')
        if title_tag:
            metadata["title"] = title_tag.get_text(strip=True)
        
        # Extract meta tags
        for meta in soup.find_all('meta'):
            name = meta.get('name', '').lower()
            property_attr = meta.get('property', '').lower()
            content = meta.get('content', '')
            
            if not content:
                continue
            
            # Description
            if name == 'description' or property_attr == 'og:description':
                metadata["description"] = content
            
            # Keywords
            elif name == 'keywords':
                metadata["keywords"] = [k.strip() for k in content.split(',')]
            
            # Author
            elif name == 'author' or property_attr == 'article:author':
                metadata["author"] = content
            
            # Published date
            elif name in ['publication_date', 'publishdate', 'publish_date'] or \
                 property_attr in ['article:published_time', 'og:article:published_time']:
                metadata["published_date"] = content
            
            # Modified date
            elif name in ['last_modified', 'modified', 'lastmod'] or \
                 property_attr in ['article:modified_time', 'og:article:modified_time']:
                metadata["modified_date"] = content
            
            # Language
            elif name == 'language' or property_attr == 'og:locale':
                metadata["language"] = content
            
            # Publisher
            elif property_attr == 'og:site_name' or name == 'publisher':
                metadata["publisher"] = content
        
        # Extract structured data (JSON-LD)
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    # Title fallback
                    if 'headline' in data and not metadata["title"]:
                        metadata["title"] = data['headline']
                    
                    # Author extraction
                    if 'author' in data and not metadata["author"]:
                        if isinstance(data['author'], dict):
                            metadata["author"] = data['author'].get('name', '')
                        else:
                            metadata["author"] = str(data['author'])
                    
                    # Date extraction
                    if 'datePublished' in data and not metadata["published_date"]:
                        metadata["published_date"] = data['datePublished']
                    
                    if 'dateModified' in data and not metadata["modified_date"]:
                        metadata["modified_date"] = data['dateModified']
                    
                    # Publisher extraction
                    if 'publisher' in data and not metadata["publisher"]:
                        if isinstance(data['publisher'], dict):
                            metadata["publisher"] = data['publisher'].get('name', '')
                        else:
                            metadata["publisher"] = str(data['publisher'])
            except:
                pass
        
        return metadata
        
    except Exception as e:
        logger.error(f"Metadata extraction failed: {e}")
        return metadata


def extract_links(html_content: str, base_url: Optional[str] = None) -> List[str]:
    """
    Extract all links from HTML content.
    
    Args:
        html_content: HTML string to parse
        base_url: Optional base URL for resolving relative links
    
    Returns:
        List of absolute URLs found
    """
    links = []
    
    if not html_content:
        return links
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Handle relative URLs if base_url provided
            if base_url and not href.startswith(('http://', 'https://', 'mailto:', 'tel:', '#')):
                from urllib.parse import urljoin
                href = urljoin(base_url, href)
            
            # Only include HTTP(S) links
            if href.startswith(('http://', 'https://')):
                links.append(href)
        
        return list(set(links))  # Remove duplicates
        
    except Exception as e:
        logger.error(f"Link extraction failed: {e}")
        return links