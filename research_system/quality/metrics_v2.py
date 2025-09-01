"""Unified metrics computation for v8.13.0."""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from collections import Counter
import logging

from research_system.config_v2 import load_quality_config
from research_system.utils.file_ops import atomic_write_json

logger = logging.getLogger(__name__)

@dataclass
class FinalMetrics:
    """Immutable metrics computed once after final filtering."""
    primary_share: float
    triangulation_rate: float
    domain_concentration: float
    sample_sizes: Dict[str, int]
    unique_domains: int
    credible_cards: int
    provider_error_rate: float = 0.0
    recent_primary_count: int = 0
    triangulated_clusters: int = 0

def compute_metrics(cards: List[Any], clusters: Optional[List] = None, 
                   provider_errors: int = 0, provider_attempts: int = 0) -> FinalMetrics:
    """
    Compute metrics once from final filtered cards.
    
    Args:
        cards: List of evidence cards after dedup, canonicalization, and final acceptance
        clusters: Optional list of triangulation clusters
        provider_errors: Number of provider failures (403/429/timeout)
        provider_attempts: Total provider attempts
        
    Returns:
        FinalMetrics object with all computed values
    """
    cfg = load_quality_config()
    n = len(cards) or 1
    
    # Primary share calculation (handle Mock objects properly)
    primary = 0
    for c in cards:
        # Check is_primary_source first
        is_primary_source = getattr(c, 'is_primary_source', False)
        # Explicit boolean check to avoid Mock objects being truthy
        if is_primary_source is True:
            primary += 1
            continue
            
        # Check labels.is_primary as fallback
        labels_obj = getattr(c, 'labels', None)
        if labels_obj is not None:
            labels_is_primary = getattr(labels_obj, 'is_primary', False)
            # Explicit boolean check to avoid Mock objects being truthy
            if labels_is_primary is True:
                primary += 1
    primary_share = primary / n
    
    # v8.24.0: Triangulation rate based on post-sanitization clusters
    # If clusters are provided, use them to determine triangulated cards
    tri_support = 0
    if clusters:
        # Collect all card indices that are in multi-domain clusters
        triangulated_indices = set()
        for cluster in clusters:
            # Check if cluster has multiple domains
            cluster_domains = getattr(cluster, 'domains', [])
            if isinstance(cluster, dict):
                cluster_domains = cluster.get('domains', [])
            
            if len(cluster_domains) >= 2:
                # Add all card indices from this cluster
                cluster_indices = getattr(cluster, 'indices', [])
                if isinstance(cluster, dict):
                    cluster_indices = cluster.get('indices', [])
                triangulated_indices.update(cluster_indices)
        
        # Count cards that are in triangulated clusters
        tri_support = len(triangulated_indices)
    else:
        # Fallback to card-level triangulated attribute
        tri_support = sum(1 for c in cards if getattr(c, "triangulated", False))
    
    triangulation_rate = tri_support / n
    
    # Domain concentration
    domains = [getattr(c, 'source_domain', getattr(c, 'domain', 'unknown')).lower() 
               for c in cards]
    dom_counts = Counter(domains)
    domain_concentration = max(dom_counts.values()) / n if dom_counts else 0.0
    unique_domains = len(set(domains))
    
    # Credible cards (above threshold)
    credible_cards = sum(1 for c in cards 
                        if getattr(c, 'credibility_score', 0.5) >= 0.6)
    
    # Provider error rate
    provider_error_rate = (provider_errors / max(provider_attempts, 1)) if provider_attempts else 0.0
    
    # Recent primary count (from gates.py if available)
    recent_primary_count = 0
    if cards and hasattr(cards[0], '__class__'):  # Check if we can import
        try:
            from research_system.quality.gates import calculate_recent_primary_count
            recent_primary_count = calculate_recent_primary_count(cards)
        except ImportError:
            pass
    
    # Triangulated clusters count
    triangulated_clusters = 0
    if clusters:
        triangulated_clusters = sum(1 for cluster in clusters 
                                  if len(getattr(cluster, 'domains', [])) >= 2)
    
    metrics = FinalMetrics(
        primary_share=primary_share,
        triangulation_rate=triangulation_rate,
        domain_concentration=domain_concentration,
        sample_sizes={"total_cards": len(cards), "primary": primary, "credible": credible_cards},
        unique_domains=unique_domains,
        credible_cards=credible_cards,
        provider_error_rate=provider_error_rate,
        recent_primary_count=recent_primary_count,
        triangulated_clusters=triangulated_clusters
    )
    
    logger.info(
        "Computed final metrics: primary=%.1f%%, triangulation=%.1f%%, domains=%d, concentration=%.1f%%",
        metrics.primary_share * 100,
        metrics.triangulation_rate * 100,
        metrics.unique_domains,
        metrics.domain_concentration * 100
    )
    
    return metrics

