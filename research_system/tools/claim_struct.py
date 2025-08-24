"""
Structured claim extraction with metric, period, and value normalization
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional, List, Tuple
from .metrics_lexicon import canon_metric_name
from .period_norm import normalize_period
from .num_norm import parse_number_with_unit, numbers_compatible, format_number_with_unit
from .entity_norm import normalize_entity

@dataclass
class StructuredClaim:
    """A structured claim with entity, metric, period, value, and unit"""
    entity: Optional[str] = None
    metric: Optional[str] = None
    period: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None
    raw_text: str = ""


def extract_struct_claim(text: str) -> StructuredClaim:
    """
    Extract structured claim from text.
    Returns StructuredClaim with normalized components.
    """
    if not text:
        return StructuredClaim(raw_text=text)
    
    # Extract and normalize entity
    entity = _extract_entity(text)
    
    # Extract and normalize metric
    metric = _extract_metric(text)
    metric = canon_metric_name(metric) or metric
    
    # Extract and normalize period
    period = normalize_period(text)
    
    # Extract value and unit
    value, unit = parse_number_with_unit(text)
    
    return StructuredClaim(
        entity=entity,
        metric=metric,
        period=period,
        value=value,
        unit=unit,
        raw_text=text
    )


def _extract_entity(text: str) -> Optional[str]:
    """Extract entity (country, region, sector) from text"""
    t = text.lower()
    
    # Common tourism entities - now simpler since normalize_entity handles aliases
    entities = [
        "global", "worldwide", "international",
        "europe", "european", "eu",
        "asia", "asia pacific", "asia-pacific", "apac",
        "americas", "america", "north america", "south america",
        "middle east", "mena",
        "africa", "african",
        "united states", "u.s.", "us", "usa",
        "china", "chinese",
        "germany", "german",
        "uk", "united kingdom", "britain",
        "saudi", "saudi arabia", "ksa",
        "france", "french",
        "italy", "italian",
        "spain", "spanish",
        "japan", "japanese",
        "canada", "canadian",
        "australia", "australian",
        "india", "indian",
        "brazil", "brazilian",
        "mexico", "mexican",
        "unwto", "un tourism",
        "iata", "wttc"
    ]
    
    # Find the first matching entity in the text
    for entity in entities:
        if entity.lower() in t:
            # Return the normalized version
            return normalize_entity(entity)
    
    return None


def _extract_metric(text: str) -> Optional[str]:
    """Extract metric type from text"""
    t = text.lower()
    
    # Look for common metric patterns
    patterns = [
        r"(tourist arrivals?|visitor arrivals?|arrivals?)",
        r"(tourism gdp|gdp contribution|contribution to gdp)",
        r"(occupancy rate?|hotel occupancy)",
        r"(visitor spending|tourist spending|tourism receipts?)",
        r"(tourism jobs?|employment|jobs? supported)",
        r"(air passengers?|passenger traffic|rpk)",
        r"(growth rate?|increased?|grew|rose|declined?|fell)",
    ]
    
    for pattern in patterns:
        m = re.search(pattern, t)
        if m:
            return m.group(1)
    
    return None


def struct_key(sc: StructuredClaim) -> Optional[str]:
    """
    Generate a normalized key for a structured claim.
    Format: entity|metric|period
    """
    if not sc.metric:
        return None
    
    parts = []
    if sc.entity:
        parts.append(sc.entity)
    if sc.metric:
        parts.append(sc.metric)
    if sc.period:
        parts.append(sc.period)
    
    return "|".join(parts) if len(parts) >= 2 else None


def numbers_close(v1: float, v2: float, tol: float = 0.10) -> bool:
    """Check if two numbers are within tolerance"""
    if v1 == v2:
        return True
    if v1 == 0 or v2 == 0:
        return False
    return abs(v1 - v2) / max(abs(v1), abs(v2)) <= tol


def struct_claims_match(sc1: StructuredClaim, sc2: StructuredClaim) -> bool:
    """
    Check if two structured claims match.
    They match if they have the same key and compatible values.
    """
    k1 = struct_key(sc1)
    k2 = struct_key(sc2)
    
    if not k1 or not k2 or k1 != k2:
        return False
    
    # If both have values, check compatibility
    if sc1.value is not None and sc2.value is not None:
        return numbers_compatible(
            (sc1.value, sc1.unit),
            (sc2.value, sc2.unit)
        )
    
    return True