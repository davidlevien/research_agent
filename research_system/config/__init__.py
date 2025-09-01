"""Unified configuration module.

Single source of truth for all configuration and settings.
"""

from .settings import (
    settings,
    Settings,
    QualityThresholds,
    quality_for_intent,
    PRIMARY_ORGS,
    SEMI_AUTHORITATIVE_ORGS,
    INTENT_BLOCKLIST,
    PER_DOMAIN_HEADERS,
    INTENT_THRESHOLDS,
    STRICT_ADJUSTMENTS,
)

# Alias for backward compatibility
config = settings

__all__ = [
    "settings",
    "config",  # Backward compatibility
    "Settings",
    "QualityThresholds",
    "quality_for_intent",
    "PRIMARY_ORGS",
    "SEMI_AUTHORITATIVE_ORGS",
    "INTENT_BLOCKLIST",
    "PER_DOMAIN_HEADERS",
    "INTENT_THRESHOLDS",
    "STRICT_ADJUSTMENTS",
]