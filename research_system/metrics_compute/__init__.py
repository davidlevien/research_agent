"""Metrics computation for research system."""

from .triangulation import (
    compute_union_triangulation,
    provider_entropy,
    primary_share_in_triangulated,
    label_finding
)

__all__ = [
    "compute_union_triangulation",
    "provider_entropy", 
    "primary_share_in_triangulated",
    "label_finding"
]