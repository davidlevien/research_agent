"""Adaptive orchestrator enhancements for supply-aware quality gates."""

import logging
from typing import List, Dict, Tuple, Optional, Set
from pathlib import Path
from collections import Counter

from research_system.quality_config.quality import QualityConfig
from research_system.quality_config.report import ReportConfig, choose_report_tier, format_tier_badge
from research_system.strict.adaptive_guard import (
    adaptive_strict_check, 
    SupplyContext,
    ConfidenceLevel,
    format_confidence_report,
    should_attempt_last_mile_backfill
)
from research_system.models import EvidenceCard


logger = logging.getLogger(__name__)


def apply_adaptive_domain_balance(
    cards: List[EvidenceCard],
    config: QualityConfig,
    unique_domains: int
) -> Tuple[List[EvidenceCard], Dict[str, int], str]:
    """
    Apply domain balance with adaptive cap based on domain diversity.
    
    Args:
        cards: Evidence cards to balance
        config: Quality configuration
        unique_domains: Number of unique domains
        
    Returns:
        Tuple of (balanced_cards, domain_counts, adjustment_note)
    """
    from research_system.selection.domain_balance import canonical_domain
    
    # Determine cap based on domain diversity
    if unique_domains < config.domain_balance.few_domains_threshold:
        cap = config.domain_balance.cap_when_few_domains
        adjustment_note = f"Domain cap relaxed to {cap:.0%} (few domains: {unique_domains})"
    else:
        cap = config.domain_balance.cap_default
        adjustment_note = f"Standard domain cap {cap:.0%} applied"
    
    # Count cards per domain
    domain_counts = Counter()
    domain_cards = {}
    
    for card in cards:
        domain = canonical_domain(card.source_domain)
        domain_counts[domain] += 1
        if domain not in domain_cards:
            domain_cards[domain] = []
        domain_cards[domain].append(card)
    
    # Apply cap
    max_per_domain = max(1, int(len(cards) * cap))
    balanced_cards = []
    kept_counts = {}
    
    for domain, cards_list in domain_cards.items():
        # Sort by confidence/credibility to keep best
        cards_list.sort(
            key=lambda c: c.confidence * c.credibility_score,
            reverse=True
        )
        keep = cards_list[:max_per_domain]
        balanced_cards.extend(keep)
        kept_counts[domain] = len(keep)
    
    logger.info(
        f"Adaptive domain balance: cap={cap:.2f} kept={len(balanced_cards)} "
        f"from {len(cards)} cards across {unique_domains} domains"
    )
    
    return balanced_cards, kept_counts, adjustment_note


