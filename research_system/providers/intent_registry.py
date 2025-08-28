"""Intent-based provider registry with tiered fallbacks."""

import os
import logging
from typing import Dict, List, Optional
from research_system.intent.classifier import Intent

logger = logging.getLogger(__name__)


# Provider registry with tiered fallbacks by intent
INTENT_REGISTRY: Dict[Intent, Dict[str, List[str]]] = {
    Intent.ENCYCLOPEDIA: {
        "free_primary": ["wikipedia", "wikidata"],
        "free_fallback": ["wayback"],
        "paid_primary": [],
        "paid_fallback": ["tavily", "serper"]
    },
    Intent.NEWS: {
        "free_primary": ["gdelt"],
        "free_fallback": ["wayback"],
        "paid_primary": ["tavily", "brave", "serper"],
        "paid_fallback": ["serpapi"]
    },
    Intent.PRODUCT: {
        "free_primary": [],
        "free_fallback": ["wikipedia"],
        "paid_primary": ["brave", "serper", "tavily"],
        "paid_fallback": ["serpapi"]
    },
    Intent.LOCAL: {
        "free_primary": ["nominatim", "wikivoyage", "wikipedia"],
        "free_fallback": ["osmtags", "overpass"],
        "paid_primary": ["brave", "serper"],
        "paid_fallback": ["tavily"]
    },
    Intent.ACADEMIC: {
        "free_primary": ["openalex", "crossref", "pubmed", "arxiv", "europepmc"],
        "free_fallback": ["unpaywall"],
        "paid_primary": [],
        "paid_fallback": ["tavily"]
    },
    Intent.STATS: {
        "free_primary": ["worldbank", "fred", "oecd", "imf", "eurostat", "ec"],
        "free_fallback": [],  # GDELT removed - not suitable for stats
        "paid_primary": [],
        "paid_fallback": ["tavily", "brave"]  # Added brave as secondary fallback
    },
    Intent.TRAVEL: {
        "free_primary": ["wikivoyage", "wikipedia", "wikidata"],
        "free_fallback": ["osmtags", "nominatim", "overpass"],
        "paid_primary": ["tavily", "brave"],
        "paid_fallback": ["serper"]
    },
    Intent.REGULATORY: {
        "free_primary": ["edgar"],  # To be implemented
        "free_fallback": [],
        "paid_primary": ["tavily", "brave"],
        "paid_fallback": ["serper", "serpapi"]
    },
    Intent.HOWTO: {
        "free_primary": ["wikipedia"],
        "free_fallback": [],
        "paid_primary": ["brave", "serper", "tavily"],
        "paid_fallback": ["serpapi"]
    },
    Intent.MEDICAL: {
        "free_primary": ["pubmed", "europepmc", "who"],  # WHO to be implemented
        "free_fallback": ["openalex", "crossref"],
        "paid_primary": [],
        "paid_fallback": ["tavily"]
    },
    Intent.GENERIC: {
        "free_primary": ["wikipedia", "wikidata"],
        "free_fallback": ["wayback"],  # Remove verticals from generic
        "paid_primary": ["brave", "serper", "tavily"],
        "paid_fallback": ["serpapi"]
    }
}


def expand_providers_for_intent(intent: Intent, available_keys: Optional[Dict[str, str]] = None) -> List[str]:
    """
    Expand provider list based on intent and available API keys.
    
    Args:
        intent: The classified intent
        available_keys: Dict of available API keys (if None, reads from env)
        
    Returns:
        Ordered list of providers to use
    """
    if available_keys is None:
        available_keys = _detect_available_keys()
    
    bundle = INTENT_REGISTRY.get(intent, INTENT_REGISTRY[Intent.GENERIC])
    providers = []
    
    # Add providers in tier order
    for tier in ["free_primary", "paid_primary", "free_fallback", "paid_fallback"]:
        for provider in bundle.get(tier, []):
            if _is_provider_available(provider, available_keys):
                if provider not in providers:  # De-duplicate
                    providers.append(provider)
    
    if not providers:
        # Ultimate fallback - try generic free providers
        providers = ["wikipedia", "wikidata"]
    
    logger.info(f"Intent {intent.value} -> providers: {providers}")
    return providers


