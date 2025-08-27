"""Registry for all API providers with full implementation."""

from __future__ import annotations
from typing import Dict, Callable, Any

from .openalex import search_openalex, to_cards as openalex_to_cards
from .crossref import crossref_query, to_cards as crossref_to_cards
from .unpaywall import lookup_fulltext
from .wikipedia import wiki_search, to_cards as wiki_to_cards
from .wikidata import wikidata_labels, entity_search
from .wayback import wayback_latest, save_page_now
from .gdelt import gdelt_events, to_cards as gdelt_to_cards
from .fred import fred_series, to_cards as fred_to_cards, search_series as fred_search
from .worldbank import search_worldbank, to_cards as wb_to_cards
from .oecd import search_oecd, to_cards as oecd_to_cards
from .imf import search_imf, to_cards as imf_to_cards
from .arxiv import arxiv_search, to_cards as arxiv_to_cards
from .pubmed import pubmed_search, to_cards as pubmed_to_cards
from .europepmc import europepmc_search, to_cards as epmc_to_cards
from .overpass import overpass_search, to_cards as overpass_to_cards
from .ec import ec_search, to_cards as ec_to_cards
from .eurostat import eurostat_search, to_cards as eurostat_to_cards
from .nominatim import search_places as nominatim_search, to_cards as nominatim_to_cards
from .wikivoyage import search_destinations as wikivoyage_search, to_cards as wikivoyage_to_cards
from .osmtags import search_by_tags as osmtags_search, to_cards as osmtags_to_cards

# Complete provider registry with all implementations
PROVIDERS: Dict[str, Dict[str, Callable[..., Any]]] = {
    # Scholarly & Research
    "openalex": {
        "search": search_openalex,
        "to_cards": openalex_to_cards
    },
    "crossref": {
        "search": crossref_query,
        "to_cards": crossref_to_cards
    },
    "arxiv": {
        "search": arxiv_search,
        "to_cards": arxiv_to_cards
    },
    
    # Biomedical
    "pubmed": {
        "search": pubmed_search,
        "to_cards": pubmed_to_cards
    },
    "europepmc": {
        "search": europepmc_search,
        "to_cards": epmc_to_cards
    },
    
    # Economic & Statistical
    "worldbank": {
        "search": search_worldbank,
        "to_cards": wb_to_cards
    },
    "oecd": {
        "search": search_oecd,
        "to_cards": oecd_to_cards
    },
    "imf": {
        "search": search_imf,
        "to_cards": imf_to_cards
    },
    "eurostat": {
        "search": eurostat_search,
        "to_cards": eurostat_to_cards
    },
    "fred": {
        "series": fred_series,
        "to_cards": fred_to_cards,
        "search": fred_search
    },
    
    # European Data
    "ec": {
        "search": ec_search,
        "to_cards": ec_to_cards
    },
    
    # Knowledge & Encyclopedia
    "wikipedia": {
        "search": wiki_search,
        "to_cards": wiki_to_cards
    },
    "wikidata": {
        "labels": wikidata_labels,
        "search": entity_search
    },
    
    # News & Events
    "gdelt": {
        "events": gdelt_events,
        "to_cards": gdelt_to_cards
    },
    
    # Geospatial
    "overpass": {
        "search": overpass_search,
        "to_cards": overpass_to_cards
    },
    "nominatim": {
        "search": nominatim_search,
        "to_cards": nominatim_to_cards
    },
    "osmtags": {
        "search": osmtags_search,
        "to_cards": osmtags_to_cards
    },
    
    # Travel
    "wikivoyage": {
        "search": wikivoyage_search,
        "to_cards": wikivoyage_to_cards
    },
    
    # Enrichment & Resilience
    "unpaywall": {
        "lookup": lookup_fulltext  # Enrichment by DOI
    },
    "wayback": {
        "latest": wayback_latest,  # Archive lookup
        "save": save_page_now      # Request archiving
    }
}

def get_provider(name: str) -> Dict[str, Callable]:
    """Get provider implementation by name."""
    return PROVIDERS.get(name, {})