"""Adapters for converting between legacy and unified metrics.

Provides compatibility layer for existing code using different metric formats.
"""

from __future__ import annotations
from typing import Any, Dict, Optional
from .run import RunMetrics, TriangulationMetrics


def from_quality_metrics_v2(m: Any) -> RunMetrics:
    """Convert from quality/metrics_v2.FinalMetrics to RunMetrics.
    
    Args:
        m: A FinalMetrics or similar object with expected attributes
        
    Returns:
        Unified RunMetrics instance
    """
    return RunMetrics(
        primary_share=float(getattr(m, "primary_share", 0)),
        triangulation=float(getattr(m, "triangulation_rate", 0)),
        domain_concentration=float(getattr(m, "domain_concentration", 0)),
        effective_thresholds=getattr(m, "effective_thresholds", None),
        unique_domains=getattr(m, "unique_domains", 0),
        total_cards=getattr(m, "total_cards", 0),
        triangulated_cards=getattr(m, "triangulated_cards", 0),
        credible_cards=getattr(m, "credible_cards", 0),
        recent_primary_count=getattr(m, "recent_primary_count", 0),
        triangulated_clusters=getattr(m, "triangulated_clusters", 0),
        sample_sizes=getattr(m, "sample_sizes", None),
        intent=getattr(m, "intent", None),
        strict_mode=getattr(m, "strict_mode", False),
    )


def from_orchestrator_metrics(metrics_dict: Dict[str, Any]) -> RunMetrics:
    """Convert from orchestrator metrics dictionary to RunMetrics.
    
    Args:
        metrics_dict: Dictionary with metric values
        
    Returns:
        Unified RunMetrics instance
    """
    return RunMetrics(
        primary_share=metrics_dict.get("primary_share_in_union", 0),
        triangulation=metrics_dict.get("union_triangulation", 0),
        domain_concentration=metrics_dict.get("domain_concentration", 0),
        effective_thresholds=metrics_dict.get("effective_thresholds"),
        unique_domains=metrics_dict.get("unique_domains", 0),
        total_cards=metrics_dict.get("total_cards", 0),
        triangulated_cards=metrics_dict.get("triangulated_cards", 0),
        credible_cards=metrics_dict.get("credible_cards", 0),
        recent_primary_count=metrics_dict.get("recent_primary_count", 0),
        triangulated_clusters=metrics_dict.get("triangulated_clusters", 0),
        sample_sizes=metrics_dict.get("sample_sizes"),
        intent=metrics_dict.get("intent"),
        strict_mode=metrics_dict.get("strict_mode", False),
    )


def to_legacy_format(metrics: RunMetrics) -> Dict[str, Any]:
    """Convert RunMetrics to legacy format for backward compatibility.
    
    Args:
        metrics: Unified RunMetrics instance
        
    Returns:
        Dictionary in legacy format
    """
    return {
        "primary_share_in_union": metrics.primary_share,
        "union_triangulation": metrics.triangulation,
        "domain_concentration": metrics.domain_concentration,
        "unique_domains": metrics.unique_domains,
        "total_cards": metrics.total_cards,
        "triangulated_cards": metrics.triangulated_cards,
        "credible_cards": metrics.credible_cards,
        "recent_primary_count": metrics.recent_primary_count,
        "triangulated_clusters": metrics.triangulated_clusters,
        "sample_sizes": metrics.sample_sizes,
        "intent": metrics.intent,
        "strict_mode": metrics.strict_mode,
        "effective_thresholds": metrics.effective_thresholds,
    }


def merge_triangulation_metrics(
    run_metrics: RunMetrics, 
    tri_metrics: TriangulationMetrics
) -> RunMetrics:
    """Merge triangulation metrics into run metrics.
    
    Args:
        run_metrics: Base run metrics
        tri_metrics: Detailed triangulation metrics
        
    Returns:
        Updated RunMetrics with triangulation data
    """
    run_metrics.triangulation = tri_metrics.post_sanitization_rate
    run_metrics.triangulated_clusters = tri_metrics.preserved_clusters
    run_metrics.triangulated_cards = tri_metrics.cards_triangulated
    return run_metrics