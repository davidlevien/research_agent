"""
Aggregation and triangulation tools for evidence analysis
"""

from __future__ import annotations
from typing import List, Dict, Tuple, Set
from collections import defaultdict, Counter
from urllib.parse import urlparse
from datetime import datetime
from .claims import canonical_claim_key, cluster_claims_sbert


def canonical_domain(url: str) -> str:
    """Extract canonical domain from URL"""
    try:
        netloc = urlparse(url).netloc.lower()
        # Remove port if present
        domain = netloc.split(":")[0]
        # Remove www prefix
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except:
        return "unknown"


def source_quality(cards: List) -> List[Dict]:
    """
    Analyze source quality metrics from evidence cards.
    Returns list of domain-level quality assessments.
    """
    by_domain: Dict[str, Dict] = defaultdict(lambda: {
        "domain": "",
        "total_cards": 0,
        "unique_claims": set(),
        "avg_credibility": 0.0,
        "avg_relevance": 0.0,
        "pct_recent": 0.0,
        "first_seen": None,
        "last_seen": None,
        "corroborated_rate": 0.0,
        "independence_score": 0.0,
        "providers": set()
    })
    
    by_claim: Dict[str, Set[str]] = defaultdict(set)
    
    for card in cards:
        # Get domain from url or source_url
        url = getattr(card, 'url', None) or getattr(card, 'source_url', None)
        if not url:
            continue
            
        domain = canonical_domain(url)
        slot = by_domain[domain]
        slot["domain"] = domain
        slot["total_cards"] += 1
        
        # Track credibility and relevance
        slot["avg_credibility"] += getattr(card, 'credibility_score', 0.5)
        slot["avg_relevance"] += getattr(card, 'relevance_score', 0.5)
        
        # Track unique claims using canonical keys
        claim_text = getattr(card, 'claim', '') or getattr(card, 'snippet', '') or getattr(card, 'title', '')
        key = canonical_claim_key(claim_text)
        if key:
            slot["unique_claims"].add(key)
            by_claim[key].add(domain)
        
        # Track providers
        provider = getattr(card, 'provider', None) or getattr(card, 'search_provider', None)
        if provider:
            slot["providers"].add(provider)
        
        # Track dates
        date_str = getattr(card, 'date', None) or getattr(card, 'publication_date', None)
        if date_str:
            try:
                if isinstance(date_str, str):
                    # Handle ISO format with Z timezone
                    date_str = date_str.replace('Z', '+00:00')
                    card_date = datetime.fromisoformat(date_str)
                else:
                    card_date = date_str
                    
                if not slot["first_seen"] or card_date < slot["first_seen"]:
                    slot["first_seen"] = card_date
                if not slot["last_seen"] or card_date > slot["last_seen"]:
                    slot["last_seen"] = card_date
            except:
                pass
    
    # Calculate final metrics
    rows = []
    for domain, metrics in by_domain.items():
        if metrics["total_cards"] == 0:
            continue
            
        # Calculate corroboration rate
        corroborated = sum(
            1 for claim_text, domains in by_claim.items() 
            if domain in domains and len(domains) >= 2
        )
        
        # Simple independence score (diversity of providers)
        independence = len(metrics["providers"]) / max(1, metrics["total_cards"])
        
        # Average scores
        avg_cred = metrics["avg_credibility"] / max(1, metrics["total_cards"])
        avg_rel = metrics["avg_relevance"] / max(1, metrics["total_cards"])
        
        rows.append({
            "domain": domain,
            "total_cards": metrics["total_cards"],
            "unique_claims": len(metrics["unique_claims"]),
            "avg_credibility": round(avg_cred, 3),
            "avg_relevance": round(avg_rel, 3),
            "corroborated_rate": round(corroborated / max(1, metrics["total_cards"]), 3),
            "first_seen": metrics["first_seen"].isoformat() if metrics["first_seen"] else None,
            "last_seen": metrics["last_seen"].isoformat() if metrics["last_seen"] else None,
            "independence_score": round(independence, 3),
            "providers": list(metrics["providers"])
        })
    
    # Sort by quality indicators
    rows.sort(key=lambda r: (
        -r["avg_credibility"], 
        -r["corroborated_rate"], 
        -r["total_cards"]
    ))
    
    return rows


