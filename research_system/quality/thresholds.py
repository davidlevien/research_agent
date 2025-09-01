"""Intent-aware quality thresholds for evidence validation.

v8.24.0: Implements adaptive thresholds based on query intent and strict mode.
"""

from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class QualityThresholds:
    """Quality thresholds for evidence validation."""
    primary: float          # Minimum primary source share
    triangulation: float    # Minimum triangulation rate
    domain_cap: float      # Maximum domain concentration

    @staticmethod
    def for_intent(intent: Optional[str], strict: bool = False) -> "QualityThresholds":
        """Get quality thresholds based on intent and mode.
        
        Args:
            intent: The classified intent (e.g., 'travel', 'stats', 'finance')
            strict: Whether to use strict validation mode
            
        Returns:
            QualityThresholds configured for the intent and mode
        """
        intent = (intent or "").lower()
        
        # Default thresholds
        if strict:
            # Strict mode defaults - higher bars
            default = QualityThresholds(
                primary=0.50, 
                triangulation=0.45, 
                domain_cap=0.25
            )
        else:
            # Lenient mode defaults
            default = QualityThresholds(
                primary=0.30, 
                triangulation=0.25, 
                domain_cap=0.35
            )
        
        # Intent-specific overrides
        # Macro trends need moderate thresholds (cross-domain queries)
        if intent in {"macro_trends", "travel", "tourism", "travel_tourism"}:
            if strict:
                return QualityThresholds(
                    primary=0.30,      # Moderate primary requirement
                    triangulation=0.25, # Moderate triangulation requirement
                    domain_cap=0.35    # Higher domain diversity allowed
                )
            else:
                return QualityThresholds(
                    primary=0.20,      # Lower for lenient mode
                    triangulation=0.15,
                    domain_cap=0.40
                )
        
        # Stats/data queries need high primary share
        elif intent in {"stats", "statistics", "data", "economic", "gov_stats"}:
            if strict:
                return QualityThresholds(
                    primary=0.60,      # High primary requirement
                    triangulation=0.40, # Moderate triangulation
                    domain_cap=0.30    # Some concentration OK
                )
            else:
                return QualityThresholds(
                    primary=0.40,
                    triangulation=0.30,
                    domain_cap=0.35
                )
        
        # Company filings and regulatory queries need authoritative sources
        elif intent in {"company_filings", "finance", "regulatory", "company", "corporate"}:
            if strict:
                return QualityThresholds(
                    primary=0.55,      # High primary requirement
                    triangulation=0.45, # High triangulation
                    domain_cap=0.25    # Low concentration
                )
            else:
                return QualityThresholds(
                    primary=0.35,
                    triangulation=0.30,
                    domain_cap=0.30
                )
        
        # Medical/health queries need peer-reviewed sources
        elif intent in {"medical", "health", "clinical"}:
            if strict:
                return QualityThresholds(
                    primary=0.65,      # Very high primary requirement
                    triangulation=0.50, # High triangulation
                    domain_cap=0.20    # Very low concentration
                )
            else:
                return QualityThresholds(
                    primary=0.45,
                    triangulation=0.35,
                    domain_cap=0.25
                )
        
        # Academic/research queries
        elif intent in {"academic", "research", "scientific"}:
            if strict:
                return QualityThresholds(
                    primary=0.60,
                    triangulation=0.45,
                    domain_cap=0.25
                )
            else:
                return QualityThresholds(
                    primary=0.40,
                    triangulation=0.30,
                    domain_cap=0.30
                )
        
        # News/current events - lower bars for timeliness
        elif intent in {"news", "current", "events", "breaking"}:
            if strict:
                return QualityThresholds(
                    primary=0.35,
                    triangulation=0.30,
                    domain_cap=0.35
                )
            else:
                return QualityThresholds(
                    primary=0.25,
                    triangulation=0.20,
                    domain_cap=0.40
                )
        
        # Default to configured defaults
        return default
    
    def to_dict(self) -> dict:
        """Convert thresholds to dictionary for logging/metrics."""
        return {
            "primary": self.primary,
            "triangulation": self.triangulation,
            "domain_cap": self.domain_cap
        }
    
    def passes(self, primary_share: float, triangulation_rate: float, 
               domain_concentration: float) -> bool:
        """Check if metrics pass these thresholds.
        
        Args:
            primary_share: Share of primary sources (0-1)
            triangulation_rate: Rate of triangulated evidence (0-1)
            domain_concentration: HHI-like domain concentration (0-1)
            
        Returns:
            True if all thresholds are met
        """
        return (
            primary_share >= self.primary and
            triangulation_rate >= self.triangulation and
            domain_concentration <= self.domain_cap
        )
    
    def __str__(self) -> str:
        """String representation for logging."""
        return (
            f"QualityThresholds(primary={self.primary:.0%}, "
            f"triangulation={self.triangulation:.0%}, "
            f"domain_cap={self.domain_cap:.0%})"
        )