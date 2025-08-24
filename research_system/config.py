from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import Literal, Optional, List

class Settings(BaseSettings):
    # ==== LLM provider (blueprint: choose one, gated) ====
    LLM_PROVIDER: Literal["openai", "anthropic", "azure_openai"] = "openai"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_BASE: Optional[str] = None
    OPENAI_ORG_ID: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    AZURE_OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_DEPLOYMENT_PLANNER: Optional[str] = None
    AZURE_OPENAI_DEPLOYMENT_RESEARCHER: Optional[str] = None
    AZURE_OPENAI_DEPLOYMENT_VERIFIER: Optional[str] = None
    AZURE_OPENAI_DEPLOYMENT_WRITER: Optional[str] = None

    # ==== Search providers (blueprint: PARALLEL fan-out, first-class) ====
    SEARCH_PROVIDERS: str = "tavily,brave,serper"  # comma-separated, no fallback semantics
    TAVILY_API_KEY: Optional[str] = None
    BRAVE_API_KEY: Optional[str] = None
    SERPER_API_KEY: Optional[str] = None  # Aligned with .env
    SERPAPI_API_KEY: Optional[str] = None  # Optional SerpAPI
    NPS_API_KEY: Optional[str] = None  # National Park Service

    # ==== Runtime / budgets ====
    MAX_COST_USD: float = Field(2.50, ge=0)
    OUTPUT_DIR: str = "outputs"
    CHECKPOINT_DIR: str = "outputs/checkpoints"

    # ==== Policy ====
    FRESHNESS_WINDOW: str = "24 months"
    REGIONS: str = "US,EU"  # CSV of priority regions
    SOURCE_WHITELIST: str = '[".gov",".edu",".ac.uk",".who.int",".un.org"]'  # JSON list as str

    # ==== HTTP & retries ====
    HTTP_TIMEOUT_SECONDS: int = 30
    RETRY_MAX_TRIES: int = 5
    RETRY_BACKOFF_BASE_SECONDS: float = 0.5
    CONCURRENCY: int = 8

    # ==== Observability toggles ====
    LOG_LEVEL: Literal["DEBUG","INFO","WARNING","ERROR"] = "INFO"
    SENTRY_DSN: Optional[str] = None
    ENABLE_PROMETHEUS: bool = False
    PROMETHEUS_PORT: int = 9100

    # ==== Infra toggles (keep OFF until their code paths are used) ====
    ENABLE_REDIS: bool = False
    REDIS_URL: Optional[str] = None
    ENABLE_DATABASE: bool = False
    DATABASE_URL: Optional[str] = None
    
    # ==== Enhanced Features (PE-level) ====
    ENABLE_PRIMARY_CONNECTORS: bool = True
    ENABLE_EXTRACT: bool = True
    ENABLE_SNAPSHOT: bool = False  # Off by default to avoid Wayback writes
    ENABLE_MINHASH_DEDUP: bool = True
    ENABLE_DUCKDB_AGG: bool = True
    ENABLE_SBERT_CLUSTERING: bool = True
    
    # ==== Quality Thresholds ====
    MIN_TRIANGULATION_RATE: float = 0.35
    MAX_DOMAIN_CONCENTRATION: float = 0.25
    MIN_CREDIBILITY: float = 0.6
    STRICT: bool = False
    
    # ==== Open Access & Fallback Features ====
    ENABLE_UNPAYWALL: bool = Field(default=False, description="Enable Unpaywall OA resolver")
    ENABLE_S2: bool = Field(default=False, description="Enable Semantic Scholar fallback")
    ENABLE_CORE: bool = Field(default=False, description="Enable CORE Academic fallback")
    
    # ==== Content Processing Features ====
    ENABLE_PDF_TABLES: bool = Field(default=False, description="Enable PDF table extraction")
    ENABLE_LANGDETECT: bool = Field(default=False, description="Enable language detection")
    
    # ==== Crawling & Caching Features ====
    ENABLE_HTTP_CACHE: bool = Field(default=False, description="Enable HTTP caching with ETag support")
    ENABLE_POLITENESS: bool = Field(default=False, description="Enable robots.txt compliance")
    ENABLE_WARC: bool = Field(default=False, description="Enable WARC archiving for provenance")
    HTTP_CACHE_DIR: str = Field(default="./.http_cache", description="Directory for HTTP cache")
    
    # ==== Domain Quality Features ====
    ENABLE_TRANCO: bool = Field(default=False, description="Enable Tranco domain reputation")
    ENABLE_GEO_NORM: bool = Field(default=False, description="Enable geographic normalization")

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"  # Allow extra fields from env

    def model_post_init(self, __context):
        """Validate provider configurations after all fields are set"""
        # Validate LLM provider
        if self.LLM_PROVIDER == "openai":
            assert self.OPENAI_API_KEY, "OPENAI_API_KEY required for LLM_PROVIDER=openai"
        elif self.LLM_PROVIDER == "anthropic":
            assert self.ANTHROPIC_API_KEY, "ANTHROPIC_API_KEY required for LLM_PROVIDER=anthropic"
        elif self.LLM_PROVIDER == "azure_openai":
            req = [
                self.AZURE_OPENAI_API_KEY, self.AZURE_OPENAI_ENDPOINT,
                self.AZURE_OPENAI_DEPLOYMENT_PLANNER, self.AZURE_OPENAI_DEPLOYMENT_RESEARCHER,
                self.AZURE_OPENAI_DEPLOYMENT_VERIFIER, self.AZURE_OPENAI_DEPLOYMENT_WRITER,
            ]
            missing = [name for name, val in zip([
                "AZURE_OPENAI_API_KEY","AZURE_OPENAI_ENDPOINT",
                "AZURE_OPENAI_DEPLOYMENT_PLANNER","AZURE_OPENAI_DEPLOYMENT_RESEARCHER",
                "AZURE_OPENAI_DEPLOYMENT_VERIFIER","AZURE_OPENAI_DEPLOYMENT_WRITER"
            ], req) if not val]
            assert not missing, f"Missing Azure OpenAI vars: {', '.join(missing)}"
        
        # Validate search providers
        wanted = [s.strip() for s in self.SEARCH_PROVIDERS.split(",") if s.strip()]
        valid = {"tavily", "brave", "serper", "serpapi", "nps"}
        unknown = [p for p in wanted if p not in valid]
        assert not unknown, f"Unknown providers: {unknown}"
        missing = []
        if "tavily" in wanted and not self.TAVILY_API_KEY: 
            missing.append("TAVILY_API_KEY")
        if "brave" in wanted and not self.BRAVE_API_KEY:  
            missing.append("BRAVE_API_KEY")
        if "serper" in wanted and not self.SERPER_API_KEY: 
            missing.append("SERPER_API_KEY")
        if "serpapi" in wanted and not self.SERPAPI_API_KEY:
            missing.append("SERPAPI_API_KEY")
        if "nps" in wanted and not self.NPS_API_KEY:
            missing.append("NPS_API_KEY")
        assert not missing, f"Missing API keys: {', '.join(missing)}"

    def enabled_providers(self) -> List[str]:
        return [s.strip() for s in self.SEARCH_PROVIDERS.split(",") if s.strip()]