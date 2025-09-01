"""Provider group definitions for reusable composition.

v8.26.0: Implements generic provider groups for cross-domain research.
"""

from typing import List, Dict

# Reusable provider groups
GROUPS: Dict[str, List[str]] = {
    "macro_econ": ["worldbank", "oecd", "imf", "eurostat", "fred"],
    "encyclopedic": ["wikipedia", "wikidata"],
    "geo_poi": ["osmtags", "nominatim", "overpass"],
    "academic": ["openalex", "crossref"],
    "filings": ["sec"],
    "news": ["newsapi", "mediastack"],
    "general_search": ["brave", "tavily", "serper"],
    "specialized_data": ["statista", "tradingeconomics"],
    "travel": ["wikivoyage"],
    "medical": ["pubmed", "clinicaltrials"],
}


def get_providers_for_groups(group_names: List[str]) -> List[str]:
    """Get all providers from specified groups.
    
    Args:
        group_names: List of group names
        
    Returns:
        Combined list of providers (deduplicated)
    """
    providers = []
    seen = set()
    
    for group_name in group_names:
        if group_name in GROUPS:
            for provider in GROUPS[group_name]:
                if provider not in seen:
                    providers.append(provider)
                    seen.add(provider)
    
    return providers


def get_all_providers() -> List[str]:
    """Get all available providers from all groups.
    
    Returns:
        List of all unique providers
    """
    all_providers = []
    seen = set()
    
    for providers in GROUPS.values():
        for provider in providers:
            if provider not in seen:
                all_providers.append(provider)
                seen.add(provider)
    
    return all_providers


def get_primary_providers() -> List[str]:
    """Get providers considered as primary sources.
    
    Returns:
        List of primary source providers
    """
    # Combine macro_econ, filings, and some academic
    return get_providers_for_groups(["macro_econ", "filings"])


def get_contextual_providers() -> List[str]:
    """Get providers for contextual information.
    
    Returns:
        List of contextual providers
    """
    return get_providers_for_groups(["encyclopedic", "general_search"])


# Alias for backward compatibility
expand_groups = get_providers_for_groups