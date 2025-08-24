"""
Enhanced deduplication with title similarity and URL canonicalization
"""

import re
from typing import List, Any, Set, Tuple
from ..tools.url_canon import canonical_url

def jaccard_title(a: str, b: str) -> float:
    """Calculate Jaccard similarity between two titles"""
    tok = lambda s: set(re.findall(r"[A-Za-z0-9]+", (s or "").lower()))
    A, B = tok(a), tok(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)

def dedup_cards(cards: List[Any], title_threshold: float = 0.9) -> List[Any]:
    """
    Deduplicate evidence cards by URL and title similarity.
    Returns deduplicated list preserving highest quality cards.
    """
    if not cards:
        return []
    
    seen_urls = {}  # canonical_url -> card
    seen_titles = {}  # (domain, title_tokens) -> card
    out = []
    
    for c in cards:
        # Get canonical URL
        url = canonical_url(c.url or c.source_url or "")
        if not url:
            continue
        
        domain = c.source_domain or ""
        title = c.title or c.source_title or ""
        
        # Check URL duplicate
        if url in seen_urls:
            # Keep the one with higher credibility
            existing = seen_urls[url]
            if c.credibility_score > existing.credibility_score:
                # Replace with better version
                idx = out.index(existing)
                out[idx] = c
                seen_urls[url] = c
            continue
        
        # Check title near-duplicate (same domain only)
        is_dup = False
        if domain and title:
            for other in out:
                if other.source_domain == domain:
                    other_title = other.title or other.source_title or ""
                    if jaccard_title(title, other_title) >= title_threshold:
                        # Near-duplicate title on same domain
                        if c.credibility_score > other.credibility_score:
                            # Replace with better version
                            idx = out.index(other)
                            out[idx] = c
                            # Update seen_urls
                            other_url = canonical_url(other.url or other.source_url or "")
                            if other_url in seen_urls:
                                del seen_urls[other_url]
                            seen_urls[url] = c
                        is_dup = True
                        break
        
        if not is_dup:
            seen_urls[url] = c
            out.append(c)
    
    return out

def find_duplicate_groups(cards: List[Any]) -> List[Set[int]]:
    """
    Find groups of duplicate cards by URL or title.
    Returns list of index sets representing duplicate groups.
    """
    groups = []
    processed = set()
    
    for i, c1 in enumerate(cards):
        if i in processed:
            continue
        
        group = {i}
        url1 = canonical_url(c1.url or c1.source_url or "")
        domain1 = c1.source_domain or ""
        title1 = c1.title or c1.source_title or ""
        
        for j, c2 in enumerate(cards[i+1:], start=i+1):
            if j in processed:
                continue
            
            url2 = canonical_url(c2.url or c2.source_url or "")
            domain2 = c2.source_domain or ""
            title2 = c2.title or c2.source_title or ""
            
            # Check if duplicate
            is_dup = False
            
            # Same canonical URL
            if url1 and url2 and url1 == url2:
                is_dup = True
            
            # Same domain with very similar title
            elif domain1 and domain2 and domain1 == domain2:
                if jaccard_title(title1, title2) >= 0.9:
                    is_dup = True
            
            if is_dup:
                group.add(j)
                processed.add(j)
        
        if len(group) > 1:
            groups.append(group)
            processed.update(group)
    
    return groups