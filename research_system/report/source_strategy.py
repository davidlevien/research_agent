"""
Source strategy report generation with actual provider tracking.
Implements v8.15.0 improvements for transparent source usage reporting.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Optional
from research_system.context import RunContext
import logging

logger = logging.getLogger(__name__)

OUTPUT_NAME = "source_strategy.md"

HEADER = "# Source Strategy\n"

# Primary source domains that meet scholarly standards
PRIMARY_SOURCES = {
    "oecd.org", "stats.oecd.org", "worldbank.org", "data.worldbank.org",
    "imf.org", "treasury.gov", "irs.gov", "europa.eu", "ec.europa.eu",
    "eurostat.ec.europa.eu", "cbo.gov", "gao.gov", "ons.gov.uk", "bea.gov",
    "who.int", "un.org", "unesco.org", "ilo.org", "cdc.gov", "nih.gov",
    "census.gov", "bls.gov", "federalreserve.gov", "ecb.europa.eu"
}

# Vertical API providers for specific domains
VERTICAL_APIS = {
    "nps": "National Park Service API",
    "fred": "Federal Reserve Economic Data",
    "oecd": "OECD Statistics",
    "worldbank": "World Bank Data",
    "imf": "International Monetary Fund",
    "eurostat": "Eurostat European Statistics",
    "crossref": "CrossRef Academic Citations",
    "pubmed": "PubMed Medical Literature",
    "arxiv": "arXiv Scientific Papers",
    "gdelt": "GDELT Global Events Database"
}


def write(ctx: RunContext) -> None:
    """
    Write source strategy document reflecting actual providers used.
    
    Args:
        ctx: RunContext with provider information
    """
    out = ctx.outdir / OUTPUT_NAME
    providers = ctx.providers_used or []
    
    lines = [HEADER, ""]
    
    # Document actual providers used
    if providers:
        lines.append("## Providers Used in This Run\n")
        
        # Separate vertical APIs from general search
        vertical = [p for p in providers if p in VERTICAL_APIS]
        general = [p for p in providers if p not in VERTICAL_APIS]
        
        if vertical:
            lines.append("### Specialized Data Sources")
            for p in vertical:
                desc = VERTICAL_APIS.get(p, p)
                lines.append(f"- **{p}**: {desc}")
            lines.append("")
        
        if general:
            lines.append("### General Search Providers")
            for p in general:
                lines.append(f"- {p}")
            lines.append("")
    else:
        lines.append("**Note**: No provider information available for this run.\n")
    
    # Document primary source criteria
    lines.append("## Primary Source Criteria\n")
    lines.append("The following domains are considered primary sources for high-confidence claims:\n")
    
    # Group primary sources by category
    gov_sources = [s for s in PRIMARY_SOURCES if s.endswith(".gov")]
    org_sources = [s for s in PRIMARY_SOURCES if s.endswith(".org")]
    eu_sources = [s for s in PRIMARY_SOURCES if ".eu" in s or ".europa" in s]
    other_sources = [s for s in PRIMARY_SOURCES if s not in gov_sources + org_sources + eu_sources]
    
    if gov_sources:
        lines.append("### Government Sources")
        for s in sorted(gov_sources):
            lines.append(f"- {s}")
        lines.append("")
    
    if org_sources:
        lines.append("### International Organizations")
        for s in sorted(org_sources):
            lines.append(f"- {s}")
        lines.append("")
    
    if eu_sources:
        lines.append("### European Union")
        for s in sorted(eu_sources):
            lines.append(f"- {s}")
        lines.append("")
    
    if other_sources:
        lines.append("### Other Authoritative Sources")
        for s in sorted(other_sources):
            lines.append(f"- {s}")
        lines.append("")
    
    # Document backfill policy based on quality gates
    lines.append("## Backfill Policy\n")
    
    if ctx.allow_final_report:
        lines.append("### Status: Quality Gates Met")
        lines.append("- Primary share: **{:.0f}%** (threshold: 33%)".format(ctx.metrics.primary_share * 100))
        lines.append("- Triangulation: **{:.0f}%** (threshold: 50%)".format(ctx.metrics.union_triangulation * 100))
        lines.append("- Evidence cards: **{}** (threshold: 25)".format(ctx.metrics.cards))
        lines.append("")
        lines.append("Backfill may have been used opportunistically, but all quality thresholds were achieved.")
    else:
        lines.append("### Status: Quality Gates Not Met")
        if ctx.reason_final_report_blocked:
            lines.append(f"- **Reason**: {ctx.reason_final_report_blocked}")
        lines.append("")
        lines.append("**Backfill strategy enabled** to improve evidence quality:")
        lines.append("- Expand provider set to include Eurostat, EC, UN data sources")
        lines.append("- Apply domain concentration cap of 25% to ensure diversity")
        lines.append("- Require minimum 3 independent domains per claim")
        lines.append("- Target primary share ≥ 33% through focused queries")
    
    lines.append("")
    
    # Document search approach
    lines.append("## Search Approach\n")
    
    if ctx.intent:
        lines.append(f"### Intent-Based Strategy")
        lines.append(f"Query classified as: **{ctx.intent}**\n")
        
        intent_strategies = {
            "stats": "Focus on statistical databases (OECD, World Bank, IMF) with SDMX data endpoints",
            "news": "Prioritize recent coverage from credible news sources with timestamp filtering",
            "medical": "Target PubMed, NIH, CDC for peer-reviewed medical literature",
            "regulatory": "Search government sites, legal databases, and official policy documents",
            "travel": "Include tourism boards, travel statistics, and destination-specific sources",
            "howto": "Focus on instructional content, documentation, and tutorial sources",
            "product": "Include reviews, comparisons, and technical specifications",
            "generic": "Balanced search across all available provider types"
        }
        
        strategy = intent_strategies.get(ctx.intent, "Topic-specific provider selection")
        lines.append(f"- {strategy}")
    
    lines.append("")
    lines.append("### Quality Filters Applied")
    lines.append("- Deduplication by canonical URL and content hash")
    lines.append("- Domain diversity enforcement (max 25% from single domain)")
    lines.append("- Primary source prioritization for statistical claims")
    lines.append("- Contradiction detection and filtering")
    lines.append("- Relevance scoring with intent-aware thresholds")
    
    lines.append("")
    lines.append("### Evidence Validation")
    lines.append("- All cards validated against JSON schema")
    lines.append("- Required fields: title, url, snippet, provider")
    lines.append("- Credibility scoring based on domain authority")
    lines.append("- Quote extraction and validation for key claims")
    lines.append("- Triangulation across multiple independent sources")
    
    # Write the document
    out.write_text("\n".join(lines))
    logger.info(f"Wrote source strategy to {out}")


class ReportWriter:
    """Compatibility wrapper for consistent API."""
    
    def __init__(self, ctx: RunContext):
        self.ctx = ctx
    
    def write(self) -> None:
        """Write source strategy document."""
        write(self.ctx)