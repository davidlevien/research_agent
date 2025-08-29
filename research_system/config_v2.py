"""Quality configuration loader for v8.13.0."""

import json
import yaml
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass(frozen=True)
class QualityConfigV2:
    """Immutable quality configuration for consistent thresholds."""
    primary_share_floor: float
    triangulation_floor: float
    domain_concentration_cap: float
    numeric_quote_min_density: float
    topic_similarity_floor: float
    tiers: Dict[str, float]
    sources: Dict[str, List[str]]
    intents: Dict[str, Dict]

_cfg_singleton: Optional[QualityConfigV2] = None

def load_quality_config(path: str = "config/quality.yml") -> QualityConfigV2:
    """Load quality configuration from YAML file."""
    global _cfg_singleton
    if _cfg_singleton:
        return _cfg_singleton
    
    # Check if file exists
    if not os.path.exists(path):
        # Fall back to default values if config file doesn't exist
        _cfg_singleton = QualityConfigV2(
            primary_share_floor=0.50,
            triangulation_floor=0.45,
            domain_concentration_cap=0.25,
            numeric_quote_min_density=0.03,
            topic_similarity_floor=0.50,
            tiers={
                "TIER1": 1.00,
                "TIER2": 0.75,
                "TIER3": 0.40,
                "TIER4": 0.20
            },
            sources={
                "treat_as_secondary": ["ourworldindata.org"],
                "partisan_exclude_default": [
                    "www.jec.senate.gov/public/index.cfm/democrats",
                    "www.jec.senate.gov/public/index.cfm/republicans",
                    "www.americanprogress.org",
                    "www.heritage.org"
                ],
                "mirrors": ["sgp.fas.org", "www.everycrsreport.com"]
            },
            intents={
                "stats": {
                    "providers_hard_prefer": ["worldbank", "oecd", "imf", "eurostat", "ec", "un"],
                    "require_numeric_evidence": True,
                    "demote_general_to_context": True,
                    "data_fallback": ["treasury", "irs", "census", "cbo", "crs", "bls", "bea", "crossref", "openalex"]
                }
            }
        )
        return _cfg_singleton
    
    with open(path, "r") as f:
        y = yaml.safe_load(f)
    
    m = y["metrics"]
    _cfg_singleton = QualityConfigV2(
        primary_share_floor=m["primary_share_floor"],
        triangulation_floor=m["triangulation_floor"],
        domain_concentration_cap=m["domain_concentration_cap"],
        numeric_quote_min_density=m["numeric_quote_min_density"],
        topic_similarity_floor=m["topic_similarity_floor"],
        tiers=y["tiers"],
        sources=y["sources"],
        intents=y["intents"],
    )
    return _cfg_singleton