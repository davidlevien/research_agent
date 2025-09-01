"""Unified configuration and settings module.

Single source of truth for all configuration, thresholds, and domain-specific settings.
Consolidates config.py, config_v2.py, and quality/thresholds.py.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import os
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QualityThresholds:
    """Quality thresholds for evidence validation."""
    primary: float          # Minimum primary source share
    triangulation: float    # Minimum triangulation rate
    domain_cap: float      # Maximum domain concentration

    def to_dict(self) -> Dict[str, float]:
        """Convert thresholds to dictionary for logging/metrics."""
        return {
            "primary": self.primary, 
            "triangulation": self.triangulation, 
            "domain_cap": self.domain_cap
        }
    
    def passes(self, primary_share: float, triangulation_rate: float, 
               domain_concentration: float) -> bool:
        """Check if metrics pass these thresholds."""
        return (
            primary_share >= self.primary and
            triangulation_rate >= self.triangulation and
            domain_concentration <= self.domain_cap
        )


# Intent-specific quality thresholds
INTENT_THRESHOLDS: Dict[str, QualityThresholds] = {
    # Conservative defaults
    "default": QualityThresholds(primary=0.50, triangulation=0.45, domain_cap=0.25),
    
    # Travel/tourism needs lower thresholds due to diverse sources
    "travel": QualityThresholds(primary=0.30, triangulation=0.25, domain_cap=0.35),
    "tourism": QualityThresholds(primary=0.30, triangulation=0.25, domain_cap=0.35),
    "travel_tourism": QualityThresholds(primary=0.30, triangulation=0.25, domain_cap=0.35),
    
    # Stats/data queries need high primary share
    "stats": QualityThresholds(primary=0.60, triangulation=0.40, domain_cap=0.30),
    "statistics": QualityThresholds(primary=0.60, triangulation=0.40, domain_cap=0.30),
    "data": QualityThresholds(primary=0.60, triangulation=0.40, domain_cap=0.30),
    "economic": QualityThresholds(primary=0.60, triangulation=0.40, domain_cap=0.30),
    
    # Finance/regulatory
    "finance": QualityThresholds(primary=0.55, triangulation=0.45, domain_cap=0.25),
    "regulatory": QualityThresholds(primary=0.55, triangulation=0.45, domain_cap=0.25),
    "company": QualityThresholds(primary=0.55, triangulation=0.45, domain_cap=0.25),
    "corporate": QualityThresholds(primary=0.55, triangulation=0.45, domain_cap=0.25),
    
    # Medical/health needs peer-reviewed sources
    "medical": QualityThresholds(primary=0.65, triangulation=0.50, domain_cap=0.20),
    "health": QualityThresholds(primary=0.65, triangulation=0.50, domain_cap=0.20),
    "clinical": QualityThresholds(primary=0.65, triangulation=0.50, domain_cap=0.20),
    
    # Academic/research
    "academic": QualityThresholds(primary=0.60, triangulation=0.45, domain_cap=0.25),
    "research": QualityThresholds(primary=0.60, triangulation=0.45, domain_cap=0.25),
    "scientific": QualityThresholds(primary=0.60, triangulation=0.45, domain_cap=0.25),
    
    # News/current events - lower bars for timeliness
    "news": QualityThresholds(primary=0.35, triangulation=0.30, domain_cap=0.35),
    "current": QualityThresholds(primary=0.35, triangulation=0.30, domain_cap=0.35),
    "events": QualityThresholds(primary=0.35, triangulation=0.30, domain_cap=0.35),
    "breaking": QualityThresholds(primary=0.35, triangulation=0.30, domain_cap=0.35),
}

# Intent-specific strict mode adjustments
STRICT_ADJUSTMENTS: Dict[str, QualityThresholds] = {
    # Travel still needs realistic thresholds in strict mode
    "travel": QualityThresholds(primary=0.30, triangulation=0.25, domain_cap=0.35),
    "tourism": QualityThresholds(primary=0.30, triangulation=0.25, domain_cap=0.35),
    "travel_tourism": QualityThresholds(primary=0.30, triangulation=0.25, domain_cap=0.35),
    
    # Stats/data needs exact values in strict mode (not scaled)
    "stats": QualityThresholds(primary=0.60, triangulation=0.40, domain_cap=0.30),
    "statistics": QualityThresholds(primary=0.60, triangulation=0.40, domain_cap=0.30),
    "data": QualityThresholds(primary=0.60, triangulation=0.40, domain_cap=0.30),
    "economic": QualityThresholds(primary=0.60, triangulation=0.40, domain_cap=0.30),
}

# Primary source organizations
PRIMARY_ORGS: Set[str] = {
    # International organizations
    "unwto.org", "wttc.org", "worldbank.org", "oecd.org",
    "imf.org", "un.org", "who.int", "ec.europa.eu",
    "eurostat.ec.europa.eu", "ecb.europa.eu",
    
    # Government sources
    "fred.stlouisfed.org", "bls.gov", "census.gov", "bea.gov",
    "treasury.gov", "federalreserve.gov", "cbo.gov", "gao.gov",
    
    # Academic/Research
    "nber.org", "brookings.edu", "piie.com", "cfr.org",
    
    # Industry authorities (for specific domains)
    "iata.org", "ata.org", "ahla.com", "str.com",
}

# Semi-authoritative organizations (count as primary when they have data)
SEMI_AUTHORITATIVE_ORGS: Set[str] = {
    "mastercard.com", "visa.com", "deloitte.com", "pwc.com",
    "ey.com", "kpmg.com", "mckinsey.com", "bcg.com",
    "accenture.com", "gartner.com", "forrester.com",
}

# Intent-aware domain excludes to avoid wasting budget
INTENT_BLOCKLIST: Dict[str, Set[str]] = {
    "travel": {"sec.gov", "edgar.sec.gov"},
    "tourism": {"sec.gov", "edgar.sec.gov"},
    "travel_tourism": {"sec.gov", "edgar.sec.gov"},
    "medical": {"tripadvisor.com", "booking.com", "expedia.com"},
    "health": {"tripadvisor.com", "booking.com", "expedia.com"},
    "finance": {"wikipedia.org", "wikimedia.org"},
}

# Per-domain fetch headers (extensible, kept here to avoid scattering)
PER_DOMAIN_HEADERS: Dict[str, Dict[str, str]] = {
    "sec.gov": {
        "User-Agent": "Mozilla/5.0 research_agent/1.0 (contact: research@example.com)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "identity",
    },
    "edgar.sec.gov": {
        "User-Agent": "Mozilla/5.0 research_agent/1.0 (contact: research@example.com)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "identity",
    },
    "www.mastercard.com": {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.mastercard.com/newsroom/",
    },
    "mastercard.com": {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.mastercard.com/newsroom/",
    },
    "oecd.org": {
        "Accept": "application/json,text/plain,*/*",
        "User-Agent": "research_agent/1.0",
    },
    "stats.oecd.org": {
        "Accept": "application/json,text/plain,*/*",
        "User-Agent": "research_agent/1.0",
    },
    "stats-nxd.oecd.org": {
        "Accept": "application/json,text/plain,*/*",
        "User-Agent": "research_agent/1.0",
    },
}


def quality_for_intent(intent: Optional[str], strict: bool = True) -> QualityThresholds:
    """Get quality thresholds based on intent and mode.
    
    Args:
        intent: The classified intent (e.g., 'travel', 'stats', 'finance')
        strict: Whether to use strict validation mode
        
    Returns:
        QualityThresholds configured for the intent and mode
    """
    key = (intent or "default").lower()
    
    if strict:
        # Check for strict mode adjustments first
        if key in STRICT_ADJUSTMENTS:
            return STRICT_ADJUSTMENTS[key]
        # Otherwise use default strict thresholds
        base = INTENT_THRESHOLDS.get(key, INTENT_THRESHOLDS["default"])
        # Apply strict mode scaling (except for already-adjusted intents)
        if key not in {"travel", "tourism", "travel_tourism"}:
            return QualityThresholds(
                primary=min(base.primary * 1.2, 0.70),
                triangulation=min(base.triangulation * 1.2, 0.60),
                domain_cap=max(base.domain_cap * 0.8, 0.15)
            )
        return base
    else:
        return INTENT_THRESHOLDS.get(key, INTENT_THRESHOLDS["default"])


@dataclass(frozen=True)
class Settings:
    """Global application settings."""
    time_budget_seconds: int = field(default_factory=lambda: int(os.getenv("RS_TIME_BUDGET", "1800")))
    max_backfill_attempts: int = field(default_factory=lambda: int(os.getenv("MAX_BACKFILL_ATTEMPTS", "3")))
    min_evidence_cards: int = field(default_factory=lambda: int(os.getenv("MIN_EVIDENCE_CARDS", "20")))
    
    # API settings
    enable_free_apis: bool = field(default_factory=lambda: os.getenv("ENABLE_FREE_APIS", "true").lower() == "true")
    use_llm_claims: bool = field(default_factory=lambda: os.getenv("USE_LLM_CLAIMS", "false").lower() == "true")
    use_llm_synth: bool = field(default_factory=lambda: os.getenv("USE_LLM_SYNTH", "false").lower() == "true")
    
    # Timeout settings
    HTTP_TIMEOUT_SECONDS: int = field(default_factory=lambda: int(os.getenv("HTTP_TIMEOUT_SECONDS", "30")))
    WALL_TIMEOUT_SEC: int = field(default_factory=lambda: int(os.getenv("WALL_TIMEOUT_SEC", "1800")))
    PROVIDER_TIMEOUT_SEC: int = field(default_factory=lambda: int(os.getenv("PROVIDER_TIMEOUT_SEC", "20")))
    
    # Contact info for API compliance
    contact_email: str = field(default_factory=lambda: os.getenv("CONTACT_EMAIL", "research@example.com"))
    
    # Stats-specific configuration
    STATS_ALLOWED_PRIMARY_DOMAINS: set = field(default_factory=lambda: {
        "oecd.org", "stats.oecd.org", "imf.org", "worldbank.org", "data.worldbank.org",
        "ec.europa.eu", "eurostat.ec.europa.eu", "ecb.europa.eu",
        "bea.gov", "bls.gov", "irs.gov", "cbo.gov", "gao.gov", "treasury.gov", 
        "federalreserve.gov", "fred.stlouisfed.org", "census.gov",
        "un.org", "data.un.org", "ourworldindata.org",
        "nber.org", "jstor.org", "nature.com", "science.org", "pnas.org",
        "stats.govt.nz", "abs.gov.au", "statistics.gov.uk", "statcan.gc.ca"
    })
    
    STATS_BANNED_REPRESENTATIVE_DOMAINS: set = field(default_factory=lambda: {
        "americanprogress.org", "taxfoundation.org", "epi.org", "cfr.org",
        "heritage.org", "aei.org", "cato.org", "brookings.edu",
        "gobankingrates.com", "investopedia.com", "concordcoalition.org",
        "wikipedia.org", "medium.com", "substack.com", "wordpress.com"
    })
    
    STATS_TOPIC_REGEX: str = field(default_factory=lambda: (
        r"(tax(\s|-|_)?(rate|burden|share|progressiv)|marginal|effective|average.*tax|"
        r"gini|income\s+(share|quintile|decile)|percentile|bracket|growth|gdp|"
        r"unemployment|inflation|deficit|debt|revenue|spending|budget)"
    ))
    
    STATS_TRIANGULATED_MIN: int = field(default_factory=lambda: int(os.getenv("STATS_TRIANGULATED_MIN", "1")))
    STATS_CLUSTER_PRIMARY_DOMAINS_MIN: int = field(default_factory=lambda: int(os.getenv("STATS_CLUSTER_PRIMARY_DOMAINS_MIN", "2")))
    
    # Retry configuration
    RETRY_MAX_TRIES: int = field(default_factory=lambda: int(os.getenv("RETRY_MAX_TRIES", "5")))
    RETRY_BACKOFF_BASE_SECONDS: float = field(default_factory=lambda: float(os.getenv("RETRY_BACKOFF_BASE_SECONDS", "0.5")))
    
    def thresholds(self, intent: Optional[str], strict: bool = True) -> QualityThresholds:
        """Get quality thresholds for the given intent and mode."""
        return quality_for_intent(intent, strict)


# Global settings instance
settings = Settings()