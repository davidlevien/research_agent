"""OECD provider for economic statistics and datasets."""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from .http import http_json_with_policy as http_json
import logging
import time
import os

logger = logging.getLogger(__name__)

# v8.26.3: OECD API endpoints - FINAL FIX based on complete documentation review
# 
# ROOT CAUSE OF 404s:
# 1. Legacy stats.oecd.org endpoints were shut down June 2024
# 2. '/dataflow/OECD' fails because 'OECD' is not a valid agency ID
# 3. Must use 'all' for agency ID or specific patterns like OECD.ENV.EPI
# 4. Response can be huge (>1MB), may timeout or fail to parse
#
# Export primary URL for tests
DATAFLOW_URL = "https://sdmx.oecd.org/public/rest/dataflow/all/all/latest"

# Endpoints in priority order - using correct patterns from documentation
DATAFLOW_URLS = [
    "https://sdmx.oecd.org/public/rest/dataflow/all/all/latest",  # Correct pattern with wildcards
    "https://sdmx.oecd.org/public/rest/dataflow",                 # Fallback without params
    # Legacy endpoints removed - they're permanently offline
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
# v8.26.1: Increased thresholds to be more tolerant of transient failures
CIRCUIT_COOLDOWN = int(os.getenv("OECD_CIRCUIT_COOLDOWN", "600"))  # 10 minutes (was 5)
CIRCUIT_THRESHOLD = int(os.getenv("OECD_CIRCUIT_THRESHOLD", "5"))  # Trip after 5 failures (was 2)
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
            
            # v8.26.2: Updated headers and format based on official OECD API docs
            headers = {
                "Accept": "application/json,application/vnd.sdmx.structure+json,*/*",
                "User-Agent": "research_agent/1.0"
            }
            
            # For new sdmx.oecd.org endpoints, JSON is requested via Accept header
            # Don't add format parameter - it causes errors
            # The API returns JSON when Accept: application/json is set
            
            data = http_json(
                "oecd", 
                "GET", 
                url,
                headers=headers,
                timeout=30  # Restored with proper support
            )
            
            # v8.26.2: Handle SDMX-JSON response formats
            result = {}
            
            # New v2 structure API returns: {"references": {"urn:...": {...}}}
            if isinstance(data, dict) and "references" in data:
                # New format from /v2/structure/dataflow endpoint
                refs = data.get("references", {})
                for urn, df in refs.items():
                    if isinstance(df, dict):
                        agency_id = df.get("agencyID", "")
                        # Filter for OECD agencies (OECD.XXX pattern)
                        if agency_id.startswith("OECD"):
                            df_id = df.get("id", "")
                            name = df.get("name", "")
                            if isinstance(name, dict):
                                name = name.get("en", "") or str(name)
                            key = f"{agency_id}:{df_id}" if agency_id and df_id else df_id or urn
                            result[key] = {"name": str(name), "agency": agency_id}
            
            # Handle data wrapper format
            elif isinstance(data, dict) and "data" in data:
                # New SDMX format from sdmx.oecd.org
                data_content = data.get("data", {})
                
                # Check for dataflows in various formats
                if "dataflows" in data_content:
                    dflows = data_content["dataflows"]
                    if isinstance(dflows, list):
                        # Array of dataflow objects
                        for df in dflows:
                            if isinstance(df, dict):
                                # Extract ID - try multiple fields
                                key = df.get("id") or df.get("ID") or df.get("agencyID", "") + ":" + df.get("id", "")
                                if not key or key == ":":
                                    continue
                                
                                # Extract name - handle multilingual names
                                name = ""
                                nm = df.get("name")
                                if isinstance(nm, dict):
                                    # Multilingual: {"en": "Name", "fr": "Nom"}
                                    name = nm.get("en") or nm.get("EN") or next(iter(nm.values()), "")
                                elif isinstance(nm, str):
                                    name = nm
                                elif nm:
                                    name = str(nm)
                                
                                # Store with normalized structure
                                result[str(key)] = {"name": name or key}
                    
                    elif isinstance(dflows, dict):
                        # Direct dict mapping
                        result = dflows
                
                elif "Dataflow" in data_content:
                    # Alternative structure
                    dflows = data_content["Dataflow"]
                    if isinstance(dflows, list):
                        for df in dflows:
                            key = df.get("id") or df.get("ID")
                            name = df.get("name") or df.get("Name") or ""
                            if key:
                                result[str(key)] = {"name": str(name)}
            
            # Check if data is a list at root (some API responses)
            elif isinstance(data, list):
                # New SDMX API returns list of dataflow objects
                for df in data:
                    if isinstance(df, dict):
                        # Extract ID from various possible fields
                        key = df.get("id") or df.get("ID") or df.get("Key") or df.get("@id")
                        if not key:
                            continue
                        
                        # Extract name from various possible structures
                        name = ""
                        nm = df.get("name") or df.get("Name")
                        if isinstance(nm, dict):
                            # Sometimes name is {"en": "English Name"}
                            name = nm.get("en") or nm.get("value") or str(nm)
                        elif isinstance(nm, list) and nm:
                            # Sometimes it's [{"lang": "en", "value": "Name"}]
                            for n in nm:
                                if isinstance(n, dict):
                                    if n.get("lang") == "en" or "value" in n:
                                        name = n.get("value") or n.get("$") or ""
                                        break
                            if not name and nm:
                                name = str(nm[0])
                        elif isinstance(nm, str):
                            name = nm
                        else:
                            name = str(nm) if nm else ""
                        
                        result[str(key)] = {"name": name}
            
            # Handle object responses (older format)
            elif isinstance(data, dict):
                if "data" in data and "dataflows" in data["data"]:
                    dflows = data["data"]["dataflows"]
                    if isinstance(dflows, dict):
                        result = dflows
                    elif isinstance(dflows, list):
                        # Convert list to dict
                        for df in dflows:
                            if isinstance(df, dict):
                                key = df.get("id") or df.get("ID") or df.get("Key")
                                name = df.get("name") or df.get("Name") or ""
                                if key:
                                    result[str(key)] = {"name": str(name)}
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
                elif "dataflows" in data:
                    # Direct dataflows at root
                    dflows = data["dataflows"]
                    if isinstance(dflows, dict):
                        result = dflows
                    elif isinstance(dflows, list):
                        for df in dflows:
                            if isinstance(df, dict):
                                key = df.get("id") or df.get("ID")
                                name = df.get("name") or ""
                                if key:
                                    result[str(key)] = {"name": str(name)}
            
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
    
    # v8.26.2: Fallback to hardcoded popular OECD datasets when API fails
    # This ensures the provider returns something useful even when the API is down
    FALLBACK_DATASETS = [
        {"code": "OECD.SDD:DP_LIVE", "name": "OECD Data - Main Economic Indicators"},
        {"code": "OECD.SDD:PRICES_CPI", "name": "Consumer Price Index"},
        {"code": "OECD.ENV.EPI:AIR_EMISSIONS", "name": "Air Emissions Statistics"},
        {"code": "OECD.CFE:TOURISM_TRIPS", "name": "Tourism Trips and Travel Statistics"},
        {"code": "OECD.SDD:NAAG", "name": "National Accounts at a Glance"},
        {"code": "OECD.SDD:EO", "name": "Economic Outlook"},
        {"code": "OECD.SDD:TRADE", "name": "International Trade Statistics"},
    ]
    
    dfs = _dataflows()
    
    # v8.26.2: Use fallback datasets if API fails
    if not dfs or not isinstance(dfs, dict):
        logger.warning("OECD API unavailable, using fallback dataset list")
        # Filter fallback datasets by query
        items = []
        for ds in FALLBACK_DATASETS:
            name = ds.get("name", "").lower()
            code = ds.get("code", "").lower()
            score = sum(name.count(t) for t in q.split()) + sum(code.count(t) for t in q.split())
            if score > 0:
                items.append({**ds, "score": score})
        items.sort(key=lambda x: x["score"], reverse=True)
        return items[:limit]
    
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