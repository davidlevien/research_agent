"""Adaptive quality gate configuration for supply-aware thresholds."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from pathlib import Path
import json


@dataclass
class TriangulationConfig:
    """Adaptive triangulation thresholds."""
    target_strict_pct: float = 0.35
    target_normal_pct: float = 0.30
    floor_pct_low_supply: float = 0.25
    min_cards_abs: int = 10
    min_cards_abs_low_supply: int = 8
    
    # Low supply triggers
    min_unique_domains: int = 6
    min_credible_cards: int = 25
    provider_error_rate: float = 0.30
    
    def get_threshold(self, cards: int, domains: int) -> float:
        """Get adaptive triangulation threshold based on supply."""
        if cards < self.min_credible_cards or domains < self.min_unique_domains:
            return self.floor_pct_low_supply
        return self.target_normal_pct


@dataclass
class PrimaryShareConfig:
    """Adaptive primary source requirements."""
    target_pct: float = 0.40
    low_supply_pct: float = 0.30
    primary_supply_relaxed_threshold: float = 0.50  # Relax if primary/credible < 0.5


@dataclass
class DomainBalanceConfig:
    """Domain concentration limits."""
    cap_default: float = 0.25
    cap_when_few_domains: float = 0.40
    few_domains_threshold: int = 6
    
    def get_cap(self, domain_count: int) -> float:
        """Get adaptive domain cap based on domain diversity."""
        if domain_count < self.few_domains_threshold:
            return self.cap_when_few_domains
        return self.cap_default


@dataclass
class BackfillConfig:
    """Backfill strategy configuration."""
    max_attempts: int = 3
    last_mile_enabled: bool = True
    last_mile_pp_shortfall: float = 0.05  # 5 percentage points
    last_mile_min_time_budget: float = 0.20  # 20% time remaining


@dataclass
class CredibilityConfig:
    """Credibility assessment configuration."""
    whitelist_singletons: List[str] = field(default_factory=lambda: [
        "oecd.org",
        "unwto.org",
        "worldbank.org",
        "imf.org",
        "fred.stlouisfed.org",
        "ecb.europa.eu",
        "trade.gov",
        "ustravel.org",
        "bls.gov",
        "census.gov",
        "federalreserve.gov",
        "stats.govt.nz",
        "statistics.gov.uk",
        "abs.gov.au",
        "statcan.gc.ca",
        "destatis.de",
        "insee.fr",
        "istat.it",
        "stat.go.jp",
    ])
    singleton_downweight: float = 0.85


@dataclass
class QualityConfig:
    """Complete quality gate configuration."""
    triangulation: TriangulationConfig = field(default_factory=TriangulationConfig)
    primary_share: PrimaryShareConfig = field(default_factory=PrimaryShareConfig)
    domain_balance: DomainBalanceConfig = field(default_factory=DomainBalanceConfig)
    backfill: BackfillConfig = field(default_factory=BackfillConfig)
    credibility: CredibilityConfig = field(default_factory=CredibilityConfig)
    
    @classmethod
    def load(cls, path: Optional[Path] = None) -> "QualityConfig":
        """Load configuration from JSON file or use defaults."""
        if path and path.exists():
            with open(path) as f:
                data = json.load(f)
                return cls(
                    triangulation=TriangulationConfig(**data.get("triangulation", {})),
                    primary_share=PrimaryShareConfig(**data.get("primary_share", {})),
                    domain_balance=DomainBalanceConfig(**data.get("domain_balance", {})),
                    backfill=BackfillConfig(**data.get("backfill", {})),
                    credibility=CredibilityConfig(**data.get("credibility", {}))
                )
        return cls()
    
    def save(self, path: Path) -> None:
        """Save configuration to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "triangulation": {
                "target_strict_pct": self.triangulation.target_strict_pct,
                "target_normal_pct": self.triangulation.target_normal_pct,
                "floor_pct_low_supply": self.triangulation.floor_pct_low_supply,
                "min_cards_abs": self.triangulation.min_cards_abs,
                "min_cards_abs_low_supply": self.triangulation.min_cards_abs_low_supply,
                "min_unique_domains": self.triangulation.min_unique_domains,
                "min_credible_cards": self.triangulation.min_credible_cards,
                "provider_error_rate": self.triangulation.provider_error_rate
            },
            "primary_share": {
                "target_pct": self.primary_share.target_pct,
                "low_supply_pct": self.primary_share.low_supply_pct,
                "primary_supply_relaxed_threshold": self.primary_share.primary_supply_relaxed_threshold
            },
            "domain_balance": {
                "cap_default": self.domain_balance.cap_default,
                "cap_when_few_domains": self.domain_balance.cap_when_few_domains,
                "few_domains_threshold": self.domain_balance.few_domains_threshold
            },
            "backfill": {
                "max_attempts": self.backfill.max_attempts,
                "last_mile_enabled": self.backfill.last_mile_enabled,
                "last_mile_pp_shortfall": self.backfill.last_mile_pp_shortfall,
                "last_mile_min_time_budget": self.backfill.last_mile_min_time_budget
            },
            "credibility": {
                "whitelist_singletons": self.credibility.whitelist_singletons,
                "singleton_downweight": self.credibility.singleton_downweight
            }
        }


# Global instance
DEFAULT_CONFIG = QualityConfig()