"""Consistent insufficient evidence report writer."""

import logging
from typing import Optional, List, Dict, Any

from research_system.config_v2 import load_quality_config
from research_system.utils.file_ops import atomic_write_text
from research_system.quality.metrics_v2 import FinalMetrics

logger = logging.getLogger(__name__)

def write_insufficient_evidence_report(
    output_dir: str, 
    metrics: FinalMetrics,
    intent: str = "generic",
    errors: Optional[List[str]] = None
) -> None:
    """
    Write a consistent insufficient evidence report.
    
    Uses the same metrics object as all other reports to ensure consistency.
    
    Args:
        output_dir: Output directory path
        metrics: Final computed metrics
        intent: Research intent
        errors: Optional list of specific error messages
    """
    cfg = load_quality_config()
    
    # Build the report content
    lines = [
        "# Insufficient Evidence Report",
        "",
        "This research run did not meet the required quality standards for producing a comprehensive report.",
        "",
        "## Quality Gate Results",
        "",
        f"**Intent**: {intent}",
        "",
        "| Metric | Actual | Required | Status |",
        "|--------|--------|----------|--------|"
    ]
    
    # Primary share check
    primary_status = "✅" if metrics.primary_share >= cfg.primary_share_floor else "❌"
    lines.append(
        f"| Primary Sources | **{metrics.primary_share:.1%}** | "
        f"{cfg.primary_share_floor:.0%} | {primary_status} |"
    )
    
    # Triangulation check
    tri_status = "✅" if metrics.triangulation_rate >= cfg.triangulation_floor else "❌"
    lines.append(
        f"| Triangulation Rate | **{metrics.triangulation_rate:.1%}** | "
        f"{cfg.triangulation_floor:.0%} | {tri_status} |"
    )
    
    # Domain concentration check
    conc_status = "✅" if metrics.domain_concentration <= cfg.domain_concentration_cap else "❌"
    lines.append(
        f"| Domain Concentration | **{metrics.domain_concentration:.1%}** | "
        f"≤{cfg.domain_concentration_cap:.0%} | {conc_status} |"
    )
    
    # Stats-specific checks
    if intent == "stats":
        lines.extend([
            f"| Recent Primary (24mo) | **{metrics.recent_primary_count}** | ≥3 | "
            f"{'✅' if metrics.recent_primary_count >= 3 else '❌'} |",
            f"| Triangulated Clusters | **{metrics.triangulated_clusters}** | ≥1 | "
            f"{'✅' if metrics.triangulated_clusters >= 1 else '❌'} |"
        ])
    
    lines.extend([
        "",
        "## Evidence Summary",
        "",
        f"- Total evidence cards: {metrics.sample_sizes.get('total_cards', 0)}",
        f"- Primary sources: {metrics.sample_sizes.get('primary', 0)}",
        f"- Credible sources: {metrics.credible_cards}",
        f"- Unique domains: {metrics.unique_domains}",
        f"- Provider error rate: {metrics.provider_error_rate:.1%}",
        ""
    ])
    
    # Add specific errors if provided
    if errors:
        lines.extend([
            "## Specific Issues",
            ""
        ])
        for error in errors:
            lines.append(f"- {error}")
        lines.append("")
    
    # Add recommendations based on intent
    lines.extend([
        "## Recommendations",
        ""
    ])
    
    if intent == "stats":
        lines.extend([
            "For statistical/economic queries, try:",
            "",
            "1. **Expand official sources**: Query OECD, IMF, World Bank, Eurostat, central banks directly",
            "2. **Add recent data**: Ensure at least 3 primary sources from the last 24 months",
            "3. **Improve triangulation**: Seek corroboration from multiple official statistics providers",
            "4. **Check data availability**: Some statistics may have embargo periods or limited coverage",
            "5. **Use specific terms**: Include exact metric names, time periods, and geographic scopes",
            ""
        ])
    else:
        lines.extend([
            "To improve evidence quality:",
            "",
            "1. **Broaden search terms**: Try synonyms and related concepts",
            "2. **Check spelling**: Ensure query terms are correctly spelled",
            "3. **Break down complex queries**: Search for sub-topics separately",
            "4. **Try different time periods**: Some topics have better historical coverage",
            "5. **Consider geographic scope**: Add or remove location constraints",
            ""
        ])
    
    # Add technical details
    lines.extend([
        "## Technical Details",
        "",
        f"- Quality configuration: v{cfg.__dict__.get('version', 1)}",
        f"- Run status: Quality gates not passed",
        f"- Output: `insufficient_evidence_report.md` only",
        "",
        "No final report has been generated. To view detailed metrics, see `metrics.json`.",
        "",
        "---",
        "",
        "*For detailed diagnostic information, check `RUN_STATE.json` and log files.*"
    ])
    
    # Write the report
    report_content = "\n".join(lines)
    report_path = f"{output_dir}/insufficient_evidence_report.md"
    atomic_write_text(report_path, report_content)
    
    logger.info(f"Wrote insufficient evidence report to {report_path}")
    logger.warning(
        f"Quality gates failed for {intent}: primary={metrics.primary_share:.1%}, "
        f"triangulation={metrics.triangulation_rate:.1%}, concentration={metrics.domain_concentration:.1%}"
    )

def format_gate_failure_message(
    metrics: FinalMetrics,
    intent: str = "generic"
) -> str:
    """
    Format a concise gate failure message for logging.
    
    Args:
        metrics: Final computed metrics
        intent: Research intent
        
    Returns:
        Formatted failure message
    """
    cfg = load_quality_config()
    
    failures = []
    
    if metrics.primary_share < cfg.primary_share_floor:
        failures.append(
            f"primary_share={metrics.primary_share:.1%}<{cfg.primary_share_floor:.0%}"
        )
    
    if metrics.triangulation_rate < cfg.triangulation_floor:
        failures.append(
            f"triangulation={metrics.triangulation_rate:.1%}<{cfg.triangulation_floor:.0%}"
        )
    
    if metrics.domain_concentration > cfg.domain_concentration_cap:
        failures.append(
            f"concentration={metrics.domain_concentration:.1%}>{cfg.domain_concentration_cap:.0%}"
        )
    
    if intent == "stats":
        if metrics.recent_primary_count < 3:
            failures.append(f"recent_primary={metrics.recent_primary_count}<3")
        if metrics.triangulated_clusters < 1:
            failures.append(f"triangulated_clusters={metrics.triangulated_clusters}<1")
    
    return f"Gates failed: {', '.join(failures)}"