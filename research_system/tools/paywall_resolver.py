from __future__ import annotations
import re, os, httpx, datetime as dt
from typing import Optional, Dict, Any, Tuple

UA = {"User-Agent": "ResearchAgent/1.0 (+mailto:research@example.com)"}

# ---- DOI utilities -----------------------------------------------------------
_DOI_URL_RX = re.compile(r"/doi/(?:abs/|pdf/|full/)?(?P<doi>10\.\d{4,9}/[^\s?#]+)", re.I)
_META_DOI_RX = re.compile(r'<meta[^>]+(?:name|property)="(?:citation_doi|dc\.identifier|dc.identifier)".*?content="(?P<doi>10\.\d{4,9}/[^"]+)"', re.I)

def extract_doi_from_url(url: str) -> Optional[str]:
    m = _DOI_URL_RX.search(url or "")
    return m.group("doi") if m else None

def extract_doi_from_html(html: str) -> Optional[str]:
    if not html: return None
    m = _META_DOI_RX.search(html)
    return m.group("doi") if m else None

def crossref_meta(doi: str) -> Dict[str, Any]:
    try:
        r = httpx.get(f"https://api.crossref.org/works/{doi}", headers=UA, timeout=25)
        if r.status_code != 200: return {}
        msg = (r.json() or {}).get("message", {})
        title = (msg.get("title") or [None])[0]
        abstract = msg.get("abstract") or ""
        y = (msg.get("issued",{}).get("date-parts") or [[None]])[0][0]
        date = dt.date(int(y),1,1).isoformat() if isinstance(y,int) else None
        return {"title": title, "abstract": abstract, "date": date}
    except Exception:
        return {}

def unpaywall_best_oa(doi: str) -> Optional[str]:
    email = os.getenv("UNPAYWALL_EMAIL", "open@example.com")
    try:
        r = httpx.get(f"https://api.unpaywall.org/v2/{doi}?email={email}", timeout=25)
        if r.status_code != 200: return None
        best = (r.json() or {}).get("best_oa_location") or {}
        return best.get("url_for_pdf") or best.get("url")
    except Exception:
        return None

# ---- HTML meta PDF discovery -------------------------------------------------
_META_PDF_RX = re.compile(
    r'<meta[^>]+(?:name|property)=["\'](?:citation_pdf_url|pdf_url|og:pdf|eprints\.pdfUrl)["\'][^>]+content=["\'](?P<url>[^"\']+)["\']',
    re.I
)
_LINK_PDF_RX = re.compile(
    r'<link[^>]+(?:rel|type)=["\'](?:alternate|canonical|related)["\'][^>]+(?:href|content)=["\'](?P<url>[^"\']+\.pdf[^"\']*)["\']',
    re.I
)
def find_pdf_in_html(html: str) -> Optional[str]:
    if not html: return None
    m = _META_PDF_RX.search(html) or _LINK_PDF_RX.search(html)
    return (m.group("url") if m else None)

# ---- Mirror hints for well-known orgs (optional, extendable) ----------------
MIRRORS = (
    # (predicate, transform)
    (lambda u: "unwto.org" in u, lambda u: u.replace("www.unwto.org", "en.unwto-ap.org").replace("unwto.org","en.unwto-ap.org")),
    (lambda u: "who.int" in u,  lambda u: u.replace("www.who.int","iris.who.int")),  # WHO IRIS
    (lambda u: "imf.org" in u,  lambda u: u.replace("/publications/","/en/Publications/")),
    # add others as discovered (OECD has DOIs; WorldBank often exposes direct PDFs)
)

# ---- Gating detection --------------------------------------------------------
def looks_gated(status: int, url: str, html: Optional[str]) -> bool:
    if status in (401, 402, 403): return True
    if not html: return False
    l = html.lower()
    # conservative patterns (avoid previous false-positives on mere "login" words in nav)
    signals = ("paywall", "metered access", "subscribe to read", "purchase this article",
               "get access", "institutional access", "please sign in to continue")
    return any(s in l for s in signals)

# ---- Main entry --------------------------------------------------------------
def resolve(url: str, html: Optional[str], content_type: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Return a dict with at least one of: {"text", "title", "date", "quotes"} or None if no improvement.
    Strategy:
      1) If DOI present (in URL or meta): try Unpaywall OA PDF, else Crossref abstract.
      2) Else: scan HTML for citation_pdf_url/link rel=alternate PDF and fetch.
      3) Else: try a known mirror transform (if any), GET and return HTML.
    """
    # 1) DOI path (publisher-agnostic)
    doi = extract_doi_from_url(url) or extract_doi_from_html(html or "")
    if doi:
        oa = unpaywall_best_oa(doi)
        if oa:
            # Use guarded_get to avoid paywall loops
            from research_system.net.guarded_get import guarded_get
            try:
                with httpx.Client(headers=UA, timeout=httpx.Timeout(45), follow_redirects=False) as cl:
                    pr = guarded_get(oa, cl)
                if pr.status_code == 200 and "pdf" in pr.headers.get("content-type","").lower():
                    from .pdf_extract import extract_pdf_text
                    from .claim_select import select_claim_sentences
                    pdf = extract_pdf_text(pr.content, max_pages=6)
                    quotes = select_claim_sentences(pdf.get("text",""), 2)
                    return {"title": pdf.get("title"), "text": pdf.get("text",""), "date": None, "quotes": quotes, "oa_url": oa, "doi": doi, "source": "unpaywall"}
            except (PermissionError, httpx.TooManyRedirects):
                pass  # Paywall or redirect loop detected
        meta = crossref_meta(doi)
        if meta and (meta.get("abstract") or meta.get("title")):
            from .claim_select import select_claim_sentences
            quotes = select_claim_sentences((meta.get("abstract") or "")[:2000], 2)
            return {"title": meta.get("title"), "text": meta.get("abstract") or "", "date": meta.get("date"), "quotes": quotes, "doi": doi, "source": "crossref"}

    # 2) HTML meta/link pointing to a PDF
    pdf_url = find_pdf_in_html(html or "")
    if pdf_url:
        # Use guarded_get to avoid paywall loops
        from research_system.net.guarded_get import guarded_get
        try:
            with httpx.Client(headers=UA, timeout=httpx.Timeout(45), follow_redirects=False) as cl:
                pr = guarded_get(pdf_url, cl)
            if pr.status_code == 200 and "pdf" in pr.headers.get("content-type","").lower():
                from .pdf_extract import extract_pdf_text
                from .claim_select import select_claim_sentences
                pdf = extract_pdf_text(pr.content, max_pages=6)
                quotes = select_claim_sentences(pdf.get("text",""), 2)
                return {"title": pdf.get("title"), "text": pdf.get("text",""), "quotes": quotes, "source": "meta-pdf"}
        except (PermissionError, httpx.TooManyRedirects):
            pass  # Paywall or redirect loop detected

    # 3) Domain mirrors (org-specific but optional)
    for pred, transform in MIRRORS:
        if pred(url):
            try:
                mu = transform(url)
                mr = httpx.get(mu, headers=UA, timeout=30, follow_redirects=True)
                if mr.status_code == 200 and len((mr.text or "")) > 500:
                    return {"title": None, "text": mr.text, "quotes": None, "source": "mirror", "mirror_url": mu}
            except Exception:
                pass

    return None