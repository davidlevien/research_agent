"""
Triangulation computation and union rate calculation
"""

from typing import List, Dict, Any

def union_rate(para_clusters: List[Dict[str, Any]], struct_tris: List[Dict[str, Any]], total_cards: int) -> float:
    """
    Calculate the union rate of triangulated evidence.
    This is the percentage of cards that are triangulated via either paraphrase or structure.
    """
    idx = set()
    
    # Add indices from paraphrase clusters (multi-domain only)
    for c in (para_clusters or []):
        if len(set(c.get("domains", []))) >= 2:
            idx.update(c.get("indices", []))
    
    # Add indices from structured triangulation (multi-domain only)
    for t in (struct_tris or []):
        if len(set(t.get("domains", []))) >= 2:
            idx.update(t.get("indices", []))
    
    return len(idx) / max(1, total_cards)


def compute_structured_triangles(cards: List[Any]) -> List[Dict[str, Any]]:
    """
    Compute structured triangulation from evidence cards.
    Returns list of triangles with indices, domains, and keys.
    """
    from ..tools.claim_struct import extract_struct_claim, struct_key
    
    structured_claims = []
    claim_texts = [
        (getattr(c, "quote_span", None) or getattr(c, "claim", "") or 
         getattr(c, "snippet", "") or getattr(c, "source_title", ""))
        for c in cards
    ]
    
    # Extract structured claims
    for i, text in enumerate(claim_texts):
        sc = extract_struct_claim(text)
        key = struct_key(sc)
        if key:
            structured_claims.append({
                "index": i,
                "key": key,
                "entity": sc.entity,
                "metric": sc.metric,
                "period": sc.period,
                "value": sc.value,
                "unit": sc.unit,
                "text": text[:200]
            })
    
    # Group by key
    by_key = {}
    for claim in structured_claims:
        key = claim["key"]
        by_key.setdefault(key, []).append(claim)
    
    # Build triangles (2+ cards with same key from different domains)
    triangles = []
    for key, group in by_key.items():
        if len(group) >= 2:
            indices = [c["index"] for c in group]
            domains = list({cards[i].source_domain for i in indices})
            
            # Only count as triangulated if from 2+ domains
            if len(domains) >= 2:
                # Get representative text (highest credibility)
                best_idx = max(indices, key=lambda i: cards[i].credibility_score)
                representative = claim_texts[best_idx][:240]
                
                triangles.append({
                    "key": key,
                    "indices": indices,
                    "domains": domains,
                    "count": len(group),
                    "representative_claim": representative,
                    "entity": group[0].get("entity"),
                    "metric": group[0].get("metric"),
                    "period": group[0].get("period")
                })
    
    return triangles


def primary_share_in_triangulated(cards: List[Any], para_clusters: List[Dict], struct_tris: List[Dict], 
                                  primary_domains: set) -> float:
    """
    Calculate the share of primary sources in triangulated evidence.
    """
    # Get all triangulated indices
    tri_indices = set()
    for c in (para_clusters or []):
        if len(set(c.get("domains", []))) >= 2:
            tri_indices.update(c.get("indices", []))
    for t in (struct_tris or []):
        if len(set(t.get("domains", []))) >= 2:
            tri_indices.update(t.get("indices", []))
    
    if not tri_indices:
        return 0.0
    
    # Count primary sources in triangulated set
    primary_count = sum(1 for i in tri_indices if cards[i].source_domain in primary_domains)
    return primary_count / len(tri_indices)