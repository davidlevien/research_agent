"""DEPRECATION SHIM — use research_system.utils.deterministic instead."""

# v8.25.0: Forward to single source of truth
from .deterministic import set_global_seeds  # noqa

__all__ = ["set_global_seeds"]