"""
Query templates for targeting primary sources
"""

from __future__ import annotations
from typing import List

PRIMARY_ANCHORS = {
    "travel technology and tourism trends 2025": [
        "site:unwto.org 2025 tourism barometer",
        "site:wttc.org 2025 economic impact report",
        "site:iata.org 2025 air passenger market analysis pdf",
        "site:ustravel.org 2025 monthly travel indicators",
        "site:oecd.org 2025 tourism statistics pdf",
        "site:str.com 2025 hotel performance report",
        "site:skift.com 2025 travel health index"
    ],
    "artificial intelligence": [
        "site:arxiv.org artificial intelligence 2025",
        "site:openai.com research papers 2025",
        "site:deepmind.com publications 2025",
        "site:ai.google research 2025",
        "site:research.fb.com AI papers 2025"
    ],
    "sustainable technology": [
        "site:iea.org renewable energy report 2025",
        "site:irena.org sustainability statistics 2025",
        "site:unep.org green technology 2025",
        "site:wri.org climate tech 2025",
        "site:ipcc.ch assessment report technology"
    ]
}

def anchor_queries(topic: str) -> List[str]:
    """
    Generate anchor queries to target primary sources based on topic.
    Returns list of site-specific queries for authoritative sources.
    """
    t = topic.lower().strip()
    
    # Check for exact matches first
    for key, queries in PRIMARY_ANCHORS.items():
        if all(word in t for word in key.split()):
            return queries
    
    # Generic fallback for trends topics
    if "2025" in t and "trend" in t:
        base_queries = []
        
        # Travel/tourism specific
        if any(word in t for word in ["travel", "tourism", "hospitality", "airline", "hotel"]):
            base_queries.extend([
                "site:unwto.org 2025 tourism barometer",
                "site:wttc.org 2025 economic impact",
                "site:iata.org 2025 air passenger market",
                "site:ustravel.org 2025 indicators",
                "site:ec.europa.eu tourism statistics 2025",
                "site:statista.com tourism industry 2025"
            ])
        
        # Technology specific
        if any(word in t for word in ["technology", "tech", "digital", "ai", "artificial"]):
            base_queries.extend([
                "site:gartner.com technology trends 2025",
                "site:forrester.com tech predictions 2025",
                "site:mckinsey.com digital trends 2025",
                "site:bcg.com technology outlook 2025"
            ])
        
        # Business/economic specific
        if any(word in t for word in ["business", "economic", "market", "industry"]):
            base_queries.extend([
                "site:oecd.org economic outlook 2025",
                "site:imf.org global prospects 2025",
                "site:worldbank.org development report 2025",
                "site:weforum.org global risks 2025"
            ])
        
        return base_queries[:8]  # Limit to 8 queries
    
    # No specific anchors found
    return []