def triangulate_claims(cards: List) -> Dict[str, Dict]:
    """
    Triangulate claims across sources using semantic clustering.
    Returns mapping of claims to their triangulation status.
    """
    # Extract all claim texts and build index
    claim_texts = []
    card_indices = []  # Maps claim index to card
    
    for i, card in enumerate(cards):
        claim_text = getattr(card, 'claim', '') or getattr(card, 'snippet', '') or getattr(card, 'title', '')
        if claim_text:
            claim_texts.append(claim_text)
            card_indices.append(i)
    
    # First try SBERT semantic clustering for better triangulation
    # Using 0.75 threshold for better recall on paraphrased claims
    clusters = cluster_claims_sbert(claim_texts, min_size=2, cos_threshold=0.75)
    
    # Build claim groups from clusters
    by_claim: Dict[str, Dict] = defaultdict(lambda: {
        "claim": "",
        "sources": set(),
        "providers": set(),
        "dates": [],
        "stances": [],
        "is_triangulated": False,
        "confidence": 0.0,
        "cluster_size": 1
    })
    
    # Process SBERT clusters
    clustered_indices = set()
    for cluster_idx, cluster in enumerate(clusters):
        # Use first claim in cluster as representative
        representative_idx = min(cluster)
        representative_text = claim_texts[representative_idx]
        cluster_key = f"cluster_{cluster_idx}_{canonical_claim_key(representative_text) or cluster_idx}"
        
        slot = by_claim[cluster_key]
        slot["claim"] = representative_text[:200]
        slot["cluster_size"] = len(cluster)
        
        # Aggregate data from all claims in cluster
        for claim_idx in cluster:
            clustered_indices.add(claim_idx)
            card = cards[card_indices[claim_idx]]
            
            # Track source domains
            url = getattr(card, 'url', None) or getattr(card, 'source_url', None)
            if url:
                slot["sources"].add(canonical_domain(url))
            
            # Track providers
            provider = getattr(card, 'provider', None) or getattr(card, 'search_provider', None)
            if provider:
                slot["providers"].add(provider)
            
            # Track dates
            date_str = getattr(card, 'date', None) or getattr(card, 'publication_date', None)
            if date_str:
                slot["dates"].append(date_str)
            
            # Track stances
            stance = getattr(card, 'stance', 'neutral')
            slot["stances"].append(stance)
    
    # Process unclustered claims with canonical keys as fallback
    for i, claim_text in enumerate(claim_texts):
        if i in clustered_indices:
            continue
            
        key = canonical_claim_key(claim_text)
        if not key:
            continue
            
        card = cards[card_indices[i]]
        slot = by_claim[key]
        
        # Only update claim text if empty (first occurrence)
        if not slot["claim"]:
            slot["claim"] = claim_text[:200]
        
        # Track source domains
        url = getattr(card, 'url', None) or getattr(card, 'source_url', None)
        if url:
            slot["sources"].add(canonical_domain(url))
        
        # Track providers
        provider = getattr(card, 'provider', None) or getattr(card, 'search_provider', None)
        if provider:
            slot["providers"].add(provider)
        
        # Track dates
        date_str = getattr(card, 'date', None) or getattr(card, 'publication_date', None)
        if date_str:
            slot["dates"].append(date_str)
        
        # Track stances
        stance = getattr(card, 'stance', 'neutral')
        slot["stances"].append(stance)
    
    # Calculate triangulation status
    results = {}
    for claim_key, data in by_claim.items():
        num_sources = len(data["sources"])
        num_providers = len(data["providers"])
        cluster_size = data.get("cluster_size", 1)
        
        # Triangulated if 2+ independent sources OR semantic cluster found
        is_triangulated = num_sources >= 2 or cluster_size >= 2
        
        # Calculate confidence based on source diversity and cluster size
        confidence = min(1.0, (num_sources * 0.25 + num_providers * 0.15 + cluster_size * 0.1))
        
        results[claim_key] = {
            "claim": data["claim"],
            "num_sources": num_sources,
            "num_providers": num_providers,
            "cluster_size": cluster_size,
            "sources": list(data["sources"]),
            "providers": list(data["providers"]),
            "is_triangulated": is_triangulated,
            "confidence": round(confidence, 3),
            "dates": data["dates"][:5],  # Keep first 5 dates
            "stance_distribution": dict(Counter(data["stances"]))
        }
    
    return results


