"""Adaptive quality configuration for research system."""

from .quality import (
    QualityConfig,
    TriangulationConfig,
    PrimaryShareConfig,
    DomainBalanceConfig,
    BackfillConfig,
    CredibilityConfig
)

from .report import (
    ReportConfig,
    ReportTier,
    TierConfig,
    choose_report_tier,
    compute_confidence,
    format_tier_badge
)

__all__ = [
    # Quality configs
    'QualityConfig',
    'TriangulationConfig',
    'PrimaryShareConfig',
    'DomainBalanceConfig',
    'BackfillConfig',
    'CredibilityConfig',
    # Report configs
    'ReportConfig',
    'ReportTier',
    'TierConfig',
    'choose_report_tier',
    'compute_confidence',
    'format_tier_badge',
]