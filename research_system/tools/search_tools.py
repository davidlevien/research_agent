"""
Search tools for evidence collection
"""

import asyncio
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from ..config import Settings
from ..exceptions import APIError, RateLimitError
from .registry import get_registry

logger = logging.getLogger(__name__)


class SearchTools:
    """Collection of search tools"""
    
    def __init__(self, config: Settings):
        self.config = config
        self._register_tools()
    
    def _register_tools(self):
        """Register all search tools"""
        tool_registry.register(
            name="tavily_search",
            description="Search using Tavily API",
            category="search",
            function=self.tavily_search,
            requires_api_key=True,
            cost_per_use=0.001,
            rate_limit=60
        )
        
        tool_registry.register(
            name="serper_search",
            description="Search using Serper API",
            category="search",
            function=self.serper_search,
            requires_api_key=True,
            cost_per_use=0.002,
            rate_limit=100
        )
        
        tool_registry.register(
            name="multi_search",
            description="Search using multiple providers",
            category="search",
            function=self.multi_search,
            requires_api_key=True,
            cost_per_use=0.005
        )
    
    async def tavily_search(
        self,
        query: str,
        max_results: int = 10,
        search_depth: str = "basic",
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Search using Tavily API"""
        
        if not self.config.api.tavily_key:
            raise APIError("Tavily API key not configured", provider="tavily")
        
        url = "https://api.tavily.com/search"
        
        payload = {
            "api_key": self.config.api.tavily_key,
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_answer": True,
            "include_raw_content": True
        }
        
        if include_domains:
            payload["include_domains"] = include_domains
        if exclude_domains:
            payload["exclude_domains"] = exclude_domains
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=30)
                
                if response.status_code == 429:
                    raise RateLimitError("Tavily rate limit exceeded", provider="tavily")
                
                response.raise_for_status()
                data = response.json()
                
                return self._process_tavily_results(data.get("results", []))
                
        except httpx.HTTPError as e:
            logger.error(f"Tavily search failed: {e}")
            raise APIError(f"Tavily search failed: {e}", provider="tavily")
    
    async def serper_search(
        self,
        query: str,
        num: int = 10,
        gl: str = "us",
        hl: str = "en"
    ) -> List[Dict[str, Any]]:
        """Search using Serper API"""
        
        if not self.config.api.serper_key:
            raise APIError("Serper API key not configured", provider="serper")
        
        url = "https://google.serper.dev/search"
        
        headers = {
            "X-API-KEY": self.config.api.serper_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "q": query,
            "num": num,
            "gl": gl,
            "hl": hl
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code == 429:
                    raise RateLimitError("Serper rate limit exceeded", provider="serper")
                
                response.raise_for_status()
                data = response.json()
                
                return self._process_serper_results(data.get("organic", []))
                
        except httpx.HTTPError as e:
            logger.error(f"Serper search failed: {e}")
            raise APIError(f"Serper search failed: {e}", provider="serper")
    
    async def multi_search(
        self,
        query: str,
        providers: Optional[List[str]] = None,
        max_results_per_provider: int = 5
    ) -> List[Dict[str, Any]]:
        """Search using multiple providers concurrently"""
        
        if providers is None:
            providers = ["tavily", "serper"]
        
        tasks = []
        
        if "tavily" in providers and self.config.api.tavily_key:
            tasks.append(self.tavily_search(query, max_results_per_provider))
        
        if "serper" in providers and self.config.api.serper_key:
            tasks.append(self.serper_search(query, max_results_per_provider))
        
        if not tasks:
            raise APIError("No search providers available")
        
        # Execute searches concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine results
        combined_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Search provider failed: {result}")
                continue
            combined_results.extend(result)
        
        # Deduplicate by URL
        seen_urls = set()
        unique_results = []
        for result in combined_results:
            if result["url"] not in seen_urls:
                seen_urls.add(result["url"])
                unique_results.append(result)
        
        return unique_results[:max_results_per_provider * len(providers)]
    
    def _process_tavily_results(self, results: List[Dict]) -> List[Dict[str, Any]]:
        """Process Tavily search results"""
        processed = []
        
        for result in results:
            processed.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("content", ""),
                "raw_content": result.get("raw_content", ""),
                "score": result.get("score", 0.5),
                "provider": "tavily",
                "collected_at": datetime.utcnow().isoformat()
            })
        
        return processed
    
    def _process_serper_results(self, results: List[Dict]) -> List[Dict[str, Any]]:
        """Process Serper search results"""
        processed = []
        
        for i, result in enumerate(results):
            processed.append({
                "title": result.get("title", ""),
                "url": result.get("link", ""),
                "snippet": result.get("snippet", ""),
                "raw_content": "",  # Serper doesn't provide raw content
                "score": 1.0 - (i * 0.05),  # Rank-based scoring
                "provider": "serper",
                "collected_at": datetime.utcnow().isoformat()
            })
        
        return processed


async def search_with_single_provider(query: str, provider: str = "tavily") -> List[Dict]:
    """Fallback search with single provider"""
    from ..config import config
    tools = SearchTools(config)
    
    if provider == "tavily":
        return await tools.tavily_search(query, max_results=5)
    elif provider == "serper":
        return await tools.serper_search(query, num=5)
    else:
        raise ValueError(f"Unknown provider: {provider}")