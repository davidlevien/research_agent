# research_system/data/cache.py
"""
Redis cache management
"""

import asyncio
import json
import time
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
import redis.asyncio as aioredis
import structlog

logger = structlog.get_logger()


class CacheManager:
    """Redis cache management system"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.redis_client: Optional[aioredis.Redis] = None
        self.default_ttl = config.get("default_ttl", 3600)
        self.max_memory_mb = config.get("max_memory_mb", 500)
        self._setup_redis()
    
    def _setup_redis(self):
        """Setup Redis connection"""
        
        redis_url = self.config.get("redis_url")
        if not redis_url:
            logger.warning("Redis URL not configured, cache disabled")
            return
        
        try:
            self.redis_client = aioredis.from_url(
                redis_url,
                decode_responses=True,
                max_connections=50,
                retry_on_timeout=True,
                health_check_interval=30
            )
            logger.info(f"Redis cache initialized: {redis_url}")
        except Exception as e:
            logger.error(f"Redis initialization failed: {e}")
            self.redis_client = None
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        
        if not self.redis_client:
            return None
        
        try:
            value = await self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get failed: {key}, Error: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        
        if not self.redis_client:
            return False
        
        try:
            ttl = ttl or self.default_ttl
            serialized_value = json.dumps(value, default=str)
            await self.redis_client.setex(key, ttl, serialized_value)
            return True
        except Exception as e:
            logger.error(f"Cache set failed: {key}, Error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        
        if not self.redis_client:
            return False
        
        try:
            result = await self.redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Cache delete failed: {key}, Error: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        
        if not self.redis_client:
            return False
        
        try:
            result = await self.redis_client.exists(key)
            return result > 0
        except Exception as e:
            logger.error(f"Cache exists check failed: {key}, Error: {e}")
            return False
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration for key"""
        
        if not self.redis_client:
            return False
        
        try:
            result = await self.redis_client.expire(key, ttl)
            return result
        except Exception as e:
            logger.error(f"Cache expire failed: {key}, Error: {e}")
            return False
    
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache"""
        
        if not self.redis_client:
            return {}
        
        try:
            values = await self.redis_client.mget(keys)
            result = {}
            for key, value in zip(keys, values):
                if value:
                    result[key] = json.loads(value)
            return result
        except Exception as e:
            logger.error(f"Cache get_many failed: {keys}, Error: {e}")
            return {}
    
    async def set_many(self, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set multiple values in cache"""
        
        if not self.redis_client:
            return False
        
        try:
            ttl = ttl or self.default_ttl
            
            # Serialize all values
            serialized_data = {
                key: json.dumps(value, default=str)
                for key, value in data.items()
            }
            
            # Use pipeline for atomic operations
            async with self.redis_client.pipeline(transaction=True) as pipe:
                for key, value in serialized_data.items():
                    pipe.setex(key, ttl, value)
                await pipe.execute()
            
            return True
        except Exception as e:
            logger.error(f"Cache set_many failed: Error: {e}")
            return False
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment counter in cache"""
        
        if not self.redis_client:
            return None
        
        try:
            result = await self.redis_client.incrby(key, amount)
            return result
        except Exception as e:
            logger.error(f"Cache increment failed: {key}, Error: {e}")
            return None
    
    async def decrement(self, key: str, amount: int = 1) -> Optional[int]:
        """Decrement counter in cache"""
        
        if not self.redis_client:
            return None
        
        try:
            result = await self.redis_client.decrby(key, amount)
            return result
        except Exception as e:
            logger.error(f"Cache decrement failed: {key}, Error: {e}")
            return None
    
    async def get_ttl(self, key: str) -> Optional[int]:
        """Get TTL for key"""
        
        if not self.redis_client:
            return None
        
        try:
            ttl = await self.redis_client.ttl(key)
            return ttl if ttl >= 0 else None
        except Exception as e:
            logger.error(f"Cache get_ttl failed: {key}, Error: {e}")
            return None
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        
        if not self.redis_client:
            return 0
        
        try:
            keys = []
            async for key in self.redis_client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                result = await self.redis_client.delete(*keys)
                return result
            return 0
        except Exception as e:
            logger.error(f"Cache clear_pattern failed: {pattern}, Error: {e}")
            return 0
    
    async def get_memory_usage(self) -> Optional[Dict[str, Any]]:
        """Get Redis memory usage statistics"""
        
        if not self.redis_client:
            return None
        
        try:
            info = await self.redis_client.info("memory")
            return {
                "used_memory": info.get("used_memory", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "used_memory_peak": info.get("used_memory_peak", 0),
                "used_memory_peak_human": info.get("used_memory_peak_human", "0B"),
                "memory_fragmentation_ratio": info.get("mem_fragmentation_ratio", 1.0),
                "max_memory_configured": self.max_memory_mb * 1024 * 1024
            }
        except Exception as e:
            logger.error(f"Cache get_memory_usage failed: Error: {e}")
            return None
    
    async def health_check(self) -> bool:
        """Check Redis health"""
        
        if not self.redis_client:
            return False
        
        try:
            await self.redis_client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False
    
    async def close(self):
        """Close Redis connection"""
        
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis connection closed")


class CacheKeyBuilder:
    """Helper class for building cache keys"""
    
    @staticmethod
    def research_request(request_id: str) -> str:
        """Build cache key for research request"""
        return f"research:request:{request_id}"
    
    @staticmethod
    def evidence_card(evidence_id: str) -> str:
        """Build cache key for evidence card"""
        return f"research:evidence:{evidence_id}"
    
    @staticmethod
    def search_results(query: str, provider: str) -> str:
        """Build cache key for search results"""
        import hashlib
        query_hash = hashlib.md5(query.encode()).hexdigest()
        return f"search:{provider}:{query_hash}"
    
    @staticmethod
    def api_response(provider: str, endpoint: str, params: Dict[str, Any]) -> str:
        """Build cache key for API response"""
        import hashlib
        params_str = json.dumps(params, sort_keys=True)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()
        return f"api:{provider}:{endpoint}:{params_hash}"
    
    @staticmethod
    def rate_limit(user_id: str, operation: str) -> str:
        """Build cache key for rate limiting"""
        return f"ratelimit:{user_id}:{operation}"
    
    @staticmethod
    def cost_tracker(date: str) -> str:
        """Build cache key for cost tracking"""
        return f"cost:daily:{date}"


class CachedOperation:
    """Decorator for caching function results"""
    
    def __init__(self, cache_manager: CacheManager, ttl: int = 3600):
        self.cache_manager = cache_manager
        self.ttl = ttl
    
    def __call__(self, func):
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = self._generate_cache_key(func.__name__, args, kwargs)
            
            # Try to get from cache
            cached_value = await self.cache_manager.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Store in cache
            await self.cache_manager.set(cache_key, result, self.ttl)
            logger.debug(f"Cache miss, stored: {cache_key}")
            
            return result
        
        return wrapper
    
    def _generate_cache_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """Generate cache key from function name and arguments"""
        import hashlib
        
        # Serialize arguments
        args_str = json.dumps({
            "args": args,
            "kwargs": kwargs
        }, sort_keys=True, default=str)
        
        # Hash arguments
        args_hash = hashlib.md5(args_str.encode()).hexdigest()
        
        return f"func:{func_name}:{args_hash}"


# Global cache manager instance
cache_manager = None


def init_cache(config: Dict[str, Any]):
    """Initialize global cache"""
    global cache_manager
    cache_manager = CacheManager(config)
    return cache_manager


def get_cache_manager():
    """Get global cache manager"""
    return cache_manager