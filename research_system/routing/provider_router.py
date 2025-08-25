"""Topic-agnostic provider router with config-driven selection."""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Set, Tuple
import re
import json
import yaml
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Categories are broad and topic-agnostic
CATEGORIES = [
    "biomed", "macro", "policy", "science", "tech", "climate", "geospatial", "news", "general"
]

# Very light keyword heuristics; you can extend safely
KEYWORDS = {
    "biomed":   r"\b(trial|randomi[sz]ed|placebo|cohort|vaccine|biomarker|pubmed|doi:10\.)\b",
    "macro":    r"\b(gdp|inflation|cpi|unemployment|tourism|arrivals|exports|imports|bond|sovereign|oecd|imf|world bank|fred)\b",
    "policy":   r"\b(regulat|policy|directive|ordinance|legislation|sec filing|fcc|who|eu|ec)\b",
    "science":  r"\b(arxiv|preprint|citation|h-index|openalex|doi:10\.)\b",
    "tech":     r"\b(software|framework|library|benchmark|github|ai model|dataset|latency|throughput)\b",
    "climate":  r"\b(ghg|emissions?|ipcc|temperature anomaly|pmm|precipitation|ocean heat|noaa|cop\d+|climate change)\b",
    "geospatial": r"\b(osm|openstreetmap|poi|overpass|geocode|shapefile|geojson)\b",
    "news":     r"\b(breaking|today|this week|press release|announced|report says|news)\b",
}

@dataclass(frozen=True)
class RouterDecision:
    categories: List[str]
    providers: List[str]        # provider keys
    reason: str

def _load_profiles() -> Dict[str, List[str]]:
    """Load provider profiles from YAML config or use defaults."""
    try:
        # Try to load from resources directory
        config_path = Path(__file__).parent.parent / "resources" / "provider_profiles.yaml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data if data else _get_default_profiles()
    except Exception as e:
        logger.debug(f"Could not load provider profiles: {e}")
    
    return _get_default_profiles()

def _get_default_profiles() -> Dict[str, List[str]]:
    """Return default provider profiles."""
    return {
        "general": ["wikipedia", "wikidata", "openalex", "crossref", "unpaywall", "wayback"],
        "news":    ["gdelt", "wikipedia", "wayback"],
        "biomed":  ["pubmed", "europepmc", "crossref", "unpaywall", "openalex", "wayback"],
        "macro":   ["worldbank", "oecd", "eurostat", "imf", "fred", "wikidata", "wikipedia", "wayback"],
        "science": ["openalex", "crossref", "unpaywall", "arxiv", "wikidata", "wikipedia", "wayback"],
        "tech":    ["openalex", "arxiv", "crossref", "unpaywall", "wikidata", "wikipedia", "wayback"],
        "climate": ["oecd", "worldbank", "eurostat", "openalex", "crossref", "unpaywall", "wayback"],
        "geospatial":["overpass", "wikipedia", "wikidata", "wayback"],
        "policy":  ["oecd", "ec", "worldbank", "openalex", "crossref", "wayback"],
    }

def infer_categories(topic: str) -> List[str]:
    """Infer categories from topic keywords."""
    t = (topic or "").lower()
    hits: List[Tuple[str, int]] = []
    
    for cat, pat in KEYWORDS.items():
        matches = re.findall(pat, t)
        if matches:
            hits.append((cat, len(matches)))
    
    # Sort by match count, always include 'general' as fallback
    cats = [c for c, _ in sorted(hits, key=lambda x: -x[1])]
    if "general" not in cats:
        cats.append("general")
    
    # Keep a sensible max breadth
    return cats[:3]

def choose_providers(topic: str) -> RouterDecision:
    """Choose providers based on topic analysis."""
    cats = infer_categories(topic)
    profiles = _load_profiles()
    chosen: List[str] = []
    
    for c in cats:
        chosen.extend(profiles.get(c, []))
    
    # Stable uniqueness, preserve order
    seen: Set[str] = set()
    providers = [p for p in chosen if not (p in seen or seen.add(p))]
    
    reason = json.dumps({"categories": cats})
    return RouterDecision(categories=cats, providers=providers, reason=reason)