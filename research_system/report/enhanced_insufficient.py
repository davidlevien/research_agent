"""
Enhanced insufficient evidence report with actionable next steps.
Implements v8.15.0 improvements for clear guidance when quality gates fail.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Optional
import logging
from datetime import datetime

from research_system.context import RunContext
from research_system.report.utils import format_bullet_list

logger = logging.getLogger(__name__)

OUTPUT_NAME = "insufficient_evidence_report.md"


class ReportWriter:
    """Insufficient evidence report writer with actionable guidance."""
    
    def __init__(self, ctx: RunContext):
        self.ctx = ctx
        self.out = ctx.insufficient_report_path
    
    def _generate_next_steps(self) -> List[str]:
        """
        Generate concrete, actionable next steps based on query and failures.
        
        Returns:
            List of specific action items
        """
        q = self.ctx.query
        steps: List[str] = []
        
        # Intent-specific primary source recommendations
        if self.ctx.intent == "stats":
            steps.extend([
                f"Query **OECD** datasets via SDMX for series matching '{q}'. "
                f"Require ≥2 countries and ≥10 years of data. "
                f"Example: search 'site:stats.oecd.org {q} SDMX' or use API endpoint.",
                
                f"Pull **World Bank** indicators using partial token matching on '{q}'. "
                f"Accept only indicators with complete metadata and ≥80% coverage since 2000.",
                
                f"Check **IMF** SDMX dataflows for structural series related to '{q}'. "
                f"Use IMF working papers for definitions only, not as factual sources."
            ])
        
        elif self.ctx.intent == "medical":
            steps.extend([
                f"Search **PubMed** for systematic reviews and meta-analyses on '{q}'. "
                f"Filter for publications from last 5 years with full text available.",
                
                f"Query **CDC** and **NIH** databases for clinical guidelines on '{q}'. "
                f"Prioritize official recommendations over research papers.",
                
                f"Check **WHO** global health observatory for international data on '{q}'."
            ])
        
        elif self.ctx.intent == "regulatory":
            steps.extend([
                f"Search **official government sites** (.gov) for regulations on '{q}'. "
                f"Focus on primary sources: legislation, rules, and official guidance.",
                
                f"Query **EUR-Lex** for EU regulations if '{q}' has European relevance.",
                
                f"Check **Federal Register** for recent US regulatory changes on '{q}'."
            ])
        
        else:
            # Generic recommendations
            steps.extend([
                f"Expand search to primary sources for '{q}' using site: operators. "
                f"Target .gov, .edu, and international organization domains.",
                
                f"Use specialized databases relevant to '{q}' instead of general search.",
                
                f"Consider breaking '{q}' into sub-topics for more focused searches."
            ])
        
        # Backfill strategy based on specific failures
        m = self.ctx.metrics
        
        if m.primary_share < 0.33:
            steps.append(
                "Enable **primary source backfill**: Widen provider set to include "
                "Eurostat, EC, UN data, and academic databases. Apply domain cap of 25% "
                "and require minimum 3 independent domains per claim."
            )
        
        if m.union_triangulation < 0.50:
            steps.append(
                "Improve **triangulation**: Focus queries on widely-reported facts. "
                "Use date ranges and geographic filters to find corroborating sources. "
                "Consider time-series data that multiple sources would report."
            )
        
        if m.cards < 25:
            steps.append(
                "Increase **evidence volume**: Broaden search terms while maintaining relevance. "
                "Use synonyms, related concepts, and industry-specific terminology. "
                "Enable additional providers if available."
            )
        
        # Quality thresholds reminder
        steps.append(
            "**Quality Gates**: Only generate final report when triangulation ≥ 50%, "
            "primary share ≥ 33%, and evidence cards ≥ 25. Otherwise, remain on "
            "insufficient evidence path."
        )
        
        return steps
    
    def _generate_troubleshooting_tips(self) -> List[str]:
        """
        Generate troubleshooting tips based on metrics.
        
        Returns:
            List of diagnostic suggestions
        """
        tips: List[str] = []
        m = self.ctx.metrics
        
        # Diagnose low triangulation
        if m.union_triangulation < 0.30:
            tips.append(
                "**Low triangulation** (<30%): Query may be too specific or recent. "
                "Try broader terms or established topics with historical data."
            )
        
        # Diagnose low primary share
        if m.primary_share < 0.20:
            tips.append(
                "**Low primary share** (<20%): Secondary sources dominating results. "
                "Use site: operators to target authoritative domains directly."
            )
        
        # Diagnose high domain concentration
        if m.top_domain_share > 0.40:
            tips.append(
                "**High domain concentration** (>40%): Single source dominating. "
                "Exclude dominant domain and re-run, or use diverse provider set."
            )
        
        # Check for provider issues
        if self.ctx.providers_used and len(self.ctx.providers_used) < 3:
            tips.append(
                f"**Limited providers** ({len(self.ctx.providers_used)}): "
                f"Enable additional search providers for better coverage."
            )
        
        return tips
    
    def write(self) -> None:
        """Write insufficient evidence report with actionable guidance."""
        
        # Reload metrics to ensure freshness
        self.ctx.reload_metrics()
        m = self.ctx.metrics
        
        lines: List[str] = []
        
        # Header
        lines.append("# Insufficient Evidence Report")
        lines.append("")
        lines.append(f"**Query:** {self.ctx.query}")
        lines.append(f"**Generated:** {datetime.utcnow().isoformat()}Z")
        
        if self.ctx.intent:
            lines.append(f"**Intent Classification:** {self.ctx.intent}")
        
        lines.append("")
        
        # Why this was gated
        lines.append("## Why Quality Gates Were Not Met")
        lines.append("")
        
        reason = self.ctx.reason_final_report_blocked or "Quality thresholds were not met."
        lines.append(f"**Gate Failures:** {reason}")
        lines.append("")
        
        # Current metrics vs thresholds
        lines.append("### Current Metrics")
        lines.append("")
        lines.append(f"- Evidence cards: **{m.cards}** (required: ≥25)")
        lines.append(f"- Triangulation: **{m.union_triangulation:.2f}** (required: ≥0.50)")
        lines.append(f"- Primary share: **{m.primary_share:.2f}** (required: ≥0.33)")
        
        if m.unique_domains > 0:
            lines.append(f"- Unique domains: **{m.unique_domains}**")
        
        if m.credible_cards > 0:
            lines.append(f"- Credible sources: **{m.credible_cards}**")
        
        lines.append("")
        
        # Concrete next steps
        lines.append("## Next Steps (Concrete Actions)")
        lines.append("")
        
        next_steps = self._generate_next_steps()
        for i, step in enumerate(next_steps, 1):
            lines.append(f"{i}. {step}")
            lines.append("")
        
        # Troubleshooting if applicable
        tips = self._generate_troubleshooting_tips()
        if tips:
            lines.append("## Troubleshooting Tips")
            lines.append("")
            lines.append(format_bullet_list(tips))
            lines.append("")
        
        # Provider information if available
        if self.ctx.providers_used:
            lines.append("## Providers Attempted")
            lines.append("")
            lines.append(format_bullet_list(self.ctx.providers_used))
            lines.append("")
        
        # Path forward
        lines.append("## Path Forward")
        lines.append("")
        lines.append(
            "This report indicates that the current evidence does not meet scholarly "
            "standards for a comprehensive analysis. Follow the concrete next steps above "
            "to improve evidence quality. The system will automatically generate a full "
            "report once quality gates are met."
        )
        lines.append("")
        
        # Appendix links
        appendix_files = [
            ("Source Strategy", "source_strategy.md"),
            ("Acceptance Guardrails", "acceptance_guardrails.md"),
            ("Gaps & Risks", "GAPS_AND_RISKS.md"),
        ]
        
        existing_appendix = [
            (title, fname) 
            for title, fname in appendix_files 
            if (self.ctx.outdir / fname).exists()
        ]
        
        if existing_appendix:
            lines.append("## Additional Information")
            lines.append("")
            
            for title, fname in existing_appendix:
                lines.append(f"- {title}: `{fname}`")
            
            lines.append("")
        
        # Write the report
        content = "\n".join(lines).strip() + "\n"
        self.out.write_text(content)
        logger.info(f"Wrote insufficient evidence report to {self.out}")


def write_insufficient_report(ctx: RunContext) -> None:
    """Convenience function to write insufficient evidence report."""
    ReportWriter(ctx).write()