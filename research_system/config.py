"""
Configuration management
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from dotenv import load_dotenv
import jsonschema
import yaml

# Load environment variables
load_dotenv()


@dataclass
class APIConfig:
    """API configuration"""
    openai_key: Optional[str] = None
    anthropic_key: Optional[str] = None
    tavily_key: Optional[str] = None
    serper_key: Optional[str] = None
    serpapi_key: Optional[str] = None


@dataclass
class DatabaseConfig:
    """Database configuration"""
    url: str = "postgresql://localhost:5432/research"
    pool_size: int = 20
    max_overflow: int = 0


@dataclass
class RedisConfig:
    """Redis configuration"""
    url: str = "redis://localhost:6379"
    ttl: int = 3600
    max_connections: int = 50


@dataclass
class RateLimitConfig:
    """Rate limiting configuration"""
    max_requests_per_minute: int = 60
    max_concurrent_requests: int = 10


@dataclass
class CostConfig:
    """Cost management configuration"""
    max_cost_per_request_usd: float = 1.0
    max_daily_cost_usd: float = 100.0
    alert_threshold: float = 0.8


@dataclass
class PerformanceConfig:
    """Performance configuration"""
    cache_ttl_seconds: int = 3600
    max_cache_memory_mb: int = 500
    enable_redis_cache: bool = True
    enable_memory_cache: bool = True


@dataclass
class SecurityConfig:
    """Security configuration"""
    enable_encryption: bool = True
    enable_sanitization: bool = True
    enable_privacy: bool = True
    allowed_domains: list = field(default_factory=list)
    blocked_patterns: list = field(default_factory=list)


@dataclass
class MonitoringConfig:
    """Monitoring configuration"""
    prometheus_endpoint: str = "http://localhost:9090"
    jaeger_endpoint: str = "http://localhost:4317"
    grafana_url: str = "http://localhost:3000"
    log_level: str = "INFO"
    log_format: str = "json"


class Config:
    """Main configuration class"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        
        # Load configurations
        self.api = self._load_api_config()
        self.database = self._load_database_config()
        self.redis = self._load_redis_config()
        self.rate_limits = self._load_rate_limit_config()
        self.cost_management = self._load_cost_config()
        self.performance = self._load_performance_config()
        self.security = self._load_security_config()
        self.monitoring = self._load_monitoring_config()
        
        # Load from file if provided
        if config_path:
            self._load_from_file(config_path)
        
        # Validate configuration
        self._validate_config()
    
    def _load_api_config(self) -> APIConfig:
        """Load API configuration from environment"""
        return APIConfig(
            openai_key=os.getenv("OPENAI_API_KEY"),
            anthropic_key=os.getenv("ANTHROPIC_API_KEY"),
            tavily_key=os.getenv("TAVILY_API_KEY"),
            serper_key=os.getenv("SERPER_API_KEY"),
            serpapi_key=os.getenv("SERPAPI_API_KEY")
        )
    
    def _load_database_config(self) -> DatabaseConfig:
        """Load database configuration"""
        return DatabaseConfig(
            url=os.getenv("DATABASE_URL", "postgresql://localhost:5432/research"),
            pool_size=int(os.getenv("DB_POOL_SIZE", "20"))
        )
    
    def _load_redis_config(self) -> RedisConfig:
        """Load Redis configuration"""
        return RedisConfig(
            url=os.getenv("REDIS_URL", "redis://localhost:6379"),
            ttl=int(os.getenv("CACHE_TTL_SECONDS", "3600"))
        )
    
    def _load_rate_limit_config(self) -> RateLimitConfig:
        """Load rate limit configuration"""
        return RateLimitConfig(
            max_requests_per_minute=int(os.getenv("MAX_REQUESTS_PER_MINUTE", "60")),
            max_concurrent_requests=int(os.getenv("MAX_CONCURRENT_REQUESTS", "10"))
        )
    
    def _load_cost_config(self) -> CostConfig:
        """Load cost management configuration"""
        return CostConfig(
            max_cost_per_request_usd=float(os.getenv("MAX_COST_PER_REQUEST_USD", "1.0")),
            max_daily_cost_usd=float(os.getenv("MAX_DAILY_COST_USD", "100.0")),
            alert_threshold=float(os.getenv("ALERT_COST_THRESHOLD", "0.8"))
        )
    
    def _load_performance_config(self) -> PerformanceConfig:
        """Load performance configuration"""
        return PerformanceConfig(
            cache_ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "3600")),
            max_cache_memory_mb=int(os.getenv("MAX_CACHE_MEMORY_MB", "500")),
            enable_redis_cache=os.getenv("ENABLE_REDIS_CACHE", "true").lower() == "true",
            enable_memory_cache=os.getenv("ENABLE_MEMORY_CACHE", "true").lower() == "true"
        )
    
    def _load_security_config(self) -> SecurityConfig:
        """Load security configuration"""
        allowed_domains = os.getenv("ALLOWED_DOMAINS", "").split(",") if os.getenv("ALLOWED_DOMAINS") else []
        blocked_patterns = os.getenv("BLOCKED_PATTERNS", "").split(",") if os.getenv("BLOCKED_PATTERNS") else []
        
        return SecurityConfig(
            enable_encryption=os.getenv("ENABLE_ENCRYPTION", "true").lower() == "true",
            enable_sanitization=os.getenv("ENABLE_SANITIZATION", "true").lower() == "true",
            enable_privacy=os.getenv("ENABLE_PRIVACY_PROTECTION", "true").lower() == "true",
            allowed_domains=allowed_domains,
            blocked_patterns=blocked_patterns
        )
    
    def _load_monitoring_config(self) -> MonitoringConfig:
        """Load monitoring configuration"""
        return MonitoringConfig(
            prometheus_endpoint=os.getenv("PROMETHEUS_ENDPOINT", "http://localhost:9090"),
            jaeger_endpoint=os.getenv("JAEGER_ENDPOINT", "http://localhost:4317"),
            grafana_url=os.getenv("GRAFANA_URL", "http://localhost:3000"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_format=os.getenv("LOG_FORMAT", "json")
        )
    
    def _load_from_file(self, config_path: str):
        """Load configuration from YAML/JSON file"""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(path, 'r') as f:
            if path.suffix in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            elif path.suffix == '.json':
                data = json.load(f)
            else:
                raise ValueError(f"Unsupported config format: {path.suffix}")
        
        # Update configurations from file
        self._update_from_dict(data)
    
    def _update_from_dict(self, data: Dict[str, Any]):
        """Update configuration from dictionary"""
        if 'api_keys' in data:
            for key, value in data['api_keys'].items():
                setattr(self.api, f"{key}_key", value)
        
        if 'database' in data:
            for key, value in data['database'].items():
                setattr(self.database, key, value)
        
        if 'redis' in data:
            for key, value in data['redis'].items():
                setattr(self.redis, key, value)
        
        # Update other sections similarly...
    
    def _validate_config(self):
        """Validate configuration against schema"""
        schema_path = Path(__file__).parent / "resources/schemas/config.schema.json"
        if schema_path.exists():
            with open(schema_path, 'r') as f:
                schema = json.load(f)
            
            config_dict = self.to_dict()
            try:
                jsonschema.validate(config_dict, schema)
            except jsonschema.ValidationError as e:
                raise ValueError(f"Invalid configuration: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            "environment": self.environment,
            "debug": self.debug,
            "api_keys": {
                "openai": self.api.openai_key,
                "anthropic": self.api.anthropic_key,
                "tavily": self.api.tavily_key,
                "serper": self.api.serper_key,
                "serpapi": self.api.serpapi_key
            },
            "database": {
                "url": self.database.url,
                "pool_size": self.database.pool_size
            },
            "redis": {
                "url": self.redis.url,
                "ttl": self.redis.ttl
            },
            "rate_limits": {
                "max_requests_per_minute": self.rate_limits.max_requests_per_minute,
                "max_concurrent_requests": self.rate_limits.max_concurrent_requests
            },
            "cost_management": {
                "max_cost_per_request_usd": self.cost_management.max_cost_per_request_usd,
                "max_daily_cost_usd": self.cost_management.max_daily_cost_usd,
                "alert_threshold": self.cost_management.alert_threshold
            },
            "performance": {
                "cache_ttl_seconds": self.performance.cache_ttl_seconds,
                "max_cache_memory_mb": self.performance.max_cache_memory_mb,
                "enable_redis_cache": self.performance.enable_redis_cache,
                "enable_memory_cache": self.performance.enable_memory_cache
            },
            "security": {
                "enable_encryption": self.security.enable_encryption,
                "enable_sanitization": self.security.enable_sanitization,
                "enable_privacy": self.security.enable_privacy,
                "allowed_domains": self.security.allowed_domains,
                "blocked_patterns": self.security.blocked_patterns
            },
            "monitoring": {
                "prometheus_endpoint": self.monitoring.prometheus_endpoint,
                "jaeger_endpoint": self.monitoring.jaeger_endpoint,
                "log_level": self.monitoring.log_level
            }
        }


# Global configuration instance
config = Config()