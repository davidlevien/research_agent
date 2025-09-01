"""
Parsing tools for content extraction
"""

import re
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
import logging

from .registry import get_registry

logger = logging.getLogger(__name__)


class ParseTools:
    """Collection of parsing tools"""
    
    def __init__(self):
        self._register_tools()
    
    def _register_tools(self):
        """Register all parsing tools if not already registered"""
        from .registry import ToolSpec
        
        # Check if tools are already registered to avoid duplicates
        # Register tool
        get_registry().register(ToolSpec(
                name="extract_text",
                fn=self.extract_text,
                description="Extract clean text from HTML"
            ))
        
        # Register tool
        get_registry().register(ToolSpec(
                name="clean_html",
                fn=self.clean_html,
                description="Clean and sanitize HTML"
            ))
        
        # Register tool
        get_registry().register(ToolSpec(
                name="extract_metadata",
                fn=self.extract_metadata,
                description="Extract metadata from HTML"
            ))
    
    def extract_text(self, html_content: str, preserve_structure: bool = False) -> str:
        """Extract clean text from HTML"""
        if not html_content:
            return ""
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            if preserve_structure:
                # Get text with some structure preserved
                text = soup.get_text(separator='\n', strip=True)
            else:
                # Get plain text
                text = soup.get_text(strip=True)
            
            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text)
            text = re.sub(r'\n{3,}', '\n\n', text)
            
            return text.strip()
            
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return ""
    
    def clean_html(self, html_content: str) -> str:
        """Clean and sanitize HTML content"""
        if not html_content:
            return ""
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove dangerous tags
            dangerous_tags = ['script', 'style', 'iframe', 'object', 'embed', 'form']
            for tag in dangerous_tags:
                for element in soup.find_all(tag):
                    element.decompose()
            
            # Remove dangerous attributes
            dangerous_attrs = ['onclick', 'onload', 'onerror', 'onmouseover']
            for tag in soup.find_all():
                for attr in dangerous_attrs:
                    if attr in tag.attrs:
                        del tag.attrs[attr]
            
            return str(soup)
            
        except Exception as e:
            logger.error(f"HTML cleaning failed: {e}")
            return ""
    
    def extract_metadata(self, html_content: str) -> Dict[str, Any]:
        """Extract metadata from HTML"""
        metadata = {
            "title": "",
            "description": "",
            "keywords": [],
            "author": "",
            "published_date": "",
            "modified_date": "",
            "language": ""
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
                
                if name == 'description' or property_attr == 'og:description':
                    metadata["description"] = content
                elif name == 'keywords':
                    metadata["keywords"] = [k.strip() for k in content.split(',')]
                elif name == 'author':
                    metadata["author"] = content
                elif name in ['publication_date', 'article:published_time']:
                    metadata["published_date"] = content
                elif name in ['last_modified', 'article:modified_time']:
                    metadata["modified_date"] = content
                elif name == 'language' or property_attr == 'og:locale':
                    metadata["language"] = content
            
            # Extract structured data (JSON-LD)
            for script in soup.find_all('script', type='application/ld+json'):
                try:
                    import json
                    data = json.loads(script.string)
                    if isinstance(data, dict):
                        if 'headline' in data and not metadata["title"]:
                            metadata["title"] = data['headline']
                        if 'author' in data and not metadata["author"]:
                            if isinstance(data['author'], dict):
                                metadata["author"] = data['author'].get('name', '')
                            else:
                                metadata["author"] = str(data['author'])
                        if 'datePublished' in data:
                            metadata["published_date"] = data['datePublished']
                except:
                    pass
            
            return metadata
            
        except Exception as e:
            logger.error(f"Metadata extraction failed: {e}")
            return metadata
    
    def extract_links(self, html_content: str, base_url: Optional[str] = None) -> List[str]:
        """Extract all links from HTML"""
        links = []
        
        if not html_content:
            return links
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            for link in soup.find_all('a', href=True):
                href = link['href']
                
                # Handle relative URLs if base_url provided
                if base_url and not href.startswith(('http://', 'https://', 'mailto:', 'tel:')):
                    from urllib.parse import urljoin
                    href = urljoin(base_url, href)
                
                if href.startswith(('http://', 'https://')):
                    links.append(href)
            
            return list(set(links))  # Remove duplicates
            
        except Exception as e:
            logger.error(f"Link extraction failed: {e}")
            return links
    
    def extract_images(self, html_content: str, base_url: Optional[str] = None) -> List[Dict[str, str]]:
        """Extract image information from HTML"""
        images = []
        
        if not html_content:
            return images
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            for img in soup.find_all('img'):
                image_info = {
                    "src": img.get('src', ''),
                    "alt": img.get('alt', ''),
                    "title": img.get('title', '')
                }
                
                # Handle relative URLs
                if base_url and image_info["src"] and not image_info["src"].startswith(('http://', 'https://', 'data:')):
                    from urllib.parse import urljoin
                    image_info["src"] = urljoin(base_url, image_info["src"])
                
                if image_info["src"]:
                    images.append(image_info)
            
            return images
            
        except Exception as e:
            logger.error(f"Image extraction failed: {e}")
            return images