"""HTML cleaning and text extraction utilities.

v8.21.0: Removes navigation, headers, footers, and other non-content elements
to extract clean text for claim mining.
"""

from bs4 import BeautifulSoup
from typing import List

def clean_html_to_text(html: str) -> str:
    """
    Extract clean text from HTML, removing navigation and non-content elements.
    
    Args:
        html: Raw HTML string
        
    Returns:
        Clean text with one paragraph per line
    """
    if not html:
        return ""
    
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        # Fallback to html.parser if lxml not available
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            return ""
    
    # Remove non-content elements
    for tag in soup(["nav", "header", "footer", "aside", "script", "style", "noscript"]):
        tag.decompose()
    
    # Remove elements that look like table of contents
    for tag in soup.find_all(["ul", "ol"]):
        # Check class names for ToC indicators
        classes = tag.get("class", [])
        if any("toc" in str(c).lower() for c in classes):
            tag.decompose()
        # Check id for ToC indicators  
        tag_id = tag.get("id", "")
        if "toc" in tag_id.lower() or "contents" in tag_id.lower():
            tag.decompose()
    
    # Remove elements with navigation roles
    for tag in soup.find_all(attrs={"role": "navigation"}):
        tag.decompose()
    
    # Extract text with newline separation
    text = soup.get_text("\n", strip=True)
    
    # Clean up lines
    lines = []
    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned and len(cleaned) > 2:  # Skip very short lines
            lines.append(cleaned)
    
    return "\n".join(lines)