def triangulation_summary(cards: List) -> Dict[str, any]:
    """
    Generate summary statistics for triangulation analysis.
    """
    claims = triangulate_claims(cards)
    
    total_claims = len(claims)
    triangulated = sum(1 for c in claims.values() if c["is_triangulated"])
    
    # Calculate stance distribution
    all_stances = []
    for claim_data in claims.values():
        all_stances.extend(claim_data.get("stance_distribution", {}).keys())
    
    from collections import Counter
    stance_counts = dict(Counter(all_stances))
    
    return {
        "total_claims": total_claims,
        "triangulated_claims": triangulated,
        "triangulation_rate": round(triangulated / max(1, total_claims), 3),
        "avg_sources_per_claim": round(
            sum(c["num_sources"] for c in claims.values()) / max(1, total_claims), 
            2
        ),
        "avg_providers_per_claim": round(
            sum(c["num_providers"] for c in claims.values()) / max(1, total_claims),
            2
        ),
        "stance_distribution": stance_counts,
        "high_confidence_claims": sum(
            1 for c in claims.values() if c["confidence"] >= 0.7
        )
    }


def detect_syndication(cards: List) -> List[Dict]:
    """
    Detect potential content syndication by identifying identical content hashes.
    """
    by_hash: Dict[str, List] = defaultdict(list)
    
    for card in cards:
        content_hash = getattr(card, 'content_hash', None)
        if not content_hash:
            # Generate hash from snippet if not present
            snippet = getattr(card, 'snippet', '') or getattr(card, 'supporting_text', '')
            if snippet:
                import hashlib
                content_hash = hashlib.sha256(snippet.encode()).hexdigest()[:16]
        
        if content_hash:
            url = getattr(card, 'url', None) or getattr(card, 'source_url', None)
            by_hash[content_hash].append({
                "url": url,
                "domain": canonical_domain(url) if url else "unknown",
                "title": getattr(card, 'title', None) or getattr(card, 'source_title', ''),
                "provider": getattr(card, 'provider', None) or getattr(card, 'search_provider', None)
            })
    
    # Find syndicated content (same hash, different domains)
    syndications = []
    for content_hash, sources in by_hash.items():
        if len(sources) > 1:
            unique_domains = set(s["domain"] for s in sources)
            if len(unique_domains) > 1:
                syndications.append({
                    "content_hash": content_hash,
                    "num_sources": len(sources),
                    "num_domains": len(unique_domains),
                    "sources": sources,
                    "domains": list(unique_domains)
                })
    
    return syndications


def calculate_provider_diversity(cards: List) -> Dict[str, float]:
    """
    Calculate diversity metrics for search providers.
    """
    provider_counts = defaultdict(int)
    domain_by_provider = defaultdict(set)
    
    for card in cards:
        provider = getattr(card, 'provider', None) or getattr(card, 'search_provider', None)
        if provider:
            provider_counts[provider] += 1
            url = getattr(card, 'url', None) or getattr(card, 'source_url', None)
            if url:
                domain_by_provider[provider].add(canonical_domain(url))
    
    total_cards = sum(provider_counts.values())
    
    # Calculate Shannon entropy for provider distribution
    import math
    entropy = 0.0
    for count in provider_counts.values():
        if count > 0:
            p = count / total_cards
            entropy -= p * math.log2(p)
    
    # Normalize entropy (max entropy when all providers equal)
    max_entropy = math.log2(len(provider_counts)) if provider_counts else 0
    normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0
    
    return {
        "provider_counts": dict(provider_counts),
        "total_cards": total_cards,
        "num_providers": len(provider_counts),
        "entropy": round(entropy, 3),
        "normalized_entropy": round(normalized_entropy, 3),
        "domains_per_provider": {
            p: len(domains) for p, domains in domain_by_provider.items()
        },
        "avg_domains_per_provider": round(
            sum(len(d) for d in domain_by_provider.values()) / max(1, len(domain_by_provider)),
            2
        )
    }