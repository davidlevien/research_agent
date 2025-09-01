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

__all__ = [
    "settings",
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