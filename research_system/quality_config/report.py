"""Adaptive report length configuration based on evidence quality."""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from enum import Enum


class ReportTier(Enum):
    """Report length tiers."""
    BRIEF = "brief"
    STANDARD = "standard"  
    DEEP = "deep"


@dataclass
class SectionBudgets:
    """Token budgets for report sections."""
    exec_summary: int
    trends: int
    quant: int
    caveats: int
    actions: int
    
    def total(self) -> int:
        """Total token budget."""
        return (
            self.exec_summary + 
            self.trends + 
            self.quant + 
            self.caveats + 
            self.actions
        )


@dataclass
class TierConfig:
    """Configuration for a report tier."""
    max_tokens: int
    appendix_rows: int
    sections: SectionBudgets


@dataclass 
class ReportConfig:
    """Adaptive report length configuration."""
    
    # Tier definitions
    tiers: Dict[ReportTier, TierConfig] = field(default_factory=lambda: {
        ReportTier.BRIEF: TierConfig(
            max_tokens=1200,
            appendix_rows=12,
            sections=SectionBudgets(
                exec_summary=160,
                trends=500,
                quant=220,
                caveats=160,
                actions=160
            )
        ),
        ReportTier.STANDARD: TierConfig(
            max_tokens=2200,
            appendix_rows=25,
            sections=SectionBudgets(
                exec_summary=200,
                trends=800,
                quant=300,
                caveats=220,
                actions=240
            )
        ),
        ReportTier.DEEP: TierConfig(
            max_tokens=3800,
            appendix_rows=50,
            sections=SectionBudgets(
                exec_summary=260,
                trends=1400,
                quant=500,
                caveats=300,
                actions=340
            )
        )
    })
    
    # Hard limits
    max_tokens_default: int = 3800
    safety_margin_pct: float = 0.20
    min_tokens: int = 600
    
    # Tier routing thresholds
    brief_confidence_max: float = 0.55
    deep_confidence_min: float = 0.75
    deep_triangulated_min: int = 20
    deep_domains_min: int = 8
    low_supply_domains: int = 6
    low_supply_cards: int = 25
    low_supply_error_rate: float = 0.30


def compute_confidence(
    triangulated_cards: int,
    credible_cards: int,
    primary_share: float,
    unique_domains: int,
    provider_error_rate: float
) -> float:
    """
    Compute confidence score (0-1) based on evidence quality.
    
    Args:
        triangulated_cards: Number of triangulated evidence cards
        credible_cards: Total credible cards
        primary_share: Percentage from primary sources (0-1)
        unique_domains: Number of unique source domains
        provider_error_rate: Rate of provider errors (0-1)
        
    Returns:
        Confidence score between 0 and 1
    """
    # Component scores
    tri = triangulated_cards / max(credible_cards, 1)  # 0-1
    prim = primary_share  # 0-1
    dom = min(unique_domains / 10, 1.0)  # Saturates at 10 domains
    err = min(provider_error_rate, 1.0)  # 0-1
    
    # Weighted combination
    confidence = (
        0.4 * tri +      # 40% weight on triangulation
        0.3 * prim +     # 30% weight on primary sources
        0.2 * dom +      # 20% weight on domain diversity  
        0.1 * (1 - err)  # 10% weight on provider health
    )
    
    return confidence


def is_low_supply(
    unique_domains: int,
    credible_cards: int, 
    provider_error_rate: float,
    config: ReportConfig
) -> bool:
    """Check if evidence supply is constrained."""
    return (
        unique_domains < config.low_supply_domains or
        credible_cards < config.low_supply_cards or
        provider_error_rate >= config.low_supply_error_rate
    )


def choose_report_tier(
    triangulated_cards: int,
    credible_cards: int,
    primary_share: float,
    unique_domains: int,
    provider_error_rate: float,
    depth: str,
    time_budget_remaining_sec: float,
    tokens_per_second: float = 100,
    max_tokens_override: Optional[int] = None,
    config: Optional[ReportConfig] = None
) -> Tuple[ReportTier, float, int, str]:
    """
    Choose appropriate report tier based on evidence and constraints.
    
    Args:
        triangulated_cards: Number of triangulated evidence cards
        credible_cards: Total credible cards
        primary_share: Percentage from primary sources (0-1)
        unique_domains: Number of unique source domains
        provider_error_rate: Rate of provider errors (0-1)
        depth: Requested depth ("rapid", "standard", "deep")
        time_budget_remaining_sec: Time budget remaining in seconds
        tokens_per_second: Token generation rate
        max_tokens_override: Optional max token override from CLI
        config: Report configuration (uses defaults if None)
        
    Returns:
        Tuple of (tier, confidence, max_tokens, explanation)
    """
    if config is None:
        config = ReportConfig()
    
    # Compute confidence score
    confidence = compute_confidence(
        triangulated_cards, credible_cards, 
        primary_share, unique_domains, provider_error_rate
    )
    
    # Check supply conditions
    low_supply = is_low_supply(
        unique_domains, credible_cards, provider_error_rate, config
    )
    
    # Determine tier
    if depth == "rapid" or low_supply or confidence < config.brief_confidence_max:
        tier = ReportTier.BRIEF
        if low_supply:
            explanation = f"Limited evidence supply (domains={unique_domains}, cards={credible_cards})"
        elif confidence < config.brief_confidence_max:
            explanation = f"Low confidence ({confidence:.2f})"
        else:
            explanation = "Rapid depth requested"
            
    elif (confidence >= config.deep_confidence_min and 
          triangulated_cards >= config.deep_triangulated_min and
          unique_domains >= config.deep_domains_min):
        tier = ReportTier.DEEP
        explanation = f"High confidence ({confidence:.2f}) with rich evidence"
        
    else:
        tier = ReportTier.STANDARD
        explanation = f"Standard confidence ({confidence:.2f})"
    
    # Compute hard cap
    tier_config = config.tiers[tier]
    cli_cap = max_tokens_override or config.max_tokens_default
    safety = 1.0 - config.safety_margin_pct
    time_cap = int(tokens_per_second * time_budget_remaining_sec * safety)
    
    # Apply limits
    max_tokens = max(
        config.min_tokens,
        min(tier_config.max_tokens, cli_cap, time_cap)
    )
    
    return tier, confidence, max_tokens, explanation


def format_tier_badge(
    tier: ReportTier,
    confidence: float,
    explanation: str
) -> str:
    """
    Format a badge for the report header.
    
    Args:
        tier: Report tier selected
        confidence: Confidence score
        explanation: Explanation for tier selection
        
    Returns:
        Formatted markdown badge
    """
    tier_emoji = {
        ReportTier.BRIEF: "📄",
        ReportTier.STANDARD: "📋", 
        ReportTier.DEEP: "📚"
    }[tier]
    
    confidence_emoji = "🟢" if confidence >= 0.75 else "🟡" if confidence >= 0.55 else "🔴"
    
    lines = [
        f"**Report Profile:** {tier_emoji} {tier.value.upper()} "
        f"(confidence: {confidence_emoji} {confidence:.2f})",
        ""
    ]
    
    if tier == ReportTier.BRIEF and "Limited evidence" in explanation:
        lines.extend([
            f"ℹ️ **Note:** {explanation}. Narrative condensed; see evidence table for all sources.",
            ""
        ])
    
    return "\n".join(lines)