"""PDF fetch module with size limits, timeouts, and streaming."""
from __future__ import annotations
import httpx
import os
import time
import random
import logging
from typing import Optional, Set, Dict
from urllib.parse import urlparse, urlunparse
import hashlib

logger = logging.getLogger(__name__)


MAX_PDF_MB = float(os.getenv("MAX_PDF_MB", "12"))  # hard cap
CHUNK = 64 * 1024
TIMEOUT = httpx.Timeout(connect=6.0, read=15.0, write=10.0, pool=10.0)
RETRIES = int(os.getenv("PDF_RETRIES", "2"))

# Track downloaded URLs by content hash to prevent redundant downloads
_seen_downloads: Dict[str, bytes] = {}  # URL hash -> content
_url_to_hash: Dict[str, str] = {}  # Canonical URL -> content hash

def _canonicalize_url(url: str) -> str:
    """Canonicalize URL for deduplication."""
    parsed = urlparse(url.lower())
    # Remove fragment, normalize path
    clean_path = parsed.path.rstrip('/') if parsed.path else '/'
    # Sort query params for consistency
    query = '&'.join(sorted(parsed.query.split('&'))) if parsed.query else ''
    return urlunparse((parsed.scheme, parsed.netloc, clean_path, '', query, ''))

def _content_hash(content: bytes) -> str:
    """Generate SHA256 hash of content."""
    return hashlib.sha256(content).hexdigest()


def _too_large(content_length: int) -> bool:
    """Check if content length exceeds max PDF size."""
    return content_length and content_length > MAX_PDF_MB * 1024 * 1024


def download_pdf(client: httpx.Client, url: str) -> bytes:
    """Download PDF with size limits, streaming, and retries.
    
    Prevents redundant downloads in the same session by caching.
    
    Args:
        client: httpx client instance
        url: URL to download PDF from
        
    Returns:
        PDF content as bytes
        
    Raises:
        ValueError: If PDF exceeds size limit
        httpx.HTTPError: If download fails after retries
    """
    # Check if already downloaded in this session by URL
    canonical_url = _canonicalize_url(url)
    if canonical_url in _url_to_hash:
        content_hash = _url_to_hash[canonical_url]
        if content_hash in _seen_downloads:
            import logging
            logging.getLogger(__name__).info(f"Returning cached PDF for {url} (hash: {content_hash[:8]}...)")
            return _seen_downloads[content_hash]
    # 1) HEAD gate
    try:
        h = client.head(url, timeout=TIMEOUT, follow_redirects=True)
        cl = int(h.headers.get("content-length", "0") or "0")
        if _too_large(cl):
            raise ValueError(f"PDF too large: {cl}B > {MAX_PDF_MB}MB")
    except Exception:
        # HEAD might be blocked; continue with GET but enforce stream cap
        pass

    # 2) Stream with cap + retry
    delay = 0.0
    for attempt in range(RETRIES + 1):
        if delay:
            time.sleep(delay)
            delay = min(2.0, delay * 1.8) + random.uniform(0, 0.2)
        try:
            with client.stream("GET", url, timeout=TIMEOUT, follow_redirects=True) as r:
                r.raise_for_status()
                buf, size, budget = bytearray(), 0, int(MAX_PDF_MB * 1024 * 1024)
                for chunk in r.iter_bytes(CHUNK):
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > budget:
                        raise ValueError(f"PDF exceeded cap {MAX_PDF_MB}MB")
                    buf.extend(chunk)
                result = bytes(buf)
                # Cache by content hash to catch duplicate content at different URLs
                content_hash = _content_hash(result)
                _seen_downloads[content_hash] = result
                _url_to_hash[canonical_url] = content_hash
                # Also cache the final redirected URL if different
                if hasattr(r, 'url') and str(r.url) != url:
                    redirected_canonical = _canonicalize_url(str(r.url))
                    _url_to_hash[redirected_canonical] = content_hash
                    logger.debug(f"Cached PDF: {url} -> {str(r.url)[:50]}... (hash: {content_hash[:8]}...)")
                return result
        except Exception as e:
            if attempt == 0:
                delay = 0.35
            elif attempt >= RETRIES:
                raise
            else:
                continue