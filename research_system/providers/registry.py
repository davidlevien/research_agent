"""Registry for all API providers with full implementation."""

from __future__ import annotations
from typing import Dict, Callable, Any
import logging

logger = logging.getLogger(__name__)

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


def register_web_search_providers():
    """v8.26.4: Register web search providers if API keys are available.
    
    These providers all have free tiers with API keys.
    They should be used based on query needs, not artificial free/paid distinction.
    """
    import os
    
    # Tavily - Best for general web search
    if os.getenv("TAVILY_API_KEY"):
        try:
            from research_system.tools import search_tavily
            from research_system.tools.search_models import SearchRequest
            
            def tavily_search(query: str, limit: int = 10):
                req = SearchRequest(query=query, count=limit)
                return search_tavily.run(req.model_dump())
            
            def tavily_to_cards(results):
                cards = []
                for r in results:
                    cards.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("snippet", ""),
                        "source_domain": r.get("domain", "")
                    })
                return cards
            
            PROVIDERS["tavily"] = {
                "search": tavily_search,
                "to_cards": tavily_to_cards
            }
            logger.info("Registered Tavily web search provider")
        except Exception as e:
            logger.debug(f"Could not register Tavily: {e}")
    
    # Brave - Good for privacy-focused and recent content
    if os.getenv("BRAVE_API_KEY"):
        try:
            from research_system.tools import search_brave
            from research_system.tools.search_models import SearchRequest
            
            def brave_search(query: str, limit: int = 10):
                req = SearchRequest(query=query, count=limit)
                return search_brave.run(req.model_dump())
            
            def brave_to_cards(results):
                cards = []
                for r in results:
                    cards.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("snippet", ""),
                        "source_domain": r.get("domain", "")
                    })
                return cards
            
            PROVIDERS["brave"] = {
                "search": brave_search,
                "to_cards": brave_to_cards
            }
            logger.info("Registered Brave web search provider")
        except Exception as e:
            logger.debug(f"Could not register Brave: {e}")
    
    # Serper - Google search results
    if os.getenv("SERPER_API_KEY"):
        try:
            from research_system.tools import search_serper
            from research_system.tools.search_models import SearchRequest
            
            def serper_search(query: str, limit: int = 10):
                req = SearchRequest(query=query, count=limit)
                return search_serper.run(req.model_dump())
            
            def serper_to_cards(results):
                cards = []
                for r in results:
                    cards.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("snippet", ""),
                        "source_domain": r.get("domain", "")
                    })
                return cards
            
            PROVIDERS["serper"] = {
                "search": serper_search,
                "to_cards": serper_to_cards
            }
            logger.info("Registered Serper web search provider")
        except Exception as e:
            logger.debug(f"Could not register Serper: {e}")
    
    # SerpAPI - Alternative Google search
    if os.getenv("SERPAPI_API_KEY"):
        try:
            from research_system.tools import search_serpapi
            from research_system.tools.search_models import SearchRequest
            
            def serpapi_search(query: str, limit: int = 10):
                req = SearchRequest(query=query, count=limit)
                return search_serpapi.run(req.model_dump())
            
            def serpapi_to_cards(results):
                cards = []
                for r in results:
                    cards.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("snippet", ""),
                        "source_domain": r.get("domain", "")
                    })
                return cards
            
            PROVIDERS["serpapi"] = {
                "search": serpapi_search,
                "to_cards": serpapi_to_cards
            }
            logger.info("Registered SerpAPI web search provider")
        except Exception as e:
            logger.debug(f"Could not register SerpAPI: {e}")

# v8.26.4: Auto-register web search providers on module import
try:
    register_web_search_providers()
except Exception as e:
    logger.debug(f"Could not register web search providers: {e}")