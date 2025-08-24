"""Domain reputation baseline using Tranco rankings."""

import os
import csv
from typing import Optional, Dict
from functools import lru_cache

# Cache for loaded rankings
_tranco_cache: Optional[Dict[str, int]] = None


def load_tranco_rankings(filepath: str = "data/tranco_top1m.csv") -> Dict[str, int]:
    """
    Load Tranco rankings from CSV file.
    
    Expected format: rank,domain
    
    Args:
        filepath: Path to Tranco CSV file
        
    Returns:
        Dictionary mapping domain to rank
    """
    global _tranco_cache
    
    if _tranco_cache is not None:
        return _tranco_cache
    
    rankings = {}
    
    if not os.path.exists(filepath):
        # Return empty dict if file doesn't exist
        _tranco_cache = {}
        return _tranco_cache
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    try:
                        rank = int(row[0])
                        domain = row[1].strip().lower()
                        rankings[domain] = rank
                    except (ValueError, IndexError):
                        continue
    except Exception:
        pass
    
    _tranco_cache = rankings
    return rankings


@lru_cache(maxsize=1024)
def tranco_rank(domain: str, filepath: str = "data/tranco_top1m.csv") -> Optional[int]:
    """
    Get Tranco rank for a domain.
    
    Args:
        domain: Domain name
        filepath: Path to Tranco CSV file
        
    Returns:
        Rank if found, None otherwise
    """
    rankings = load_tranco_rankings(filepath)
    return rankings.get(domain.lower())


@lru_cache(maxsize=1024)
def popularity_prior(domain: str, filepath: str = "data/tranco_top1m.csv") -> float:
    """
    Calculate popularity-based credibility prior for a domain.
    
    Maps Tranco rank to a credibility score between 0.55 and 0.8.
    Higher rank (lower number) = higher credibility.
    
    Args:
        domain: Domain name
        filepath: Path to Tranco CSV file
        
    Returns:
        Credibility prior between 0.5 and 0.8
    """
    rank = tranco_rank(domain, filepath)
    
    if not rank:
        # Unknown domain gets neutral prior
        return 0.5
    
    # Map rank to credibility
    # Top 1K: 0.8
    # Top 10K: 0.75
    # Top 100K: 0.7
    # Top 500K: 0.6
    # Rest: 0.55
    
    if rank <= 1000:
        return 0.8
    elif rank <= 10000:
        return 0.75
    elif rank <= 100000:
        return 0.7
    elif rank <= 500000:
        return 0.6
    else:
        # Linear decay from 0.6 to 0.55 for ranks 500K to 1M
        return max(0.55, 0.6 - (min(rank, 1000000) - 500000) / 1000000)


def is_reputable_domain(domain: str, min_rank: int = 100000) -> bool:
    """
    Check if a domain is considered reputable based on Tranco ranking.
    
    Args:
        domain: Domain name
        min_rank: Maximum rank to be considered reputable
        
    Returns:
        True if domain rank is below min_rank
    """
    rank = tranco_rank(domain)
    return rank is not None and rank <= min_rank


def download_tranco_list(output_path: str = "data/tranco_top1m.csv"):
    """
    Download the latest Tranco list.
    
    Note: This is a placeholder. In production, you would:
    1. Fetch the latest list ID from https://tranco-list.eu/api/lists/date/today
    2. Download from https://tranco-list.eu/download/{list_id}/1000000
    
    Args:
        output_path: Where to save the CSV
    """
    import httpx
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    try:
        # Get latest list ID
        r = httpx.get("https://tranco-list.eu/api/lists/date/today", timeout=30)
        if r.status_code != 200:
            return False
            
        list_info = r.json()
        list_id = list_info.get("list_id")
        
        if not list_id:
            return False
        
        # Download top 1M
        url = f"https://tranco-list.eu/download/{list_id}/1000000"
        r = httpx.get(url, timeout=60)
        
        if r.status_code != 200:
            return False
        
        # Save to file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(r.text)
        
        # Clear cache
        global _tranco_cache
        _tranco_cache = None
        tranco_rank.cache_clear()
        popularity_prior.cache_clear()
        
        return True
        
    except Exception:
        return False