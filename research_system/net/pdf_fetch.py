"""PDF fetch module with size limits, timeouts, and streaming."""
from __future__ import annotations
import httpx
import os
import time
import random
from typing import Optional


MAX_PDF_MB = float(os.getenv("MAX_PDF_MB", "12"))  # hard cap
CHUNK = 64 * 1024
TIMEOUT = httpx.Timeout(connect=6.0, read=15.0, write=10.0, pool=10.0)
RETRIES = int(os.getenv("PDF_RETRIES", "2"))


def _too_large(content_length: int) -> bool:
    """Check if content length exceeds max PDF size."""
    return content_length and content_length > MAX_PDF_MB * 1024 * 1024


def download_pdf(client: httpx.Client, url: str) -> bytes:
    """Download PDF with size limits, streaming, and retries.
    
    Args:
        client: httpx client instance
        url: URL to download PDF from
        
    Returns:
        PDF content as bytes
        
    Raises:
        ValueError: If PDF exceeds size limit
        httpx.HTTPError: If download fails after retries
    """
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
                return bytes(buf)
        except Exception as e:
            if attempt == 0:
                delay = 0.35
            elif attempt >= RETRIES:
                raise
            else:
                continue