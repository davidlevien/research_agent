"""Quality gates for research evidence, with strict stats intent requirements."""

import logging
from typing import Dict, Tuple, Any

logger = logging.getLogger(__name__)


def safe_get(metrics: dict, key: str, default: Any = 0.0) -> Any:
    """Safely get a value from metrics dict."""
    return metrics.get(key, default)


def meets_minimum_bar(metrics: Dict, intent: str) -> bool:
    """
    Check if evidence meets minimum quality bar for given intent.
    
    For stats intent, requires:
    - ≥50% primary/official sources
    - ≥3 recent primary sources (last 24 months)
    - ≥1 triangulated cluster
    
    Args:
        metrics: Quality metrics dict
        intent: Research intent (e.g., "stats", "generic")
        
    Returns:
        True if quality gates pass, False otherwise
    """
    from research_system.config import Settings
    settings = Settings()
    
    if intent == settings.STATS_INTENT:
        primary_share = safe_get(metrics, "primary_share_in_union", 0.0)
        recent_primary = safe_get(metrics, "recent_primary_count", 0)
        triangulated = safe_get(metrics, "triangulated_clusters", 0)
        
        # All three conditions must be met for stats
        passes = (
            primary_share >= settings.STATS_PRIMARY_SHARE_MIN and
            recent_primary >= settings.STATS_RECENT_PRIMARY_MIN and
            triangulated >= settings.STATS_TRIANGULATED_MIN
        )
        
        if not passes:
            logger.warning(
                "Stats quality gates failed: primary_share=%.2f (need >=%.2f), "
                "recent_primary=%d (need >=%d), triangulated=%d (need >=%d)",
                primary_share, settings.STATS_PRIMARY_SHARE_MIN,
                recent_primary, settings.STATS_RECENT_PRIMARY_MIN,
                triangulated, settings.STATS_TRIANGULATED_MIN
            )
        
        return passes
    
    # Generic intent - use existing thresholds
    primary_share = safe_get(metrics, "primary_share_in_union", 0.0)
    triangulation = safe_get(metrics, "union_triangulation", 0.0)
    confidence = safe_get(metrics, "confidence", 0.0)
    
    # Original thresholds for non-stats
    return (
        primary_share >= 0.40 and
        triangulation >= 0.25 and
        confidence >= 0.35
    )


def explain_bar(metrics: Dict, intent: str) -> Dict[str, Tuple[Any, Any]]:
    """
    Explain why quality gates failed with comprehensive logging.
    
    Returns dict mapping metric name to (actual_value, required_value) tuples.
    """
    from research_system.config import Settings
    settings = Settings()
    
    logger.info(f"=== Quality Gate Analysis for intent={intent} ===")
    
    explanations = {}
    
    if intent == settings.STATS_INTENT:
        # Log all relevant metrics for stats intent
        primary_share = metrics.get("primary_share_in_union", 0.0)
        recent_primary = metrics.get("recent_primary_count", 0)
        triangulated = metrics.get("triangulated_clusters", 0)
        
        logger.info(f"Stats intent quality check:")
        logger.info(f"  Primary source share: {primary_share:.1%} (required: {settings.STATS_PRIMARY_SHARE_MIN:.0%})")
        logger.info(f"  Recent primary sources: {recent_primary} (required: {settings.STATS_RECENT_PRIMARY_MIN})")
        logger.info(f"  Triangulated clusters: {triangulated} (required: {settings.STATS_TRIANGULATED_MIN})")
        
        # Check each gate
        if primary_share < settings.STATS_PRIMARY_SHARE_MIN:
            logger.warning(f"  ❌ FAILED: Primary share {primary_share:.1%} < {settings.STATS_PRIMARY_SHARE_MIN:.0%}")
        else:
            logger.info(f"  ✅ PASSED: Primary share requirement")
            
        if recent_primary < settings.STATS_RECENT_PRIMARY_MIN:
            logger.warning(f"  ❌ FAILED: Recent primary {recent_primary} < {settings.STATS_RECENT_PRIMARY_MIN}")
        else:
            logger.info(f"  ✅ PASSED: Recent primary requirement")
            
        if triangulated < settings.STATS_TRIANGULATED_MIN:
            logger.warning(f"  ❌ FAILED: Triangulated clusters {triangulated} < {settings.STATS_TRIANGULATED_MIN}")
        else:
            logger.info(f"  ✅ PASSED: Triangulation requirement")
        
        explanations["primary_share"] = (primary_share, settings.STATS_PRIMARY_SHARE_MIN)
        explanations["recent_primary_count"] = (recent_primary, settings.STATS_RECENT_PRIMARY_MIN)
        explanations["triangulated_clusters"] = (triangulated, settings.STATS_TRIANGULATED_MIN)
    else:
        # Log metrics for generic intent
        primary_share = metrics.get("primary_share_in_union", 0.0)
        triangulation = metrics.get("union_triangulation", 0.0)
        confidence = metrics.get("confidence", 0.0)
        
        logger.info(f"Generic intent quality check:")
        logger.info(f"  Primary share: {primary_share:.1%} (required: 40%)")
        logger.info(f"  Triangulation: {triangulation:.1%} (required: 25%)")
        logger.info(f"  Confidence: {confidence:.2f} (required: 0.35)")
        
        if primary_share < 0.40:
            logger.warning(f"  ❌ FAILED: Primary share {primary_share:.1%} < 40%")
        if triangulation < 0.25:
            logger.warning(f"  ❌ FAILED: Triangulation {triangulation:.1%} < 25%")
        if confidence < 0.35:
            logger.warning(f"  ❌ FAILED: Confidence {confidence:.2f} < 0.35")
        
        explanations["primary_share"] = (primary_share, 0.40)
        explanations["triangulation"] = (triangulation, 0.25)
        explanations["confidence"] = (confidence, 0.35)
    
    # Log additional context
    logger.info(f"Additional metrics:")
    logger.info(f"  Total cards: {metrics.get('total_cards', 0)}")
    logger.info(f"  Unique domains: {metrics.get('unique_domains', 0)}")
    logger.info(f"  Credible cards: {metrics.get('credible_cards', 0)}")
    logger.info(f"  Provider error rate: {metrics.get('provider_error_rate', 0):.1%}")
    
    return explanations