def gates_pass(m: FinalMetrics, intent: str = "generic") -> bool:
    """
    Check if metrics pass quality gates for given intent.
    v8.22.0: Use intent-specific thresholds when available.
    
    Args:
        m: Computed metrics
        intent: Research intent
        
    Returns:
        True if all gates pass, False otherwise
    """
    cfg = load_quality_config()
    
    # v8.22.0: Get intent-specific thresholds if available
    try:
        from research_system.providers.intent_registry import get_intent_thresholds
        intent_thresholds = get_intent_thresholds(intent)
        
        # Use intent-specific thresholds if they exist
        primary_floor = intent_thresholds.get("primary_share", cfg.primary_share_floor)
        triangulation_floor = intent_thresholds.get("triangulation", cfg.triangulation_floor)
        domain_cap = intent_thresholds.get("domain_cap", cfg.domain_concentration_cap)
        
        logger.info(f"Using intent-specific thresholds for {intent}: primary={primary_floor}, triangulation={triangulation_floor}, domain_cap={domain_cap}")
    except ImportError:
        # Fall back to default config if intent registry not available
        primary_floor = cfg.primary_share_floor
        triangulation_floor = cfg.triangulation_floor
        domain_cap = cfg.domain_concentration_cap
    
    # Basic gates with intent-specific thresholds
    basic_pass = (
        m.primary_share >= primary_floor and
        m.triangulation_rate >= triangulation_floor and
        m.domain_concentration <= domain_cap
    )
    
    # Additional gates for stats intent
    if intent == "stats":
        stats_pass = (
            m.recent_primary_count >= 3 and
            m.triangulated_clusters >= 1
        )
        return basic_pass and stats_pass
    
    return basic_pass

def write_metrics(run_dir: str, m: FinalMetrics, intent: str = None) -> None:
    """
    Write metrics to JSON file atomically.
    v8.23.0: Include pass/fail status aligned with intent-specific gates.
    """
    # Get intent-specific thresholds
    from research_system.providers.intent_registry import get_intent_thresholds
    intent_thresholds = get_intent_thresholds(intent) if intent else {}
    
    # Use intent-specific or default thresholds
    from research_system.quality_config.quality import QualityConfig
    cfg = QualityConfig()
    # Use defaults from config or intent-specific overrides
    primary_floor = intent_thresholds.get("primary_share", cfg.primary_share.target_pct)
    triangulation_floor = intent_thresholds.get("triangulation", cfg.triangulation.target_normal_pct)
    domain_cap = intent_thresholds.get("domain_cap", cfg.domain_balance.cap_default)
    
    # v8.23.0: Write metrics with pass/fail status aligned to gates
    atomic_write_json(f"{run_dir}/metrics.json", {
        "primary_share": round(m.primary_share, 4),
        "triangulation_rate": round(m.triangulation_rate, 4),
        "domain_concentration": round(m.domain_concentration, 4),
        "unique_domains": m.unique_domains,
        "credible_cards": m.credible_cards,
        "provider_error_rate": round(m.provider_error_rate, 4),
        "recent_primary_count": m.recent_primary_count,
        "triangulated_clusters": m.triangulated_clusters,
        "sample_sizes": m.sample_sizes,
        # v8.23.0: Add pass/fail status aligned with actual gates
        "pass_primary": m.primary_share >= primary_floor,
        "pass_triangulation": m.triangulation_rate >= triangulation_floor,
        "pass_concentration": m.domain_concentration <= domain_cap,
        "thresholds_used": {
            "primary_share_floor": primary_floor,
            "triangulation_floor": triangulation_floor,
            "domain_cap": domain_cap,
            "intent": intent or "generic"
        }
    })
    logger.info(f"Wrote metrics to {run_dir}/metrics.json")