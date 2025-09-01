"""Unified collection module.

Single source of truth for evidence collection from various providers.
"""

from .enhanced import (
    _exec,
    _provider_policy,
    parallel_provider_search,
    collect_from_free_apis,
)

__all__ = [
    "_exec",
    "_provider_policy",
    "parallel_provider_search",
    "collect_from_free_apis",
]