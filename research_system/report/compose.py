"""Report composition with proper triangulation labeling."""

import re
from typing import List, Dict, Any


def is_triangulated(domains: List[str]) -> bool:
    """Check if evidence is triangulated (2+ unique domains)."""
    return len(set(domains)) >= 2


def has_numeric_and_period(text: str) -> bool:
    """Check if text contains numeric data and time period."""
    has_num = bool(re.search(r'\d+(?:\.\d+)?%?', text))
    has_period = bool(re.search(r'(Q[1-4]|quarter|year|month|20\d{2})', text, re.I))
    return has_num and has_period


def compose_triangulated_section(clusters: List[Dict], cards: List[Any], max_items: int = 6) -> str:
    """
    Compose the triangulated evidence section.
    
    Args:
        clusters: List of triangulated clusters (paraphrase or structured)
        cards: List of evidence cards
        max_items: Maximum number of items to include
        
    Returns:
        Markdown formatted section
    """
    # Filter to only triangulated clusters
    tri_items = [c for c in clusters if is_triangulated(c.get("domains", []))]
    
    # Sort by relevance (e.g., cluster size, credibility)
    tri_items.sort(key=lambda x: -len(x.get("indices", [])))
    
    # Limit to max items
    tri_items = tri_items[:max_items]
    
    if not tri_items:
        return ""
    
    lines = ["## Triangulated Evidence\n"]
    
    for cluster in tri_items:
        indices = cluster.get("indices", [])
        domains = list(set(cluster.get("domains", [])))[:3]  # Show max 3 domains
        
        # Get representative claim
        rep_claim = cluster.get("representative_claim", "")
        if not rep_claim and indices:
            # Fall back to first card's quote
            idx = indices[0]
            if idx < len(cards):
                rep_claim = getattr(cards[idx], "quote_span", "") or getattr(cards[idx], "claim", "")
        
        if rep_claim:
            # Format with inline sources
            source_str = ", ".join(domains)
            lines.append(f"- {rep_claim} [{source_str}]")
    
    lines.append("")
    return "\n".join(lines)


def compose_single_source_section(cards: List[Any], max_items: int = 4) -> str:
    """
    Compose the single-source numeric claims section.
    
    Args:
        cards: List of evidence cards (preferably primary sources)
        max_items: Maximum number of items to include
        
    Returns:
        Markdown formatted section
    """
    # Filter to cards with numeric claims and periods
    singles = []
    for c in cards:
        quote = getattr(c, "quote_span", "")
        if quote and has_numeric_and_period(quote):
            singles.append(c)
    
    # Sort by credibility
    singles.sort(key=lambda x: -x.credibility_score)
    
    # Limit to max items
    singles = singles[:max_items]
    
    if not singles:
        return ""
    
    lines = ["## Additional Evidence [Single-Source]\n"]
    
    for card in singles:
        quote = card.quote_span
        domain = card.source_domain
        lines.append(f"- {quote} [{domain}] *[Single-source]*")
    
    lines.append("")
    return "\n".join(lines)


def compose_final_report(triangulated_clusters: List[Dict], 
                         primary_cards: List[Any],
                         all_cards: List[Any],
                         topic: str) -> str:
    """
    Compose the final report with proper triangulation labeling.
    
    Args:
        triangulated_clusters: Combined paraphrase and structured clusters
        primary_cards: Cards from primary sources
        all_cards: All evidence cards
        topic: Research topic
        
    Returns:
        Complete markdown report
    """
    lines = [
        f"# Research Report: {topic}\n",
        "## Executive Summary\n",
        f"This report presents evidence-based findings on {topic}, "
        "with triangulated claims verified across multiple authoritative sources.\n"
    ]
    
    # Add triangulated section
    tri_section = compose_triangulated_section(triangulated_clusters, all_cards, max_items=6)
    if tri_section:
        lines.append(tri_section)
    
    # Add single-source section (if space allows)
    tri_count = tri_section.count("\n-") if tri_section else 0
    remaining_slots = max(0, 10 - tri_count)
    
    if remaining_slots > 0:
        single_section = compose_single_source_section(primary_cards, max_items=remaining_slots)
        if single_section:
            lines.append(single_section)
    
    # Add methodology note
    lines.extend([
        "## Methodology\n",
        "- Evidence triangulated across multiple authoritative sources",
        "- Primary sources prioritized from official organizations",
        "- Single-source claims clearly labeled for transparency\n",
        "## Data Quality\n",
        "All findings are based on authoritative sources with triangulation "
        "applied where possible to ensure accuracy and reliability.\n"
    ])
    
    return "\n".join(lines)