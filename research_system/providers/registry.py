"""Registry for free API providers."""

from __future__ import annotations
from typing import Dict, Callable, Any, List
from . import http
from .openalex import search_openalex, to_cards as openalex_to_cards
from .crossref import crossref_query, to_cards as crossref_to_cards
from .unpaywall import lookup_fulltext
from .wikipedia import wiki_search, to_cards as wiki_to_cards
from .wikidata import wikidata_labels, entity_search
from .wayback import wayback_latest, save_page_now
from .gdelt import gdelt_events, to_cards as gdelt_to_cards
from .fred import fred_series, to_cards as fred_to_cards, search_series as fred_search

def not_implemented(*args, **kwargs):
    """Placeholder for providers not yet implemented."""
    return []

# Provider registry with search and conversion functions
PROVIDERS: Dict[str, Dict[str, Callable[..., Any]]] = {
    "openalex": {
        "search": search_openalex,
        "to_cards": openalex_to_cards
    },
    "crossref": {
        "search": crossref_query,
        "to_cards": crossref_to_cards
    },
    "unpaywall": {
        "lookup": lookup_fulltext  # Enrichment by DOI
    },
    "wikipedia": {
        "search": wiki_search,
        "to_cards": wiki_to_cards
    },
    "wikidata": {
        "labels": wikidata_labels,  # Entity resolution
        "search": entity_search
    },
    "gdelt": {
        "events": gdelt_events,
        "to_cards": gdelt_to_cards
    },
    "wayback": {
        "latest": wayback_latest,  # Archive lookup
        "save": save_page_now      # Request archiving
    },
    "fred": {
        "series": fred_series,
        "to_cards": fred_to_cards,
        "search": fred_search
    },
    
    # Placeholders for future implementation
    "worldbank": {"search": not_implemented},
    "oecd": {"search": not_implemented},
    "eurostat": {"search": not_implemented},
    "imf": {"search": not_implemented},
    "arxiv": {"search": not_implemented},
    "pubmed": {"search": not_implemented},
    "europepmc": {"search": not_implemented},
    "overpass": {"search": not_implemented},
    "ec": {"search": not_implemented},
}

def get_provider(name: str) -> Dict[str, Callable]:
    """Get provider implementation by name."""
    return PROVIDERS.get(name, {})