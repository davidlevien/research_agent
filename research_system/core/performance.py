"""
Performance optimization with caching and connection pooling
"""

import asyncio
import hashlib
import json
import time
from typing import Any, Optional, Dict, List
from dataclasses import dataclass
import redis.asyncio as aioredis
import httpx
from functools import lru_cache

import structlog

logger = structlog.get_logger()


@dataclass
class CacheConfig:
    redis_url: str = "redis://localhost:6379"
    default_ttl: int = 3600
    max_memory_items: int = 1000
    enable_redis: bool = True
    enable_memory: bool = True


# Deprecated: Import CacheManager from data.cache instead
from warnings import warn
warn(
    "research_system.core.performance.CacheManager is deprecated; "
    "use research_system.data.cache.CacheManager",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export for backward compatibility
from research_system.data.cache import CacheManager

# Keep the old multi-tier version as _LegacyCacheManager if needed
class _LegacyCacheManager:
    """Legacy multi-tier caching system - deprecated."""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self.memory_cache: Dict[str, tuple[Any, float]] = {}
        self.redis_client: Optional[aioredis.Redis] = None
        
        if config.enable_redis:
            self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = aioredis.from_url(
                self.config.redis_url,
                decode_responses=True
            )
        except Exception as e:
            logger.warning(f"Redis initialization failed: {e}")
            self.redis_client = None
    
    def _generate_key(self, operation: str, params: Dict) -> str:
        """Generate cache key from operation and parameters."""
        key_data = f"{operation}:{json.dumps(params, sort_keys=True)}"
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    async def get(self, operation: str, params: Dict) -> Optional[Any]:
        """Get from cache (memory first, then Redis)."""
        key = self._generate_key(operation, params)
        
        # Check memory cache
        if self.config.enable_memory and key in self.memory_cache:
            value, expiry = self.memory_cache[key]
            if time.time() < expiry:
                logger.debug(f"Memory cache hit: {operation}")
                return value
            else:
                del self.memory_cache[key]
        
        # Check Redis cache
        if self.config.enable_redis and self.redis_client:
            try:
                value = await self.redis_client.get(key)
                if value:
                    logger.debug(f"Redis cache hit: {operation}")
                    # Store in memory cache too
                    if self.config.enable_memory:
                        self.memory_cache[key] = (
                            json.loads(value),
                            time.time() + 300  # 5 min memory cache
                        )
                    return json.loads(value)
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")
        
        return None
    
    async def set(
        self,
        operation: str,
        params: Dict,
        value: Any,
        ttl: Optional[int] = None
    ):
        """Set in cache (both memory and Redis)."""
        key = self._generate_key(operation, params)
        ttl = ttl or self.config.default_ttl
        
        # Store in memory cache
        if self.config.enable_memory:
            # Implement LRU by removing oldest if at capacity
            if len(self.memory_cache) >= self.config.max_memory_items:
                oldest = min(self.memory_cache.items(), key=lambda x: x[1][1])
                del self.memory_cache[oldest[0]]
            
            self.memory_cache[key] = (value, time.time() + ttl)
        
        # Store in Redis
        if self.config.enable_redis and self.redis_client:
            try:
                await self.redis_client.setex(
                    key,
                    ttl,
                    json.dumps(value, default=str)
                )
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")
    
    async def invalidate(self, operation: str, params: Optional[Dict] = None):
        """Invalidate cache entries."""
        if params:
            key = self._generate_key(operation, params)
            
            # Remove from memory
            self.memory_cache.pop(key, None)
            
            # Remove from Redis
            if self.redis_client:
                await self.redis_client.delete(key)
        else:
            # Invalidate all entries for operation
            # Memory cache
            keys_to_remove = [
                k for k in self.memory_cache.keys()
                if k.startswith(operation)
            ]
            for key in keys_to_remove:
                del self.memory_cache[key]
            
            # Redis (use pattern matching)
            if self.redis_client:
                pattern = f"{operation}:*"
                cursor = 0
                while cursor != 0:
                    cursor, keys = await self.redis_client.scan(
                        cursor, match=pattern
                    )
                    if keys:
                        await self.redis_client.delete(*keys)


class ConnectionPoolManager:
    """HTTP connection pooling for better performance."""
    
    def __init__(self, max_connections: int = 100):
        self.pools: Dict[str, httpx.AsyncClient] = {}
        self.max_connections = max_connections
    
    def get_client(self, base_url: str) -> httpx.AsyncClient:
        """Get or create pooled client for base URL."""
        if base_url not in self.pools:
            self.pools[base_url] = httpx.AsyncClient(
                base_url=base_url,
                limits=httpx.Limits(
                    max_keepalive_connections=20,
                    max_connections=self.max_connections
                ),
                timeout=httpx.Timeout(30.0),
                http2=True  # Enable HTTP/2
            )
        return self.pools[base_url]
    
    async def close_all(self):
        """Close all connection pools."""
        for client in self.pools.values():
            await client.aclose()
        self.pools.clear()


class PerformanceOptimizer:
    """Main performance optimization coordinator."""
    
    def __init__(self, cache_config: Optional[CacheConfig] = None):
        self.cache = CacheManager(cache_config or CacheConfig())
        self.connection_pool = ConnectionPoolManager()
        self.metrics = PerformanceMetrics()
    
    async def cached_operation(
        self,
        operation_name: str,
        operation: callable,
        params: Dict,
        ttl: Optional[int] = None,
        force_refresh: bool = False
    ) -> Any:
        """Execute operation with caching."""
        
        # Check cache unless forced refresh
        if not force_refresh:
            cached = await self.cache.get(operation_name, params)
            if cached is not None:
                self.metrics.record_cache_hit(operation_name)
                return cached
        
        # Execute operation
        self.metrics.record_cache_miss(operation_name)
        start_time = time.time()
        
        try:
            result = await operation(**params)
            
            # Cache result
            await self.cache.set(operation_name, params, result, ttl)
            
            # Record metrics
            duration = time.time() - start_time
            self.metrics.record_operation(operation_name, duration, True)
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            self.metrics.record_operation(operation_name, duration, False)
            raise


class PerformanceMetrics:
    """Performance metrics collection."""
    
    def __init__(self):
        self.operation_times: Dict[str, List[float]] = {}
        self.cache_hits: Dict[str, int] = {}
        self.cache_misses: Dict[str, int] = {}
        self.error_counts: Dict[str, int] = {}
    
    def record_operation(self, name: str, duration: float, success: bool):
        """Record operation metrics."""
        if name not in self.operation_times:
            self.operation_times[name] = []
        
        self.operation_times[name].append(duration)
        
        # Keep only last 100 measurements
        if len(self.operation_times[name]) > 100:
            self.operation_times[name] = self.operation_times[name][-100:]
        
        if not success:
            self.error_counts[name] = self.error_counts.get(name, 0) + 1
    
    def record_cache_hit(self, operation: str):
        """Record cache hit."""
        self.cache_hits[operation] = self.cache_hits.get(operation, 0) + 1
    
    def record_cache_miss(self, operation: str):
        """Record cache miss."""
        self.cache_misses[operation] = self.cache_misses.get(operation, 0) + 1
    
    def get_stats(self, operation: str) -> Dict[str, Any]:
        """Get performance statistics for operation."""
        times = self.operation_times.get(operation, [])
        
        if not times:
            return {"error": "No data for operation"}
        
        return {
            "operation": operation,
            "avg_duration": sum(times) / len(times),
            "min_duration": min(times),
            "max_duration": max(times),
            "cache_hit_rate": self._calculate_cache_hit_rate(operation),
            "error_rate": self._calculate_error_rate(operation),
            "sample_size": len(times)
        }
    
    def _calculate_cache_hit_rate(self, operation: str) -> float:
        """Calculate cache hit rate."""
        hits = self.cache_hits.get(operation, 0)
        misses = self.cache_misses.get(operation, 0)
        total = hits + misses
        
        return hits / total if total > 0 else 0.0
    
    def _calculate_error_rate(self, operation: str) -> float:
        """Calculate error rate."""
        errors = self.error_counts.get(operation, 0)
        total = len(self.operation_times.get(operation, [])) + errors
        
        return errors / total if total > 0 else 0.0