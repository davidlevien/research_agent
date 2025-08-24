"""Ensure quotes for primary sources through fallback mechanisms."""

import httpx
from typing import List, Any

PRIMARY = {
    "unwto.org", "e-unwto.org", "iata.org", "wttc.org",
    "oecd.org", "worldbank.org", "imf.org", "ec.europa.eu"
}


async def ensure_quotes_for_primaries(cards: List[Any]) -> None:
    """
    Ensure primary source cards have quotes through DOI/OA PDF/Crossref fallback.
    
    Args:
        cards: List of evidence cards to process
    """
    from ..tools.paywall_resolver import resolve as resolve_paywall
    
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for c in cards:
            # Skip non-primary sources
            if c.source_domain not in PRIMARY:
                continue
            
            # Skip if already has quote
            if c.quote_span:
                continue
            
            # Try to fetch and resolve
            try:
                r = await client.get(c.url)
                alt = resolve_paywall(c.url, r.text, r.headers.get("content-type", ""))
                
                # Apply quotes if found
                if alt and alt.get("quotes"):
                    c.quote_span = alt["quotes"][0]
                    
            except Exception:
                # Silently continue on errors
                pass