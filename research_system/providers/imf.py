"""IMF provider for international financial statistics."""

from __future__ import annotations
from typing import List, Dict, Any
from .http import http_json_with_policy as http_json
import logging
import time
import os

logger = logging.getLogger(__name__)

_DATAFLOW = "https://dataservices.imf.org/REST/SDMX_JSON.svc/Dataflow"

# Circuit breaker state
_circuit_state = {
    "is_open": False,
    "last_failure": 0,
    "consecutive_failures": 0,
    "catalog_cache": None,
    "cache_time": 0
}

# Configuration
# v8.26.1: Increased thresholds to be more tolerant of transient failures
CIRCUIT_COOLDOWN = int(os.getenv("IMF_CIRCUIT_COOLDOWN", "600"))  # 10 minutes (was 5)
CIRCUIT_THRESHOLD = int(os.getenv("IMF_CIRCUIT_THRESHOLD", "5"))  # Trip after 5 failures (was 2)
CACHE_TTL = int(os.getenv("IMF_CACHE_TTL", "7200"))  # 2 hours (was 1)

def _dataflows() -> List[Dict[str, Any]]:
    """Fetch IMF dataflows catalog with circuit breaker and caching."""
    current_time = time.time()
    
    # Check circuit breaker
    if _circuit_state["is_open"]:
        if current_time - _circuit_state["last_failure"] < CIRCUIT_COOLDOWN:
            logger.info("IMF circuit breaker OPEN, returning cached catalog")
            return _circuit_state["catalog_cache"] or []
        else:
            # Try to close circuit
            logger.info("IMF circuit breaker attempting to close")
            _circuit_state["is_open"] = False
            _circuit_state["consecutive_failures"] = 0
    
    # Check cache
    if (_circuit_state["catalog_cache"] is not None and 
        current_time - _circuit_state["cache_time"] < CACHE_TTL):
        logger.debug("IMF returning cached catalog")
        return _circuit_state["catalog_cache"]
    
    try:
        data = http_json("imf", "GET", _DATAFLOW)
        # Typically {"Structure":{"Dataflows":{"Dataflow":[...]}}}
        flows = (((data.get("Structure") or {}).get("Dataflows") or {}).get("Dataflow")) or []
        out = []
        
        for f in flows:
            key = f.get("Key") or f.get("@id") or f.get("id")
            nm = f.get("Name") or []
            name = ""
            if isinstance(nm, list) and nm:
                name = nm[0].get("$") or nm[0].get("value") or ""
            elif isinstance(nm, str):
                name = nm
            out.append({"code": key, "name": name})
        
        # Success - cache and reset failures
        _circuit_state["catalog_cache"] = out
        _circuit_state["cache_time"] = current_time
        _circuit_state["consecutive_failures"] = 0
        return out
        
    except Exception as e:
        logger.warning(f"IMF dataflows fetch failed: {e}")
        _circuit_state["consecutive_failures"] += 1
        _circuit_state["last_failure"] = current_time
        
        # Trip circuit if threshold reached
        if _circuit_state["consecutive_failures"] >= CIRCUIT_THRESHOLD:
            _circuit_state["is_open"] = True
            logger.warning(f"IMF circuit breaker TRIPPED after {CIRCUIT_THRESHOLD} failures")
        
        # Return cached data if available
        return _circuit_state["catalog_cache"] or []

def search_imf(query: str, limit: int = 25) -> List[Dict[str, Any]]:
    """Search IMF datasets by relevance to query."""
    q = (query or "").lower()
    flows = _dataflows()
    
    for f in flows:
        f["score"] = sum((f.get("name", "") or "").lower().count(t) for t in q.split())
        f["score"] += 2 if (f.get("code", "") or "").lower() in q else 0
    
    flows.sort(key=lambda x: x["score"], reverse=True)
    return [f for f in flows if f["score"] > 0][:limit]

def to_cards(rows: List[Dict[str, Any]]) -> List[dict]:
    """Convert IMF datasets to evidence cards."""
    cards = []
    for r in rows:
        code = r.get("code")
        name = r.get("name") or code
        # IMF dataset landing
        url = f"https://dataservices.imf.org/REST/SDMX_JSON.svc/Dataflow/{code}" if code else "https://dataservices.imf.org/"
        
        cards.append({
            "title": f"IMF: {name}",
            "url": url,
            "snippet": f"IMF dataset {code}: {name}",
            "source_domain": "imf.org",
            "metadata": {
                "provider": "imf",
                "dataset_code": code,
                "license": "IMF Copyright and Usage"
            }
        })
    return cards