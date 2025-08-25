"""
Related Topics via Axes - PE-Grade Topic Expansion
Generates related topics using structured axes from topic packs.
"""

from typing import List, Tuple, Dict, Optional
import logging
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

# Load topic packs with axes definitions
TOPIC_PACKS_PATH = Path(__file__).parent.parent / "resources" / "topic_packs.yaml"

def load_topic_packs() -> Dict:
    """Load topic packs configuration"""
    try:
        with open(TOPIC_PACKS_PATH, 'r') as f:
            data = yaml.safe_load(f)
            return data if data else {}
    except Exception as e:
        logger.warning(f"Failed to load topic packs: {e}")
        return {}

TOPIC_PACKS = load_topic_packs()

def propose_related_topics(
    topic_key: str, 
    user_query: str, 
    k_per_axis: int = 2,
    include_counter: bool = True
) -> List[Tuple[str, str]]:
    """
    Generate related topics based on structured axes.
    
    Args:
        topic_key: The classified topic key (e.g., "technology", "macroeconomics")
        user_query: Original user query
        k_per_axis: Number of topics per axis to generate
        include_counter: Whether to include counter-queries
    
    Returns:
        List of (axis_name, query) tuples
    """
    pack = TOPIC_PACKS.get(topic_key, TOPIC_PACKS.get("general", {}))
    related = []
    
    # Process structured axes
    axes = pack.get("related_axes", {})
    for axis_name, seed_terms in axes.items():
        for term in seed_terms[:k_per_axis]:
            # Create focused query combining original + axis term
            expanded_query = f"{user_query} {term}"
            related.append((axis_name, expanded_query))
    
    # Add counter-queries for balance
    if include_counter:
        antithesis_terms = pack.get("antithesis_terms", [])
        for term in antithesis_terms[:k_per_axis]:
            counter_query = f"{user_query} {term}"
            related.append(("counter", counter_query))
    
    return related

def generate_backfill_queries(
    topic_key: str,
    user_query: str,
    metrics: Dict,
    max_queries: int = 6
) -> List[Tuple[str, str]]:
    """
    Generate targeted backfill queries based on quality metrics gaps.
    
    Args:
        topic_key: Topic classification
        user_query: Original query
        metrics: Current quality metrics
        max_queries: Maximum queries to generate
    
    Returns:
        List of (purpose, query) tuples for backfilling
    """
    queries = []
    pack = TOPIC_PACKS.get(topic_key, TOPIC_PACKS.get("general", {}))
    
    # Check triangulation gap
    if metrics.get("union_triangulation", 0) < 0.35:
        # Need more diverse perspectives
        axes = pack.get("related_axes", {})
        
        # Prioritize upstream/downstream for triangulation
        for axis in ["upstream", "downstream", "risks"]:
            if axis in axes and len(queries) < max_queries:
                terms = axes[axis]
                for term in terms[:2]:
                    queries.append((f"triangulation_{axis}", f"{user_query} {term}"))
                    if len(queries) >= max_queries:
                        break
    
    # Check primary source gap
    if metrics.get("primary_share", 0) < 0.30:
        # Need more authoritative sources
        if "macroeconomics" in topic_key:
            queries.append(("primary_imf", f"{user_query} site:imf.org"))
            queries.append(("primary_worldbank", f"{user_query} site:worldbank.org"))
            queries.append(("primary_oecd", f"{user_query} site:oecd.org"))
        elif "health" in topic_key:
            queries.append(("primary_who", f"{user_query} site:who.int"))
            queries.append(("primary_pubmed", f"{user_query} pubmed"))
        elif "climate" in topic_key:
            queries.append(("primary_ipcc", f"{user_query} IPCC report"))
            queries.append(("primary_noaa", f"{user_query} site:noaa.gov"))
    
    # Check quote coverage gap
    if metrics.get("avg_quote_coverage", 0) < 0.50:
        # Need more quotable content (PDFs, reports)
        queries.append(("quotes_pdf", f"{user_query} filetype:pdf"))
        queries.append(("quotes_report", f"{user_query} research report"))
    
    # Check domain diversity
    top_domain_share = metrics.get("top_domain_share", 0)
    if top_domain_share > 0.25:
        # Too concentrated, need diversity
        antithesis = pack.get("antithesis_terms", ["alternative", "different", "contrary"])
        for term in antithesis[:2]:
            queries.append(("diversity", f"{user_query} {term}"))
            if len(queries) >= max_queries:
                break
    
    return queries[:max_queries]

