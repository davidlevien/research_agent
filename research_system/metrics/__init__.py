"""Unified metrics module.

Single source of truth for all research run metrics.
"""

from .run import RunMetrics, TriangulationMetrics
from .adapters import (
    from_quality_metrics_v2,
    from_orchestrator_metrics,
    to_legacy_format,
    merge_triangulation_metrics,
)

# Import prometheus metrics from the monitoring module
try:
    from research_system.monitoring_metrics import SEARCH_REQUESTS, SEARCH_ERRORS, SEARCH_LATENCY
except ImportError:
    # If prometheus_client not installed, create dummies
    class DummyMetric:
        def labels(self, **kwargs):
            return self
        def inc(self):
            pass
        def observe(self, value):
            pass
    
    SEARCH_REQUESTS = DummyMetric()
    SEARCH_ERRORS = DummyMetric()
    SEARCH_LATENCY = DummyMetric()

__all__ = [
    "RunMetrics",
    "TriangulationMetrics",
    "from_quality_metrics_v2",
    "from_orchestrator_metrics",
    "to_legacy_format",
    "merge_triangulation_metrics",
    "SEARCH_REQUESTS",
    "SEARCH_ERRORS",
    "SEARCH_LATENCY",
]