def apply_adaptive_credibility_floor(
    cards: List[EvidenceCard],
    config: QualityConfig
) -> Tuple[List[EvidenceCard], int, Set[str]]:
    """
    Apply credibility floor with whitelisted singleton protection.
    v8.21.0: Enhanced to prevent over-filtering of trusted sources.
    
    Args:
        cards: Evidence cards to filter
        config: Quality configuration
        
    Returns:
        Tuple of (filtered_cards, num_filtered, retained_singletons)
    """
    import os
    from research_system.selection.domain_balance import canonical_domain
    
    # v8.21.0: Default trusted domains that should never be filtered
    TRUSTED_DEFAULT = {
        "oecd.org", "stats.oecd.org", "unwto.org", "e-unwto.org", "wttc.org",
        "etc-corporate.org", "eurostat.ec.europa.eu", "iata.org", "icao.int",
        "ustravel.org", "amadeus.com", "skift.com", "abta.com", "americanexpress.com",
        "mastercard.com", "bbc.com", "cnbc.com", "worldbank.org", "data.worldbank.org",
        "imf.org", "treasury.gov", "europa.eu", "ec.europa.eu", "who.int", "un.org",
        "unesco.org", "ilo.org", "cdc.gov", "nih.gov", "census.gov", "bls.gov",
        "federalreserve.gov", "ecb.europa.eu", "weforum.org"
    }
    
    # Parse additional trusted domains from environment
    def _parse_set(env_name: str, base: Set[str]) -> Set[str]:
        raw = os.getenv(env_name)
        if not raw:
            return base
        return base | {d.strip().lower() for d in raw.split(",") if d.strip()}
    
    trusted = _parse_set("TRUSTED_DOMAINS", TRUSTED_DEFAULT)
    
    # Count domain frequencies
    domain_counts = Counter(
        canonical_domain(c.source_domain) for c in cards
    )
    
    filtered_cards = []
    retained_singletons = set()
    num_filtered = 0
    
    for card in cards:
        domain = canonical_domain(card.source_domain).lower()
        is_singleton = domain_counts[canonical_domain(card.source_domain)] == 1
        
        # v8.21.0: Always keep trusted domains regardless of frequency or credibility
        if domain in trusted:
            filtered_cards.append(card)
            if is_singleton:
                retained_singletons.add(domain)
            continue
        
        if is_singleton:
            # Check whitelist
            if domain in config.credibility.whitelist_singletons:
                # Keep but potentially downweight
                if hasattr(card, 'credibility_score'):
                    card.credibility_score *= config.credibility.singleton_downweight
                filtered_cards.append(card)
                retained_singletons.add(domain)
            elif card.credibility_score >= 0.7:
                # Keep high-credibility singletons
                filtered_cards.append(card)
                retained_singletons.add(domain)
            else:
                # Filter low-credibility non-whitelisted singleton
                num_filtered += 1
        else:
            # Always keep non-singletons
            filtered_cards.append(card)
    
    if num_filtered > 0:
        logger.info(
            f"Adaptive credibility floor: filtered {num_filtered} low-cred singletons, "
            f"retained {len(retained_singletons)} whitelisted/high-cred singletons"
        )
    
    return filtered_cards, num_filtered, retained_singletons


def compute_adaptive_metrics(
    cards: List[EvidenceCard],
    triangulated_cards: int,
    primary_share: float,
    provider_errors: int = 0,
    provider_attempts: int = 1
) -> Dict:
    """
    Compute comprehensive metrics including supply indicators.
    
    Args:
        cards: Evidence cards
        triangulated_cards: Number of triangulated cards
        primary_share: Share of primary sources (0-1)
        provider_errors: Number of provider errors (403s, 429s, timeouts)
        provider_attempts: Total provider attempts
        
    Returns:
        Dictionary of metrics including supply context
    """
    from research_system.selection.domain_balance import canonical_domain
    
    unique_domains = len(set(
        canonical_domain(c.source_domain) for c in cards
    ))
    
    credible_cards = len([c for c in cards if c.credibility_score >= 0.5])
    provider_error_rate = provider_errors / max(1, provider_attempts)
    
    # Domain concentration
    domain_counts = Counter(
        canonical_domain(c.source_domain) for c in cards
    )
    max_domain_share = (
        max(domain_counts.values()) / len(cards) if cards else 0
    )
    
    return {
        "total_cards": len(cards),
        "credible_cards": credible_cards,
        "unique_domains": unique_domains,
        "triangulated_cards": triangulated_cards,
        "triangulation_rate": triangulated_cards / max(1, len(cards)),
        "primary_share": primary_share,
        "primary_cards": int(primary_share * len(cards)),
        "provider_errors": provider_errors,
        "provider_attempts": provider_attempts,
        "provider_error_rate": provider_error_rate,
        "domain_concentration": max_domain_share,
        "strict_mode": False  # Will be set by orchestrator
    }


