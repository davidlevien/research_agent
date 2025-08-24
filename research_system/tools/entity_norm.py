"""Entity normalization for improved triangulation across different name variations."""

from __future__ import annotations
from typing import Optional, Dict, Set

# Canonical entity names and their aliases
ALIASES: Dict[str, Set[str]] = {
    # Countries
    "united states": {
        "usa", "u.s.", "u.s", "us", "united states of america", "america", "the united states"
    },
    "united kingdom": {
        "u.k.", "uk", "great britain", "britain", "england", "the uk"
    },
    "south korea": {
        "republic of korea", "r.o.k", "rok", "korea, republic of", "s. korea"
    },
    "north korea": {
        "democratic people's republic of korea", "dprk", "n. korea"
    },
    "uae": {
        "united arab emirates", "the uae", "emirates"
    },
    "china": {
        "people's republic of china", "prc", "mainland china"
    },
    "germany": {
        "federal republic of germany", "deutschland"
    },
    "france": {
        "french republic", "republique francaise"
    },
    "saudi arabia": {
        "kingdom of saudi arabia", "ksa", "saudi"
    },
    "european union": {
        "eu", "e.u.", "europe", "european"
    },
    
    # International Organizations
    "unwto": {
        "un tourism", "u.n. tourism", "un-tourism", "world tourism organization",
        "united nations world tourism organization", "un world tourism organization"
    },
    "iata": {
        "international air transport association"
    },
    "wttc": {
        "world travel & tourism council", "world travel and tourism council",
        "world travel tourism council"
    },
    "who": {
        "world health organization", "w.h.o."
    },
    "un": {
        "united nations", "u.n.", "the un"
    },
    "imf": {
        "international monetary fund"
    },
    "world bank": {
        "the world bank", "world bank group", "ibrd"
    },
    "oecd": {
        "organisation for economic co-operation and development",
        "organization for economic cooperation and development"
    },
    "wef": {
        "world economic forum", "davos"
    },
    "icao": {
        "international civil aviation organization"
    },
    
    # Regions
    "asia pacific": {
        "asia-pacific", "apac", "asia and the pacific", "asia & pacific"
    },
    "middle east": {
        "mena", "middle east and north africa", "near east"
    },
    "latin america": {
        "latam", "central and south america", "south america", "central america"
    },
    "north america": {
        "n. america", "northern america"
    },
    "sub-saharan africa": {
        "ssa", "subsaharan africa", "africa south of the sahara"
    }
}

# Build reverse mapping for fast lookup
REVERSE_MAP: Dict[str, str] = {}
for canonical, aliases in ALIASES.items():
    # Map canonical to itself
    REVERSE_MAP[canonical.lower()] = canonical
    # Map each alias to canonical
    for alias in aliases:
        REVERSE_MAP[alias.lower()] = canonical


def normalize_entity(name: Optional[str]) -> Optional[str]:
    """
    Normalize an entity name to its canonical form.
    
    Args:
        name: Entity name to normalize
        
    Returns:
        Canonical entity name if found in aliases, otherwise returns
        the original name with basic normalization
    """
    if not name:
        return None
    
    # Clean and lowercase for lookup
    key = name.strip().lower()
    
    # Check if we have a canonical form
    canonical = REVERSE_MAP.get(key)
    if canonical:
        return canonical
    
    # Return original with basic cleanup if no canonical form found
    return name.strip()


def is_same_entity(entity1: Optional[str], entity2: Optional[str]) -> bool:
    """
    Check if two entity names refer to the same entity.
    
    Args:
        entity1: First entity name
        entity2: Second entity name
        
    Returns:
        True if both normalize to the same canonical form
    """
    if not entity1 or not entity2:
        return False
    
    return normalize_entity(entity1) == normalize_entity(entity2)