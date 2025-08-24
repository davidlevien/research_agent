"""Geographic normalization using ISO-3166 country codes."""

from typing import Optional, Dict, List

# Manual mapping for common countries/regions to avoid pycountry dependency
# ISO-3166 alpha-3 codes
COUNTRY_MAP: Dict[str, str] = {
    # Major countries
    "united states": "USA",
    "usa": "USA",
    "u.s.": "USA",
    "u.s": "USA",
    "us": "USA",
    "america": "USA",
    "united states of america": "USA",
    
    "united kingdom": "GBR",
    "uk": "GBR",
    "u.k.": "GBR",
    "great britain": "GBR",
    "britain": "GBR",
    "england": "GBR",
    
    "china": "CHN",
    "people's republic of china": "CHN",
    "prc": "CHN",
    "mainland china": "CHN",
    
    "germany": "DEU",
    "deutschland": "DEU",
    "federal republic of germany": "DEU",
    
    "france": "FRA",
    "french republic": "FRA",
    
    "japan": "JPN",
    "nippon": "JPN",
    
    "italy": "ITA",
    "italia": "ITA",
    
    "spain": "ESP",
    "españa": "ESP",
    
    "canada": "CAN",
    
    "australia": "AUS",
    
    "india": "IND",
    "bharat": "IND",
    
    "brazil": "BRA",
    "brasil": "BRA",
    
    "russia": "RUS",
    "russian federation": "RUS",
    
    "mexico": "MEX",
    "méxico": "MEX",
    
    "south korea": "KOR",
    "korea": "KOR",
    "republic of korea": "KOR",
    "rok": "KOR",
    
    "saudi arabia": "SAU",
    "ksa": "SAU",
    "kingdom of saudi arabia": "SAU",
    
    "uae": "ARE",
    "united arab emirates": "ARE",
    "emirates": "ARE",
    
    "singapore": "SGP",
    
    "thailand": "THA",
    
    "indonesia": "IDN",
    
    "turkey": "TUR",
    "türkiye": "TUR",
    
    "south africa": "ZAF",
    "rsa": "ZAF",
    
    "egypt": "EGY",
    
    "argentina": "ARG",
    
    "netherlands": "NLD",
    "holland": "NLD",
    
    "switzerland": "CHE",
    
    "sweden": "SWE",
    
    "norway": "NOR",
    
    "denmark": "DNK",
    
    "finland": "FIN",
    
    "belgium": "BEL",
    
    "austria": "AUT",
    
    "greece": "GRC",
    
    "portugal": "PRT",
    
    "poland": "POL",
    
    "israel": "ISR",
    
    "new zealand": "NZL",
    "nz": "NZL",
}

# Region mappings
REGION_MAP: Dict[str, List[str]] = {
    "europe": ["DEU", "FRA", "ITA", "ESP", "GBR", "NLD", "BEL", "CHE", "AUT", 
               "SWE", "NOR", "DNK", "FIN", "GRC", "PRT", "POL"],
    
    "asia_pacific": ["CHN", "JPN", "KOR", "IND", "IDN", "THA", "SGP", "AUS", "NZL"],
    
    "americas": ["USA", "CAN", "MEX", "BRA", "ARG"],
    
    "middle_east": ["SAU", "ARE", "ISR", "TUR", "EGY"],
    
    "africa": ["ZAF", "EGY", "KEN", "NGA", "MAR"],
    
    "g7": ["USA", "CAN", "GBR", "DEU", "FRA", "ITA", "JPN"],
    
    "g20": ["USA", "CAN", "MEX", "BRA", "ARG", "GBR", "DEU", "FRA", "ITA",
            "RUS", "TUR", "SAU", "ZAF", "IND", "CHN", "JPN", "KOR", "IDN", "AUS"],
    
    "eu": ["DEU", "FRA", "ITA", "ESP", "NLD", "BEL", "AUT", "GRC", "PRT", "POL",
           "SWE", "DNK", "FIN"],
    
    "asean": ["IDN", "THA", "SGP", "MYS", "PHL", "VNM"],
}


def to_iso3(name: Optional[str]) -> Optional[str]:
    """
    Convert country name to ISO-3166 alpha-3 code.
    
    Args:
        name: Country name
        
    Returns:
        ISO-3166 alpha-3 code if found, None otherwise
    """
    if not name:
        return None
        
    # Normalize input
    normalized = name.strip().lower()
    
    # Direct lookup
    return COUNTRY_MAP.get(normalized)


def get_region(iso3: str) -> Optional[str]:
    """
    Get region for an ISO-3 country code.
    
    Args:
        iso3: ISO-3166 alpha-3 code
        
    Returns:
        Region name if found
    """
    for region, countries in REGION_MAP.items():
        if iso3 in countries:
            return region
    return None


def countries_in_region(region: str) -> List[str]:
    """
    Get list of ISO-3 codes for countries in a region.
    
    Args:
        region: Region name
        
    Returns:
        List of ISO-3 country codes
    """
    return REGION_MAP.get(region.lower(), [])


def normalize_location(text: str) -> tuple[Optional[str], Optional[str]]:
    """
    Extract and normalize location from text.
    
    Args:
        text: Text potentially containing location
        
    Returns:
        Tuple of (iso3_code, region)
    """
    text_lower = text.lower()
    
    # Check for country mentions
    for country_name, iso3 in COUNTRY_MAP.items():
        if country_name in text_lower:
            region = get_region(iso3)
            return iso3, region
    
    # Check for region mentions
    for region in REGION_MAP.keys():
        if region.replace("_", " ") in text_lower:
            return None, region
            
    return None, None