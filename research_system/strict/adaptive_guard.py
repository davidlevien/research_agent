"""Adaptive strict mode with supply-aware quality gates."""

import json
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Any
from enum import Enum
from dataclasses import dataclass

from research_system.quality_config.quality import QualityConfig


logger = logging.getLogger(__name__)


class ConfidenceLevel(Enum):
    """Confidence levels for research outputs."""
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    
    def to_emoji(self) -> str:
        """Get emoji representation."""
        return {
            ConfidenceLevel.HIGH: "🟢",
            ConfidenceLevel.MODERATE: "🟡", 
            ConfidenceLevel.LOW: "🔴"
        }[self]


class SupplyContext(Enum):
    """Evidence supply context levels."""
    NORMAL = "normal"
    LOW_EVIDENCE = "low_evidence"
    CONSTRAINED = "constrained"


def detect_supply_context(metrics: Dict) -> SupplyContext:
    """Detect evidence supply context from metrics."""
    unique_domains = metrics.get("unique_domains", 0)
    credible_cards = metrics.get("credible_cards", metrics.get("cards", 0))
    provider_error_rate = metrics.get("provider_error_rate", 0.0)
    
    # Check for low evidence conditions
    if unique_domains < 6 or credible_cards < 25 or provider_error_rate >= 0.30:
        return SupplyContext.LOW_EVIDENCE
    elif unique_domains < 8 or credible_cards < 30 or provider_error_rate >= 0.20:
        return SupplyContext.CONSTRAINED
    else:
        return SupplyContext.NORMAL


def determine_confidence_level(metrics: Dict, supply_context: SupplyContext) -> ConfidenceLevel:
    """Determine confidence level based on metrics and supply context."""
    tri = metrics.get("union_triangulation", 0)
    prim = metrics.get("primary_share_in_union", 0)
    
    if supply_context == SupplyContext.LOW_EVIDENCE:
        # Relaxed thresholds for low evidence
        if tri >= 0.25 and prim >= 0.30:
            return ConfidenceLevel.MODERATE
        else:
            return ConfidenceLevel.LOW
    elif supply_context == SupplyContext.CONSTRAINED:
        # Slightly relaxed thresholds
        if tri >= 0.30 and prim >= 0.35:
            return ConfidenceLevel.HIGH
        elif tri >= 0.25 and prim >= 0.30:
            return ConfidenceLevel.MODERATE
        else:
            return ConfidenceLevel.LOW
    else:
        # Normal thresholds
        if tri >= 0.35 and prim >= 0.40:
            return ConfidenceLevel.HIGH
        elif tri >= 0.30 and prim >= 0.35:
            return ConfidenceLevel.MODERATE
        else:
            return ConfidenceLevel.LOW


def adaptive_strict_check(
    out_dir: Path,
    config: Optional[QualityConfig] = None
) -> Tuple[List[str], ConfidenceLevel, Dict[str, str]]:
    """
    Adaptive quality checks with supply awareness.
    
    Args:
        out_dir: Output directory containing metrics.json
        config: Quality configuration (uses defaults if None)
        
    Returns:
        Tuple of (errors, confidence_level, adjustments_made)
    """
    if config is None:
        config = QualityConfig()
    
    errs = []
    adjustments = {}
    
    # Load metrics
    metrics_path = out_dir / "metrics.json"
    if not metrics_path.exists():
        return (["METRICS_MISSING: metrics.json not found"], ConfidenceLevel.LOW, {})
    
    try:
        metrics = json.loads(metrics_path.read_text())
    except Exception as e:
        return ([f"METRICS_INVALID: {e}"], ConfidenceLevel.LOW, {})
    
    # Detect supply context
    ctx = detect_supply_context(metrics)
    confidence = determine_confidence_level(metrics, ctx)
    
    # Extract values from metrics
    unique_domains = metrics.get("unique_domains", 0)
    credible_cards = metrics.get("credible_cards", metrics.get("cards", 0))
    triangulated_cards = metrics.get("triangulated_cards", 0)
    union_triangulation = metrics.get("union_triangulation", 0)
    primary_share = metrics.get("primary_share_in_union", 0)
    provider_error_rate = metrics.get("provider_error_rate", 0.0)
    
    # Log supply conditions
    if ctx == SupplyContext.LOW_EVIDENCE:
        logger.info(
            f"Low supply detected: domains={unique_domains}, "
            f"credible={credible_cards}, error_rate={provider_error_rate:.2f}"
        )
    
    # 1. ADAPTIVE TRIANGULATION CHECK
    if ctx == SupplyContext.LOW_EVIDENCE:
        # Relax threshold in low-supply mode
        threshold = config.triangulation.floor_pct_low_supply
        min_cards = config.triangulation.min_cards_abs_low_supply
        adjustments["triangulation_threshold"] = f"relaxed to {threshold:.0%} (low supply)"
    elif ctx == SupplyContext.CONSTRAINED:
        threshold = config.triangulation.target_normal_pct
        min_cards = config.triangulation.min_cards_abs
        adjustments["triangulation_threshold"] = f"adjusted to {threshold:.0%} (constrained)"
    else:
        # Standard strict mode
        threshold = config.triangulation.target_strict_pct
        min_cards = config.triangulation.min_cards_abs
    
    if union_triangulation < threshold:
        errs.append(f"TRIANGULATION({int(union_triangulation*100)}%) < {int(threshold*100)}%")
    if triangulated_cards < min_cards:
        errs.append(f"TRIANGULATED_COUNT({triangulated_cards}) < {min_cards}")
    
    # 2. ADAPTIVE PRIMARY SHARE CHECK
    primary_supply_ratio = metrics.get("primary_cards", 0) / max(1, credible_cards)
    if primary_supply_ratio < config.primary_share.primary_supply_relaxed_threshold:
        # Relax primary share requirement if supply is limited
        primary_threshold = config.primary_share.low_supply_pct
        adjustments["primary_threshold"] = f"relaxed to {primary_threshold:.0%} (limited primary supply)"
    else:
        primary_threshold = config.primary_share.target_pct
    
    if primary_share < primary_threshold:
        errs.append(
            f"PRIMARY_SHARE({int(primary_share*100)}%) < {int(primary_threshold*100)}%"
        )
    
    # 3. DOMAIN DIVERSITY (adaptive cap)
    if unique_domains < config.domain_balance.few_domains_threshold:
        adjustments["domain_cap"] = f"relaxed to {config.domain_balance.cap_pct_when_few_domains:.0%} (few domains)"
    
    # Minimum domain diversity check
    if unique_domains < 3:
        errs.append(f"DOMAINS({unique_domains}) < 3 minimum")
    
    # 4. EVIDENCE VOLUME
    min_evidence = 15 if ctx == SupplyContext.LOW_EVIDENCE else 20
    if credible_cards < min_evidence:
        errs.append(f"EVIDENCE_COUNT({credible_cards}) < {min_evidence}")
    
    # 5. EXTREME FAILURE CONDITIONS (non-negotiable)
    if union_triangulation < 0.10:
        errs.append("CRITICAL: Triangulation below 10% floor")
    if unique_domains < 2:
        errs.append("CRITICAL: Single-source evidence")
    
    return errs, confidence, adjustments


