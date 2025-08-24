"""Refined AREX query builder with discipline-aware negative terms and primary site hints."""

from __future__ import annotations
from typing import List, Set, Dict

# Negative terms by discipline to reduce tangential results
NEG_BY_DISC: Dict[str, Set[str]] = {
    "travel_tourism": {
        "jobs", "visa", "campground", "lottery", "coupon", 
        "hotel review", "itinerary", "travel guide", "booking",
        "vacation package", "travel insurance", "flight deals"
    },
    "medicine": {
        "alternative medicine", "homeopathy", "wellness", "spa",
        "diet pills", "supplements", "testimonial"
    },
    "finance_econ": {
        "crypto", "bitcoin", "nft", "get rich quick", "trading signals",
        "penny stocks", "forex"
    },
    "science": {
        "pseudoscience", "conspiracy", "flat earth", "perpetual motion"
    },
    "security": {
        "hacking tutorial", "exploit kit", "crack", "keygen", "warez"
    }
}

# Primary site hints for travel/tourism discipline
PRIMARY_HINTS_TOUR = [
    "site:unwto.org",
    "site:e-unwto.org", 
    "site:iata.org",
    "site:wttc.org",
    "filetype:pdf"
]

# Primary hints for other disciplines
PRIMARY_HINTS_BY_DISC: Dict[str, List[str]] = {
    "medicine": [
        "site:pubmed.ncbi.nlm.nih.gov",
        "site:who.int",
        "site:cdc.gov",
        "site:nih.gov",
        "filetype:pdf"
    ],
    "science": [
        "site:arxiv.org",
        "site:doi.org",
        "site:nature.com",
        "site:science.org",
        "filetype:pdf"
    ],
    "finance_econ": [
        "site:sec.gov",
        "site:fred.stlouisfed.org",
        "site:oecd.org",
        "site:imf.org",
        "filetype:pdf"
    ],
    "law_policy": [
        "site:eur-lex.europa.eu",
        "site:law.cornell.edu",
        "site:supremecourt.gov",
        "filetype:pdf"
    ],
    "security": [
        "site:nvd.nist.gov",
        "site:mitre.org",
        "site:cve.mitre.org",
        "site:cisa.gov",
        "filetype:pdf"
    ],
    "climate_env": [
        "site:ipcc.ch",
        "site:noaa.gov",
        "site:nasa.gov",
        "site:epa.gov",
        "filetype:pdf"
    ],
    "tech_software": [
        "site:github.com",
        "site:ietf.org",
        "site:stackoverflow.com",
        "site:arxiv.org",
        "filetype:pdf"
    ]
}


def build_queries(
    entity: str,
    metric: str,
    period: str,
    discipline: str
) -> List[str]:
    """
    Build refined AREX queries with primary site hints and negative terms.
    
    Args:
        entity: Entity name (e.g., "germany", "global")
        metric: Metric name (e.g., "tourist arrivals")
        period: Time period (e.g., "Q1 2025")
        discipline: Discipline name for context-aware query building
        
    Returns:
        List of search queries (max 6)
    """
    # Get negative terms for this discipline
    neg_terms = NEG_BY_DISC.get(discipline, set())
    neg_str = " ".join(f'-"{t}"' for t in sorted(neg_terms))
    
    # Get primary hints for this discipline
    if discipline == "travel_tourism":
        primary_hints = PRIMARY_HINTS_TOUR
    else:
        primary_hints = PRIMARY_HINTS_BY_DISC.get(discipline, ["filetype:pdf"])
    
    # Build queries with exact phrases for metric and period
    queries = []
    
    # First, try primary sources with all terms
    for hint in primary_hints[:3]:  # Top 3 primary hints
        q = f'{entity} "{metric}" "{period}" {hint} {neg_str}'.strip()
        queries.append(q)
    
    # Then broader query without site restrictions
    queries.append(f'{entity} "{metric}" "{period}" {neg_str}'.strip())
    
    # If we still have room, try variations
    if len(queries) < 6:
        # Try without entity (for global metrics)
        queries.append(f'"{metric}" "{period}" {primary_hints[0]} {neg_str}'.strip())
    
    if len(queries) < 6:
        # Try with just metric and period
        queries.append(f'"{metric}" "{period}" {neg_str}'.strip())
    
    # De-duplicate while preserving order
    seen = set()
    out = []
    for q in queries:
        if q not in seen:
            out.append(q)
            seen.add(q)
    
    return out[:6]  # Max 6 queries