def classify_query_axis(query: str, topic_key: str) -> str:
    """
    Classify which axis a query belongs to.
    
    Args:
        query: The search query
        topic_key: Topic classification
    
    Returns:
        Axis name or "general"
    """
    query_lower = query.lower()
    pack = TOPIC_PACKS.get(topic_key, TOPIC_PACKS.get("general", {}))
    axes = pack.get("related_axes", {})
    
    # Check each axis for term matches
    for axis_name, terms in axes.items():
        for term in terms:
            if term.lower() in query_lower:
                return axis_name
    
    # Check for counter/antithesis
    antithesis = pack.get("antithesis_terms", [])
    for term in antithesis:
        if term.lower() in query_lower:
            return "counter"
    
    return "general"

def enrich_with_axes(
    cards: List[Dict],
    topic_key: str,
    user_query: str
) -> List[Dict]:
    """
    Enrich evidence cards with axis classification.
    
    Args:
        cards: Evidence cards to enrich
        topic_key: Topic classification
        user_query: Original query
    
    Returns:
        Cards with added axis metadata
    """
    for card in cards:
        # Classify based on content
        content = f"{card.get('title', '')} {card.get('snippet', '')}"
        card['axis'] = classify_query_axis(content, topic_key)
        
        # Add axis weight for balancing
        if card['axis'] == 'counter':
            card['axis_weight'] = 1.2  # Boost counter perspectives
        elif card['axis'] in ['upstream', 'downstream']:
            card['axis_weight'] = 1.1  # Slight boost for causal chains
        else:
            card['axis_weight'] = 1.0
    
    return cards

def balance_by_axes(
    cards: List[Dict],
    max_per_axis: int = 8,
    min_axes: int = 3
) -> List[Dict]:
    """
    Balance evidence cards across different axes.
    
    Args:
        cards: All evidence cards with axis metadata
        max_per_axis: Maximum cards per axis
        min_axes: Minimum number of axes to include
    
    Returns:
        Balanced subset of cards
    """
    # Group by axis
    by_axis = {}
    for card in cards:
        axis = card.get('axis', 'general')
        if axis not in by_axis:
            by_axis[axis] = []
        by_axis[axis].append(card)
    
    # Sort axes by importance
    axis_priority = ['counter', 'upstream', 'downstream', 'risks', 'general']
    
    balanced = []
    axes_included = set()
    
    # First pass: ensure minimum axis diversity
    for axis in axis_priority:
        if axis in by_axis and len(by_axis[axis]) > 0:
            # Take at least one from each axis
            balanced.append(by_axis[axis][0])
            axes_included.add(axis)
            if len(axes_included) >= min_axes:
                break
    
    # Second pass: fill up to max_per_axis
    for axis in axis_priority:
        if axis in by_axis:
            # Sort by relevance within axis
            axis_cards = sorted(
                by_axis[axis],
                key=lambda c: c.get('confidence', 0) * c.get('axis_weight', 1),
                reverse=True
            )
            
            # Add up to max_per_axis
            for card in axis_cards[:max_per_axis]:
                if card not in balanced:
                    balanced.append(card)
    
    return balanced

def get_axis_distribution(cards: List[Dict]) -> Dict[str, int]:
    """
    Get distribution of cards across axes.
    
    Args:
        cards: Evidence cards with axis metadata
    
    Returns:
        Dictionary of axis -> count
    """
    distribution = {}
    for card in cards:
        axis = card.get('axis', 'general')
        distribution[axis] = distribution.get(axis, 0) + 1
    
    return distribution

def suggest_missing_axes(
    current_distribution: Dict[str, int],
    topic_key: str
) -> List[str]:
    """
    Suggest which axes are missing or underrepresented.
    
    Args:
        current_distribution: Current axis distribution
        topic_key: Topic classification
    
    Returns:
        List of missing/weak axis names
    """
    pack = TOPIC_PACKS.get(topic_key, TOPIC_PACKS.get("general", {}))
    all_axes = list(pack.get("related_axes", {}).keys())
    
    if pack.get("antithesis_terms"):
        all_axes.append("counter")
    
    missing = []
    for axis in all_axes:
        if current_distribution.get(axis, 0) < 2:
            missing.append(axis)
    
    return missing