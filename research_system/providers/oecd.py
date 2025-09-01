"""OECD provider for economic statistics and datasets."""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from .http import http_json_with_policy as http_json
import logging
import time
import os

logger = logging.getLogger(__name__)

# v8.24.0: Multiple OECD endpoints with fallback to alt host
# Export primary URL for tests
DATAFLOW_URL = "https://stats.oecd.org/sdmx-json/dataflow/ALL"

# All endpoints to try in order (with mirror host fallback)
DATAFLOW_URLS = [
    "https://stats.oecd.org/sdmx-json/dataflow/ALL",
    "https://stats.oecd.org/sdmx-json/dataflow",
    "https://stats-nxd.oecd.org/sdmx-json/dataflow/ALL",  # Mirror host
    "https://stats-nxd.oecd.org/sdmx-json/dataflow",      # Mirror host
]

# Circuit breaker state
_circuit_state = {
    "is_open": False,
    "last_failure": 0,
    "consecutive_failures": 0,
    "catalog_cache": None,
    "cache_time": 0
}

def reset_circuit_state():
    """Reset circuit breaker state for testing."""
    global _circuit_state
    _circuit_state["is_open"] = False
    _circuit_state["last_failure"] = 0
    _circuit_state["consecutive_failures"] = 0
    _circuit_state["catalog_cache"] = None
    _circuit_state["cache_time"] = 0

# Configuration
CIRCUIT_COOLDOWN = int(os.getenv("OECD_CIRCUIT_COOLDOWN", "300"))  # 5 minutes
CIRCUIT_THRESHOLD = int(os.getenv("OECD_CIRCUIT_THRESHOLD", "2"))  # Trip after 2 failures
CACHE_TTL = int(os.getenv("OECD_CACHE_TTL", "3600"))  # 1 hour

def _dataflows() -> Dict[str, Dict[str, Any]]:
    """Fetch OECD dataflows catalog with circuit breaker and caching."""
    current_time = time.time()
    
    # Check circuit breaker
    if _circuit_state["is_open"]:
        if current_time - _circuit_state["last_failure"] < CIRCUIT_COOLDOWN:
            logger.info("OECD circuit breaker OPEN, returning cached catalog")
            return _circuit_state["catalog_cache"] or {}
        else:
            # Try to close circuit
            logger.info("OECD circuit breaker attempting to close")
            _circuit_state["is_open"] = False
            _circuit_state["consecutive_failures"] = 0
    
    # Check cache
    if (_circuit_state["catalog_cache"] is not None and 
        current_time - _circuit_state["cache_time"] < CACHE_TTL):
        logger.debug("OECD returning cached catalog")
        return _circuit_state["catalog_cache"]
    
    # v8.24.0: Try multiple endpoints with fallback to alt hosts
    last_err = None
    
    for url in DATAFLOW_URLS:
        try:
            logger.info(f"Fetching OECD dataflows from: {url}")
            
            # Use explicit JSON accept header - critical for OECD
            data = http_json(
                "oecd", 
                "GET", 
                url,
                headers={
                    "Accept": "application/json,text/plain,*/*",
                    "User-Agent": "research_agent/1.0"
                },
                timeout=30  # Restored with proper support
            )
            
            # Shape varies; normalize
            result = {}
            if "data" in data and "dataflows" in data["data"]:
                result = data["data"]["dataflows"]
            elif "Dataflows" in data and "Dataflow" in data["Dataflows"]:
                for df in data["Dataflows"]["Dataflow"]:
                    key = df.get("Key") or df.get("@id") or df.get("id")
                    name = ""
                    nm = df.get("Name") or df.get("name")
                    if isinstance(nm, list) and nm:
                        name = nm[0].get("$") or nm[0].get("value") or ""
                    elif isinstance(nm, str):
                        name = nm
                    result[str(key)] = {"name": name}
            
            # Success - cache and reset failures
            _circuit_state["catalog_cache"] = result
            _circuit_state["cache_time"] = current_time
            _circuit_state["consecutive_failures"] = 0
            logger.info(f"OECD dataflows fetched successfully from {url}")
            return result
            
        except Exception as e:
            last_err = e
            logger.debug(f"OECD endpoint {url} failed: {e}")
            continue
    
    # All endpoints failed
    logger.warning(f"All OECD endpoints failed: {last_err}")
    
    # All attempts failed
    _circuit_state["consecutive_failures"] += 1
    _circuit_state["last_failure"] = current_time
    
    # Trip circuit if threshold reached
    if _circuit_state["consecutive_failures"] >= CIRCUIT_THRESHOLD:
        _circuit_state["is_open"] = True
        logger.warning(f"OECD circuit breaker TRIPPED after {CIRCUIT_THRESHOLD} failures")
    
    # Return cached data if available
    return _circuit_state["catalog_cache"] or {}

def search_oecd(query: str, limit: int = 25) -> List[Dict[str, Any]]:
    """Search OECD datasets by relevance to query."""
    q = (query or "").lower()
    dfs = _dataflows()
    items = []
    
    for code, meta in dfs.items():
        name = (meta.get("name") or "").lower()
        score = sum(name.count(t) for t in q.split()) + (2 if code.lower() in q else 0)
        if score > 0:
            items.append({"code": code, "name": meta.get("name"), "score": score})
    
    items.sort(key=lambda x: x["score"], reverse=True)
    return items[:limit]

def to_cards(rows: List[Dict[str, Any]]) -> List[dict]:
    """Convert OECD datasets to evidence cards."""
    cards = []
    for r in rows:
        code = r.get("code")
        title = r.get("name") or code
        # Link to dataset landing page in OECD stats
        url = f"https://stats.oecd.org/Index.aspx?DataSetCode={code}" if code else "https://stats.oecd.org/"
        
        cards.append({
            "title": f"OECD: {title}",
            "url": url,
            "snippet": f"OECD dataset {code}",
            "source_domain": "oecd.org",
            "metadata": {
                "provider": "oecd",
                "dataset_code": code,
                "license": "OECD Terms and Conditions"
            }
        })
    return cards