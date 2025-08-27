"""OSM Tags provider for OpenStreetMap tag-based searches."""

import time
import logging
import requests
from typing import List, Dict, Any, Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

# Rate limit for Overpass API
RATE_LIMIT = 1.0
last_request_time = 0


def search_by_tags(tags: Dict[str, str], bbox: str = None, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Search OpenStreetMap features by tags using Overpass API.
    
    Args:
        tags: Dictionary of OSM tags (e.g., {"amenity": "cafe", "cuisine": "italian"})
        bbox: Bounding box as "south,west,north,east" or None for global
        limit: Maximum number of results
        
    Returns:
        List of OSM features
    """
    global last_request_time
    
    # Rate limiting
    current_time = time.time()
    time_since_last = current_time - last_request_time
    if time_since_last < RATE_LIMIT:
        time.sleep(RATE_LIMIT - time_since_last)
    
    try:
        # Build Overpass QL query
        tag_filters = "".join([f'["{k}"="{v}"]' for k, v in tags.items()])
        
        if bbox:
            bbox_str = f"({bbox})"
        else:
            # Default to a reasonable global search
            bbox_str = "(-90,-180,90,180)"
        
        # Overpass QL query
        query = f"""
        [out:json][timeout:25];
        (
          node{tag_filters}{bbox_str};
          way{tag_filters}{bbox_str};
          relation{tag_filters}{bbox_str};
        );
        out body {limit};
        >;
        out skel qt;
        """
        
        # Use public Overpass API endpoint
        url = "https://overpass-api.de/api/interpreter"
        
        logger.info(f"OSM tags search: {tags}")
        response = requests.post(url, data={"data": query}, timeout=30)
        last_request_time = time.time()
        
        if response.status_code == 200:
            data = response.json()
            elements = data.get("elements", [])
            logger.info(f"OSM tags found {len(elements)} elements")
            return elements
        else:
            logger.warning(f"Overpass API error {response.status_code}: {response.text}")
            return []
            
    except Exception as e:
        logger.error(f"OSM tags search failed: {e}")
        return []


def search_amenities(amenity_type: str, location: str = None, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Search for amenities of a specific type.
    
    Args:
        amenity_type: Type of amenity (e.g., "cafe", "restaurant", "hospital")
        location: Optional location name to search near
        limit: Maximum results
        
    Returns:
        List of amenities
    """
    tags = {"amenity": amenity_type}
    
    # If location provided, try to get bounding box
    bbox = None
    if location:
        # Use Nominatim to geocode and get bbox
        from .nominatim import geocode
        geo = geocode(location)
        if geo and "boundingbox" in geo:
            bb = geo["boundingbox"]
            # Convert from [south, north, west, east] to "south,west,north,east"
            bbox = f"{bb[0]},{bb[2]},{bb[1]},{bb[3]}"
    
    return search_by_tags(tags, bbox, limit)


def search_tourism(tourism_type: str, location: str = None, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Search for tourism features.
    
    Args:
        tourism_type: Type of tourism feature (e.g., "hotel", "attraction", "museum")
        location: Optional location name
        limit: Maximum results
        
    Returns:
        List of tourism features
    """
    tags = {"tourism": tourism_type}
    
    bbox = None
    if location:
        from .nominatim import geocode
        geo = geocode(location)
        if geo and "boundingbox" in geo:
            bb = geo["boundingbox"]
            bbox = f"{bb[0]},{bb[2]},{bb[1]},{bb[3]}"
    
    return search_by_tags(tags, bbox, limit)


def search_natural(natural_type: str, location: str = None, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Search for natural features.
    
    Args:
        natural_type: Type of natural feature (e.g., "beach", "park", "water")
        location: Optional location name
        limit: Maximum results
        
    Returns:
        List of natural features
    """
    tags = {"natural": natural_type}
    
    bbox = None
    if location:
        from .nominatim import geocode
        geo = geocode(location)
        if geo and "boundingbox" in geo:
            bb = geo["boundingbox"]
            bbox = f"{bb[0]},{bb[2]},{bb[1]},{bb[3]}"
    
    return search_by_tags(tags, bbox, limit)


def to_cards(elements: List[Dict[str, Any]], query: str = "") -> List[Dict[str, Any]]:
    """
    Convert OSM elements to evidence cards.
    
    Args:
        elements: OSM elements from Overpass API
        query: Original query
        
    Returns:
        List of evidence card dictionaries
    """
    cards = []
    
    for elem in elements:
        if elem.get("type") not in ["node", "way", "relation"]:
            continue
            
        tags = elem.get("tags", {})
        if not tags:
            continue
        
        # Extract name and key attributes
        name = tags.get("name", "")
        amenity = tags.get("amenity", "")
        tourism = tags.get("tourism", "")
        natural = tags.get("natural", "")
        shop = tags.get("shop", "")
        
        # Determine feature type
        feature_types = []
        if amenity:
            feature_types.append(f"Amenity: {amenity}")
        if tourism:
            feature_types.append(f"Tourism: {tourism}")
        if natural:
            feature_types.append(f"Natural: {natural}")
        if shop:
            feature_types.append(f"Shop: {shop}")
        
        feature_type = ", ".join(feature_types) if feature_types else "Location"
        
        # Build title
        if name:
            title = f"{name} ({feature_type})"
        else:
            title = feature_type
        
        # Build snippet from tags
        snippet_parts = []
        
        # Add description if available
        if tags.get("description"):
            snippet_parts.append(tags["description"])
        
        # Add address info
        addr_parts = []
        for k in ["addr:street", "addr:housenumber", "addr:city", "addr:state", "addr:country"]:
            if tags.get(k):
                addr_parts.append(tags[k])
        if addr_parts:
            snippet_parts.append(f"Address: {' '.join(addr_parts)}")
        
        # Add contact info
        if tags.get("phone"):
            snippet_parts.append(f"Phone: {tags['phone']}")
        if tags.get("website"):
            snippet_parts.append(f"Website: {tags['website']}")
        if tags.get("opening_hours"):
            snippet_parts.append(f"Hours: {tags['opening_hours']}")
        
        # Add special attributes
        if tags.get("cuisine"):
            snippet_parts.append(f"Cuisine: {tags['cuisine']}")
        if tags.get("wheelchair"):
            snippet_parts.append(f"Wheelchair access: {tags['wheelchair']}")
        if tags.get("internet_access"):
            snippet_parts.append(f"Internet: {tags['internet_access']}")
        
        snippet = ". ".join(snippet_parts)[:500] if snippet_parts else f"{title} on OpenStreetMap"
        
        # Build OSM URL
        osm_type = elem.get("type", "node")
        osm_id = elem.get("id", "")
        url = f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
        
        card = {
            "title": title[:200],
            "url": url,
            "snippet": snippet,
            "source_domain": "openstreetmap.org",
            "provider": "osmtags",
            "credibility_score": 0.85,
            "relevance_score": 0.7,
            "confidence": 0.6,
            "is_primary_source": True,
            "metadata": {
                "osm_type": osm_type,
                "osm_id": osm_id,
                "tags": tags,
                "lat": elem.get("lat"),
                "lon": elem.get("lon")
            }
        }
        
        cards.append(card)
    
    return cards


def parse_query(query: str) -> Dict[str, str]:
    """
    Parse a natural language query into OSM tags.
    
    Args:
        query: Natural language query
        
    Returns:
        Dictionary of OSM tags
    """
    query_lower = query.lower()
    tags = {}
    
    # Amenity mappings
    amenity_keywords = {
        "cafe": "cafe",
        "coffee": "cafe",
        "restaurant": "restaurant",
        "hospital": "hospital",
        "school": "school",
        "bank": "bank",
        "atm": "atm",
        "pharmacy": "pharmacy",
        "gas station": "fuel",
        "parking": "parking",
        "library": "library",
        "police": "police",
        "fire station": "fire_station",
        "post office": "post_office"
    }
    
    # Tourism mappings
    tourism_keywords = {
        "hotel": "hotel",
        "motel": "motel",
        "hostel": "hostel",
        "museum": "museum",
        "attraction": "attraction",
        "viewpoint": "viewpoint",
        "information": "information",
        "camp": "camp_site",
        "camping": "camp_site"
    }
    
    # Natural mappings
    natural_keywords = {
        "beach": "beach",
        "forest": "wood",
        "park": "park",
        "water": "water",
        "lake": "water",
        "mountain": "peak",
        "valley": "valley",
        "cliff": "cliff"
    }
    
    # Check for amenity keywords
    for keyword, tag_value in amenity_keywords.items():
        if keyword in query_lower:
            tags["amenity"] = tag_value
            break
    
    # Check for tourism keywords
    if not tags:
        for keyword, tag_value in tourism_keywords.items():
            if keyword in query_lower:
                tags["tourism"] = tag_value
                break
    
    # Check for natural keywords
    if not tags:
        for keyword, tag_value in natural_keywords.items():
            if keyword in query_lower:
                tags["natural"] = tag_value
                break
    
    # Default to amenity=* for general searches
    if not tags and any(word in query_lower for word in ["near", "in", "around", "places"]):
        tags["amenity"] = "*"
    
    return tags