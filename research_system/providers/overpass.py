"""Overpass API provider for OpenStreetMap data."""

from __future__ import annotations
from typing import List, Dict, Any
import httpx
from urllib.parse import quote
from .http import DEFAULT_TIMEOUT, RETRY_STATUSES
import time
import logging

logger = logging.getLogger(__name__)

# v8.20.0: Multiple Overpass API mirrors for fallback
_OVERPASS_URLS = [
    "https://overpass.kumi.systems/api/interpreter",  # Fast mirror
    "https://z.overpass-api.de/api/interpreter",      # German mirror
    "https://overpass-api.de/api/interpreter",        # Main instance (often slow)
]
_last_call = 0

def overpass_search(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Conservative global POI search on OpenStreetMap.
    Enforces 1 request per second rate limit.
    """
    global _last_call
    
    # Enforce 1-second minimum between requests
    now = time.time()
    if _last_call > 0:
        elapsed = now - _last_call
        if elapsed < 1:
            time.sleep(1 - elapsed)
    _last_call = time.time()
    
    q = query.strip()
    if not q:
        return []
    
    # Use case-insensitive regex on 'name' for tourism/transport POIs
    # Be conservative to avoid overloading the service
    overpass_q = f"""
    [out:json][timeout:10];
    (
      node["name"~"{quote(q)}",i]["tourism"];
      node["name"~"{quote(q)}",i]["amenity"~"airport|train_station|bus_station"];
    );
    out {limit};
    """
    
    # v8.20.0: Try each mirror in order until one works
    last_error = None
    js = None
    
    for overpass_url in _OVERPASS_URLS:
        try:
            logger.debug(f"Trying Overpass mirror: {overpass_url}")
            with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
                r = client.post(overpass_url, data={"data": overpass_q})
                if r.status_code in RETRY_STATUSES:
                    time.sleep(1)  # Respect rate limit on retry
                    r = client.post(overpass_url, data={"data": overpass_q})
                    _last_call = time.time()
                r.raise_for_status()
                js = r.json()
                logger.info(f"Overpass search successful via {overpass_url}")
                break  # Success, exit loop
        except Exception as e:
            last_error = e
            logger.debug(f"Overpass mirror {overpass_url} failed: {e}")
            continue
    
    if js is None:
        # All mirrors failed
        logger.warning(f"All Overpass mirrors failed: {last_error}")
        return []
    
    els = js.get("elements", [])[:limit]
    out = []
    
    for e in els:
        lat, lon = e.get("lat"), e.get("lon")
        tags = e.get("tags", {})
        name = tags.get("name") or "OSM Feature"
        
        # Build description from tags
        feature_type = tags.get("tourism") or tags.get("amenity", "")
        description = f"{feature_type} at {lat:.6f}, {lon:.6f}" if lat and lon else feature_type
        
        url = f"https://www.openstreetmap.org/{e.get('type', 'node')}/{e.get('id', '')}"
        
        out.append({
            "title": name,
            "url": url,
            "snippet": description,
            "source_domain": "openstreetmap.org",
            "metadata": {
                "provider": "overpass",
                "lat": lat,
                "lon": lon,
                "tags": tags
            }
        })
    
    return out

def to_cards(rows: List[Dict[str, Any]]) -> List[dict]:
    """Convert Overpass results to evidence cards."""
    return [
        {
            "title": r["title"],
            "url": r["url"],
            "snippet": r.get("snippet", ""),
            "source_domain": "openstreetmap.org",
            "metadata": {
                **r.get("metadata", {}),
                "license": "ODbL 1.0"  # OpenStreetMap license
            }
        }
        for r in rows
    ]