"""
Text normalization and cleaning utilities.
Consolidates text cleaning functionality from content_processor.py.
"""

import re
import hashlib
from typing import Set, List


def clean_text(text: str, remove_html: bool = True, remove_urls: bool = True, 
               remove_emails: bool = True) -> str:
    """
    Clean and normalize text content.
    
    Args:
        text: Raw text to clean
        remove_html: Remove HTML tags if present
        remove_urls: Remove URLs from text
        remove_emails: Remove email addresses
    
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove HTML tags if requested and present
    if remove_html and '<' in text and '>' in text:
        from .extract import remove_html_tags
        text = remove_html_tags(text)
    
    # Remove URLs
    if remove_urls:
        text = re.sub(r'https?://\S+|www\.\S+', '', text)
    
    # Remove email addresses
    if remove_emails:
        text = re.sub(r'\S+@\S+\.\S+', '', text)
    
    # Remove special characters but keep sentence structure
    text = re.sub(r'[^\w\s\.\,\!\?\-\:\;\'\"]', ' ', text)
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text


def tokenize(text: str, lowercase: bool = True) -> List[str]:
    """
    Tokenize text into words.
    
    Args:
        text: Text to tokenize
        lowercase: Convert to lowercase
    
    Returns:
        List of tokens
    """
    if not text:
        return []
    
    # Extract words (alphanumeric sequences)
    if lowercase:
        words = re.findall(r'\b[a-z0-9]+\b', text.lower())
    else:
        words = re.findall(r'\b[a-zA-Z0-9]+\b', text)
    
    return words


def remove_stopwords(words: List[str], stopwords: Set[str]) -> List[str]:
    """
    Remove stopwords from a list of words.
    
    Args:
        words: List of words to filter
        stopwords: Set of stopwords to remove
    
    Returns:
        Filtered list of words
    """
    return [w for w in words if w.lower() not in stopwords]


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace in text.
    
    Args:
        text: Text to normalize
    
    Returns:
        Text with normalized whitespace
    """
    if not text:
        return ""
    
    # Replace multiple spaces with single space
    text = re.sub(r' +', ' ', text)
    
    # Replace multiple newlines with double newline
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Replace tabs with spaces
    text = re.sub(r'\t', ' ', text)
    
    return text.strip()


def remove_quotes(text: str) -> str:
    """
    Remove quotation marks from text.
    
    Args:
        text: Text containing quotes
    
    Returns:
        Text with quotes removed
    """
    if not text:
        return ""
    
    # Remove various quote styles
    text = re.sub(r'["\'\`''""„]', '', text)
    
    return text


def truncate_text(text: str, max_length: int, add_ellipsis: bool = True) -> str:
    """
    Truncate text to maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        add_ellipsis: Add '...' if truncated
    
    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text
    
    if add_ellipsis and max_length > 3:
        return text[:max_length - 3] + '...'
    else:
        return text[:max_length]


def generate_text_hash(text: str, normalize: bool = True) -> str:
    """
    Generate a hash for text content (useful for deduplication).
    
    Args:
        text: Text to hash
        normalize: Normalize text before hashing
    
    Returns:
        SHA-256 hash of the text
    """
    if not text:
        return ""
    
    if normalize:
        # Normalize for hashing
        text = clean_text(text)
        text = text.lower()
        text = normalize_whitespace(text)
    
    # Generate SHA-256 hash
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def get_default_stopwords() -> Set[str]:
    """
    Get a default set of English stopwords.
    
    Returns:
        Set of common English stopwords
    """
    return {
        'the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'but',
        'in', 'with', 'to', 'for', 'of', 'as', 'by', 'that', 'this',
        'it', 'from', 'be', 'are', 'was', 'were', 'been', 'have', 'has',
        'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
        'may', 'might', 'can', 'must', 'shall', 'if', 'when', 'where',
        'what', 'who', 'whom', 'whose', 'why', 'how', 'than', 'then',
        'so', 'not', 'no', 'nor', 'only', 'just', 'more', 'most', 'less',
        'least', 'very', 'much', 'any', 'all', 'each', 'every', 'some',
        'few', 'many', 'such', 'own', 'same', 'other', 'another', 'both',
        'either', 'neither', 'too', 'also', 'else', 'ever', 'never',
        'here', 'there', 'these', 'those', 'them', 'they', 'their', 'our',
        'we', 'us', 'you', 'your', 'he', 'him', 'his', 'she', 'her', 'hers',
        'i', 'me', 'my', 'mine', 'myself', 'yourself', 'himself', 'herself'
    }