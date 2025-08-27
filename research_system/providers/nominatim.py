"""Nominatim provider for OpenStreetMap geocoding and place search."""

import time
import logging
import requests
from typing import List, Dict, Any, Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

# Rate limit: 1 request per second per Nominatim usage policy
RATE_LIMIT = 1.0
last_request_time = 0


def search_places(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search for places using Nominatim.
    
    Args:
        query: Search query (e.g., "beaches in Portland" or "cafes near Central Park")
        limit: Maximum number of results
        
    Returns:
        List of place dictionaries
    """
    global last_request_time
    
    # Rate limiting
    current_time = time.time()
    time_since_last = current_time - last_request_time
    if time_since_last < RATE_LIMIT:
        time.sleep(RATE_LIMIT - time_since_last)
    
    try:
        # Nominatim API endpoint
        url = "https://nominatim.openstreetmap.org/search"
        
        # Parameters
        params = {
            "q": query,
            "format": "json",
            "limit": limit,
            "addressdetails": 1,
            "extratags": 1,
            "namedetails": 1,
            "accept-language": "en"
        }
        
        # Required headers per OSM policy
        headers = {
            "User-Agent": "ResearchAgent/1.0 (https://github.com/research-agent)"
        }
        
        logger.info(f"Nominatim search: {query}")
        response = requests.get(url, params=params, headers=headers, timeout=10)
        last_request_time = time.time()
        
        if response.status_code == 200:
            results = response.json()
            logger.info(f"Nominatim found {len(results)} results")
            return results
        else:
            logger.warning(f"Nominatim error {response.status_code}: {response.text}")
            return []
            
    except Exception as e:
        logger.error(f"Nominatim search failed: {e}")
        return []


def geocode(location: str) -> Optional[Dict[str, Any]]:
    """
    Geocode a location string to coordinates.
    
    Args:
        location: Location name (e.g., "Portland, Oregon")
        
    Returns:
        Location dict with lat/lon or None
    """
    results = search_places(location, limit=1)
    return results[0] if results else None


def to_cards(results: List[Dict[str, Any]], query: str = "") -> List[Dict[str, Any]]:
    """
    Convert Nominatim results to evidence cards.
    
    Args:
        results: Nominatim search results
        query: Original query for context
        
    Returns:
        List of evidence card dictionaries
    """
    cards = []
    
    for r in results:
        # Extract key information
        name = r.get("display_name", "")
        place_type = r.get("type", "").replace("_", " ").title()
        category = r.get("category", "").replace("_", " ").title()
        
        # Build description
        parts = []
        if place_type and place_type != "Yes":
            parts.append(place_type)
        if category and category not in ["Unknown", "Yes"]:
            parts.append(f"({category})")
            
        # Get address details
        addr = r.get("address", {})
        city = addr.get("city") or addr.get("town") or addr.get("village", "")
        state = addr.get("state", "")
        country = addr.get("country", "")
        
        location_parts = [p for p in [city, state, country] if p]
        location = ", ".join(location_parts)
        
        # Extract extra tags for more info
        extratags = r.get("extratags", {})
        opening_hours = extratags.get("opening_hours", "")
        website = extratags.get("website", "")
        phone = extratags.get("phone", "")
        
        # Build snippet
        snippet_parts = [name]
        if parts:
            snippet_parts.append(" - ".join(parts))
        if location:
            snippet_parts.append(f"Location: {location}")
        if opening_hours:
            snippet_parts.append(f"Hours: {opening_hours}")
        if website:
            snippet_parts.append(f"Website: {website}")
        if phone:
            snippet_parts.append(f"Phone: {phone}")
            
        snippet = ". ".join(snippet_parts)[:500]
        
        # Create OSM URL
        osm_type = r.get("osm_type", "node")
        osm_id = r.get("osm_id", "")
        osm_url = f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
        
        # Build card
        card = {
            "title": name[:200] if name else f"{place_type} in {location}"[:200],
            "url": osm_url,
            "snippet": snippet,
            "source_domain": "openstreetmap.org",
            "provider": "nominatim",
            "credibility_score": 0.85,  # OSM data is generally reliable
            "relevance_score": 0.7,
            "confidence": 0.6,
            "is_primary_source": True,
            "metadata": {
                "lat": r.get("lat"),
                "lon": r.get("lon"),
                "place_type": place_type,
                "category": category,
                "location": location
            }
        }
        
        cards.append(card)
    
    return cards


def detect_ambiguity(query: str) -> List[str]:
    """
    Detect geographic ambiguity and suggest clarifications.
    
    Args:
        query: Search query
        
    Returns:
        List of clarified location strings
    """
    # Common ambiguous cities (from third-party review)
    ambiguous = {
        "portland": ["Portland, Oregon", "Portland, Maine"],
        "springfield": ["Springfield, Illinois", "Springfield, Massachusetts", "Springfield, Missouri"],
        "columbus": ["Columbus, Ohio", "Columbus, Georgia"],
        "cambridge": ["Cambridge, Massachusetts", "Cambridge, UK"],
        "oxford": ["Oxford, UK", "Oxford, Mississippi"],
    }
    
    query_lower = query.lower()
    for city, locations in ambiguous.items():
        if city in query_lower and not any(
            state in query_lower 
            for state in ["oregon", "or", "maine", "me", "massachusetts", "ma", "illinois", "il", 
                         "missouri", "mo", "ohio", "oh", "georgia", "ga", "uk", "mississippi", "ms"]
        ):
            logger.info(f"Geographic ambiguity detected for '{city}': {locations}")
            return locations
    
    return []