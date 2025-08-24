"""Polite crawling with robots.txt respect and rate limiting."""

import asyncio
import time
import urllib.robotparser as rp
from urllib.parse import urlparse
from collections import defaultdict
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Cache for robots.txt parsers per host
_robots_cache: Dict[str, rp.RobotFileParser] = {}

# Last access time per host for rate limiting
_host_gate: Dict[str, float] = defaultdict(lambda: 0.0)


def allowed(url: str, user_agent: str = "ResearchAgentBot") -> bool:
    """
    Check if URL is allowed according to robots.txt.
    
    Args:
        url: URL to check
        user_agent: User agent string
        
    Returns:
        True if crawling is allowed
    """
    try:
        parsed = urlparse(url)
        host = parsed.netloc
        
        if not host:
            return False
        
        # Check cache
        if host not in _robots_cache:
            robot_parser = rp.RobotFileParser()
            robot_url = f"{parsed.scheme}://{host}/robots.txt"
            robot_parser.set_url(robot_url)
            
            try:
                robot_parser.read()
            except Exception as e:
                # If robots.txt can't be fetched, assume allowed
                logger.debug(f"Could not fetch robots.txt for {host}: {e}")
                robot_parser = None
            
            _robots_cache[host] = robot_parser
        
        robot_parser = _robots_cache[host]
        
        if robot_parser is None:
            # No robots.txt or couldn't fetch it
            return True
            
        return robot_parser.can_fetch(user_agent, url)
        
    except Exception as e:
        logger.warning(f"Error checking robots.txt for {url}: {e}")
        # On error, be conservative and allow
        return True


async def host_throttle(url: str, min_interval: float = 0.8):
    """
    Throttle requests to the same host.
    
    Args:
        url: URL being accessed
        min_interval: Minimum seconds between requests to same host
    """
    try:
        parsed = urlparse(url)
        host = parsed.netloc
        
        if not host:
            return
        
        now = time.time()
        last_access = _host_gate[host]
        
        # Calculate wait time
        wait = max(0.0, (last_access + min_interval) - now)
        
        if wait > 0:
            logger.debug(f"Throttling {host} for {wait:.2f}s")
            await asyncio.sleep(wait)
        
        # Update last access time
        _host_gate[host] = time.time()
        
    except Exception as e:
        logger.warning(f"Error in host throttling for {url}: {e}")


def get_crawl_delay(url: str, user_agent: str = "ResearchAgentBot") -> Optional[float]:
    """
    Get crawl delay from robots.txt if specified.
    
    Args:
        url: URL to check
        user_agent: User agent string
        
    Returns:
        Crawl delay in seconds if specified, None otherwise
    """
    try:
        parsed = urlparse(url)
        host = parsed.netloc
        
        if host in _robots_cache and _robots_cache[host]:
            delay = _robots_cache[host].crawl_delay(user_agent)
            return delay
            
    except Exception:
        pass
        
    return None


def clear_cache():
    """Clear robots.txt cache and rate limit history."""
    global _robots_cache, _host_gate
    _robots_cache.clear()
    _host_gate.clear()


def sync_host_throttle(url: str, min_interval: float = 0.8):
    """
    Synchronous version of host throttling for non-async contexts.
    
    Args:
        url: URL being accessed
        min_interval: Minimum seconds between requests to same host
    """
    try:
        parsed = urlparse(url)
        host = parsed.netloc
        
        if not host:
            return
        
        now = time.time()
        last_access = _host_gate[host]
        
        # Calculate wait time
        wait = max(0.0, (last_access + min_interval) - now)
        
        if wait > 0:
            logger.debug(f"Throttling {host} for {wait:.2f}s")
            time.sleep(wait)
        
        # Update last access time
        _host_gate[host] = time.time()
        
    except Exception as e:
        logger.warning(f"Error in sync host throttling for {url}: {e}")