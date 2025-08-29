"""
Central run context and metrics loader for single source of truth.
Implements v8.15.0 improvements for topic-agnostic quality control.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class Metrics:
    """Centralized metrics loaded from disk to prevent drift."""
    cards: int = 0
    quote_coverage: float = 0.0
    union_triangulation: float = 0.0
    primary_share: float = 0.0
    top_domain_share: float = 0.0
    triangulated_cards: int = 0
    credible_cards: int = 0
    unique_domains: int = 0
    
    @classmethod
    def from_file(cls, path: Path) -> "Metrics":
        """Load metrics from JSON file with fallbacks for missing fields."""
        try:
            if not path.exists():
                logger.warning(f"Metrics file not found: {path}")
                return cls()
            
            data = json.loads(path.read_text())
        except Exception as e:
            logger.error(f"Failed to load metrics from {path}: {e}")
            return cls()
        
        def safe_float(key: str, default: float = 0.0) -> float:
            """Safely extract float value with fallback."""
            try:
                val = data.get(key, default)
                if val is None:
                    return default
                return float(val)
            except (TypeError, ValueError):
                return default
        
        def safe_int(key: str, default: int = 0) -> int:
            """Safely extract int value with fallback."""
            try:
                val = data.get(key, default)
                if val is None:
                    return default
                return int(val)
            except (TypeError, ValueError):
                return default
        
        # Load from various possible field names for compatibility
        cards = safe_int("cards", 0)
        if cards == 0:
            cards = safe_int("total_cards", 0)
        
        triangulation = safe_float("union_triangulation", 0.0)
        if triangulation == 0.0:
            triangulation = safe_float("union_triangulation_rate", 0.0)
        
        primary = safe_float("primary_share", 0.0)
        if primary == 0.0:
            primary = safe_float("primary_share_in_union", 0.0)
        
        return cls(
            cards=cards,
            quote_coverage=safe_float("quote_coverage"),
            union_triangulation=triangulation,
            primary_share=primary,
            top_domain_share=safe_float("top_domain_share"),
            triangulated_cards=safe_int("triangulated_cards"),
            credible_cards=safe_int("credible_cards"),
            unique_domains=safe_int("unique_domains")
        )
    
    def meets_gates(self, min_triangulation: float = 0.50, 
                    min_primary: float = 0.33, 
                    min_cards: int = 25) -> bool:
        """Check if metrics meet quality gates."""
        return (
            self.union_triangulation >= min_triangulation
            and self.primary_share >= min_primary
            and self.cards >= min_cards
        )
    
    def get_gate_failures(self, min_triangulation: float = 0.50,
                         min_primary: float = 0.33,
                         min_cards: int = 25) -> List[str]:
        """Get list of failed quality gates with details."""
        failures = []
        
        if self.union_triangulation < min_triangulation:
            failures.append(
                f"triangulation {self.union_triangulation:.2f} < {min_triangulation:.2f}"
            )
        
        if self.primary_share < min_primary:
            failures.append(
                f"primary_share {self.primary_share:.2f} < {min_primary:.2f}"
            )
        
        if self.cards < min_cards:
            failures.append(f"cards {self.cards} < {min_cards}")
        
        return failures


@dataclass
class RunContext:
    """Central context for orchestrator run with all metrics and decisions."""
    outdir: Path
    query: str
    metrics: Metrics
    allow_final_report: bool
    reason_final_report_blocked: Optional[str] = None
    providers_used: List[str] = field(default_factory=list)
    intent: Optional[str] = None
    depth: str = "rapid"
    strict: bool = False
    
    @property
    def metrics_path(self) -> Path:
        """Path to metrics JSON file."""
        return self.outdir / "metrics.json"
    
    @property
    def cards_path(self) -> Path:
        """Path to evidence cards JSONL file."""
        return self.outdir / "evidence_cards.jsonl"
    
    @property
    def final_report_path(self) -> Path:
        """Path to final report markdown file."""
        return self.outdir / "final_report.md"
    
    @property
    def insufficient_report_path(self) -> Path:
        """Path to insufficient evidence report."""
        return self.outdir / "insufficient_evidence_report.md"
    
    def reload_metrics(self) -> None:
        """Reload metrics from disk to ensure freshness."""
        self.metrics = Metrics.from_file(self.metrics_path)
    
    def should_generate_final(self, min_triangulation: float = 0.50,
                            min_primary: float = 0.33,
                            min_cards: int = 25) -> bool:
        """Determine if final report should be generated based on gates."""
        # Reload metrics to ensure we have latest
        self.reload_metrics()
        
        # Check gates
        meets_gates = self.metrics.meets_gates(
            min_triangulation, min_primary, min_cards
        )
        
        # Update context
        if not meets_gates:
            failures = self.metrics.get_gate_failures(
                min_triangulation, min_primary, min_cards
            )
            self.reason_final_report_blocked = "; ".join(failures)
            self.allow_final_report = False
        else:
            self.allow_final_report = True
            self.reason_final_report_blocked = None
        
        return self.allow_final_report