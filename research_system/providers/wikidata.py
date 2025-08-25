"""Wikidata provider for entity resolution and knowledge graph."""

from typing import List, Dict, Any
from .http import http_json
import logging

logger = logging.getLogger(__name__)

SPARQL = "https://query.wikidata.org/sparql"

def wikidata_labels(qids: List[str]) -> Dict[str, str]:
    """Get labels for Wikidata QIDs."""
    if not qids:
        return {}
    
    try:
        # Build SPARQL query
        values = " ".join(f"(wd:{q})" for q in qids)
        query = f"""
        SELECT ?q ?label WHERE {{
            VALUES ?q {{ {values} }}
            ?q rdfs:label ?label
            FILTER(LANG(?label)='en')
        }}
        """
        
        headers = {"Accept": "application/sparql-results+json"}
        data = http_json("GET", SPARQL, params={"query": query}, headers=headers)
        
        # Extract results
        bindings = data.get("results", {}).get("bindings", [])
        result = {}
        for b in bindings:
            qid = b["q"]["value"].split("/")[-1]
            label = b["label"]["value"]
            result[qid] = label
        
        return result
    except Exception as e:
        logger.debug(f"Wikidata labels lookup failed: {e}")
        return {}

def entity_search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Search for Wikidata entities."""
    try:
        url = "https://www.wikidata.org/w/api.php"
        params = {
            "action": "wbsearchentities",
            "search": query,
            "language": "en",
            "limit": limit,
            "format": "json"
        }
        data = http_json("GET", url, params=params)
        return data.get("search", [])
    except Exception as e:
        logger.debug(f"Wikidata entity search failed: {e}")
        return []