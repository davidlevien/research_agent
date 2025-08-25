from __future__ import annotations
import httpx, datetime as dt, os, logging, re
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Make optional dependencies robust
try:
    import trafilatura
    import extruct
    HAS_TRAFILATURA = True
except ImportError:
    trafilatura = None
    extruct = None
    HAS_TRAFILATURA = False

try:
    from w3lib.html import get_base_url
    HAS_W3LIB = True
except ImportError:
    HAS_W3LIB = False
    def get_base_url(html: str, url: str) -> str:
        # Simple fallback
        return url
from .claim_select import select_claim_sentences
from .pdf_extract import extract_pdf_text
from .doi_tools import extract_doi, crossref_meta
from .unpaywall import doi_to_oa_url
from .politeness import allowed, sync_host_throttle
from .cache import get as cached_get, get_binary as cached_get_binary
from .doi_fallback import doi_rescue, extract_doi_from_url
from .warc_dump import warc_capture
from .langpipe import to_english, detect_language
from .pdf_tables import find_numeric_cells
from ..config import get_settings

# Lazy load UA to avoid import-time Settings instantiation
def _get_ua():
    return {"User-Agent": "Mozilla/5.0 (ResearchAgent/1.0)"}

def fetch_html(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Fetch HTML with caching, politeness, and paywall detection."""
    try:
        settings = get_settings()
        # Check robots.txt if enabled
        if settings.ENABLE_POLITENESS:
            if not allowed(url):
                return None, None
            sync_host_throttle(url)
        
        # Use cache if enabled
        if settings.ENABLE_HTTP_CACHE:
            status, headers, content = cached_get(url, headers=_get_ua(), timeout=25)
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
            r = httpx.get(url, timeout=25, headers=_get_ua(), follow_redirects=True)
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
    from urllib.parse import urlparse
    from research_system.net.circuit import CIRCUIT
    from research_system.net.cache import get as cache_get, set as cache_set, parse_cache_control
    from research_system.net.robots import is_allowed as robots_allowed
    from research_system.time_budget import get_timeout
    
    html_ct = None
    status = 200  # Default status for when html is provided
    
    # Check robots.txt compliance
    if not robots_allowed(url):
        logger.info(f"Robots.txt disallows {url}, trying DOI/mirror fallback")
        from .paywall_resolver import resolve as resolve_paywall
        alt = resolve_paywall(url, None, None)
        if alt:
            return alt
        return {}
    
    # Check circuit breaker
    host = urlparse(url).netloc.lower()
    if not CIRCUIT.allow(host):
        logger.warning(f"Circuit open for {host}, skipping")
        return {}
    
    if html is None:
        # Check cache first
        cache_key = ("GET", url)
        cached = cache_get(cache_key)
        if cached:
            body, headers, status, ct = cached
            if status == 200:
                html = body if isinstance(body, str) else body.decode('utf-8', errors='ignore')
                html_ct = ct
                logger.debug(f"Cache hit for {url}")
            
        if html is None:
            # Fetch with GET request (not HEAD) for better content
            try:
                timeout = get_timeout(30)
                r = httpx.get(url, timeout=timeout, headers=_get_ua(), follow_redirects=True)
                
                # Cache successful responses
                if 200 <= r.status_code < 300:
                    ttl = parse_cache_control(dict(r.headers))
                    if ttl > 0:
                        cache_set(cache_key, ttl, (r.text, dict(r.headers), r.status_code, r.headers.get("content-type", "")))
                    CIRCUIT.ok(host)
                else:
                    # Check for 401/403 and try DOI fallback if applicable
                    if r.status_code in (401, 403):
                        doi = extract_doi_from_url(url)
                        if doi:
                            logger.info(f"Got {r.status_code} for {url}, trying DOI metadata fallback")
                            email = os.getenv("CONTACT_EMAIL", "ci@example.org")
                            meta = doi_rescue(doi, email=email)
                            if meta:
                                text = meta.get("abstract") or ""
                                title_fallback = meta.get("title") or None
                                quotes = select_claim_sentences(text or title_fallback or "", max_sentences=2)
                                return {
                                    "title": title_fallback,
                                    "text": (text or title_fallback or "")[:5000],
                                    "date": meta.get("date"),
                                    "publisher": meta.get("publisher"),
                                    "quotes": quotes,
                                    "source": meta.get("source", "doi_metadata")
                                }
                    CIRCUIT.fail(host)
                
                # Check for Cloudflare challenge
                from research_system.net.cloudflare import is_cf_challenge, get_unwto_mirror_url
                if is_cf_challenge(r):
                    # Jump straight to resolver (DOI/Unpaywall or mirror)
                    from .paywall_resolver import resolve as resolve_paywall
                    alt = resolve_paywall(url, r.text, r.headers.get("content-type", ""))
                    if alt:
                        return alt
                    # Final UNWTO mirror fallback
                    mu = get_unwto_mirror_url(url)
                    if mu:
                        try:
                            mr = httpx.get(mu, headers=_get_ua(), timeout=30)
                            if mr.status_code == 200 and len((mr.text or "")) > 500:
                                return {"title": None, "text": mr.text, "quotes": None, "source": "mirror", "mirror_url": mu}
                        except Exception:
                            pass
                    raise PermissionError("Cloudflare challenge")
                
                html = r.text
                html_ct = r.headers.get("content-type", "").lower()
                status = r.status_code
            except PermissionError:
                CIRCUIT.fail(host)
                return {}  # Cloudflare block
            except Exception as e:
                CIRCUIT.fail(host)
                logger.debug(f"Fetch failed for {url}: {e}")
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
            # Use new PDF fetch with size limits and timeouts
            from research_system.net.pdf_fetch import download_pdf
            with httpx.Client() as cl:
                content = download_pdf(cl, url)
            
            # WARC capture if enabled
            if settings.ENABLE_WARC:
                warc_capture(url, headers=_get_ua())
            
            # Extract PDF text with page limit
            max_pages = int(os.getenv("PDF_MAX_PAGES", "6"))
            pdf = extract_pdf_text(content, max_pages=max_pages)
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
    
    # Try extruct if available
    if HAS_TRAFILATURA and extruct:
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
    
    # Extract text with trafilatura if available, otherwise basic fallback
    if HAS_TRAFILATURA and trafilatura:
        text = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
        try:
            tmeta = trafilatura.extract_metadata(html)
            title_fallback = tmeta.title if tmeta else None
        except Exception:
            title_fallback = None
    else:
        # Basic HTML text extraction fallback
        import re
        text = re.sub(r'<[^>]+>', ' ', html or '')
        text = re.sub(r'\s+', ' ', text).strip()[:5000]
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