def should_skip_strict_fail(
    errors: List[str],
    adjustments: Dict[str, str],
    confidence: ConfidenceLevel
) -> bool:
    """
    Determine if strict failures should be downgraded to warnings.
    
    Args:
        errors: List of strict check errors
        adjustments: Adjustments made during checking
        confidence: Overall confidence level
        
    Returns:
        True if failures should be warnings, False if they should fail
    """
    # Never skip critical failures
    if any("CRITICAL" in e for e in errors):
        return False
    
    # Skip if we made adjustments and confidence is at least moderate
    if adjustments and confidence in [ConfidenceLevel.MODERATE, ConfidenceLevel.HIGH]:
        return True
    
    # Skip if only minor violations in low-evidence context
    if confidence == ConfidenceLevel.MODERATE and len(errors) <= 2:
        return True
    
    return False


def should_attempt_last_mile_backfill(
    metrics: Dict[str, Any],
    config: QualityConfig,
    time_remaining_pct: float,
    attempt_number: int
) -> bool:
    """
    Determine if we should attempt a last-mile backfill.
    
    This is a cheap extra attempt when we're very close to passing.
    
    Args:
        metrics: Current metrics dictionary
        config: Quality configuration
        time_remaining_pct: Percentage of time budget remaining (0-1)
        attempt_number: Current backfill attempt number
        
    Returns:
        True if should attempt last-mile backfill
    """
    # Only on later attempts
    if attempt_number < 2:
        return False
    
    # Need sufficient time remaining
    if time_remaining_pct < 0.20:
        return False
    
    # Check if we're close to triangulation threshold
    current_tri = metrics.get("union_triangulation", 0)
    target_tri = config.triangulation.target_strict_pct
    
    shortfall = target_tri - current_tri
    if 0 < shortfall <= 0.05:  # Within 5 percentage points
        logger.info(f"Last-mile backfill triggered: {shortfall:.1%} from target")
        return True
    
    return False


@dataclass
class SupplyContextData:
    """Structured supply context data for reporting."""
    total_cards: int
    unique_domains: int
    provider_attempts: int
    provider_errors: int
    
    @property
    def provider_error_rate(self) -> float:
        return self.provider_errors / max(1, self.provider_attempts)


def format_confidence_report(
    confidence: ConfidenceLevel,
    adjustments: Dict[str, str],
    context: SupplyContextData
) -> str:
    """
    Format a confidence report for the user.
    
    Args:
        confidence: Overall confidence level
        adjustments: Adjustments made during checking
        context: Supply context data
        
    Returns:
        Formatted markdown report
    """
    lines = [
        f"# Research Confidence Report",
        "",
        f"**Confidence Level**: {confidence.value.title()} {confidence.to_emoji()}",
        "",
        "## Supply Context",
        f"- Unique domains: {context.unique_domains}",
        f"- Total evidence cards: {context.total_cards}",
        f"- Provider error rate: {context.provider_error_rate:.1%}",
        ""
    ]
    
    if adjustments:
        lines.extend([
            "## Quality Gate Adjustments",
            "",
            "The following thresholds were adjusted due to evidence constraints:",
            ""
        ])
        for key, adjustment in adjustments.items():
            lines.append(f"- **{key}**: {adjustment}")
        lines.append("")
    
    lines.extend([
        "## Interpretation Guide",
        "",
        "- **High** 🟢: Strong evidence base, high triangulation, multiple primary sources",
        "- **Moderate** 🟡: Acceptable evidence with some limitations, adjusted thresholds applied",
        "- **Low** 🔴: Limited evidence, significant constraints, interpret with caution",
        "",
        "*Note: Quality gates were adaptively adjusted based on available evidence supply.*"
    ])
    
    return "\n".join(lines)