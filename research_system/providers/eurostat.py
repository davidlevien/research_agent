"""Eurostat provider (via EU Open Data portal with Eurostat filtering)."""

from __future__ import annotations
from typing import List, Dict, Any
from .ec import ec_search
import logging

logger = logging.getLogger(__name__)

def eurostat_search(query: str, limit: int = 25) -> List[Dict[str, Any]]:
    """
    Search for Eurostat datasets via EU Open Data portal.
    Filters results to prioritize Eurostat publisher.
    """
    try:
        # First try to get results from EU Open Data portal
        rows = ec_search(query, limit=limit * 2)  # Get extra to filter
        
        # Filter for Eurostat publisher
        eurostat_rows = []
        other_rows = []
        
        for r in rows:
            pub = ((r.get("metadata") or {}).get("publisher") or "").lower()
            if "eurostat" in pub:
                eurostat_rows.append(r)
            else:
                other_rows.append(r)
        
        # Prioritize Eurostat results, fill with others if needed
        result = eurostat_rows[:limit]
        if len(result) < limit:
            result.extend(other_rows[:limit - len(result)])
        
        # Update titles to indicate Eurostat where applicable
        for r in result:
            if r in eurostat_rows and not r["title"].startswith("Eurostat:"):
                r["title"] = f"Eurostat: {r['title']}"
        
        return result
    except Exception as e:
        logger.warning(f"Eurostat search failed: {e}")
        return []

def to_cards(rows: List[Dict[str, Any]]) -> List[dict]:
    """Convert Eurostat results to evidence cards (already in EC format)."""
    # Update metadata to indicate Eurostat provider
    cards = []
    for r in rows:
        card = dict(r)  # Copy
        if "metadata" in card:
            card["metadata"]["provider"] = "eurostat"
            card["metadata"]["license"] = "Eurostat Copyright"
        cards.append(card)
    return cards