def generate_adaptive_report_metadata(
    metrics: Dict,
    confidence_level: ConfidenceLevel,
    adjustments: Dict[str, str],
    report_tier: str,
    report_confidence: float,
    tier_explanation: str
) -> str:
    """
    Generate comprehensive metadata section for report.
    
    Args:
        metrics: Metrics dictionary
        confidence_level: Quality gate confidence level
        adjustments: Adjustments made to quality gates
        report_tier: Selected report tier
        report_confidence: Report confidence score
        tier_explanation: Explanation for tier selection
        
    Returns:
        Formatted metadata markdown
    """
    from research_system.quality_config.report import ReportTier
    
    # Enforce invariant: confidence level always set
    from research_system.strict.adaptive_guard import ConfidenceLevel as CL
    conf_level = confidence_level if confidence_level is not None else CL.MODERATE
    emoji = conf_level.to_emoji() if hasattr(conf_level, 'to_emoji') else "🟡"
    label = conf_level.value.title() if hasattr(conf_level, 'value') else "Moderate"
    
    lines = [
        "# Research Metadata",
        "",
        "## Quality Assessment",
        "",
        f"### Overall Confidence: {emoji} {label}",
        ""
    ]
    
    # Quality adjustments
    if adjustments:
        lines.extend([
            "### Adaptive Adjustments Applied",
            ""
        ])
        for gate, adjustment in adjustments.items():
            lines.append(f"- **{gate.replace('_', ' ').title()}**: {adjustment}")
        lines.append("")
    
    # Report profile
    tier_enum = ReportTier(report_tier.lower()) if isinstance(report_tier, str) else report_tier
    badge = format_tier_badge(tier_enum, report_confidence, tier_explanation)
    lines.extend([
        "## Report Configuration", 
        "",
        badge,
        ""
    ])
    
    # Supply metrics
    lines.extend([
        "## Evidence Supply Metrics",
        "",
        f"- Total cards collected: {metrics.get('total_cards', 0)}",
        f"- Credible cards: {metrics.get('credible_cards', 0)}",
        f"- Unique domains: {metrics.get('unique_domains', 0)}",
        f"- Triangulated cards: {metrics.get('triangulated_cards', 0)}",
        f"- Triangulation rate: {metrics.get('triangulation_rate', 0):.1%}",
        f"- Primary source share: {metrics.get('primary_share', 0):.1%}",
        f"- Provider error rate: {metrics.get('provider_error_rate', 0):.1%}",
        f"- Domain concentration: {metrics.get('domain_concentration', 0):.1%}",
        ""
    ])
    
    # Warnings
    if confidence_level == ConfidenceLevel.LOW:
        lines.extend([
            "## ⚠️ Important Notice",
            "",
            "Results should be interpreted with caution due to limited evidence "
            "availability or source diversity. Consider expanding search parameters "
            "or waiting for more sources to become available.",
            ""
        ])
    elif confidence_level == ConfidenceLevel.MODERATE:
        lines.extend([
            "## ℹ️ Notice",
            "",
            "Some quality thresholds were relaxed due to evidence supply constraints. "
            "Core findings remain reliable but may benefit from additional corroboration.",
            ""
        ])
    
    return "\n".join(lines)


def should_skip_strict_fail(
    errors: List[str],
    adjustments: Dict[str, str],
    confidence: ConfidenceLevel
) -> bool:
    """
    Determine if strict mode failures should be warnings instead.
    
    Args:
        errors: List of quality gate errors
        adjustments: Adjustments that were made
        confidence: Confidence level determined
        
    Returns:
        True if errors should be warnings, False if should fail
    """
    # If we made many adjustments and still failed, convert to warning
    if len(adjustments) >= 2 and confidence in [ConfidenceLevel.LOW, ConfidenceLevel.MODERATE]:
        return True
    
    # If only triangulation failed slightly, convert to warning
    if len(errors) == 1 and "TRIANGULATION" in errors[0]:
        # Extract percentage from error string
        import re
        match = re.search(r'TRIANGULATION\((\d+)%\)', errors[0])
        if match:
            actual = int(match.group(1))
            # If within 5pp of target, make it a warning
            if actual >= 30:
                return True
    
    return False