def calculate_recent_primary_count(cards: list, days: int = 730) -> int:
    """
    Count primary sources from recent time period.
    
    Args:
        cards: List of evidence cards
        days: Number of days to consider recent (default 730 = ~24 months)
        
    Returns:
        Count of recent primary source cards
    """
    from datetime import datetime, timedelta, timezone
    from research_system.config import Settings
    
    settings = Settings()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    count = 0
    
    for card in cards:
        # Check if primary source
        domain = getattr(card, 'source_domain', '').lower()
        is_primary = (
            getattr(card, 'is_primary_source', False) or
            domain in settings.STATS_ALLOWED_PRIMARY_DOMAINS
        )
        
        if not is_primary:
            continue
        
        # Check if recent
        collected_at = getattr(card, 'collected_at', None)
        if collected_at:
            try:
                # Parse ISO format
                if isinstance(collected_at, str):
                    # Handle both 'Z' suffix and existing timezone info
                    if collected_at.endswith('Z'):
                        card_date = datetime.fromisoformat(collected_at.replace('Z', '+00:00'))
                    else:
                        card_date = datetime.fromisoformat(collected_at)
                    
                    # Ensure timezone-aware
                    if card_date.tzinfo is None:
                        card_date = card_date.replace(tzinfo=timezone.utc)
                    
                    if card_date >= cutoff:
                        count += 1
            except (ValueError, AttributeError):
                pass
    
    return count


def count_triangulated_clusters(clusters: list) -> int:
    """
    Count clusters that have true triangulation (2+ domains).
    
    Args:
        clusters: List of cluster dicts
        
    Returns:
        Count of triangulated clusters
    """
    count = 0
    
    for cluster in clusters:
        # Check if cluster has multiple domains
        domains = cluster.get('domains', [])
        if len(domains) >= 2:
            count += 1
    
    return count


def calculate_stats_metrics(cards: list, clusters: list) -> Dict:
    """
    Calculate metrics specific to stats intent validation.
    
    Args:
        cards: List of evidence cards
        clusters: List of triangulation clusters
        
    Returns:
        Dict with stats-specific metrics
    """
    from research_system.config import Settings
    settings = Settings()
    
    # Count primary sources
    primary_count = sum(
        1 for card in cards
        if getattr(card, 'is_primary_source', False) or
        getattr(card, 'source_domain', '').lower() in settings.STATS_ALLOWED_PRIMARY_DOMAINS
    )
    
    total_count = len(cards)
    primary_share = primary_count / max(1, total_count)
    
    # Count recent primary sources
    recent_primary = calculate_recent_primary_count(cards)
    
    # Count triangulated clusters
    triangulated = count_triangulated_clusters(clusters)
    
    return {
        "primary_share_in_union": primary_share,
        "recent_primary_count": recent_primary,
        "triangulated_clusters": triangulated,
        "total_cards": total_count,
        "primary_cards": primary_count
    }