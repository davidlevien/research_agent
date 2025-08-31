"""Quality metrics computation on structured claims.

v8.21.0: Computes metrics from accepted claims with tiered domain weighting
to prevent over-concentration from secondary sources.
"""

from collections import Counter
from typing import List, Dict
from research_system.extraction.claims import Claim

# Primary/authoritative domain whitelist
PRIMARY_WHITELIST = {
    # International organizations
    "unwto.org", "wttc.org", "oecd.org", "worldbank.org", "imf.org",
    # Government statistics
    "ec.europa.eu", "eurostat.ec.europa.eu", "bls.gov", "stlouisfed.org", 
    "census.gov", "commerce.gov", "bea.gov",
    # Aviation authorities
    "iata.org", "icao.int", "tsa.gov", "faa.gov",
    # Tourism boards
    "visitbritain.org", "spain.info", "japan.travel", "tourism.australia.com",
    # Research institutions  
    "str.com", "phocuswright.com", "skift.com"
}

def compute_from_claims(claims: List[Claim]) -> Dict[str, float]:
    """
    Compute quality metrics from structured claims.
    
    Args:
        claims: List of extracted and validated claims
        
    Returns:
        Dictionary of quality metrics
    """
    if not claims:
        return {
            "primary": 0.0,
            "triangulation": 0.0,
            "domains": 0,
            "concentration": 0.0,
            "claim_count": 0
        }
    
    # Extract domains from claims
    domains = [c.source_domain for c in claims if c.source_domain]
    domain_counter = Counter(domains)
    
    # Count unique domains
    unique_domains = len(domain_counter)
    
    # Calculate weighted concentration (tiered caps)
    weighted_total = 0.0
    max_weighted_count = 0.0
    
    for domain, count in domain_counter.items():
        # Apply weight based on domain tier
        if domain in PRIMARY_WHITELIST:
            weight = 1.0  # Full weight for primary sources
        else:
            weight = 0.5  # Half weight for secondary sources
        
        weighted_count = count * weight
        weighted_total += weighted_count
        max_weighted_count = max(max_weighted_count, weighted_count)
    
    # Calculate concentration metric
    if weighted_total > 0:
        concentration = max_weighted_count / weighted_total
    else:
        concentration = 0.0
    
    # Calculate primary source share
    primary_claims = [c for c in claims if c.is_primary]
    primary_share = len(primary_claims) / max(1, len(claims))
    
    # Triangulation is computed separately in triangulation.numeric
    # This is a placeholder that will be updated by the orchestrator
    triangulation = 0.0
    
    return {
        "primary": primary_share,
        "triangulation": triangulation,
        "domains": unique_domains,
        "concentration": concentration,
        "claim_count": len(claims),
        "weighted_total": weighted_total
    }

def is_primary_domain(domain: str) -> bool:
    """
    Check if a domain is considered primary/authoritative.
    
    Args:
        domain: Domain to check
        
    Returns:
        True if domain is in primary whitelist
    """
    if not domain:
        return False
    
    # Normalize domain
    domain = domain.lower().strip()
    
    # Direct match
    if domain in PRIMARY_WHITELIST:
        return True
    
    # Check for subdomains of primary domains
    for primary in PRIMARY_WHITELIST:
        if domain.endswith("." + primary):
            return True
    
    return False

def enhance_claims_with_authority(claims: List[Claim]) -> List[Claim]:
    """
    Enhance claims by marking those from primary sources.
    
    Args:
        claims: List of claims to enhance
        
    Returns:
        Enhanced claims with is_primary flag set
    """
    for claim in claims:
        if claim.source_domain:
            claim.is_primary = is_primary_domain(claim.source_domain)
    
    return claims