"""
Research data connectors for primary sources
"""

from __future__ import annotations
from typing import Dict, Callable, List

# Import available connectors
from .crossref import search_crossref
from .openalex import search_openalex
from .gdelt import search_gdelt
from .pubmed import search_pubmed
from .edgar import search_edgar
from .eurlex import search_eurlex

# Connector registry for dynamic lookup
REGISTRY: Dict[str, Callable[[str, int], List]] = {
    "crossref": lambda topic, rows=5: search_crossref(topic, rows),
    "openalex": lambda topic, rows=5: search_openalex(topic, rows),
    "gdelt": lambda topic, rows=10: search_gdelt(topic, rows),
    "pubmed": lambda topic, rows=5: search_pubmed(topic, rows),
    "edgar": lambda topic, rows=5: search_edgar(topic, rows),
    "eurlex": lambda topic, rows=5: search_eurlex(topic, rows),
    
    # Placeholder aliases for future connectors
    "arxiv": lambda topic, rows=5: search_crossref(f"{topic} site:arxiv.org", rows),  # Use Crossref for arXiv
    "clinicaltrials": lambda topic, rows=5: search_pubmed(f"{topic} clinical trial", rows),  # Use PubMed
    "fred": lambda topic, rows=5: [],  # Federal Reserve Economic Data
    "oecd": lambda topic, rows=5: [],  # OECD Stats
    "worldbank": lambda topic, rows=5: [],  # World Bank Data
    "github": lambda topic, rows=5: [],  # GitHub repositories
    "nvd": lambda topic, rows=5: [],  # National Vulnerability Database
    "mitre": lambda topic, rows=5: [],  # MITRE CVE/CWE
    "cisa": lambda topic, rows=5: [],  # CISA advisories
    "courtlistener": lambda topic, rows=5: [],  # Court Listener
    "congress": lambda topic, rows=5: [],  # Congress.gov
    "unwto": lambda topic, rows=5: [],  # UN World Tourism Organization
    "wttc": lambda topic, rows=5: [],  # World Travel & Tourism Council
    "iata": lambda topic, rows=5: [],  # International Air Transport Association
    "noaa": lambda topic, rows=5: [],  # NOAA Climate Data
    "nasa": lambda topic, rows=5: [],  # NASA Climate
    "ipcc": lambda topic, rows=5: [],  # IPCC Reports
}

__all__ = [
    'search_crossref',
    'search_openalex',
    'search_gdelt',
    'search_pubmed',
    'search_edgar',
    'search_eurlex',
    'REGISTRY'
]