"""
URL normalization utilities using w3lib and tldextract
"""

from __future__ import annotations
import hashlib
import urllib.parse as _up

# Make w3lib optional
try:
    from w3lib.url import canonicalize_url as _canon
    HAS_W3LIB = True
except ImportError:
    HAS_W3LIB = False
    # Simple fallback canonicalization
    def _canon(u: str) -> str:
        p = _up.urlparse(u or "")
        return _up.urlunparse((
            p.scheme.lower(),
            p.netloc.lower(),
            p.path,
            "",  # Drop params
            "",  # Drop query
            ""   # Drop fragment
        ))

import tldextract

def canonicalize_url(url: str) -> str:
    try:
        u = (url or "").strip()
        cu = _canon(u)
        p = _up.urlparse(cu)
        host = (p.netloc or "").lower()
        # Drop query/fragment for S3 & e-unwto DOI PDFs to avoid VersionId noise
        if host.endswith("amazonaws.com") or host.endswith("e-unwto.org"):
            cu = _up.urlunparse((p.scheme, p.netloc, p.path, "", "", ""))
        return cu
    except Exception:
        return (url or "").strip()

def domain_of(url: str) -> str:
    try:
        ext = tldextract.extract(url or "")
        root = ".".join([p for p in [ext.domain, ext.suffix] if p])
        return root.lower() or "unknown"
    except Exception:
        return "unknown"

def normalized_hash(text: str) -> str:
    t = " ".join((text or "").split()).lower()
    return hashlib.sha1(t.encode("utf-8")).hexdigest()