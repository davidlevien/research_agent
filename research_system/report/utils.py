"""
Utility functions for report generation with sentence-aware trimming.
Implements v8.15.0 improvements for clean, professional outputs.
"""

from __future__ import annotations
import re
from typing import Iterable, List, Optional, Set, Tuple
import logging

logger = logging.getLogger(__name__)

# Sentence boundary detection pattern
SENTENCE_END = re.compile(r"([\.!?])\s+")

# Abbreviations that don't end sentences
ABBREVIATIONS = {
    "Dr", "Mr", "Mrs", "Ms", "Prof", "Sr", "Jr", "Ph.D", "M.D", "B.A", "M.A",
    "Inc", "Corp", "Co", "Ltd", "LLC", "vs", "etc", "i.e", "e.g", "cf",
    "Jan", "Feb", "Mar", "Apr", "Jun", "Jul", "Aug", "Sep", "Sept", "Oct", "Nov", "Dec"
}


def sentence_trim(text: str, max_chars: int = 500) -> str:
    """
    Trim text without leaving dangling ellipses.
    End on sentence boundary where possible.
    
    Args:
        text: Text to trim
        max_chars: Maximum character length
        
    Returns:
        Trimmed text ending on sentence boundary
    """
    text = (text or "").strip()
    
    # If already short enough, return as-is
    if len(text) <= max_chars:
        return text
    
    # Hard cut at max_chars
    chunk = text[:max_chars].rstrip()
    
    # Find all sentence boundaries
    matches = list(SENTENCE_END.finditer(chunk))
    
    # Filter out abbreviations
    valid_ends = []
    for match in matches:
        # Check word before the period
        start = match.start()
        # Find the word before the punctuation
        word_start = start
        while word_start > 0 and chunk[word_start - 1].isalnum():
            word_start -= 1
        
        word = chunk[word_start:start]
        
        # Skip if it's a known abbreviation
        if word not in ABBREVIATIONS:
            valid_ends.append(match)
    
    # If we found valid sentence endings, use the last one
    if valid_ends:
        end = valid_ends[-1].end()  # Include trailing space
        return chunk[:end].strip()
    
    # If no sentence boundary found, try to end at word boundary
    last_space = chunk.rfind(' ')
    if last_space > max_chars * 0.7:  # Only if we keep at least 70% of content
        return chunk[:last_space].strip() + "…"
    
    # Last resort: hard cut with ellipsis
    return chunk + "…"


def unique_preserve_order(items: Iterable[str]) -> List[str]:
    """
    Remove duplicates while preserving order.
    
    Args:
        items: Iterable of strings
        
    Returns:
        List with duplicates removed, order preserved
    """
    seen: Set[str] = set()
    out: List[str] = []
    
    for x in items:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    
    return out


def clean_html(text: str) -> str:
    """
    Remove HTML tags and normalize whitespace.
    
    Args:
        text: Text potentially containing HTML
        
    Returns:
        Clean text without HTML tags
    """
    # Remove HTML tags
    html_pattern = re.compile(r'<[^>]+>')
    text = html_pattern.sub('', text or '')
    
    # Normalize whitespace
    text = ' '.join(text.split())
    
    return text


def extract_domain(url: str) -> str:
    """
    Extract domain from URL with normalization.
    
    Args:
        url: URL string
        
    Returns:
        Normalized domain (without www.)
    """
    try:
        from urllib.parse import urlparse
        netloc = urlparse(url).netloc.lower()
        
        # Remove www. prefix
        if netloc.startswith("www."):
            netloc = netloc[4:]
        
        return netloc
    except Exception as e:
        logger.debug(f"Failed to extract domain from {url}: {e}")
        return ""


def format_citation(url: str, index: int) -> str:
    """
    Format a URL as a markdown citation link.
    
    Args:
        url: URL to cite
        index: Citation index (1-based)
        
    Returns:
        Markdown formatted citation
    """
    return f"[{index}]({url})"


def format_citations(urls: List[str], max_citations: int = 5) -> str:
    """
    Format multiple URLs as inline citations.
    
    Args:
        urls: List of URLs to cite
        max_citations: Maximum number of citations to include
        
    Returns:
        Space-separated markdown citations
    """
    unique_urls = unique_preserve_order(urls)[:max_citations]
    
    if not unique_urls:
        return ""
    
    citations = [format_citation(url, i + 1) for i, url in enumerate(unique_urls)]
    return " ".join(citations)


def is_numeric_claim(text: str) -> bool:
    """
    Check if text contains a numeric claim.
    
    Args:
        text: Text to check
        
    Returns:
        True if text contains numbers
    """
    if not text:
        return False
    
    # Check for digits
    if any(ch.isdigit() for ch in text):
        return True
    
    # Check for spelled-out numbers
    number_words = {
        "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
        "eleven", "twelve", "twenty", "thirty", "forty", "fifty", "hundred", "thousand",
        "million", "billion", "trillion", "percent", "percentage"
    }
    
    text_lower = text.lower()
    return any(word in text_lower for word in number_words)


def truncate_list(items: List[str], max_items: int = 10, max_chars_per_item: int = 200) -> List[str]:
    """
    Truncate a list of items with per-item character limits.
    
    Args:
        items: List of text items
        max_items: Maximum number of items to keep
        max_chars_per_item: Maximum characters per item
        
    Returns:
        Truncated list
    """
    result = []
    
    for item in items[:max_items]:
        if not item:
            continue
        
        trimmed = sentence_trim(item, max_chars_per_item)
        if trimmed:
            result.append(trimmed)
    
    return result


def format_bullet_list(items: List[str], indent: str = "- ") -> str:
    """
    Format items as a markdown bullet list.
    
    Args:
        items: List of items
        indent: Bullet point style
        
    Returns:
        Formatted bullet list
    """
    if not items:
        return ""
    
    return "\n".join(f"{indent}{item}" for item in items if item)


def safe_percentage(numerator: float, denominator: float, decimals: int = 0) -> str:
    """
    Calculate percentage safely with division by zero handling.
    
    Args:
        numerator: Top number
        denominator: Bottom number
        decimals: Number of decimal places
        
    Returns:
        Formatted percentage string
    """
    if denominator <= 0:
        return "0%"
    
    pct = (numerator / denominator) * 100
    
    if decimals == 0:
        return f"{int(pct)}%"
    else:
        return f"{pct:.{decimals}f}%"


def pluralize(count: int, singular: str, plural: Optional[str] = None) -> str:
    """
    Get singular or plural form based on count.
    
    Args:
        count: Number of items
        singular: Singular form
        plural: Plural form (defaults to singular + 's')
        
    Returns:
        Appropriate form with count
    """
    if plural is None:
        plural = singular + "s"
    
    form = singular if count == 1 else plural
    return f"{count} {form}"