def _detect_available_keys() -> Dict[str, str]:
    """Detect which API keys are available in environment."""
    keys = {}
    
    # Check for search API keys
    if os.getenv("TAVILY_API_KEY"):
        keys["tavily"] = os.getenv("TAVILY_API_KEY")
    if os.getenv("BRAVE_API_KEY"):
        keys["brave"] = os.getenv("BRAVE_API_KEY")
    if os.getenv("SERPER_API_KEY"):
        keys["serper"] = os.getenv("SERPER_API_KEY")
    if os.getenv("SERPAPI_API_KEY"):
        keys["serpapi"] = os.getenv("SERPAPI_API_KEY")
    
    # Check for data API keys
    if os.getenv("FRED_API_KEY"):
        keys["fred"] = os.getenv("FRED_API_KEY")
    if os.getenv("NPS_API_KEY"):
        keys["nps"] = os.getenv("NPS_API_KEY")
    
    # Check for optional services
    if os.getenv("UNPAYWALL_EMAIL"):
        keys["unpaywall"] = os.getenv("UNPAYWALL_EMAIL")
    if os.getenv("SEC_API_KEY"):
        keys["sec_api"] = os.getenv("SEC_API_KEY")
    
    return keys


def _is_provider_available(provider: str, available_keys: Dict[str, str]) -> bool:
    """Check if a provider is available (has API key if required)."""
    
    # Free providers that don't need keys
    free_providers = {
        "wikipedia", "wikidata", "openalex", "crossref", "pubmed", "arxiv",
        "europepmc", "worldbank", "oecd", "imf", "eurostat", "ec", "gdelt",
        "wayback", "osmtags", "overpass", "nominatim", "wikivoyage", "edgar", 
        "who", "unpaywall"  # Needs email but we'll check separately
    }
    
    if provider in free_providers:
        # Special check for unpaywall
        if provider == "unpaywall":
            return "unpaywall" in available_keys
        return True
    
    # Paid providers need keys
    return provider in available_keys


def get_provider_rate_limit(provider: str) -> float:
    """
    Get rate limit for a provider (requests per second).
    
    Args:
        provider: Provider name
        
    Returns:
        Rate limit in RPS
    """
    # Check environment overrides first
    env_key = f"{provider.upper()}_RPS"
    if os.getenv(env_key):
        try:
            return float(os.getenv(env_key))
        except ValueError:
            pass
    
    # Default rate limits (conservative)
    defaults = {
        "nominatim": 1.0,      # OSM Nominatim policy
        "sec": 0.5,            # SEC EDGAR RSS
        "serpapi": 0.2,        # Avoid 429s
        "wikipedia": 5.0,      # Wikipedia API
        "openalex": 10.0,      # OpenAlex allows 10 RPS
        "crossref": 5.0,       # Crossref polite pool
        "pubmed": 3.0,         # NCBI E-utilities
        "fred": 2.0,           # FRED API
        "worldbank": 2.0,      # World Bank API
        "tavily": 1.0,         # Tavily default
        "brave": 1.0,          # Brave Search
        "serper": 1.0,         # Serper
        "gdelt": 2.0,          # GDELT
        "arxiv": 1.0,          # arXiv
        "europepmc": 3.0,      # Europe PMC
        "overpass": 0.5,       # OSM Overpass
        "osmtags": 1.0,        # OSM tags
        "wikivoyage": 2.0,     # Wikivoyage
        "edgar": 0.5,          # SEC EDGAR
    }
    
    return defaults.get(provider, 1.0)  # Default 1 RPS