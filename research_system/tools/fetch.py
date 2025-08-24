from __future__ import annotations
import httpx, datetime as dt
from typing import Optional, Dict, Any, Tuple
import trafilatura, extruct
from w3lib.html import get_base_url
from .claim_select import select_claim_sentences
from .pdf_extract import extract_pdf_text
from .doi_tools import extract_doi, crossref_meta
from .unpaywall import doi_to_oa_url
from .politeness import allowed, sync_host_throttle
from .cache import get as cached_get, get_binary as cached_get_binary
from .warc_dump import warc_capture
from .langpipe import to_english, detect_language
from .pdf_tables import find_numeric_cells
from ..config import Settings

settings = Settings()

UA = {"User-Agent": "Mozilla/5.0 (ResearchAgent/1.0)"}

def fetch_html(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Fetch HTML with caching, politeness, and paywall detection."""
    try:
        # Check robots.txt if enabled
        if settings.ENABLE_POLITENESS:
            if not allowed(url):
                return None, None
            sync_host_throttle(url)
        
        # Use cache if enabled
        if settings.ENABLE_HTTP_CACHE:
            status, headers, content = cached_get(url, headers=UA, timeout=25)
            if 200 <= status < 400:
                # Check for paywalls
                url_str = headers.get("location", url)
                if "statista.com/sso" in url_str or "statista.com/login" in url_str:
                    return None, None
                if "/login?" in url_str or "/subscribe?" in url_str:
                    return None, None
                return content, (headers.get("content-type") or "").lower()
        else:
            # Direct fetch without cache
            r = httpx.get(url, timeout=25, headers=UA, follow_redirects=True)
            if 200 <= r.status_code < 400:
                url_str = str(r.url or "")
                if "statista.com/sso" in url_str or "statista.com/login" in url_str:
                    return None, None
                if "/login?" in url_str or "/subscribe?" in url_str:
                    return None, None
                return r.text, (r.headers.get("content-type") or "").lower()
    except Exception:
        pass
    return None, None

def extract_article(url: str, html: Optional[str] = None) -> Dict[str, Any]:
    html_ct = None
    status = 200  # Default status for when html is provided
    
    if html is None:
        # Fetch with GET request (not HEAD) for better content
        try:
            r = httpx.get(url, timeout=30, headers=UA, follow_redirects=True)
            html = r.text
            html_ct = r.headers.get("content-type", "").lower()
            status = r.status_code
        except Exception:
            html, html_ct = None, None
            status = 0
    
    # Generic paywall fallback for ANY domain (DOI / meta-PDF / mirrors)
    from .paywall_resolver import looks_gated, resolve as resolve_paywall
    if looks_gated(status, url, html) or (not html and "pdf" not in (html_ct or "")) or len((html or "")) < 500:
        alt = resolve_paywall(url=url, html=html, content_type=html_ct)
        if alt:
            return alt
    
    # If still no content and looks like it should be a PDF
    if not html and not (html_ct and "pdf" in html_ct) and not (url or "").lower().endswith(".pdf"):
        return {}
    # PDF path with enhanced extraction
    if (html_ct and "pdf" in html_ct) or (url or "").lower().endswith(".pdf"):
        try:
            # Use cached binary fetch if enabled
            if settings.ENABLE_HTTP_CACHE:
                status, headers, content = cached_get_binary(url, headers=UA, timeout=45)
                if status < 200 or status >= 400:
                    return {}
            else:
                r = httpx.get(url, headers=UA, timeout=45)
                if r.status_code < 200 or r.status_code >= 400:
                    return {}
                content = r.content
            
            # WARC capture if enabled
            if settings.ENABLE_WARC:
                warc_capture(url, headers=UA)
            
            # Extract PDF text
            pdf = extract_pdf_text(content)
            text = pdf.get("text", "") or ""
            
            # Try table extraction if text is sparse
            quotes = select_claim_sentences(text, max_sentences=2)
            if not quotes and settings.ENABLE_PDF_TABLES:
                table_cells = find_numeric_cells(content, max_tables=5)
                if table_cells:
                    # Use table data as quotes
                    quotes = table_cells[:2]
            
            # Language detection and translation prep
            if settings.ENABLE_LANGDETECT:
                lang = detect_language(text[:1000])
                if lang and lang != "en":
                    # Prepare for future translation
                    text = to_english(text)
            
            return {
                "title": pdf.get("title"),
                "text": text,
                "date": None,
                "publisher": None,
                "quotes": quotes
            }
        except Exception:
            return {}
        return {}
    
    base_url = get_base_url(html, url)
    meta = {}
    try:
        ld = extruct.extract(html, base_url=base_url, syntaxes=['json-ld']).get('json-ld', [])
        for item in ld:
            if isinstance(item, dict) and item.get("@type") in ("NewsArticle","ScholarlyArticle","Article","Report"):
                meta["title"] = item.get("headline") or item.get("name")
                meta["datePublished"] = item.get("datePublished") or item.get("dateModified")
                src = item.get("publisher") or {}
                meta["publisher"] = (src.get("name") if isinstance(src, dict) else src)
                break
    except Exception:
        pass
    text = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
    try:
        tmeta = trafilatura.extract_metadata(html)
        title_fallback = tmeta.title if tmeta else None
    except Exception:
        title_fallback = None
    title = meta.get("title") or title_fallback
    date = None
    d = meta.get("datePublished")
    if d:
        try:
            date = dt.datetime.fromisoformat(d.replace("Z", "").split("+")[0])
        except Exception:
            date = None
    quotes = select_claim_sentences(text, max_sentences=2)
    return {"title": title, "text": text, "date": date, "publisher": meta.get("publisher"), "quotes": quotes}