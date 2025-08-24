"""
Metric normalization lexicon for stable keys across domains
"""

from __future__ import annotations
from typing import Optional

METRICS = {
    # Tourism/travel metrics
    "international_tourist_arrivals": {
        "arrivals", "tourist arrivals", "international arrivals", 
        "visitor arrivals", "visitor inflows", "international tourists",
        "international visitor arrivals", "tourist inflows"
    },
    "hotel_occupancy_rate": {
        "hotel occupancy", "occupancy rate", "occupancy", "room occupancy",
        "hotel room occupancy", "accommodation occupancy"
    },
    "gdp_contribution_travel": {
        "tourism gdp", "travel gdp", "gdp contribution of tourism",
        "tourism contribution to gdp", "travel & tourism gdp",
        "t&t gdp", "tourism's gdp contribution"
    },
    "air_passenger_traffic": {
        "air passengers", "passenger traffic", "rpk", "pax",
        "revenue passenger kilometers", "passenger numbers",
        "airline passengers", "air travel demand"
    },
    "tourism_receipts": {
        "tourism receipts", "visitor spending", "tourist spending",
        "international receipts", "tourism revenues", "visitor receipts",
        "tourism earnings", "travel receipts"
    },
    "tourism_employment": {
        "tourism jobs", "travel jobs", "tourism employment",
        "travel & tourism employment", "t&t jobs", "sector employment"
    },
    
    # Economic metrics (generic)
    "gdp_growth": {
        "gdp growth", "economic growth", "gdp increase", "gdp expansion"
    },
    "inflation_rate": {
        "inflation", "cpi", "consumer price index", "price inflation"
    },
    "unemployment_rate": {
        "unemployment", "jobless rate", "unemployment level"
    },
    
    # Tech/software metrics
    "monthly_active_users": {
        "mau", "monthly active users", "monthly users", "active users"
    },
    "conversion_rate": {
        "conversion", "conversion rate", "cvr", "conversion percentage"
    },
    
    # Climate/environment metrics
    "co2_emissions": {
        "co2", "carbon emissions", "greenhouse gas emissions", "ghg emissions"
    },
    "temperature_rise": {
        "temperature increase", "warming", "temperature rise", "global warming"
    }
}

# Compile reverse map once
REVERSE = {}
for canon, aliases in METRICS.items():
    for alias in aliases:
        REVERSE[alias.lower()] = canon

def canon_metric_name(s: str) -> Optional[str]:
    """
    Normalize a metric name to its canonical form.
    Returns None if no match found.
    """
    if not s:
        return None
    
    k = s.lower().strip()
    
    # Exact alias match
    if k in REVERSE:
        return REVERSE[k]
    
    # Fallback: greedy containment (longest match wins)
    best = None
    best_len = 0
    for alias, canon in REVERSE.items():
        if alias in k and len(alias) > best_len:
            best = canon
            best_len = len(alias)
    
    return best