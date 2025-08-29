"""
Enhanced final report generation with citation-bound numbers and single-source metrics.
Implements v8.15.0 improvements for scholarly-grade reports.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import json
import logging
from collections import defaultdict
from datetime import datetime

from research_system.context import RunContext
from research_system.report.utils import (
    sentence_trim, unique_preserve_order, extract_domain,
    format_citations, is_numeric_claim, truncate_list,
    format_bullet_list, safe_percentage, clean_html
)

logger = logging.getLogger(__name__)

OUTPUT_NAME = "final_report.md"
CARDS_PATH = "evidence_cards.jsonl"

# Primary / official domains that can single-source a number
PRIMARY_WHITELIST = {
    "oecd.org", "stats.oecd.org", "worldbank.org", "data.worldbank.org",
    "imf.org", "treasury.gov", "irs.gov", "europa.eu", "ec.europa.eu",
    "eurostat.ec.europa.eu", "cbo.gov", "gao.gov", "ons.gov.uk", "bea.gov",
    "who.int", "un.org", "unesco.org", "ilo.org", "cdc.gov", "nih.gov",
    "census.gov", "bls.gov", "federalreserve.gov", "ecb.europa.eu",
    "unwto.org", "e-unwto.org", "iata.org", "wttc.org"
}


class ReportWriter:
    """Final report writer with quality gates and citation binding."""
    
    def __init__(self, ctx: RunContext):
        self.ctx = ctx
        self.out = ctx.final_report_path
        self.cards_path = ctx.cards_path
        self.triangulation_path = ctx.outdir / "triangulation.json"
    
    def _load_cards(self) -> List[Dict[str, Any]]:
        """Load evidence cards from JSONL file."""
        cards: List[Dict[str, Any]] = []
        
        if not self.cards_path.exists():
            logger.warning(f"Cards file not found: {self.cards_path}")
            return cards
        
        try:
            with self.cards_path.open() as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        cards.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        logger.debug(f"Skipping invalid JSON line: {e}")
                        continue
        except Exception as e:
            logger.error(f"Failed to load cards: {e}")
        
        return cards
    
    def _load_triangulation(self) -> Dict[str, Any]:
        """Load triangulation data if available."""
        if not self.triangulation_path.exists():
            return {}
        
        try:
            return json.loads(self.triangulation_path.read_text())
        except Exception as e:
            logger.debug(f"Could not load triangulation data: {e}")
            return {}
    
    def _build_key_numbers(self, cards: List[Dict[str, Any]]) -> List[Tuple[str, List[str]]]:
        """
        Build key numbers with citation binding.
        
        A statement is included only if:
          - Supported by >=2 distinct domains, OR
          - Supported by >=1 source from PRIMARY_WHITELIST
          
        Returns:
            List of (statement, citations) tuples
        """
        claims: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"domains": set(), "citations": [], "cards": []}
        )
        
        for card in cards:
            # Extract potential claims from various fields
            claim_sources = [
                card.get("normalized_claim"),
                card.get("claim"),
                card.get("quote"),
                card.get("best_quote"),
                card.get("snippet")
            ]
            
            for claim_text in claim_sources:
                if not claim_text:
                    continue
                
                claim_text = clean_html(claim_text).strip()
                
                # Only keep claims containing numbers
                if not is_numeric_claim(claim_text):
                    continue
                
                # Extract citation info
                url = card.get("url") or card.get("source_url") or ""
                domain = extract_domain(url)
                
                if not url or not domain:
                    continue
                
                # Use trimmed claim as key
                key = sentence_trim(claim_text, 300)
                
                claims[key]["domains"].add(domain)
                claims[key]["citations"].append(url)
                claims[key]["cards"].append(card)
        
        # Filter and rank claims
        results: List[Tuple[str, List[str]]] = []
        
        for claim, meta in claims.items():
            domains = {d for d in meta["domains"] if d}
            cites = unique_preserve_order(meta["citations"])
            
            # Check if claim meets support criteria
            has_primary = any(d in PRIMARY_WHITELIST for d in domains)
            has_multi_domain = len(domains) >= 2
            
            if has_primary or has_multi_domain:
                # Prioritize claims with both criteria
                priority = 2 if (has_primary and has_multi_domain) else 1
                results.append((priority, claim, cites[:5]))  # Cap citations at 5
        
        # Sort by priority (higher first) and take top 6
        results.sort(key=lambda x: x[0], reverse=True)
        
        return [(claim, cites) for _, claim, cites in results[:6]]
    
    def _build_key_findings(self, cards: List[Dict[str, Any]], 
                           triangulation: Dict[str, Any]) -> List[str]:
        """
        Build key findings from triangulated clusters.
        
        Returns:
            List of sentence-trimmed findings
        """
        findings: List[str] = []
        
        # Try to get findings from triangulation clusters
        clusters = triangulation.get("clusters", [])
        
        for cluster in clusters[:10]:  # Process more clusters to get good findings
            # Get representative text
            rep_text = cluster.get("representative_text", "")
            if not rep_text:
                # Try to get from representative card
                rep_card = cluster.get("representative_card", {})
                rep_text = (rep_card.get("snippet") or 
                          rep_card.get("quote") or 
                          rep_card.get("claim") or "")
            
            if not rep_text:
                continue
            
            # Clean and trim
            rep_text = clean_html(rep_text)
            trimmed = sentence_trim(rep_text, 220)
            
            if trimmed and trimmed not in findings:
                findings.append(trimmed)
        
        # If we don't have enough from triangulation, try high-confidence cards
        if len(findings) < 3:
            high_conf_cards = [
                c for c in cards 
                if c.get("credibility_score", 0) > 0.7 and
                   c.get("triangulated", False)
            ]
            
            for card in high_conf_cards[:10]:
                text = card.get("snippet") or card.get("quote") or ""
                if text:
                    text = clean_html(text)
                    trimmed = sentence_trim(text, 220)
                    if trimmed and trimmed not in findings:
                        findings.append(trimmed)
                
                if len(findings) >= 5:
                    break
        
        return findings[:5]
    
    def _calculate_citation_safety(self, 
                                  key_numbers: List[Tuple[str, List[str]]]) -> Dict[str, Any]:
        """
        Calculate citation safety metrics.
        
        Returns:
            Dict with pass status and summary
        """
        total = len(key_numbers)
        
        if total == 0:
            return {
                "pass": False,
                "summary": "No key numbers were extracted."
            }
        
        with_cites = sum(1 for _, cites in key_numbers if len(cites) >= 1)
        
        return {
            "pass": (with_cites == total),
            "summary": f"{with_cites}/{total} key numbers have at least one citation."
        }
    
    def write(self) -> None:
        """Write final report if quality gates are met."""
        
        # Guard: never write if orchestrator said no
        if not self.ctx.allow_final_report:
            logger.info("Final report suppressed due to quality gates")
            return
        
        # Reload metrics to ensure freshness
        self.ctx.reload_metrics()
        m = self.ctx.metrics
        
        # Load data
        cards = self._load_cards()
        triangulation = self._load_triangulation()
        
        # Build report components
        key_numbers = self._build_key_numbers(cards)
        key_findings = self._build_key_findings(cards, triangulation)
        cite_safety = self._calculate_citation_safety(key_numbers)
        
        # Build report
        lines: List[str] = []
        
        # Header
        lines.append(f"# Final Report")
        lines.append("")
        lines.append(f"**Query:** {self.ctx.query}")
        lines.append(f"**Generated:** {datetime.utcnow().isoformat()}Z")
        lines.append(f"**Evidence Cards:** {m.cards}")
        lines.append("")
        
        # Executive Summary
        lines.append("## Executive Summary")
        lines.append("")
        
        if key_findings:
            lines.append(format_bullet_list(key_findings))
        else:
            lines.append("_Evidence-supported summary will appear here when clusters yield representative sentences._")
        lines.append("")
        
        # Key Findings
        lines.append("## Key Findings")
        lines.append("")
        
        if key_findings:
            # Use same findings but potentially with different formatting
            lines.append(format_bullet_list(key_findings))
        else:
            lines.append("_No triangulated findings were available._")
        lines.append("")
        
        # Key Numbers with Citations
        lines.append("## Key Numbers (with citations)")
        lines.append("")
        
        if key_numbers:
            for stmt, cites in key_numbers:
                cite_str = format_citations(cites)
                if cite_str:
                    lines.append(f"- {stmt} {cite_str}")
                else:
                    lines.append(f"- {stmt}")
            lines.append("")
        else:
            lines.append("_No numeric claims passed the support/whitelist criteria._")
            lines.append("")
        
        # Evidence Supply
        lines.append("## Evidence Supply")
        lines.append("")
        lines.append(f"- Total evidence cards: **{m.cards}**")
        lines.append(f"- Triangulation score: **{m.union_triangulation:.2f}**")
        lines.append(f"- Primary-source share: **{m.primary_share:.2f}**")
        
        if m.unique_domains > 0:
            lines.append(f"- Unique domains: **{m.unique_domains}**")
        
        if m.credible_cards > 0:
            cred_pct = safe_percentage(m.credible_cards, m.cards)
            lines.append(f"- High-credibility cards: **{m.credible_cards}** ({cred_pct})")
        
        if m.top_domain_share > 0:
            lines.append(f"- Top-domain concentration: **{m.top_domain_share:.2f}**")
        
        lines.append("")
        
        # Citation Safety
        lines.append("## Citation Safety")
        lines.append("")
        
        status = "PASS ✅" if cite_safety["pass"] else "NEEDS ATTENTION ⚠️"
        lines.append(f"- Status: **{status}**")
        lines.append(f"- Detail: {cite_safety['summary']}")
        lines.append("")
        
        # Source Distribution (if we have domain data)
        if cards:
            domain_counts = defaultdict(int)
            for card in cards:
                domain = extract_domain(card.get("url", ""))
                if domain:
                    domain_counts[domain] += 1
            
            if domain_counts:
                lines.append("## Source Distribution")
                lines.append("")
                
                # Sort by count
                top_domains = sorted(
                    domain_counts.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )[:10]
                
                for domain, count in top_domains:
                    pct = safe_percentage(count, len(cards))
                    primary_marker = " 🔷" if domain in PRIMARY_WHITELIST else ""
                    lines.append(f"- {domain}: {count} articles ({pct}){primary_marker}")
                
                lines.append("")
        
        # Appendix links
        appendix_files = [
            ("Source Strategy", "source_strategy.md"),
            ("Citation Checklist", "citation_checklist.md"),
            ("Source Quality Table", "source_quality_table.md"),
            ("Acceptance Guardrails", "acceptance_guardrails.md"),
            ("Gaps & Risks", "GAPS_AND_RISKS.md"),
        ]
        
        existing_appendix = [
            (title, fname) 
            for title, fname in appendix_files 
            if (self.ctx.outdir / fname).exists()
        ]
        
        if existing_appendix:
            lines.append("## Appendix")
            lines.append("")
            
            for title, fname in existing_appendix:
                lines.append(f"- {title}: `{fname}`")
            
            lines.append("")
        
        # Write the report
        content = "\n".join(lines).strip() + "\n"
        self.out.write_text(content)
        logger.info(f"Wrote final report to {self.out}")


def write_final_report(ctx: RunContext) -> None:
    """Convenience function to write final report."""
    ReportWriter(ctx).write()