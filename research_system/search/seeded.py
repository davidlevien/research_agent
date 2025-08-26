"""Pack-aware seeded discovery for primary-first search."""

from typing import List, Set, Optional
import yaml
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def load_seed_domains() -> dict:
    """Load seed domain configuration."""
    config_path = Path(__file__).resolve().parents[1] / "resources" / "pack_seed_domains.yaml"
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"Failed to load seed domains: {e}")
        return {}


def seeded_queries(topic: str, packs: Set[str], k_per_pack: int = 3) -> List[str]:
    """
    Build site-scoped queries for the first discovery wave.
    
    Args:
        topic: The research topic/query
        packs: Set of classified topic packs
        k_per_pack: Number of domains to use per pack (default 3)
    
    Returns:
        List of seeded queries targeting primary sources
    """
    config = load_seed_domains()
    seed_domains = config.get("seed_domains", {})
    
    queries = []
    
    # For each pack, create targeted queries
    for pack in packs or ["general"]:
        domains = seed_domains.get(pack, [])[:k_per_pack]
        
        for domain in domains:
            # Two query flavors: broad and document-heavy
            queries.append(f'{topic} site:{domain}')
            queries.append(f'{topic} site:{domain} (pdf OR filetype:pdf)')
    
    # Always include some macro/international primaries if not already present
    if "macro" not in (packs or []):
        for domain in seed_domains.get("macro", [])[:1]:
            queries.append(f'{topic} site:{domain}')
    
    # Dedup while preserving order
    seen = set()
    unique_queries = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique_queries.append(q)
    
    # Cap total queries to keep the wave small
    return unique_queries[:12]


def generate_expanded_seeds(topic: str, packs: Set[str], 
                           include_patterns: bool = True) -> List[str]:
    """
    Generate expanded seeded queries including pattern-based searches.
    
    Args:
        topic: Research topic
        packs: Set of topic packs
        include_patterns: Whether to include pattern-based queries
        
    Returns:
        List of expanded seed queries
    """
    queries = seeded_queries(topic, packs)
    
    if include_patterns:
        # Add some pattern-based queries for broader coverage
        pattern_queries = [
            f'{topic} site:.gov "final rule" OR "proposed rule"',
            f'{topic} site:.int "report" OR "publication"',
            f'{topic} site:.edu "research" OR "study"',
        ]
        
        # Add pack-specific patterns
        if "policy" in packs:
            pattern_queries.append(f'{topic} "federal register" "docket"')
            pattern_queries.append(f'{topic} "regulatory impact analysis"')
        
        if "health" in packs:
            pattern_queries.append(f'{topic} "clinical guidance" site:.gov')
            pattern_queries.append(f'{topic} "advisory committee" site:.gov')
        
        if "finance" in packs:
            pattern_queries.append(f'{topic} "SEC filing" OR "10-K" OR "10-Q"')
            pattern_queries.append(f'{topic} "monetary policy" site:.gov')
        
        queries.extend(pattern_queries)
    
    # Final dedup and limit
    seen = set()
    unique = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique.append(q)
    
    return unique[:20]  # Slightly larger limit for expanded seeds


def prioritize_seeds_by_pack(queries: List[str], primary_pack: str) -> List[str]:
    """
    Reorder seed queries to prioritize the primary pack's domains.
    
    Args:
        queries: List of seed queries
        primary_pack: Primary topic pack
        
    Returns:
        Reordered query list
    """
    config = load_seed_domains()
    seed_domains = config.get("seed_domains", {})
    primary_domains = seed_domains.get(primary_pack, [])
    
    # Separate queries by whether they target primary pack domains
    primary_queries = []
    other_queries = []
    
    for q in queries:
        is_primary = any(f"site:{domain}" in q for domain in primary_domains)
        if is_primary:
            primary_queries.append(q)
        else:
            other_queries.append(q)
    
    # Primary pack queries first, then others
    return primary_queries + other_queries