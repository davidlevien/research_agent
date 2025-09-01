"""DEPRECATION SHIM — use research_system.utils.datetime_safe instead."""

# v8.25.0: Forward to single source of truth
from .datetime_safe import safe_strftime  # noqa

__all__ = ["safe_strftime"]