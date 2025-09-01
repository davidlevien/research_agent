"""Unified metrics model for the research system.

Single source of truth for all run metrics.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional


@dataclass
class RunMetrics:
    """Unified metrics for a research run."""
    
    # Core quality metrics
    primary_share: float
    triangulation: float  
    domain_concentration: float
    
    # Additional metrics
    effective_thresholds: Optional[Dict[str, float]] = None
    unique_domains: int = 0
    total_cards: int = 0
    triangulated_cards: int = 0
    credible_cards: int = 0
    recent_primary_count: int = 0
    triangulated_clusters: int = 0
    
    # Sample sizes for statistical validity
    sample_sizes: Optional[Dict[str, int]] = None
    
    # Intent and configuration
    intent: Optional[str] = None
    strict_mode: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for serialization."""
        return asdict(self)
    
    def passes_gates(self, thresholds: Optional[Dict[str, float]] = None) -> bool:
        """Check if metrics pass quality gates.
        
        Args:
            thresholds: Optional dict with 'primary', 'triangulation', 'domain_cap' keys.
                       If not provided, uses effective_thresholds.
        
        Returns:
            True if all thresholds are met
        """
        if thresholds is None:
            thresholds = self.effective_thresholds
        
        if thresholds is None:
            # No thresholds to check against
            return True
        
        return (
            self.primary_share >= thresholds.get('primary', 0) and
            self.triangulation >= thresholds.get('triangulation', 0) and
            self.domain_concentration <= thresholds.get('domain_cap', 1.0)
        )
    
    def __str__(self) -> str:
        """String representation for logging."""
        return (
            f"RunMetrics(primary={self.primary_share:.1%}, "
            f"tri={self.triangulation:.1%}, "
            f"domain_conc={self.domain_concentration:.1%}, "
            f"cards={self.total_cards})"
        )


@dataclass
class TriangulationMetrics:
    """Detailed triangulation metrics."""
    
    union_rate: float  # Overall triangulation rate
    post_sanitization_rate: float  # Rate after filtering
    intersection_rate: float  # Multi-provider agreement rate
    
    # Cluster metrics
    total_clusters: int = 0
    contradictory_clusters: int = 0
    preserved_clusters: int = 0
    
    # Evidence metrics
    cards_in_clusters: int = 0
    cards_triangulated: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)