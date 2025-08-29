from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import asyncio
import uuid
import logging
import os
import re
from datetime import datetime, timezone
from collections import defaultdict, Counter
from urllib.parse import urlparse
from .models import Discipline

from research_system.models import EvidenceCard, RelatedTopic
from research_system.utils.datetime_safe import safe_format_dt, format_duration
from research_system.utils.deterministic import set_global_seeds, ensure_deterministic_environment
from research_system.tools.evidence_io import write_jsonl
from research_system.tools.registry import tool_registry as registry
from research_system.tools.search_registry import register_search_tools
from research_system.collection import parallel_provider_search
from research_system.collection_enhanced import collect_from_free_apis
from research_system.routing.provider_router import choose_providers
from research_system.config import Settings
from research_system.intent.classifier import classify, Intent, get_confidence_threshold
from research_system.providers.intent_registry import expand_providers_for_intent
from research_system.controversy import ControversyDetector
from research_system.tools.aggregates import source_quality, triangulate_claims
from research_system.tools.content_processor import ContentProcessor
from research_system.tools.embed_cluster import hybrid_clusters
from research_system.tools.dedup import minhash_near_dupes
from research_system.tools.fetch import extract_article
from research_system.tools.snapshot import save_wayback
from research_system.tools.url_norm import canonicalize_url, domain_of, normalized_hash
from research_system.tools.domain_norm import (
    canonical_domain, is_primary_domain, PRIMARY_CANONICALS, 
    PRIMARY_CONFIG, PRIMARY_PATTERNS
)
from research_system.tools.anchor import build_anchors
from research_system.routing.topic_router import route_topic, classify_topic_multi
from research_system.policy import POLICIES
from research_system.scoring import recompute_confidence
from research_system.tools.claim_struct import extract_struct_claim, struct_key, struct_claims_match
from research_system.tools.canonical_key import canonical_claim_key
from research_system.tools.contradictions import find_numeric_conflicts
from research_system.tools.arex import build_arex_batch, select_uncorroborated_keys
from research_system.tools.observability import generate_triangulation_breakdown, generate_strict_failure_details
from research_system.time_budget import set_global_budget
from research_system.quality_config.quality import QualityConfig
from research_system.quality_config.report import ReportConfig, choose_report_tier
from research_system.orchestrator_adaptive import (
    apply_adaptive_domain_balance,
    apply_adaptive_credibility_floor,
    compute_adaptive_metrics,
    generate_adaptive_report_metadata,
    should_skip_strict_fail
)
from research_system.strict.adaptive_guard import (
    adaptive_strict_check,
    format_confidence_report,
    should_attempt_last_mile_backfill,
    SupplyContextData,
    ConfidenceLevel
)

# v8.13.0 imports for scholarly-grade improvements
from research_system.utils.file_ops import run_transaction, atomic_write_text, atomic_write_json
from research_system.config_v2 import load_quality_config
from research_system.quality.metrics_v2 import compute_metrics, gates_pass, write_metrics, FinalMetrics
from research_system.evidence.canonicalize import dedup_by_canonical, get_canonical_domain
from research_system.quality.domain_weights import mark_primary, credibility_weight
from research_system.retrieval.filters import filter_for_intent, detect_jurisdiction_from_query
from research_system.orchestrator_stats import run_stats_pipeline, prioritize_stats_sources
from research_system.report.insufficient import write_insufficient_evidence_report, format_gate_failure_message
from research_system.report.binding import (
    enforce_number_bindings, build_evidence_bindings, 
    assert_no_placeholders, validate_references_section
)
from research_system.triangulation.representative import pick_cluster_representative_card
from research_system.triangulation.contradiction_filter import filter_contradictory_clusters
from research_system.triangulation.intent_filters import filter_cards_by_intent, get_filtered_clusters_for_intent
from research_system.quality.quote_rescue import rescue_quotes, extract_key_numbers

# v8.15.0 imports for enhanced reporting
from research_system.context import RunContext, Metrics
from research_system.report.enhanced_final_report import ReportWriter as FinalReportWriter
from research_system.report.enhanced_insufficient import ReportWriter as InsufficientReportWriter
from research_system.report.source_strategy import ReportWriter as SourceStrategyWriter

import json

logger = logging.getLogger(__name__)

SEVEN = [
    "plan.md",
    "source_strategy.md",
    "acceptance_guardrails.md",
    "evidence_cards.jsonl",
    "source_quality_table.md",
    "final_report.md",
    "citation_checklist.md",
]

@dataclass
class OrchestratorSettings:
    """Settings specific to a single orchestrator run."""
    topic: str
    depth: str
    output_dir: Path
    strict: bool = False
    resume: bool = False
    verbose: bool = False
    max_cost_usd: Optional[float] = None  # If None, uses Settings.MAX_COST_USD

class Orchestrator:
    def __init__(self, s: OrchestratorSettings):
        # Ensure deterministic behavior from the start
        ensure_deterministic_environment()
        
        self.s = s
        # Validate output_dir is not None
        if self.s.output_dir is None:
            raise ValueError("output_dir cannot be None")
        # Ensure output_dir is a Path object
        if not isinstance(self.s.output_dir, Path):
            self.s.output_dir = Path(self.s.output_dir)
        self.s.output_dir.mkdir(parents=True, exist_ok=True)
        # Use global registry instead of creating a new one
        register_search_tools(registry)
        
        # Initialize context dictionary for storing metadata
        self.context = {}
        
        # If max_cost_usd not specified, get from global settings
        if self.s.max_cost_usd is None:
            from research_system.config import get_settings
            self.s.max_cost_usd = get_settings().MAX_COST_USD
        
        # Initialize v8.13.0 quality configuration - single source of truth
        self.v813_config = load_quality_config()
        
        # Keep legacy configs for backward compatibility during transition
        self.quality_config = QualityConfig.load(self.s.output_dir / "quality.json")
        self.report_config = ReportConfig()
        
        # Track provider health for adaptive adjustments
        self.provider_errors = 0
        self.provider_attempts = 0
        
        # Initialize timing attributes (will be properly set in run())
        import time
        self.start_time = time.time()
        self.time_budget = 1800  # Default 30 minutes
    
    def _is_primary_class(self, domain: str) -> bool:
        """Check if domain is a primary source based on intent"""
        from research_system.selection.domain_balance import is_primary_source
        return is_primary_source(domain, intent=self.context.get("intent", "generic"))
    
    def _collect_from_providers(self, providers: List[str], query: str) -> List:
        """Helper method for v8.13.0 stats pipeline to collect from specific providers."""
        try:
            # Use existing collection infrastructure
            results = asyncio.run(
                parallel_provider_search(
                    registry, 
                    query=query, 
                    count=5,
                    freshness=Settings().FRESHNESS_WINDOW, 
                    region="US"
                )
            )
            
            # Filter to requested providers
            filtered_results = {p: results.get(p, []) for p in providers if p in results}
            
            # Convert to cards
            cards = []
            for provider, hits in filtered_results.items():
                for h in hits:
                    # Create basic EvidenceCard
                    from research_system.models import EvidenceCard
                    
                    card = EvidenceCard(
                        id=str(uuid.uuid4()),
                        url=h.url,
                        title=h.title,
                        snippet=h.snippet or h.title,
                        source_domain=domain_of(h.url),
                        search_provider=provider,
                        credibility_score=0.5  # Default, will be updated by mark_primary
                    )
                    cards.append(card)
            
            logger.info(f"v8.13.0 Collected {len(cards)} cards from providers: {list(filtered_results.keys())}")
            return cards
            
        except Exception as e:
            logger.error(f"v8.13.0 Collection from providers failed: {e}")
            return []

    def _write_insufficient_evidence_report(self, errors: List[str], metrics: Dict, confidence_level) -> None:
        """Write an enhanced insufficient evidence report when strict mode fails."""
        # Ensure confidence level is set
        if confidence_level is None:
            confidence_level = ConfidenceLevel.LOW
        
        # Extract key metrics
        total_cards = metrics.get('total_cards', metrics.get('cards', 0))
        credible_cards = metrics.get('credible_cards', total_cards)
        unique_domains = metrics.get('unique_domains', 0)
        triangulated = metrics.get('triangulated_cards', 0)
        triangulation_rate = metrics.get('union_triangulation', 0)
        primary_share = metrics.get('primary_share', 0)
        provider_error_rate = metrics.get('provider_error_rate', 0)
        
        # Determine primary issues
        primary_issues = []
        if unique_domains < 5:
            primary_issues.append("**Low domain diversity** - Evidence from too few sources")
        if triangulation_rate < 0.20:
            primary_issues.append("**Poor triangulation** - Claims not corroborated")
        if primary_share < 0.30:
            primary_issues.append("**Insufficient primary sources** - Too few authoritative sources")
        if provider_error_rate > 0.30:
            primary_issues.append("**High provider failures** - Search providers unavailable")
        
        # Build enhanced report
        report_lines = [
            "# Insufficient Evidence Report",
            "",
            f"## Research Topic: {self.s.topic}",
            "",
            f"### Confidence Level: {confidence_level.to_emoji() if hasattr(confidence_level, 'to_emoji') else '⚠️'} {confidence_level.value.title() if hasattr(confidence_level, 'value') else 'Low'}",
            "",
            "## Primary Issues",
        ]
        
        if primary_issues:
            for issue in primary_issues:
                report_lines.append(f"- {issue}")
        else:
            report_lines.append("- General evidence insufficiency")
        
        report_lines.extend([
            "",
            "## Evidence Metrics",
            "",
            "| Metric | Value | Target | Status |",
            "|--------|-------|--------|--------|",
            f"| Evidence Cards | {total_cards} | ≥20 | {'✅' if total_cards >= 20 else '❌'} |",
            f"| Unique Domains | {unique_domains} | ≥8 | {'✅' if unique_domains >= 8 else '❌'} |",
            f"| Triangulation | {triangulation_rate:.1%} | ≥30% | {'✅' if triangulation_rate >= 0.30 else '❌'} |",
            f"| Primary Sources | {primary_share:.1%} | ≥40% | {'✅' if primary_share >= 0.40 else '❌'} |",
            "",
            "## Quality Gate Failures",
            ""
        ])
        
        for error in errors:
            report_lines.append(f"- {error}")
        
        # Add intent-specific guidance
        intent = self.context.get('intent', 'generic')
        intent_tips = {
            'encyclopedia': "Try adding 'overview', 'history', or 'timeline' to your search",
            'news': "Ensure recent date ranges and current terminology",
            'academic': "Search for review papers or survey articles",
            'stats': "Specify time period and geographic region clearly",
            'local': "Include nearby regions or broader geographic areas"
        }
        
        report_lines.extend([
            "",
            f"## Query Type: {intent.upper()}",
            f"**Tip**: {intent_tips.get(intent, 'Try broader search terms')}",
            "",
            "## Recommendations",
            "",
        ])
        
        # Intent-specific recommendations (reusing intent variable from above)
        if intent == "stats":
            report_lines.extend([
                "1. **Expand official sources** - Query OECD, IMF, World Bank, BEA/BLS/IRS, Eurostat directly",
                "2. **Add recent primary data** - Need at least 3 primary sources from last 24 months",
                "3. **Increase retries** - Use exponential backoff for 403/429 from official portals",
                "4. **Verify triangulation** - Require multi-domain confirmation from official sources",
            ])
        else:
            report_lines.extend([
                "1. **Broaden search** - Use more general terms",
                "2. **Try alternatives** - Different terminology may yield results",
                "3. **Break down complex queries** - Search subtopics separately",
                "4. **Retry later** - If providers are down",
            ])
        
        report_lines.extend([
            "",
            "---",
            f"*Generated: {safe_format_dt(self.start_time, '%Y-%m-%d %H:%M')}*",
            f"*Provider attempts: {metrics.get('provider_attempts', 0)}*"
        ])
        
        self._write("insufficient_evidence_report.md", "\n".join(report_lines))
    
    def _write(self, name: str, content: str):
        """Atomic write with temp file + rename."""
        import tempfile
        # Ensure output_dir exists
        if self.s.output_dir is None:
            raise ValueError("Cannot write file: output_dir is None")
        if not self.s.output_dir.exists():
            self.s.output_dir.mkdir(parents=True, exist_ok=True)
        
        target = self.s.output_dir / name
        # Write to temp file in same directory (for atomic rename)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', 
                                        dir=self.s.output_dir, 
                                        delete=False) as tmp:
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())  # Ensure written to disk
        # Atomic rename
        os.replace(tmp.name, target)
    
    def _ensure_snippet(self, snippet: str, title: str = "", url: str = "") -> str:
        """Ensure snippet is never empty (evidence validity invariant).
        
        Args:
            snippet: Original snippet (may be None or empty)
            title: Title to use as fallback
            url: URL to use as last resort
            
        Returns:
            Non-empty snippet string
        """
        # Try original snippet
        if snippet and snippet.strip():
            return snippet.strip()
        
        # Try title as snippet
        if title and title.strip():
            return f"Content: {title.strip()}"[:280]
        
        # Last resort: synthesize from URL
        if url:
            domain = domain_of(url)
            return f"Source content from {domain}"[:280]
        
        # Absolute fallback
        return "Content available at source"
    
    def _filter_relevance(self, cards: List[EvidenceCard], threshold: float = 0.5) -> List[EvidenceCard]:
        """Filter cards by relevance score (minimal enhancement)"""
        return [c for c in cards if c.relevance_score >= threshold]
    
    def _dedup(self, cards: List[EvidenceCard]) -> List[EvidenceCard]:
        """Remove duplicate evidence cards using enhanced deduplication"""
        from research_system.collect.dedup import dedup_cards
        return dedup_cards(cards, title_threshold=0.9)
    
    def _filter_providers_by_topic(self, providers: List[str], topic: str) -> List[str]:
        """
        Guardrail: avoid domain-specific providers (e.g., NPS) unless the topic is clearly relevant.
        Keeps things general and reduces off-topic noise.
        """
        # NPS is only relevant for national parks topics
        parks_kw = re.compile(r'\b(national park|nps|campground|trail|yosemite|yellowstone|zion|grand canyon|glacier)\b', re.I)
        if "nps" in providers and not parks_kw.search(topic or ""):
            providers = [p for p in providers if p != "nps"]
            logger.info(f"Filtered out NPS provider for non-parks topic: {topic}")
        return providers
    
    def _extract_related_topics(self, cards: List[EvidenceCard], k: int = 5) -> List[Dict]:
        """Extract related topics from evidence using phrase-level extraction"""
        try:
            from .tools.related_topics import extract_related_topics
            topics = extract_related_topics(cards, max_topics=k)
            # Convert to expected format
            return [{"name": t["phrase"], "score": t["relevance_score"], "reason": f"{t['supporting_sources']} sources"} 
                    for t in topics]
        except Exception as e:
            logger.warning(f"Related topics extraction failed: {e}")
            return []
    
    def _generate_plan(self) -> str:
        """Generate research plan based on topic and depth"""
        depth_details = {
            "rapid": "Quick scan of top sources (5-10 minutes)",
            "standard": "Balanced research with quality sources (15-30 minutes)",
            "deep": "Comprehensive analysis with extensive sources (30-60 minutes)"
        }
        
        # Depth to results count mapping
        self.depth_to_count = {
            "rapid": 5,
            "standard": 8,
            "deep": 20
        }
        
        return f"""# Research Plan

## Topic
{self.s.topic}

## Depth
{self.s.depth.capitalize()} - {depth_details.get(self.s.depth, 'Standard research')}

## Objectives
1. Gather evidence from multiple search providers
2. Validate source credibility and relevance
3. Synthesize findings into actionable insights
4. Provide citations for all claims

## Budget
Maximum cost: ${self.s.max_cost_usd:.2f}
"""

    def _generate_intent_queries(self, intent: str, topic: str) -> list[str]:
        """Generate intent-specific query expansions"""
        queries = [topic]  # Always include the base query
        
        if intent == "encyclopedia":
            # Time-agnostic, facet-rich expansion
            # Define facets based on common encyclopedia queries
            if "yellowstone" in topic.lower() and "park" in topic.lower():
                facets = [
                    "establishment act 1872", "hayden survey 1871", "washburn expedition 1870",
                    "fort yellowstone", "northern pacific railroad 1883",
                    "1988 fires", "wolf reintroduction 1995", "unesco world heritage 1978"
                ]
                queries.extend([f"{topic} {facet}" for facet in facets[:3]])  # Top 3 facets
            
            # Generic encyclopedia expansions (no year filters)
            queries.extend([
                f"{topic} timeline",
                f"site:nps.gov {topic}",
                f"site:usgs.gov {topic}",
                f"{topic} history overview"  # No filetype:pdf to avoid empty results
            ])
            
        elif intent in ("news", "policy"):
            # Recent content for news/policy
            queries.extend([
                f"{topic} 2024..2025",
                f"{topic} recent developments"
            ])
            
        elif intent == "academic":
            # Academic expansions
            queries.extend([
                f"{topic} research",
                f"{topic} study",
                f"site:.edu {topic}"
            ])
            
        elif intent == "stats":
            # Statistical data queries
            queries.extend([
                f"{topic} statistics",
                f"{topic} data",
                f"site:.gov {topic} data"
            ])
            
        return queries[:5]  # Limit to 5 queries to avoid overwhelming the system
    
    def _generate_source_strategy(self) -> str:
        """Generate source strategy document"""
        return f"""## Source Strategy

### Primary Sources
- Government databases (.gov)
- Academic institutions (.edu, .ac.uk)
- International organizations (.who.int, .un.org)

### Secondary Sources
- Established organizations (.org)
- Industry publications
- News outlets with editorial standards

### Evaluation Criteria
- **Credibility**: Author expertise, institutional affiliation
- **Relevance**: Direct relation to {self.s.topic}
- **Recency**: Preference for recent publications
- **Objectivity**: Minimal bias, multiple viewpoints

### Search Approach
- Parallel queries across {len(Settings().enabled_providers())} providers
- No fallback/backfill - failures are logged
- Evidence validated against JSON schema
"""

    def _evaluate_guardrails(self, cards: List[EvidenceCard], report_path: Path) -> str:
        """Evaluate acceptance guardrails with real checks"""
        import re
        import httpx
        
        # HTTP reachability checks (sample for performance)
        ok_links = 0
        total_links = min(10, len(cards))  # Check up to 10 for performance
        checked_urls = set()
        
        for card in cards[:total_links]:
            if card.url not in checked_urls:
                checked_urls.add(card.url)
                try:
                    # Quick HEAD request to check reachability
                    with httpx.Client(timeout=5) as client:
                        resp = client.head(card.url, follow_redirects=True)
                        if 200 <= resp.status_code < 400:
                            ok_links += 1
                        elif resp.status_code in (402, 403, 451):
                            # Paywall/blocked - don't count as reachable
                            logger.info(f"Paywall/blocked domain ({resp.status_code}): {card.url}")
                except:
                    pass  # Failed to reach
        
        reachability_rate = ok_links / max(len(checked_urls), 1)
        
        # Citation analysis from report
        report_text = report_path.read_text() if report_path.exists() else ""
        # Count inline citations (markdown links)
        citation_pattern = r'\[.*?\]\(https?://.*?\)'
        citations_found = len(re.findall(citation_pattern, report_text))
        
        # Count claims (findings in report - look for bolded findings, including those with HTML)
        # Match lines starting with "- **" regardless of internal content
        claim_pattern = r'^\s*-\s+\*\*.*?\*\*'
        claims_found = len(re.findall(claim_pattern, report_text, re.MULTILINE))
        
        # If no bolded findings, fall back to counting major sections
        if claims_found == 0:
            claim_pattern = r'^###?\s+'
            claims_found = len(re.findall(claim_pattern, report_text, re.MULTILINE))
        
        citations_per_claim = citations_found / max(claims_found, 1)
        
        # Provider coverage
        providers_used = set(c.provider for c in cards if c.provider)
        all_have_provider = all(c.provider for c in cards)
        
        # Multi-source verification
        domains = set(c.source_domain for c in cards)
        multi_source = len(domains) > 1
        
        # Controversy handling
        controversial = [c for c in cards if c.controversy_score >= 0.3]
        controversy_balanced = True
        if controversial:
            # Check if controversial claims have both stances
            claim_ids = set(c.claim_id for c in controversial if c.claim_id)
            for claim_id in claim_ids:
                cluster = [c for c in controversial if c.claim_id == claim_id]
                stances = set(c.stance for c in cluster)
                if len(stances) < 2:  # Should have at least 2 different stances
                    controversy_balanced = False
                    break
        
        # Build guardrails report
        md = ["# Acceptance Guardrails Evaluation", "",
              f"**Topic**: {self.s.topic}",
              f"**Timestamp**: {datetime.now(timezone.utc).isoformat()}",
              f"**Evidence Cards**: {len(cards)}",
              f"**Unique Domains**: {len(domains)}", "",
              "## Evidence Quality Checks", ""]
        
        md.append(f"- [{'x' if reachability_rate > 0.8 else ' '}] Links reachable ({ok_links}/{len(checked_urls)} sampled, {reachability_rate:.0%} success)")
        md.append(f"- [{'x' if citations_per_claim >= 1 else ' '}] Minimum citations per claim ({citations_found} citations for {claims_found} claims)")
        md.append(f"- [{'x' if all_have_provider else ' '}] Provider provenance stamped (all {len(cards)} cards)")
        md.append(f"- [{'x' if multi_source else ' '}] Multiple domains represented ({len(domains)} unique)")
        md.append(f"- [{'x' if not controversial or controversy_balanced else ' '}] Controversial claims balanced ({len(controversial)} controversial)")
        
        md.extend(["", "## Schema Validation", ""])
        
        # Check required fields
        all_have_title = all(c.title for c in cards)
        all_have_url = all(c.url for c in cards)
        all_have_snippet = all(c.snippet and len(c.snippet.strip()) > 0 for c in cards)
        valid_providers = all(c.provider in {"tavily", "brave", "serper", "serpapi", "nps"} for c in cards)
        
        md.append(f"- [{'x' if all_have_title else ' '}] All cards have title field")
        md.append(f"- [{'x' if all_have_url else ' '}] All cards have url field")
        md.append(f"- [{'x' if all_have_snippet else ' '}] All cards have non-empty snippet")
        md.append(f"- [{'x' if valid_providers else ' '}] All providers are valid")
        
        md.extend(["", "## Coverage Metrics", ""])
        
        primary_sources = [c for c in cards if c.is_primary_source]
        high_cred = [c for c in cards if c.credibility_score > 0.7]
        high_rel = [c for c in cards if c.relevance_score > 0.5]
        
        md.append(f"- Primary sources: {len(primary_sources)} ({len(primary_sources)*100//max(len(cards),1)}%)")
        md.append(f"- High credibility (>0.7): {len(high_cred)} ({len(high_cred)*100//max(len(cards),1)}%)")
        md.append(f"- High relevance (>0.5): {len(high_rel)} ({len(high_rel)*100//max(len(cards),1)}%)")
        md.append(f"- Providers represented: {', '.join(sorted(providers_used))}")
        
        md.extend(["", "## Verdict", ""])
        
        all_checks_pass = (reachability_rate > 0.8 and citations_per_claim >= 1 and 
                          all_have_provider and multi_source and 
                          (not controversial or controversy_balanced) and
                          all_have_title and all_have_url and all_have_snippet and valid_providers)
        
        if all_checks_pass:
            md.append("✅ **PASSED**: All acceptance criteria met")
        else:
            md.append("⚠️ **PARTIAL**: Some criteria not fully met (see unchecked items above)")
        
        return "\n".join(md)
    
    def _generate_quality_table_from_jsonl(self, evidence_path: Path) -> str:
        """Generate source quality table from evidence JSONL file - ENHANCED with aggregates"""
        import json
        from research_system.tools.evidence_io import read_jsonl
        
        # Read evidence cards
        cards = read_jsonl(str(evidence_path))
        
        # Use aggregates for rich analysis
        quality_data = source_quality(cards)
        triangulation_data = triangulate_claims(cards)
        
        # Build enhanced table with triangulation
        lines = ["# Source Quality Assessment Table", "", 
                 "Derived from evidence_cards.jsonl with triangulation analysis.", "",
                 "| Domain | Cards | Claims | Avg Cred | Avg Rel | Corroboration | Providers |",
                 "|--------|------:|-------:|----------|---------|---------------|-----------|"]
        
        for source in quality_data[:20]:  # Top 20 domains
            lines.append(f"| {source['domain'][:30]} | {source['total_cards']} | {source['unique_claims']} | "
                        f"{source['avg_credibility']:.2f} | {source['avg_relevance']:.2f} | "
                        f"{source['corroborated_rate']:.1%} | {', '.join(source['providers'][:3])} |")
        
        # Triangulation summary - use same metric as metrics.json
        # Load triangulation data from the JSON file for consistency
        tri_data = {}
        try:
            tri_path = self.s.output_dir / "triangulation.json"
            if tri_path.exists():
                import json
                tri_data = json.loads(tri_path.read_text())
        except:
            pass
        
        para_clusters = tri_data.get("paraphrase_clusters", [])
        from research_system.tools.aggregates import triangulation_rate_from_clusters
        # FIX: Pass total card count to get correct triangulation rate
        triangulation_rate = triangulation_rate_from_clusters(para_clusters, total_cards=len(cards))
        
        # Count triangulated vs single-source cards
        triangulated_cards = sum(len(c.get("indices", [])) for c in para_clusters if len(c.get("indices", [])) >= 2)
        single_source_cards = len(cards) - triangulated_cards
        
        lines.extend(["", "## Triangulation Analysis",
                     f"- Total evidence cards: {len(cards)}",
                     f"- Triangulation rate: {triangulation_rate:.1%} (cards in multi-source clusters)",
                     f"- Triangulated cards: {triangulated_cards}",
                     f"- Single-source cards: {single_source_cards}",
                     "", "## Summary Statistics",
                     f"- Total unique domains: {len(quality_data)}",
                     f"- Total evidence cards: {len(cards)}",
                     f"- Average credibility: {sum(c.credibility_score for c in cards)/max(len(cards),1):.2f}",
                     f"- Average relevance: {sum(c.relevance_score for c in cards)/max(len(cards),1):.2f}"])
        
        return "\n".join(lines)
    
    def _generate_acceptance_guardrails(self, cards: List[EvidenceCard] = None) -> str:
        """Generate acceptance criteria with actual validation checks"""
        guardrails = "# Acceptance Guardrails\n\n"
        guardrails += f"**Topic**: {self.s.topic}\n"
        guardrails += f"**Execution Time**: {datetime.now(timezone.utc).isoformat()}\n\n"
        
        if cards is None:
            # Pre-collection template
            guardrails += """## Evidence Requirements (To Be Validated)
- [ ] Minimum 3 independent sources per major claim
- [ ] Primary sources preferred (government, academic)
- [ ] All sources must be reachable and verifiable
- [ ] Publication dates clearly identified
- [ ] Author credentials when available

## Quality Thresholds
- [ ] Credibility score > 0.6 for inclusion
- [ ] Relevance score > 0.5 for primary evidence
- [ ] Confidence weighted by source quality
- [ ] Controversy score tracked for all clustered claims

## Validation Checks
- [ ] JSON schema validation for all evidence cards
- [ ] URL format validation
- [ ] No duplicate evidence IDs
- [ ] Search provider attribution
"""
        else:
            # Post-collection validation with actual checks
            unique_domains = set(c.source_domain for c in cards)
            unique_ids = set(c.id for c in cards)
            primary_sources = [c for c in cards if c.is_primary_source]
            high_cred = [c for c in cards if c.credibility_score > 0.6]
            high_rel = [c for c in cards if c.relevance_score > 0.5]
            all_attributed = all(c.provider for c in cards)
            all_have_urls = all(c.url for c in cards)
            all_have_snippets = all(c.snippet and len(c.snippet) > 0 for c in cards)
            controversial = [c for c in cards if c.controversy_score >= 0.3]
            
            guardrails += f"""## Evidence Requirements
- [{'x' if len(cards) >= 3 else ' '}] Minimum 3 independent sources ({len(cards)} collected)
- [{'x' if len(primary_sources) > 0 else ' '}] Primary sources included ({len(primary_sources)} found)
- [{'x' if all_have_urls else ' '}] All sources have valid URLs
- [{'x' if any(c.date for c in cards) else ' '}] Publication dates identified where available
- [{'x' if any(c.author for c in cards) else ' '}] Author information captured where available

## Quality Thresholds
- [{'x' if len(high_cred) > 0 else ' '}] Credibility score > 0.6 ({len(high_cred)}/{len(cards)} meet threshold)
- [{'x' if len(high_rel) > 0 else ' '}] Relevance score > 0.5 ({len(high_rel)}/{len(cards)} meet threshold)
- [{'x' if len(unique_domains) > 1 else ' '}] Multiple domains represented ({len(unique_domains)} unique domains)
- [{'x' if len(controversial) == 0 or all(c.claim_id for c in controversial) else ' '}] Controversial claims properly tracked

## Schema Validation
- [{'x' if all_attributed else ' '}] All evidence attributed to search provider
- [{'x' if all_have_snippets else ' '}] All evidence has non-empty snippets
- [{'x' if len(unique_ids) == len(cards) else ' '}] No duplicate evidence IDs
- [{'x' if all(c.credibility_score >= 0 and c.credibility_score <= 1 for c in cards) else ' '}] Scores within valid range

## Coverage Analysis
- Total evidence cards: {len(cards)}
- Unique domains: {len(unique_domains)}
- Search providers used: {len(set(c.provider for c in cards))}
- Primary sources: {len(primary_sources)} ({len(primary_sources)*100//max(len(cards),1)}%)
- Average credibility: {sum(c.credibility_score for c in cards)/max(len(cards),1):.2f}
- Average relevance: {sum(c.relevance_score for c in cards)/max(len(cards),1):.2f}

## Controversy Analysis
- Claims with controversy ≥ 0.3: {len(controversial)}
- Claims with both stances: {len([c for c in controversial if c.stance != 'neutral'])}
- Disputed claims with citations: {len([c for c in controversial if len(c.disputed_by) > 0])}
"""
            
        guardrails += f"""
## Strict Mode Requirements
- [{'x' if self.s.strict else ' '}] Strict mode {"enabled" if self.s.strict else "disabled"}
- [{'x' if not self.s.strict or cards and len(cards) >= 3 else ' '}] Minimum evidence threshold met
- [{'x' if not self.s.strict or not cards or all(c.provider for c in cards) else ' '}] Provider attribution complete
"""
        
        return guardrails

    def _generate_final_report_with_appendix(self, cards: List[EvidenceCard], appendix_cards: List[EvidenceCard], detector: ControversyDetector = None) -> str:
        """Generate final report with balanced cards in body and appendix for trimmed cards."""
        # Start with standard report generation
        report = self._generate_final_report(cards, detector)
        
        # Add appendix if there are trimmed cards
        if appendix_cards:
            report += "\n\n## Evidence Appendix (Additional Sources)\n\n"
            report += "_The following sources were collected but excluded from the main analysis due to domain balancing:_\n\n"
            
            # Group appendix by domain for clarity
            from collections import defaultdict
            by_domain = defaultdict(list)
            for c in appendix_cards:
                by_domain[c.source_domain].append(c)
            
            for domain in sorted(by_domain.keys()):
                report += f"\n### {domain}\n"
                for c in by_domain[domain][:5]:  # Limit to 5 per domain in appendix
                    title = c.title or c.source_title or "Untitled"
                    if len(title) > 80:
                        title = title[:80]  # Clean truncation without ellipses
                    report += f"- [{title}]({c.url})\n"
        
        return report
    
    def _generate_adaptive_report(self, cards: List[EvidenceCard], appendix_cards: List[EvidenceCard], 
                                   detector: ControversyDetector, tier, max_tokens: int) -> str:
        """Generate adaptive report with tier-specific configuration."""
        from research_system.report.composer import compose_report
        import re
        
        # Ensure per-card best_quote exists
        for c in cards:
            if not getattr(c, "best_quote", None):
                txt = (c.supporting_text or c.snippet or c.claim or c.title or "")
                sents = re.split(r"(?<=[.!?])\s+", txt)
                picked = next((s.strip() for s in sents if 60 <= len(s) <= 400 and re.search(r"\d|(?:19|20)\d{2}", s)), "")
                c.best_quote = picked or (sents[0].strip() if sents else "")
        
        # Load triangulation and metrics
        tri = {}
        tri_path = self.s.output_dir / "triangulation.json"
        if tri_path.exists():
            tri = json.loads(tri_path.read_text())
        
        metrics = {}
        metrics_path = self.s.output_dir / "metrics.json"
        if metrics_path.exists():
            metrics = json.loads(metrics_path.read_text())
        
        # Get tier-specific configuration
        tier_config = self.report_config.tiers[tier]
        
        # Generate main report with tier constraints
        # SectionBudgets is a dataclass, not a dict - use a default value
        max_findings = 10  # Default value for findings
        main_report = compose_report(
            self.s.topic, cards, tri, metrics,
            max_findings=max_findings
        )
        
        # Add appendix if cards were filtered
        if appendix_cards and tier_config.appendix_rows > 0:
            appendix = self._generate_appendix(appendix_cards[:tier_config.appendix_rows])
            main_report += f"\n\n---\n\n## Appendix: Additional Sources\n\n{appendix}"
        
        return main_report
    
    def _generate_appendix(self, cards: List[EvidenceCard]) -> str:
        """Generate appendix with additional sources."""
        lines = []
        for c in cards:
            title = c.title or c.source_title or "Untitled"
            domain = canonical_domain(c.source_domain) if c.source_domain else "unknown"
            lines.append(f"- **{title}** [{domain}]({c.url})")
        return "\n".join(lines) if lines else "No additional sources."

    def _generate_final_report(self, cards: List[EvidenceCard], detector: ControversyDetector = None) -> str:
        """Generate final report using deterministic composer with sections and budgets."""
        from research_system.report.composer import compose_report
        import re
        
        # Ensure per-card best_quote exists for composition
        for c in cards:
            if not getattr(c, "best_quote", None):
                txt = (c.supporting_text or c.snippet or c.claim or c.title or "")
                # pick a numeric/date-bearing sentence if possible
                sents = re.split(r"(?<=[.!?])\s+", txt)
                picked = next((s.strip() for s in sents if 60 <= len(s) <= 400 and re.search(r"\d|(?:19|20)\d{2}", s)), "")
                c.best_quote = picked or (sents[0].strip() if sents else "")
        
        # Load triangulation data
        tri = {}
        tri_path = self.s.output_dir / "triangulation.json"
        if tri_path.exists():
            tri = json.loads(tri_path.read_text())
        
        # Get metrics
        metrics_path = self.s.output_dir / "metrics.json"
        metrics = {}
        if metrics_path.exists():
            metrics = json.loads(metrics_path.read_text())
        
        # Use new deterministic composer
        return compose_report(self.s.topic, cards, tri, metrics, max_findings=10)
    
    def _generate_final_report_original(self, cards: List[EvidenceCard], detector: ControversyDetector = None) -> str:
        """Generate final report using enhanced composition module"""
        if not cards:
            return "# Final Report\n\nNo evidence collected for this topic."
        
        # Use the enhanced report module if triangulation data exists
        try:
            import json
            tri_path = self.s.output_dir / "triangulation.json"
            if tri_path.exists():
                tri_data = json.loads(tri_path.read_text())
                para_clusters = tri_data.get("paraphrase_clusters", [])
                struct_tris = tri_data.get("structured_triangles", [])
                
                from research_system.report.final_report import generate_final_report
                from research_system.config import Settings
                
                return generate_final_report(
                    cards=cards,
                    para_clusters=para_clusters,
                    struct_tris=struct_tris,
                    topic=self.s.topic,
                    providers=Settings().enabled_providers()
                )
        except Exception as e:
            logger.warning(f"Enhanced report generation failed, using fallback: {e}")
        
        # Fallback to existing implementation
        return self._generate_final_report_fallback(cards, detector)
    
    def _generate_final_report_fallback(self, cards: List[EvidenceCard], detector: ControversyDetector = None) -> str:
        """Fallback report generation if enhanced module fails"""
        # Original implementation continues here
        from research_system.tools.embed_cluster import hybrid_clusters
        rel_idx = [i for i, c in enumerate(cards) if getattr(c, "relevance_score", 0) >= 0.5]
        claim_texts = [(getattr(c, "quote_span", None) or getattr(c, "claim", "") or getattr(c, "snippet", "") or getattr(c, "source_title", "")) for c in cards]
        clusters = hybrid_clusters([claim_texts[i] for i in rel_idx])
        grouped = []
        used = set()
        for cl in clusters:
            members = [cards[rel_idx[i]] for i in sorted(cl)]
            used.update(rel_idx[i] for i in cl)
            grouped.append(members)
        for i in rel_idx:
            if i not in used:
                grouped.append([cards[i]])
        def score_group(g):
            ds = []
            for x in g:
                d = getattr(x, "date", None)
                if d:
                    # Convert string dates to comparable format
                    if isinstance(d, str):
                        try:
                            from datetime import datetime as dt
                            d = dt.fromisoformat(d.replace('Z', '+00:00').split('+')[0])
                        except:
                            continue
                    ds.append(d)
            last = max(ds) if ds else None
            last_sort = last.timestamp() if last and hasattr(last, 'timestamp') else 0
            avg_cred = sum(getattr(x, "credibility_score", 0.5) for x in g) / max(1, len(g))
            return (-(len({x.source_domain for x in g})), -avg_cred, -last_sort)
        ordered = sorted(grouped, key=score_group)
        lines = []
        lines.append(f"# Final Report: {self.s.topic}")
        lines.append("")
        lines.append(f"**Generated**: {datetime.now(timezone.utc).isoformat()}")
        lines.append(f"**Evidence Cards**: {len(cards)}")
        lines.append(f"**Providers**: {', '.join(sorted({getattr(c,'provider','other') for c in cards}))}")
        
        # Related topics if available
        related = self._extract_related_topics(cards)
        if related:
            lines.append("")
            lines.append("## Topic Neighborhood")
            for r in related[:6]:
                lines.append(f"- **{r.get('name', 'Unknown')}** — {r.get('reason', 'Related')} (score: {r.get('score', 0.0):.2f})")
        
        lines.append("")
        lines.append("## Key Findings (triangulated first)")
        
        # Helper functions for density testing
        import re
        def has_numeric_and_period(text: str) -> bool:
            return bool(re.search(r"\d", text)) and bool(re.search(r"\b(20\d{2}|Q[1-4]\s*20\d{2}|H[12]\s*20\d{2}|FY\s*20\d{2})\b", text))
        
        def is_primary_domain(domain: str) -> bool:
            # Topic-agnostic primary source detection based on domain classes
            return _is_primary_class(domain)
        
        # Import intent-aware primary source detection
        from research_system.selection.domain_balance import is_primary_source
        
        def _is_primary_class(domain: str) -> bool:
            """Check if domain is a primary source based on intent"""
            return is_primary_source(domain, intent=self.context.get("intent", "generic"))
        
        def render_finding(claim: str, domains: list, sources: list, label: str) -> list:
            def md_link(text: str, url: str, maxlen: int = 80) -> str:
                t = (text or url or "").strip().replace("]", "").replace("[", "")
                if len(t) > maxlen:
                    t = t[:maxlen-1] + "…"
                return f"[{t}]({url})"
            
            out = [f"- **{claim.strip()}** _[{label}]_",
                   f"  - Domains: {', '.join(sorted(set(domains)))}"]
            for s in sources:
                title = getattr(s, 'source_title', None) or getattr(s, 'title', None) or s.url
                out.append(f"    - {md_link(title, s.url)} — {s.source_domain}")
            return out
        
        # 1) Add triangulated claims first that pass density test
        top_findings = []
        for g in ordered[:15]:  # Check more candidates
            if len(top_findings) >= 10:
                break
            domains = sorted({x.source_domain for x in g})
            sample = g[0]
            claim_text = getattr(sample, 'quote_span', None) or sample.claim or sample.snippet or sample.source_title
            
            if not has_numeric_and_period(claim_text):
                continue
            
            label = "Triangulated" if len(g) > 1 else "Single-source"
            finding_lines = render_finding(claim_text, domains, g[:3], label)
            top_findings.extend(finding_lines)
        
        # 2) If <6 findings, backfill from single-source primary domains
        if len([line for line in top_findings if line.startswith("- **")]) < 6:
            for g in ordered[15:]:  # Check remaining groups
                if len([line for line in top_findings if line.startswith("- **")]) >= 6:
                    break
                if len(g) > 1:  # Skip, already checked triangulated
                    continue
                    
                sample = g[0]
                if not is_primary_domain(sample.source_domain):
                    continue
                    
                claim_text = getattr(sample, 'quote_span', None) or sample.claim or sample.snippet or sample.source_title
                if not has_numeric_and_period(claim_text):
                    continue
                    
                finding_lines = render_finding(claim_text, [sample.source_domain], [sample], "Single-source")
                top_findings.extend(finding_lines)
        
        lines.extend(top_findings)
        
        return "\n".join(lines)
    
    def _generate_final_report_old(self, cards: List[EvidenceCard], detector: ControversyDetector = None) -> str:
        """Legacy report generation - kept for reference"""
        if not cards:
            return "# Final Report\n\nNo evidence collected for this topic."
        
        # Build claim text with inline citations
            claim_text = primary_card.snippet
            
            # Add inline citations (minimum 1 per claim, 2+ for important claims)
            citations = []
            for i, card in enumerate(supporting_cards[:3], 1):  # Up to 3 citations per claim
                citations.append(f"[{i}]({card.url})")
            
            # Important claims (high confidence) get more citations
            min_citations = 2 if primary_card.confidence > 0.7 else 1
            while len(citations) < min_citations and len(supporting_cards) > len(citations):
                idx = len(citations)
                if idx < len(supporting_cards):
                    card = supporting_cards[idx]
                    citations.append(f"[{idx+1}]({card.url})")
            
            citations_str = " ".join(citations)
            
            report += f"""### {finding_num}. {primary_card.claim}

**Primary Source**: [{primary_card.title}]({primary_card.url}) [{primary_card.provider}]  
**Credibility**: {primary_card.credibility_score:.0%} | **Relevance**: {primary_card.relevance_score:.0%}

{claim_text} {citations_str}

"""
            if len(supporting_cards) > 1:
                report += "**Supporting Evidence**:\n"
                for i, card in enumerate(supporting_cards[1:min(4, len(supporting_cards))], 1):
                    report += f"{i}. [{card.title[:60]}...]({card.url}) - {card.provider}\n"
                    report += f"   *\"{card.snippet[:150]}...\"*\n\n"
            
            report += "---\n\n"
            finding_num += 1
        
        # Add Controversies section if detector is available
        if detector:
            controversial_claims = detector.get_controversial_claims(threshold=0.3)
            if controversial_claims:
                report += """## Controversies & Disputed Points

"""
                for claim_id, cluster in controversial_claims[:3]:  # Top 3 controversies
                    controversy_score = detector.controversy_scores.get(claim_id, 0)
                    
                    # Separate supporting and disputing evidence
                    supporting = [c for c in cluster if c.stance == "supports"]
                    disputing = [c for c in cluster if c.stance == "disputes"]
                    
                    if supporting or disputing:
                        report += f"""### Claim: {cluster[0].claim[:100]}...
**Controversy Score**: {controversy_score:.0%}

#### Supporting Evidence ({len(supporting)} sources):
"""
                        for card in supporting[:2]:  # Show top 2 of each
                            report += f"""- [{card.source_domain}]({card.source_url}): "{card.supporting_text[:150]}..."
"""
                        
                        report += f"""
#### Disputing Evidence ({len(disputing)} sources):
"""
                        for card in disputing[:2]:
                            report += f"""- [{card.source_domain}]({card.source_url}): "{card.supporting_text[:150]}..."
"""
                        report += "\n---\n\n"
        
        # OPTIONAL: Add related topics section if enabled
        if getattr(self.s, 'explore_related', False):  # Opt-in feature
            related_topics = self._extract_related_topics(cards, k=5)
            if related_topics:
                report += """## Related Topics for Further Research

Based on evidence analysis, these related topics emerged:

"""
                for topic in related_topics:
                    report += f"- **{topic['name']}** (relevance: {topic['score']:.1f}): {topic['reason_to_include']}\n"
                report += "\n"
        
        report += f"""## Source Distribution
"""
        for provider, provider_cards in by_provider.items():
            avg_conf = sum(c.confidence for c in provider_cards) / len(provider_cards)
            report += f"- **{provider.capitalize()}**: {len(provider_cards)} sources (avg confidence: {avg_conf:.0%})\n"
        
        report += f"""
## Methodology
- Search depth: {self.s.depth}
- Providers used: {', '.join(by_provider.keys())}
- Evidence validated against JSON schema
- Controversy detection and claim clustering applied
- Scores calculated based on domain trust, relevance, and corroboration
- Inline citations: minimum 1 per claim, 2+ for high-confidence claims

## References

Full evidence corpus available in `evidence_cards.jsonl`. Top sources by credibility:

"""
        # Add top 10 sources as references
        top_by_cred = sorted(cards, key=lambda x: x.credibility_score, reverse=True)[:10]
        for i, card in enumerate(top_by_cred, 1):
            report += f"{i}. [{card.title}]({card.url}) - {card.provider} (Credibility: {card.credibility_score:.0%})\n"
        
        return report

    def _generate_citation_checklist(self, cards: List[EvidenceCard], error_file_path=None) -> str:
        """Generate citation validation checklist with truthful validation"""
        checklist = "# Citation Validation Checklist\n\n"
        
        # Date parsing helper
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=365)
        def _parse_dt(s):
            if not s: return None
            s = str(s).strip()
            # Try various formats
            formats = [
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S",  
                "%Y-%m-%d",
                "%Y/%m/%d",
                "%Y"
            ]
            for fmt in formats:
                try:
                    # Handle ISO format with timezone
                    clean_s = s.split('+')[0].split('.')[0]
                    dt = datetime.strptime(clean_s, fmt)
                    # Make timezone-aware (assume UTC if not specified)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except:
                    pass
            return None
        
        # Check various criteria with actual implementation
        has_primary = any(c.is_primary_source for c in cards)
        # Use timezone-aware datetime.min replacement
        min_date = datetime.min.replace(tzinfo=timezone.utc)
        recent_cards = [c for c in cards if (_parse_dt(getattr(c, 'publication_date', None) or getattr(c, 'date', None)) or min_date) >= cutoff]
        has_recent = len(recent_cards) > 0
        all_attributed = all(bool(getattr(c, 'provider', None)) for c in cards)
        high_quality = len([c for c in cards if (getattr(c, 'credibility_score', 0) or 0) > 0.7])
        
        # Check for schema errors
        schema_valid = True
        schema_errors = 0
        if error_file_path and error_file_path.exists():
            schema_errors = sum(1 for _ in error_file_path.open() if _.strip())
            schema_valid = schema_errors == 0
        
        # Check for unique IDs
        ids = [getattr(c, 'id', None) for c in cards]
        unique_ids = len(ids) == len(set(ids)) and None not in ids
        
        # Check URL formats
        import re
        url_pattern = re.compile(r'^https?://')
        valid_urls = all(bool(url_pattern.match(str(getattr(c, 'url', '')))) for c in cards)
        
        checklist += f"""## Coverage
- [{'x' if len(cards) > 0 else ' '}] Evidence collected from search providers ({len(cards)} cards)
- [{'x' if has_primary else ' '}] Primary sources included ({sum(1 for c in cards if c.is_primary_source)}/{len(cards)})
- [{'x' if len(set(c.source_domain for c in cards)) > 1 else ' '}] Multiple domains represented ({len(set(c.source_domain for c in cards))} unique)

## Quality
- [{'x' if high_quality > 0 else ' '}] High credibility sources (>{high_quality} with score >0.7)
- [{'x' if all_attributed else ' '}] All evidence attributed to search provider
- [{'x' if has_recent else ' '}] Recent sources included ({len(recent_cards)} within 365 days)

## Validation
- [{'x' if schema_valid else ' '}] JSON schema validation passed{' (' + str(schema_errors) + ' errors)' if schema_errors else ''}
- [{'x' if valid_urls else ' '}] All URLs properly formatted
- [{'x' if unique_ids else ' '}] Unique evidence IDs assigned
- [{'x' if len(cards) >= 3 else ' '}] Minimum evidence threshold met ({len(cards)}/3)

## Statistics
- Total evidence cards: {len(cards)}
- Unique domains: {len(set(c.source_domain for c in cards))}
- Primary sources: {sum(1 for c in cards if c.is_primary_source)} ({sum(1 for c in cards if c.is_primary_source)*100//max(len(cards),1)}%)
- Recent content: {len(recent_cards)} ({len(recent_cards)*100//max(len(cards),1)}%)
- Average credibility: {sum(getattr(c, 'credibility_score', 0) for c in cards)/max(len(cards), 1):.0%}
- Average relevance: {sum(getattr(c, 'relevance_score', 0) for c in cards)/max(len(cards), 1):.0%}
"""
        
        return checklist

    def run(self):
        """Main orchestrator run method with v8.13.0 transaction support."""
        
        # Load v8.13.0 configuration
        cfg = self.v813_config
        
        # Log v8.13.0 configuration once at start
        logger.info(
            "v8.13.0 Quality thresholds: primary_share=%.0f%%, triangulation=%.0f%%, domain_cap=%.0f%%",
            cfg.primary_share_floor * 100,
            cfg.triangulation_floor * 100,
            cfg.domain_concentration_cap * 100
        )
        
        # Wrap entire run in transaction for atomic writes
        with run_transaction(str(self.s.output_dir)):
            self._run_internal()
    
    def _run_internal(self):
        """Internal run method wrapped by transaction."""
        settings = Settings()  # validated at CLI
        import time
        self.start_time = time.time()  # Make it an instance variable for later access
        
        # Set global time budget (default 1800 seconds / 30 minutes)
        total_seconds = getattr(self.s, 'timeout', 1800)
        self.time_budget = total_seconds  # Store for adaptive decisions
        budget = set_global_budget(total_seconds)
        logger.info(f"Set global time budget: {total_seconds}s")
        
        # Classify intent
        intent = classify(self.s.topic)
        self.context["intent"] = intent.value
        logger.info(f"Query classified as intent: {intent.value}")
        
        # Get intent-specific thresholds
        min_triangulation, min_sources = get_confidence_threshold(intent)
        logger.info(f"Intent thresholds: triangulation={min_triangulation}, sources={min_sources}")
        
        # Generate intent-specific query expansions
        expanded_queries = self._generate_intent_queries(intent.value, self.s.topic)
        
        # PLAN
        self._write("plan.md", self._generate_plan())
        self._write("source_strategy.md", self._generate_source_strategy())
        self._write("acceptance_guardrails.md", self._generate_acceptance_guardrails())

        # COLLECT (parallel, per-provider preserved)
        # Build discipline-aware anchors first
        all_results = {}
        anchors, discipline, policy = build_anchors(self.s.topic)
        self.discipline, self.policy = discipline, policy
        
        # Use intent-based provider selection
        intent_providers = expand_providers_for_intent(intent)
        logger.info(f"Intent {intent.value} selected providers: {intent_providers[:10]}")
        
        # Also use router for additional context
        decision = choose_providers(self.s.topic)
        logger.info(f"Routing: categories={decision.categories}, providers={decision.providers[:10]}")
        
        # Merge providers: intent-based first, then router's unique additions
        merged_providers = intent_providers + [p for p in decision.providers if p not in intent_providers]
        # Create new decision object with updated providers (can't modify frozen dataclass)
        from dataclasses import replace
        decision = replace(decision, providers=merged_providers[:20])  # Limit total
        
        enabled = settings.enabled_providers()
        # Filter providers by topic relevance to prevent off-topic noise
        filtered_providers = self._filter_providers_by_topic(enabled, self.s.topic)
        selected_providers = [p for p in decision.providers if p in filtered_providers]
        
        # ===== v8.13.0 STATS PIPELINE INTEGRATION =====
        # For stats intent, use specialized pipeline instead of general collection
        if intent.value == "stats":
            logger.info("v8.13.0 Using specialized stats pipeline")
            try:
                primary_cards, context_cards = run_stats_pipeline(
                    query=self.s.topic,
                    all_providers=selected_providers,
                    collect_function=self._collect_from_providers
                )
                
                # Prioritize stats sources
                primary_cards = prioritize_stats_sources(primary_cards)
                
                # Stats-specific processing overrides normal collection
                stats_cards = primary_cards + context_cards
                logger.info(f"v8.13.0 Stats pipeline: {len(primary_cards)} primary, {len(context_cards)} context cards")
                
                # Skip normal collection for stats - we have specialized cards
                all_results = {"stats_pipeline": []}  # Dummy for compatibility
                
            except Exception as e:
                logger.warning(f"v8.13.0 Stats pipeline failed, falling back to normal collection: {e}")
                # Continue with normal collection if stats pipeline fails
        
        if anchors and self.s.depth in ["standard", "deep"]:
            # Run discipline-aware anchor queries
            for anchor_query in anchors[:6]:
                self.provider_attempts += 1
                try:
                    anchor_results = asyncio.run(
                        parallel_provider_search(registry, query=anchor_query, count=3,
                                               freshness=settings.FRESHNESS_WINDOW, region="US")
                    )
                    # Merge results by provider
                    for provider, hits in anchor_results.items():
                        if provider not in all_results:
                            all_results[provider] = []
                        all_results[provider].extend(hits)
                except Exception as e:
                    self.provider_errors += 1
                    logger.warning(f"Anchor query failed: {e}")
        
        # Run expanded queries based on intent
        results_count = self.depth_to_count.get(self.s.depth, 8)
        all_provider_results = {}
        
        # Execute each expanded query
        for query in expanded_queries[:3]:  # Limit to first 3 queries
            self.provider_attempts += 1
            try:
                query_results = asyncio.run(
                    parallel_provider_search(registry, query=query, count=results_count,
                                             freshness=settings.FRESHNESS_WINDOW if self.context["intent"] in ["news", "policy"] else None,
                                             region="US")
                )
                # Merge results per provider
                for provider, hits in query_results.items():
                    if provider not in all_provider_results:
                        all_provider_results[provider] = []
                    all_provider_results[provider].extend(hits)
                logger.info(f"Expanded query '{query}' returned {sum(len(h) for h in query_results.values())} results")
            except Exception as e:
                self.provider_errors += 1
                logger.warning(f"Expanded query '{query}' failed: {e}")
        
        # Use merged results instead of single query results
        main_results = all_provider_results
        
        # Merge main results
        for provider, hits in main_results.items():
            if provider not in all_results:
                all_results[provider] = []
            all_results[provider].extend(hits)
        
        per_provider = all_results
        
        # ADD FREE API PROVIDERS
        if getattr(settings, 'ENABLE_FREE_APIS', True):
            logger.info(f"Collecting from free APIs for topic: {self.s.topic}")
            
            # Use intent-based provider selection for free APIs too
            intent_providers = expand_providers_for_intent(intent)
            
            # Use router to select appropriate providers
            decision = choose_providers(self.s.topic)
            logger.info(f"Router selected providers: {decision.providers[:10]} for categories: {decision.categories}")
            
            # Merge with intent providers
            merged_providers = intent_providers + [p for p in decision.providers if p not in intent_providers]
            # Create new decision object with updated providers (can't modify frozen dataclass)
            from dataclasses import replace
            decision = replace(decision, providers=merged_providers[:15])  # Limit for free APIs
            
            # Collect from free APIs
            free_api_cards = collect_from_free_apis(
                self.s.topic,
                providers=decision.providers[:10],  # Limit to top 10 to avoid too many requests
                settings=settings
            )
            
            logger.info(f"Collected {len(free_api_cards)} cards from free APIs")
            
            # These will be added to cards list below
        else:
            free_api_cards = []

        # TRANSFORM to EvidenceCard (stamp search_provider)
        cards: List[EvidenceCard] = []
        
        # v8.13.0: Use stats cards if available from specialized pipeline
        if 'stats_cards' in locals() and stats_cards:
            logger.info(f"v8.13.0 Using {len(stats_cards)} cards from stats pipeline")
            cards.extend(stats_cards)
        else:
            # Normal collection path
            # Add free API cards first (they're already EvidenceCard objects)
            cards.extend(free_api_cards)
        
        # Then add web search results
        for provider, hits in per_provider.items():
            for h in hits:
                # Calculate scoring based on source attributes and discipline
                domain = domain_of(h.url)
                
                # Filter out banned domains
                from research_system.collect.filter import allowed_domain
                if not allowed_domain(domain):
                    logger.debug(f"Skipping banned domain: {domain}")
                    continue
                
                pol = getattr(self, "policy", POLICIES[route_topic(self.s.topic)])
                is_primary = domain in pol.domain_priors
                
                # Score based on domain trust and discipline priors
                credibility = pol.domain_priors.get(domain, 0.5)
                
                # Simple relevance scoring based on query match in title/snippet
                text = (h.title + " " + (h.snippet or "")).lower()
                query_terms = self.s.topic.lower().split()
                matches = sum(1 for term in query_terms if term in text)
                relevance = min(1.0, matches / max(len(query_terms), 1))
                
                # Extract author if available
                author = None
                if hasattr(h, 'author'):
                    author = h.author
                elif hasattr(h, 'metadata') and isinstance(h.metadata, dict):
                    author = h.metadata.get('author')
                
                # Ensure snippet is non-empty
                snippet_text = h.snippet or f"Content from {h.title[:200] if h.title else 'source'}"
                
                cards.append(EvidenceCard(
                    # All required blueprint fields
                    id=str(uuid.uuid4()),
                    title=h.title,
                    url=h.url,
                    snippet=snippet_text,
                    provider=provider,  # Critical: stamp the provider
                    date=h.date,  # Pass through if available
                    publication_date=getattr(h, 'publication_date', None) or h.date,  # Try both fields
                    
                    # Legacy fields for compatibility
                    source_title=h.title,
                    source_url=h.url,
                    source_domain=canonical_domain(domain),
                    claim=h.title,
                    supporting_text=snippet_text,
                    search_provider=provider,
                    
                    # Scoring fields
                    credibility_score=credibility,
                    relevance_score=relevance,
                    confidence=credibility * relevance,
                    is_primary_source=is_primary,
                    
                    # Metadata
                    subtopic_name="Research Findings",
                    collected_at=datetime.now(timezone.utc).isoformat(),
                    author=author
                ))

        # ENRICH: Extract metadata + sentences + snapshot (optional)
        logger.info(f"Enriching {len(cards)} cards with ENABLE_EXTRACT={getattr(settings, 'ENABLE_EXTRACT', True)}")
        
        # Light HTML enrichment first (fast, safe)
        from research_system.tools.fetch_simple import fetch_excerpt
        for c in cards:
            url = c.url or c.source_url or ""
            if url:
                excerpt = fetch_excerpt(url, max_chars=800)
                if excerpt and len(excerpt) > len(c.supporting_text or ""):
                    c.supporting_text = excerpt
                    # Also update snippet if it's still the placeholder
                    if c.snippet and "Content from" in c.snippet:
                        c.snippet = excerpt[:200]
        
        # Import quote rescue for primary sources
        from research_system.enrich.ensure_quotes import ensure_quotes_for_primaries
        for c in cards:
            if getattr(settings, "ENABLE_EXTRACT", True):
                url = c.url or c.source_url or ""
                logger.debug(f"Extracting article from: {url}")
                meta = extract_article(url)
                if meta.get("title"):
                    c.source_title = meta["title"]
                if not getattr(c, "date", None) and meta.get("date"):
                    c.date = meta["date"]
                quotes = meta.get("quotes") or []
                if quotes:
                    c.quote_span = quotes[0]  # deterministic, sentence-level
                    logger.debug(f"Set quote_span: {c.quote_span[:50]}...")
                # Mark paywalled/unreachable
                if not meta and any(h in (c.url or "") for h in ["e-unwto.org","statista.com"]):
                    c.reachability = 0.0
                else:
                    c.reachability = 1.0
            if getattr(settings, "ENABLE_SNAPSHOT", False):
                arch = save_wayback(c.url or c.source_url or "")
                if arch:
                    c.content_hash = (c.content_hash or f"wayback:{arch}")
            # Always compute a normalized content hash for dedup
            basis = getattr(c, 'quote_span', None) or c.claim or c.snippet or c.source_title or ""
            c.content_hash = getattr(c, 'content_hash', None) or normalized_hash(basis)
        
        # Ensure quotes for primary sources via fallback mechanisms
        ensure_quotes_for_primaries(cards)
        
        # DEDUPLICATE near-duplicates across domains (syndication control) BEFORE clustering
        if getattr(settings, "ENABLE_MINHASH_DEDUP", True):
            texts = [(getattr(c, "quote_span", None) or getattr(c, "claim", "") or getattr(c, "snippet", "") or getattr(c, "source_title","")) for c in cards]
            dup_groups = minhash_near_dupes(texts, shingle_size=6, threshold=0.92)
            drop = set()
            for g in dup_groups:
                # keep one (highest credibility), drop the rest
                group = sorted(list(g), key=lambda i: getattr(cards[i], "credibility_score", 0.5), reverse=True)
                drop.update(group[1:])
            cards = [c for i, c in enumerate(cards) if i not in drop]
        
        # Enhanced dedup and ranking
        cards = self._dedup(cards)  # Uses enhanced title-aware deduplication
        
        # Apply quality-based ranking
        from research_system.collect.ranker import rerank_cards
        cards = rerank_cards(cards)
        
        # MINIMUM CARDS FLOOR - Ensure we have enough cards for stable metrics
        MIN_CARDS = 24
        if len(cards) < MIN_CARDS:
            logger.info(f"Low volume ({len(cards)}) — expanding providers for diversity")
            from research_system.providers.registry import PROVIDERS
            
            extra_provs = ["oecd", "imf", "eurostat", "ec", "wto", "unctad", "bis"]
            for p in extra_provs:
                if p not in PROVIDERS:
                    continue
                impl = PROVIDERS[p]
                if "search" not in impl:
                    continue
                    
                try:
                    # Search for topic with this provider
                    results = impl["search"](self.s.topic)
                    if impl.get("to_cards"):
                        new_cards = impl["to_cards"](results)
                    else:
                        new_cards = results
                    
                    # Convert to EvidenceCards
                    for nc in new_cards[:5]:  # Take up to 5 from each provider
                        cards.append(EvidenceCard(
                            id=str(uuid.uuid4()),
                            title=nc.get("title", ""),
                            url=nc.get("url", ""),
                            snippet=nc.get("snippet", ""),
                            provider=p,
                            credibility_score=nc.get("credibility_score", 0.8),
                            relevance_score=nc.get("relevance_score", 0.7),
                            confidence=nc.get("confidence", 0.5),
                            source_domain=canonical_domain(nc.get("source_domain", nc.get("url", ""))),
                            collected_at=datetime.now(timezone.utc).isoformat(),
                            is_primary_source=True,
                            claim=nc.get("claim", nc.get("title", "")),
                            supporting_text=nc.get("supporting_text", nc.get("snippet", "")),
                            subtopic_name="Research Findings",
                            stance="neutral",
                            claim_id=None,
                            disputed_by=[],
                            controversy_score=0.0
                        ))
                        
                    cards = self._dedup(cards)
                    if len(cards) >= MIN_CARDS:
                        break
                except Exception as e:
                    logger.warning(f"Failed to expand with {p}: {e}")
                    continue
        
        # Early diversity check - if any single domain exceeds 25%, inject diversity BEFORE final balancing
        # This ensures we have diverse sources available for the final selection
        from research_system.selection.domain_balance import BalanceConfig, enforce_cap
        from collections import Counter
        
        # Check domain distribution
        domain_counts = Counter(canonical_domain(c.source_domain) for c in cards)
        total = len(cards)
        
        # If any domain exceeds 25%, proactively add diversity with generic class-based expansions
        for domain, count in domain_counts.items():
            if total > 0 and count / total > 0.25:
                logger.info(f"Domain {domain} at {count/total:.1%}, injecting diversity")
                
                # Generic class-based diversity expansions (topic-agnostic)
                diversity_queries = []
                
                # Check what types we already have to avoid duplication
                existing_tlds = set()
                for d in domain_counts.keys():
                    if '.gov' in d:
                        existing_tlds.add('.gov')
                    elif '.edu' in d:
                        existing_tlds.add('.edu')
                    elif '.org' in d:
                        existing_tlds.add('.org')
                
                # Add missing source classes (max 3 to stay within budget)
                if '.gov' not in existing_tlds:
                    diversity_queries.append(f"{self.s.topic} site:.gov")
                if '.edu' not in existing_tlds:
                    diversity_queries.append(f"{self.s.topic} site:.edu")
                if len(diversity_queries) < 3:
                    # Add reference sources if not already present
                    if 'wikipedia.org' not in domain_counts and 'britannica.com' not in domain_counts:
                        diversity_queries.append(f"{self.s.topic} site:wikipedia.org OR site:britannica.com")
                if len(diversity_queries) < 3:
                    # Add data sources if relevant
                    if 'data.gov' not in domain_counts and 'catalog.data.gov' not in domain_counts:
                        diversity_queries.append(f"{self.s.topic} (dataset OR data) site:data.gov OR site:catalog.data.gov")
                
                # Execute diversity queries (limit to 2 for performance)
                for div_query in diversity_queries[:2]:
                    try:
                        div_results = asyncio.run(
                            parallel_provider_search(
                                registry,
                                query=div_query,
                                count=3,
                                freshness=settings.FRESHNESS_WINDOW,
                                region="US"
                            )
                        )
                        
                        # Add diversity results
                        for provider, hits in div_results.items():
                            for h in hits[:2]:  # Limit per provider
                                new_domain = domain_of(h.url)
                                # Only add if it actually diversifies
                                if new_domain not in domain_counts or domain_counts[new_domain] < 2:
                                    cards.append(EvidenceCard(
                                        id=str(uuid.uuid4()),
                                        title=h.title,
                                        url=h.url,
                                        snippet=self._ensure_snippet(h.snippet, h.title, h.url),
                                        provider=provider,
                                        credibility_score=0.85,
                                        relevance_score=0.75,
                                        confidence=0.64,
                                        is_primary_source=_is_primary_class(new_domain),
                                        source_domain=canonical_domain(new_domain),
                                        collected_at=datetime.now(timezone.utc).isoformat()
                                    ))
                                    # Update counts to prevent over-adding from same domain
                                    domain_counts[new_domain] = domain_counts.get(new_domain, 0) + 1
                    except Exception as e:
                        logger.debug(f"Diversity injection failed: {e}")
                        continue
                
                break  # Only handle the first over-represented domain
        
        # Keep top cards based on depth (but keep all for triangulation)
        max_cards = self.depth_to_count.get(self.s.depth, 20) * 3  # 3x for triangulation
        if len(cards) > max_cards:
            cards = cards[:max_cards]

        # BUILD TRIANGULATION using enhanced paraphrase clustering
        from research_system.triangulation.paraphrase_cluster import cluster_paraphrases
        from research_system.triangulation.compute import compute_structured_triangles, union_rate
        from research_system.metrics_compute import primary_share_in_triangulated as primary_share_in_union
        from research_system.triangulation.post import sanitize_paraphrase_clusters, structured_triangles
        
        # Paraphrase clustering with SBERT
        para_clusters = cluster_paraphrases(cards)
        
        # Sanitize paraphrase clusters to prevent over-merging
        para_clusters = sanitize_paraphrase_clusters(para_clusters, cards)
        
        # Filter out contradictory clusters before representative selection
        para_clusters = filter_contradictory_clusters(para_clusters)
        logger.info(f"After contradiction filtering: {len(para_clusters)} paraphrase clusters")
        
        # Structured triangulation - NEW PE-grade indicator matching
        structured_matches = structured_triangles(cards)
        
        # Also compute legacy structured triangles if available
        try:
            legacy_structured = compute_structured_triangles(cards)
            # Merge both structured triangle sources
            if legacy_structured:
                structured_matches.extend(legacy_structured)
        except:
            pass  # Use only new structured triangles
        
        # Calculate union rate for strict mode
        tri_union = union_rate(para_clusters, structured_matches, len(cards))
        
        # Write single source of truth for triangulation
        # Convert structured_matches cards from objects to indices for JSON serialization
        serializable_structured = []
        for match in structured_matches:
            serializable_match = {
                "key": match.get("key", ""),
                "indices": match.get("indices", []),  # Use indices if available
                "domains": match.get("domains", []),
                "size": match.get("size", match.get("count", len(match.get("indices", []))))  # Handle both 'size' and 'count' fields
            }
            # If indices not available but cards are, extract indices
            if not serializable_match["indices"] and "cards" in match:
                serializable_match["indices"] = [cards.index(c) for c in match["cards"] if c in cards]
            serializable_structured.append(serializable_match)
        
        artifact = {
            "paraphrase_clusters": para_clusters,  # Already has correct structure with indices
            "structured_triangles": serializable_structured
        }
        self._write("triangulation.json", json.dumps(artifact, indent=2))
        
        # Calculate comprehensive metrics with domain and provider entropy
        from collections import Counter
        import math
        N = len(cards)
        # Use canonical domains for accurate metric calculation
        dom_ct = Counter(canonical_domain(c.source_domain) for c in cards)
        top_share = (dom_ct.most_common(1)[0][1]/N) if N and dom_ct else 0.0
        prov_ct = Counter(getattr(c, "provider", None) for c in cards if getattr(c, "provider", None))
        H = -sum((n/N)*math.log((n/N)+1e-12) for n in prov_ct.values()) if N and prov_ct else 0.0
        H_norm = H / math.log(max(2, len(prov_ct))) if prov_ct and len(prov_ct) > 1 else 0.0
        
        # Get pack-specific primary domains and patterns
        packs = classify_topic_multi(self.s.topic)
        pack_domains = set(PRIMARY_CANONICALS)
        pack_patterns = list(PRIMARY_PATTERNS)
        
        for pack_key in packs:
            pack_config = PRIMARY_CONFIG.get(pack_key, {})
            pack_domains |= set(pack_config.get("canonical", []))
            for pat_str in pack_config.get("patterns", []):
                import re
                pack_patterns.append(re.compile(pat_str, re.I))
        
        # Calculate initial metrics for decision making (not final output)
        primary_share = primary_share_in_union(cards, para_clusters, structured_matches, 
                                              primary_domains=pack_domains, 
                                              primary_patterns=pack_patterns)
        
        # Store values we'll need later for final metrics
        initial_H_norm = H_norm
        
        # PRIMARY BACKFILL if needed
        # v8.17.0: Honor strict mode - disable backfill when strict mode is on
        if self.s.strict:
            logger.info("Strict mode enabled: skipping backfill passes to match source strategy.")
            # No backfill, proceed to finalize with current evidence
        # v8.16.0: Use configured threshold (default 33%) consistently
        elif primary_share < getattr(self.v813_config, 'primary_share_floor', 0.33):
            min_primary_threshold = getattr(self.v813_config, 'primary_share_floor', 0.33)
            logger.info(f"Primary share {primary_share:.2%} < {min_primary_threshold:.0%}, running backfill")
            from research_system.enrich.primary_fill import primary_fill_for_families
            
            # Get families that need primaries
            families = para_clusters + structured_matches
            families = [f for f in families if len(set(f.get("domains", []))) >= 2]
            
            # Simple search wrapper
            def search_wrapper(query, n):
                try:
                    results = asyncio.run(parallel_provider_search(registry, query, n, None, None))
                    # Flatten results from all providers
                    all_results = []
                    for provider, hits in results.items():
                        all_results.extend(hits)
                    return all_results[:n]
                except:
                    return []
            
            # Extract wrapper  
            def extract_wrapper(url):
                try:
                    content = extract_article(url, timeout=20)
                    if content and content.text:
                        # Create minimal card
                        from research_system.models import EvidenceCard
                        return EvidenceCard(
                            id=str(uuid.uuid4()),
                            title=content.title or url,
                            url=url,
                            snippet=content.text[:500],
                            provider="primary_backfill",
                            credibility_score=0.85,
                            relevance_score=0.75,
                            confidence=0.80,
                            is_primary_source=True,
                            source_domain=canonical_domain(domain_of(url)),
                            claim=content.title or "",
                            supporting_text=content.text[:1000],
                            subtopic_name=self.s.topic,
                            collected_at=datetime.now(timezone.utc).isoformat()
                        )
                except:
                    return None
                    
            # Run primary backfill with pack-specific domains
            new_cards = primary_fill_for_families(
                families=families,
                topic=self.s.topic,
                search_fn=search_wrapper,
                extract_fn=extract_wrapper,
                k_per_family=2,
                primary_domains=pack_domains,
                primary_patterns=pack_patterns
            )
            
            if new_cards:
                logger.info(f"Added {len(new_cards)} primary source cards")
                # Merge and re-triangulate
                cards = self._dedup(cards + new_cards)
                
                # Re-run quote rescue on new cards
                ensure_quotes_for_primaries(cards, only=new_cards)
                
                # Re-compute triangulation with new cards
                para_clusters = cluster_paraphrases(cards)
                para_clusters = sanitize_paraphrase_clusters(para_clusters, cards)
                para_clusters = filter_contradictory_clusters(para_clusters)
                structured_matches = compute_structured_triangles(cards)
                tri_union = union_rate(para_clusters, structured_matches, len(cards))
                
                # Recalculate values needed for final metrics
                primary_share = primary_share_in_union(cards, para_clusters, structured_matches,
                                                      primary_domains=pack_domains,
                                                      primary_patterns=pack_patterns)
        
        # CONTRADICTION DETECTION
        claim_texts = [
            (getattr(c, "quote_span", None) or getattr(c, "claim", "") or 
             getattr(c, "snippet", "") or getattr(c, "source_title", ""))
            for c in cards
        ]
        contradictions = find_numeric_conflicts(claim_texts, tol=0.10)
        
        # AREX: Refined targeted expansion for uncorroborated structured claims
        triangulated_keys = {m.get("key") for m in structured_matches if m.get("key")}
        
        # Extract structured claims for AREX
        from research_system.tools.claim_struct import extract_struct_claim, struct_key
        structured_claims = []
        for i, text in enumerate(claim_texts):
            sc = extract_struct_claim(text)
            key = struct_key(sc)
            if key:
                structured_claims.append({
                    "index": i,
                    "key": key,
                    "entity": sc.entity,
                    "metric": sc.metric,
                    "period": sc.period,
                    "value": sc.value,
                    "unit": sc.unit,
                    "text": text[:200]
                })
        
        uncorroborated = select_uncorroborated_keys(structured_claims, triangulated_keys, max_keys=3)
        
        # Check if AREX is enabled via environment or settings
        enable_arex = os.getenv("ENABLE_AREX", "false").lower() == "true" or getattr(settings, "ENABLE_AREX", False)
        
        if enable_arex and uncorroborated and len(cards) < 50:  # Only expand if under budget
            # Get primary domains from policy
            pol = getattr(self, "policy", POLICIES[route_topic(self.s.topic)])
            discipline = getattr(self, "discipline", Discipline.GENERAL)
            
            # Import refined AREX tools
            from research_system.tools.arex_refine import build_queries
            from research_system.tools.arex_rerank import rerank_and_filter
            
            # Process each uncorroborated key with refined queries and reranking
            for claim in uncorroborated:
                entity = claim.get("entity", "")
                metric = claim.get("metric", "")
                period = claim.get("period", "")
                
                if not metric:  # Must have at least a metric
                    continue
                    
                # Build refined queries with negative terms and primary hints
                queries = build_queries(entity, metric, period, discipline.value)
                
                # Execute queries and collect results
                key_text = f"{entity} {metric} {period}".strip()
                
                for query in queries[:4]:  # Limit to 4 queries per key
                    # Execute search
                    search_results = asyncio.run(
                        parallel_provider_search(registry, query=query, count=6,
                                               freshness=settings.FRESHNESS_WINDOW, region="US")
                    )
                    
                    # Process each provider's results
                    for provider, hits in search_results.items():
                        if not hits:
                            continue
                            
                        # Prepare candidates for reranking
                        candidates = []
                        for h in hits:
                            text = f"{h.title or ''} {h.snippet or ''}".strip()
                            if text:
                                candidates.append((text, h.url))
                        
                        # Rerank by similarity to key
                        if candidates:
                            ranked = rerank_and_filter(key_text, candidates, min_sim=0.32)
                            
                            # Keep only top 3 most relevant
                            keep_urls = {url for _, url, _ in ranked[:3]}
                            
                            # Add filtered results as cards
                            for h in hits:
                                if h.url in keep_urls:
                                    domain = domain_of(h.url)
                                    credibility = pol.domain_priors.get(domain, 0.5)
                                    
                                    # Boost credibility for primary sources
                                    if domain in pol.domain_priors:
                                        credibility = min(1.0, credibility * 1.15)
                                    
                                    cards.append(EvidenceCard(
                                        id=str(uuid.uuid4()),
                                        title=h.title,
                                        url=h.url,
                                        snippet=self._ensure_snippet(h.snippet, h.title, h.url),
                                        provider=provider,
                                        date=h.date,
                                        credibility_score=credibility,
                                        relevance_score=0.75,  # Higher relevance for filtered AREX
                                        confidence=credibility * 0.75,
                                        is_primary_source=is_primary_domain(domain),
                                        search_provider=provider,
                                        source_domain=canonical_domain(domain),
                                        collected_at=datetime.now(timezone.utc).isoformat(),
                                        related_reason=f"arex_targeted_{metric}"
                                    ))
        
        # CONTROVERSY DETECTION
        detector = ControversyDetector()
        clusters, controversy_scores = detector.process_evidence(cards)
        
        # Adjust credibility based on corroboration/contradiction
        for claim_id, cluster in clusters.items():
            controversy = controversy_scores.get(claim_id, 0)
            for card in cluster:
                if controversy > 0.5:
                    # Penalize isolated claims in high-controversy clusters
                    if len(card.disputed_by) > len([c for c in cluster if c.stance == card.stance]):
                        card.credibility_score *= 0.8
                elif len(cluster) > 1 and controversy < 0.2:
                    # Reward corroborated claims with low controversy
                    card.credibility_score = min(1.0, card.credibility_score * 1.1)
        
        # RECOMPUTE per-card confidence with priors, triangulation, recency
        from research_system.scoring import recompute_confidence_with_discipline
        tri_card_index = set()
        for cl in para_clusters:
            if len(cl.get("domains", [])) >= 2:
                tri_card_index.update(cl.get("indices", []))
        for m in structured_matches:
            if len(m.get("domains", [])) >= 2:
                tri_card_index.update(m.get("indices", []))
        from datetime import timezone
        now = datetime.now(timezone.utc)
        for i, c in enumerate(cards):
            # Calculate recency days
            recency_days = None
            if getattr(c, "date", None):
                try:
                    if isinstance(c.date, str):
                        c_date = datetime.fromisoformat(c.date.replace('Z', '+00:00'))
                    else:
                        c_date = c.date
                    # Ensure both are timezone-aware for comparison
                    if c_date.tzinfo is None:
                        c_date = c_date.replace(tzinfo=timezone.utc)
                    recency_days = (now - c_date).days
                except:
                    pass
            c.confidence = recompute_confidence_with_discipline(
                c, self.s.topic, triangulated=(i in tri_card_index), recency_days=recency_days
            )

        # WRITE evidence (schema enforced) - convert dates to strings
        for c in cards:
            if hasattr(c, 'date') and c.date:
                if not isinstance(c.date, str):
                    c.date = c.date.isoformat() if hasattr(c.date, 'isoformat') else str(c.date)
        
        # Mark triangulated cards for prioritization in domain balancing
        # Use safe update pattern to avoid field assignment issues
        updated_cards = []
        for i, c in enumerate(cards):
            # Use model's copy method with update for safe field setting
            is_tri = i in tri_card_index
            if hasattr(c, 'model_copy'):  # Pydantic v2
                updated = c.model_copy(update={"is_triangulated": is_tri})
            elif hasattr(c, 'copy'):  # Pydantic v1
                updated = c.copy(update={"is_triangulated": is_tri})
            else:
                # Fallback: direct assignment if copy methods unavailable
                c.is_triangulated = is_tri
                updated = c
            updated_cards.append(updated)
        cards = updated_cards
        
        # PE-GRADE DOMAIN BALANCING - Apply after all expansion but before final metrics
        from research_system.selection.domain_balance import BalanceConfig, enforce_cap, enforce_domain_cap, need_backfill, backfill
        from research_system.providers.registry import PROVIDERS
        
        # Store raw cards before balancing for appendix
        raw_cards = list(cards)
        
        # Apply adaptive domain balance based on supply conditions
        unique_domains = len(set(canonical_domain(c.source_domain) for c in cards))
        balanced_cards, kept, balance_note = apply_adaptive_domain_balance(
            cards, self.quality_config, unique_domains
        )
        logger.info(balance_note)
        
        # Check if we need to backfill from primary sources
        # Create a temporary config for backfill check
        bal_cfg = BalanceConfig(cap=self.quality_config.domain_balance.cap_default, min_cards=24, prefer_primary=True)
        if need_backfill(balanced_cards, bal_cfg):
            logger.info(f"Backfilling from primary sources (have {len(balanced_cards)}, need {bal_cfg.min_cards})")
            # Use primary providers for backfill
            for prov in ("oecd", "ec", "eurostat", "imf", "worldbank"):
                impl = PROVIDERS.get(prov, {})
                if "search" not in impl:
                    continue
                try:
                    seeds = backfill(balanced_cards, self.s.topic, impl["search"], impl.get("to_cards"), bal_cfg)
                    for s in seeds[:5]:  # Limit per provider
                        balanced_cards.append(EvidenceCard(
                            id=str(uuid.uuid4()),
                            title=s.get("title", ""),
                            url=s.get("url", ""),
                            snippet=s.get("snippet", ""),
                            provider=prov,
                            source_domain=canonical_domain(s.get("source_domain", s.get("url", ""))),
                            credibility_score=0.85,
                            relevance_score=0.75,
                            confidence=0.64,
                            is_primary_source=True,
                            collected_at=datetime.now(timezone.utc).isoformat(),
                            claim=s.get("claim", s.get("title", "")),
                            supporting_text=s.get("supporting_text", s.get("snippet", "")),
                            subtopic_name="Research Findings"
                        ))
                    balanced_cards = self._dedup(balanced_cards)
                    # Re-enforce cap after adding
                    balanced_cards, kept = enforce_cap(balanced_cards, bal_cfg)
                    if not need_backfill(balanced_cards, bal_cfg):
                        break
                except Exception as e:
                    logger.warning(f"Backfill from {prov} failed: {e}")
            logger.info(f"After backfill: {len(balanced_cards)} cards")
        
        # Use balanced cards for everything downstream
        cards = balanced_cards
        
        # Apply final domain cap enforcement as safety measure
        cards = enforce_domain_cap(cards, cap=0.25)  # Enforce 25% domain cap
        
        # ========== CREDIBILITY FLOOR FILTERING ==========
        # Apply adaptive credibility floor based on supply conditions
        cards, num_filtered, retained = apply_adaptive_credibility_floor(
            cards, self.quality_config
        )
        if num_filtered > 0:
            logger.info(f"Adaptive credibility floor: filtered {num_filtered} low-cred sources, retained {retained}")
        
        # ========== RE-APPLY DOMAIN CAPS AFTER FILTERING ==========
        # Credibility filtering may have left domain imbalance - reapply caps
        unique_domains_after_filter = len(set(canonical_domain(c.source_domain) for c in cards))
        if cards:
            domain_counts = Counter(canonical_domain(c.source_domain) for c in cards)
            max_domain_share = max(domain_counts.values()) / len(cards)
            
            if max_domain_share > self.quality_config.domain_balance.cap_default:
                logger.info(f"Re-applying domain caps after filtering (max share: {max_domain_share:.2%})")
                cards, _, _ = apply_adaptive_domain_balance(
                    cards, self.quality_config, unique_domains_after_filter
                )
        
        # ========== ITERATIVE BACKFILL LOOP FOR QUALITY GATES ==========
        # Recompute triangulation on balanced cards for quality assessment
        para_clusters_final = cluster_paraphrases(cards)
        para_clusters_final = sanitize_paraphrase_clusters(para_clusters_final, cards)
        para_clusters_final = filter_contradictory_clusters(para_clusters_final)
        structured_matches_final = structured_triangles(cards)
        tri_union_final = union_rate(para_clusters_final, structured_matches_final, len(cards))
        
        # Calculate current metrics for quality gates
        current_metrics = {
            "cards": len(cards),
            "union_triangulation": tri_union_final,
            "primary_share": primary_share_in_union(cards, para_clusters_final, structured_matches_final,
                                                    primary_domains=pack_domains,
                                                    primary_patterns=pack_patterns),
            "quote_coverage": sum(1 for c in cards if (
                getattr(c, 'best_quote', None) or 
                getattr(c, 'quote_span', None) or 
                (getattr(c, 'quotes', None) and c.quotes) or
                getattr(c, 'supporting_text', None) or
                getattr(c, 'snippet', None)
            ))/max(1, len(cards))
        }
        
        # Check quality gates and backfill if needed
        backfill_attempts = 0
        max_attempts = getattr(settings, 'MAX_BACKFILL_ATTEMPTS', 3)
        min_cards = getattr(settings, 'MIN_EVIDENCE_CARDS', 24)
        
        while backfill_attempts < max_attempts:
            needs_backfill = False
            backfill_reason = []
            
            # Calculate time remaining for adaptive decisions
            import time
            elapsed = time.time() - self.start_time
            time_budget = getattr(self, 'time_budget', 120)
            time_left = max(0, time_budget - elapsed)
            time_remaining_pct = time_left / max(1, time_budget)
            
            # Check if we should attempt last-mile backfill
            if should_attempt_last_mile_backfill(
                current_metrics, self.quality_config,
                time_remaining_pct=time_remaining_pct,
                attempt_number=backfill_attempts
            ):
                needs_backfill = True
                backfill_reason.append("last-mile backfill (close to threshold)")
            
            # Check triangulation with adaptive threshold
            adaptive_tri_threshold = self.quality_config.triangulation.get_threshold(
                len(cards), unique_domains, self.context.get("intent")
            )
            if current_metrics["union_triangulation"] < adaptive_tri_threshold:
                needs_backfill = True
                backfill_reason.append(f"triangulation {current_metrics['union_triangulation']:.2%} < {adaptive_tri_threshold:.0%}")
            
            # Check minimum card count
            if current_metrics["cards"] < min_cards:
                needs_backfill = True
                backfill_reason.append(f"cards {current_metrics['cards']} < {min_cards}")
            
            # Check primary share (for some topics)
            discipline = getattr(self, 'discipline', Discipline.GENERAL)
            if discipline in [Discipline.FINANCE_ECON, Discipline.MEDICINE, Discipline.CLIMATE_ENV]:
                if current_metrics["primary_share"] < 0.30:
                    needs_backfill = True
                    backfill_reason.append(f"primary share {current_metrics['primary_share']:.2%} < 30%")
            
            if not needs_backfill:
                logger.info(f"Quality gates passed after {backfill_attempts} backfill attempts")
                break
            
            backfill_attempts += 1
            logger.info(f"Backfill attempt {backfill_attempts}/{max_attempts}: {', '.join(backfill_reason)}")
            
            # Generate targeted backfill queries using related topics axes
            from research_system.tools.related_topics_axes import generate_backfill_queries
            
            backfill_queries = generate_backfill_queries(
                topic_key=route_topic(self.s.topic),
                user_query=self.s.topic,
                metrics=current_metrics,
                max_queries=6
            )
            
            if not backfill_queries:
                logger.warning("No backfill queries generated, exiting loop")
                break
            
            # Execute backfill queries
            new_cards = []
            for purpose, query in backfill_queries:
                try:
                    logger.debug(f"Executing backfill query ({purpose}): {query}")
                    
                    # Use reranking for better precision
                    backfill_results = asyncio.run(
                        parallel_provider_search(
                            registry,
                            query=query,
                            count=4,
                            freshness=settings.FRESHNESS_WINDOW,
                            region="US"
                        )
                    )
                    
                    # Process results with reranking if available
                    for provider, hits in backfill_results.items():
                        # Apply reranking to improve relevance
                        if getattr(settings, 'USE_LLM_RERANK', False):
                            from research_system.rankers.cross_encoder import rerank
                            hits = rerank(self.s.topic, hits, topk=3, use_llm=False)
                        
                        for h in hits[:3]:  # Take top 3 after reranking
                            domain = domain_of(h.url)
                            
                            # Skip if already have too many from this domain
                            existing_from_domain = sum(1 for c in cards if c.source_domain == canonical_domain(domain))
                            if existing_from_domain >= 6:
                                continue
                            
                            pol = getattr(self, "policy", POLICIES[route_topic(self.s.topic)])
                            credibility = pol.domain_priors.get(domain, 0.5)
                            
                            new_cards.append(EvidenceCard(
                                id=str(uuid.uuid4()),
                                title=h.title,
                                url=h.url,
                                snippet=h.snippet or "",
                                provider=provider,
                                date=h.date,
                                credibility_score=credibility,
                                relevance_score=0.7,
                                confidence=credibility * 0.7,
                                is_primary_source=is_primary_domain(domain),
                                search_provider=provider,
                                source_domain=canonical_domain(domain),
                                collected_at=datetime.now(timezone.utc).isoformat(),
                                backfill_reason=purpose
                            ))
                except Exception as e:
                    logger.warning(f"Backfill query failed ({purpose}): {e}")
                    continue
            
            if not new_cards:
                logger.warning("No new cards from backfill, exiting loop")
                break
            
            logger.info(f"Added {len(new_cards)} cards from backfill")
            
            # Merge new cards with existing
            cards = self._dedup(cards + new_cards)
            
            # Re-apply domain cap to maintain balance
            cards = enforce_domain_cap(cards, cap=0.25)
            
            # Recompute metrics for next iteration
            para_clusters_final = cluster_paraphrases(cards)
            para_clusters_final = sanitize_paraphrase_clusters(para_clusters_final, cards)
            para_clusters_final = filter_contradictory_clusters(para_clusters_final)
            structured_matches_final = structured_triangles(cards)
            tri_union_final = union_rate(para_clusters_final, structured_matches_final, len(cards))
            
            current_metrics = {
                "cards": len(cards),
                "union_triangulation": tri_union_final,
                "primary_share": primary_share_in_union(cards, para_clusters_final, structured_matches_final,
                                                    primary_domains=pack_domains,
                                                    primary_patterns=pack_patterns),
                "quote_coverage": sum(1 for c in cards if (
                getattr(c, 'best_quote', None) or 
                getattr(c, 'quote_span', None) or 
                (getattr(c, 'quotes', None) and c.quotes) or
                getattr(c, 'supporting_text', None) or
                getattr(c, 'snippet', None)
            ))/max(1, len(cards))
            }
        
        # Store final triangulation for report generation
        para_clusters = para_clusters_final
        structured_matches = structured_matches_final
        tri_union = tri_union_final
        primary_share = current_metrics["primary_share"]
        
        # ===== v8.13.0 INTEGRATION POINT =====
        # Apply v8.13.0 improvements before final metrics calculation
        
        # 1. Canonicalize and deduplicate evidence
        logger.info(f"Before v8.13.0 canonicalization: {len(cards)} cards")
        cards = dedup_by_canonical(cards)
        logger.info(f"After v8.13.0 canonicalization: {len(cards)} cards")
        
        # 2. Mark primary sources using v8.13.0 scholarly tiers
        for card in cards:
            mark_primary(card)
        
        # 3. Filter by intent requirements
        intent = self.context.get("intent", "generic")
        jurisdiction = detect_jurisdiction_from_query(self.s.topic)
        cards = filter_for_intent(cards, intent, self.s.topic)
        logger.info(f"After v8.13.0 intent filtering for {intent}: {len(cards)} cards")
        
        # 4. Compute v8.13.0 unified metrics once
        final_metrics = compute_metrics(
            cards=cards,
            clusters=paraphrase_cluster_sets if 'paraphrase_cluster_sets' in locals() else [],
            provider_errors=self.provider_errors,
            provider_attempts=self.provider_attempts
        )
        
        # 5. Write v8.13.0 metrics to file
        write_metrics(str(self.s.output_dir), final_metrics)
        
        # 6. Check v8.13.0 quality gates (HARD GATE)
        cfg = self.v813_config
        gates_passed = gates_pass(final_metrics, intent)
        
        logger.info(
            "v8.13.0 Final metrics: primary_share=%.3f (floor=%.2f), triangulation=%.3f (floor=%.2f), domain_concentration=%.3f (cap=%.2f)",
            final_metrics.primary_share, cfg.primary_share_floor,
            final_metrics.triangulation_rate, cfg.triangulation_floor,
            final_metrics.domain_concentration, cfg.domain_concentration_cap
        )
        
        if not gates_passed:
            # HARD GATE: Stop here, only write insufficient evidence report
            failure_msg = format_gate_failure_message(final_metrics, intent)
            logger.warning(f"v8.13.0 Quality gates failed: {failure_msg}")
            
            write_insufficient_evidence_report(
                output_dir=str(self.s.output_dir),
                metrics=final_metrics,
                intent=intent,
                errors=[failure_msg]
            )
            
            # CRITICAL: Return early - do NOT generate final report
            logger.info("v8.13.0 Exiting early due to quality gate failure")
            return
        
        # Gates passed - continue to final report generation
        logger.info("v8.13.0 Quality gates passed, generating final report")
        
        # ===== LEGACY METRICS (for backward compatibility) =====
        # FINAL METRICS CALCULATION - Single source of truth after ALL processing
        N_final = len(cards)
        dom_ct_final = Counter(canonical_domain(c.source_domain) for c in cards)
        top_share_final = (dom_ct_final.most_common(1)[0][1]/N_final) if N_final and dom_ct_final else 0.0
        
        # Recalculate provider entropy on final set
        prov_ct_final = Counter(getattr(c, "provider", None) for c in cards if getattr(c, "provider", None))
        H_final = -sum((n/N_final)*math.log((n/N_final)+1e-12) for n in prov_ct_final.values()) if N_final and prov_ct_final else 0.0
        H_norm_final = H_final / math.log(max(1, len(prov_ct_final))) if prov_ct_final else 0.0
        
        # Write evidence cards FIRST; skip invalid ones instead of crashing
        ok, bad = write_jsonl(
            str(self.s.output_dir / "evidence_cards.jsonl"),
            cards,
            skip_invalid=True,
            errors_path=str(self.s.output_dir / "evidence_cards.errors.jsonl")
        )
        logger.info(f"Evidence write: ok={ok} bad={bad}")
        
        # Trim in-memory set to match what was actually written
        if bad:
            from research_system.tools.evidence_io import read_jsonl
            cards = read_jsonl(str(self.s.output_dir / "evidence_cards.jsonl"))
            logger.info(f"Trimmed cards from {N_final} to {len(cards)} after filtering invalid")
            
            # Recalculate metrics with actual valid cards
            N_final = len(cards)
            prov_ct_final = Counter(getattr(c, "provider", None) for c in cards if getattr(c, "provider", None))
            H_final = -sum((n/N_final)*math.log((n/N_final)+1e-12) for n in prov_ct_final.values()) if N_final and prov_ct_final else 0.0
            H_norm_final = H_final / math.log(max(1, len(prov_ct_final))) if prov_ct_final else 0.0
            dom_final = Counter(c.source_domain for c in cards)
            top_share_final = max(dom_final.values()) / max(1, N_final) if dom_final else 0.0
        
        # Calculate metrics with ACTUAL written cards (after filtering)
        metrics = {
            "cards": len(cards),  # Use actual count after filtering
            "quote_coverage": sum(1 for c in cards if (
                getattr(c, 'best_quote', None) or 
                getattr(c, 'quote_span', None) or 
                (getattr(c, 'quotes', None) and c.quotes) or
                getattr(c, 'supporting_text', None) or
                getattr(c, 'snippet', None)
            ))/max(1, len(cards)),
            "union_triangulation": tri_union,
            "primary_share_in_union": primary_share,  # Use last calculated value
            "top_domain_share": top_share_final,
            "provider_entropy": H_norm_final
        }
        
        # Write metrics AFTER filtering
        self._write("metrics.json", json.dumps(metrics, indent=2))
        
        # Validate consistency between metrics and actual evidence
        evidence_count = len(cards)
        if metrics["cards"] != evidence_count:
            logger.error(f"CONSISTENCY ERROR: metrics shows {metrics['cards']} cards but have {evidence_count} in memory")
            # Fix the metrics to match reality
            metrics["cards"] = evidence_count
            self._write("metrics.json", json.dumps(metrics, indent=2))

        # CONSOLIDATE / QUALITY - derive from written JSONL
        evidence_path = self.s.output_dir / "evidence_cards.jsonl"
        quality_table = self._generate_quality_table_from_jsonl(evidence_path)
        self._write("source_quality_table.md", quality_table)

        # Choose adaptive report tier based on evidence quality
        import time
        elapsed = time.time() - self.start_time  # Use instance variable
        time_left = max(0, self.time_budget - elapsed)
        
        # Calculate metrics for tier selection
        triangulated_indices = set()
        for cl in para_clusters_final:
            if len(cl.get("domains", [])) >= 2:
                triangulated_indices.update(cl.get("indices", []))
        
        tier, report_confidence, max_tokens, tier_explanation = choose_report_tier(
            triangulated_cards=len(triangulated_indices),
            credible_cards=len([c for c in cards if (c.credibility_score or 0.5) >= 0.5]),
            primary_share=current_metrics.get("primary_share", 0.0),
            unique_domains=unique_domains,
            provider_error_rate=self.provider_errors / max(1, self.provider_attempts),
            depth=self.s.depth,
            time_budget_remaining_sec=time_left,
            config=self.report_config
        )
        
        logger.info(f"Selected report tier: {tier.value} (confidence: {report_confidence:.2f}, {tier_explanation})")
        
        # CRITICAL FIX: Check quality gates BEFORE generating report
        # Import quality gates
        from research_system.quality.gates import meets_minimum_bar, explain_bar, calculate_stats_metrics
        
        # Calculate stats-specific metrics if needed
        intent = self.context.get("intent", "generic")
        if intent == "stats":
            stats_metrics = calculate_stats_metrics(cards, paraphrase_cluster_sets)
            metrics.update(stats_metrics)
        
        # v8.15.0: Load metrics from disk for single source of truth
        metrics_path = self.s.output_dir / "metrics.json"
        metrics_obj = Metrics.from_file(metrics_path)
        
        # Determine quality gate thresholds based on config
        cfg = getattr(self, 'v813_config', None) or load_quality_config()
        min_triangulation = cfg.triangulation_floor if hasattr(cfg, 'triangulation_floor') else 0.50
        min_primary = cfg.primary_share_floor if hasattr(cfg, 'primary_share_floor') else 0.33
        min_cards = 25  # Can be made configurable
        
        # Check quality gates
        allow_final = metrics_obj.meets_gates(min_triangulation, min_primary, min_cards)
        gate_failures = metrics_obj.get_gate_failures(min_triangulation, min_primary, min_cards)
        
        # Track providers used during collection
        providers_used = list(set(
            card.provider for card in cards 
            if hasattr(card, 'provider') and card.provider
        ))
        
        # Create run context
        ctx = RunContext(
            outdir=Path(self.s.output_dir),
            query=self.s.topic,
            metrics=metrics_obj,
            allow_final_report=allow_final,
            reason_final_report_blocked="; ".join(gate_failures) if gate_failures else None,
            providers_used=providers_used,
            intent=intent.value if intent else "generic",
            depth=self.s.depth,
            strict=self.s.strict
        )
        
        # Log decision
        if allow_final:
            logger.info("Quality gates met -> generating final_report.md")
        else:
            logger.warning(
                "Quality gates not met -> generating insufficient_evidence_report.md (%s)",
                ctx.reason_final_report_blocked
            )
        
        # Keep legacy variables for backward compatibility
        should_generate_final_report = allow_final
        confidence_level = None
        adjustments = {}
        
        if not should_generate_final_report:
            gate_explanation = ctx.reason_final_report_blocked or "Quality gates not met"
            logger.warning(f"Quality gates not met for intent={intent}: {gate_explanation}")
        
        # Second check: Strict mode with adaptive guard
        if self.s.strict and should_generate_final_report:
            errs, confidence_level, adjustments = adaptive_strict_check(
                self.s.output_dir, self.quality_config
            )
            
            if errs and should_skip_strict_fail(errs, adjustments, confidence_level):
                # Strict checks relaxed due to supply constraints
                logger.warning(f"Strict checks relaxed due to supply constraints: {errs}")
                supply_ctx = SupplyContextData(
                    total_cards=len(cards),
                    unique_domains=unique_domains,
                    provider_attempts=self.provider_attempts,
                    provider_errors=self.provider_errors
                )
                self._write("WARNINGS.md", format_confidence_report(
                    confidence_level, adjustments, supply_ctx
                ))
            elif errs:
                should_generate_final_report = False
                self._write("GAPS_AND_RISKS.md", "# Gaps & Risks\n\n" + "\n".join(f"- {e}" for e in errs))
        
        # v8.15.0: Generate appropriate report based on quality gates
        if ctx.allow_final_report:
            # Quality gates passed - generate final report
            try:
                FinalReportWriter(ctx).write()
                logger.info("Generated final report")
                
                # Keep legacy adaptive report generation as fallback
                # (can be removed once new system is proven stable)
                if os.getenv('USE_LEGACY_REPORT', '').lower() == 'true':
                    # Calculate appendix: raw cards minus balanced cards
                    balanced_ids = {c.id for c in cards}
                    appendix_cards = [c for c in raw_cards if c.id not in balanced_ids]
                    
                    # Generate report with tier-specific configuration
                    report = self._generate_adaptive_report(cards, appendix_cards, detector, tier, max_tokens)
                    
                    # Add adaptive metadata to report
                    combined_metrics = {**metrics, **current_metrics}
                    combined_metrics['total_cards'] = len(cards)
                    combined_metrics['credible_cards'] = len([c for c in cards if (c.credibility_score or 0.5) >= 0.5])
                    combined_metrics['triangulated_cards'] = len(triangulated_indices)
                    combined_metrics['unique_domains'] = unique_domains
                    combined_metrics['provider_error_rate'] = self.provider_errors / max(1, self.provider_attempts)
                    
                    metadata = generate_adaptive_report_metadata(
                        combined_metrics, confidence_level,
                        adjustments,
                        tier.value, report_confidence, tier_explanation
                    )
                    report = metadata + "\n\n---\n\n" + report
                    
                    self._write("final_report.md", report)
            except Exception as e:
                logger.error(f"Failed to generate final report: {e}")
                # Write error report
                error_msg = f"# Report Generation Failed\n\nError: {e!r}\n\nCards collected: {len(cards)}"
                (ctx.outdir / "final_report.md").write_text(error_msg)
        else:
            # Quality gates failed - generate insufficient evidence report
            InsufficientReportWriter(ctx).write()
            logger.info("Generated insufficient evidence report")
        
        # v8.15.0: Always generate source strategy
        SourceStrategyWriter(ctx).write()
        logger.info("Generated source strategy")
        
        error_file_path = self.s.output_dir / "evidence_cards.errors.jsonl"
        self._write("citation_checklist.md", self._generate_citation_checklist(cards, error_file_path))
        
        # Generate acceptance guardrails (even if no final report)
        if should_generate_final_report:
            guardrails_md = self._evaluate_guardrails(cards, self.s.output_dir / "final_report.md")
        else:
            guardrails_md = self._evaluate_guardrails(cards, None)
        self._write("acceptance_guardrails.md", guardrails_md)
        
        # OBSERVABILITY: Generate triangulation breakdown
        paraphrase_cluster_sets = [set(cl.get("indices", [])) for cl in para_clusters if len(cl.get("domains", [])) >= 2]
        dedup_count = 0  # Will be calculated if dedup is performed
        breakdown = generate_triangulation_breakdown(
            cards, paraphrase_cluster_sets, structured_matches, contradictions, dedup_count
        )
        self._write("triangulation_breakdown.md", breakdown)
        
        # Final check: Raise exception if quality gates not met
        if not should_generate_final_report:
            if self.s.strict:
                raise RuntimeError("Strict mode quality gates not met - generated insufficient evidence report")
        
        # STRICT GUARDRAILS (additional checks for discipline policy)
        if should_generate_final_report and (getattr(settings, "STRICT", False) or self.s.strict):
            # Calculate rates with both paraphrase and structured triangulation
            # Use the already calculated union rate
            triangulation_rate = tri_union
            
            # Calculate individual rates for reporting
            paraphrase_triangulated = sum(len(cl.get("indices", [])) for cl in para_clusters if len(cl.get("domains", [])) >= 2)
            structured_triangulated = sum(len(m.get("indices", [])) for m in structured_matches if len(m.get("domains", [])) >= 2)
            
            paraphrase_rate = paraphrase_triangulated / max(1, len(cards))
            structured_rate = structured_triangulated / max(1, len(cards))
            
            dom_counts = {}
            for c in cards:
                dom_counts[c.source_domain] = dom_counts.get(c.source_domain, 0) + 1
            domain_concentration = max(dom_counts.values()) / max(1, len(cards))
            
            # Primary share: cards from primary domains
            pol = getattr(self, "policy", POLICIES[route_topic(self.s.topic)])
            primary = set(pol.domain_priors.keys())
            primary_cards = [c for c in cards if c.source_domain in primary]
            primary_share = len(primary_cards) / max(1, len(cards))
            
            # Reachability (ignore known paywalls like statista/e-unwto if we have alternative sources)
            reach = sum(getattr(c, "reachability", 1.0) for c in cards) / max(1, len(cards))
            
            # Exclude low-quality domains from top list in strict
            LOW_QL = {"freetour.com","travelandtourworld.com","btuai.ge","sevenstonesindonesia.com","moderncampground.com"}
            top_low = max((dom_counts.get(d,0) for d in LOW_QL), default=0) / max(1,len(cards))
            
            # Generate detailed failure message
            thresholds = {
                "triangulation_min": pol.triangulation_min,
                "primary_share_min": pol.primary_share_min,
                "domain_concentration_max": 0.25,
                "reachability_min": getattr(pol, "reachability_min", 0.5),
                "low_quality_max": 0.10
            }
            
            failure_details = generate_strict_failure_details(
                triangulation_rate, structured_rate, paraphrase_rate,
                primary_share, domain_concentration, thresholds,
                reachability=reach, low_quality_share=top_low
            )
            
            # Check if any failures
            if "All checks passed" not in failure_details:
                (self.s.output_dir / "GAPS_AND_RISKS.md").write_text(
                    f"# Gaps & Risks\n\n{failure_details}\n\n" + breakdown,
                    encoding="utf-8"
                )
                
                # Check if we should degrade to report instead of hard exit
                if os.getenv("STRICT_DEGRADE_TO_REPORT", "true").lower() == "true":
                    # Generate insufficient evidence report with metrics
                    logger.warning(f"STRICT MODE: Degrading to insufficient evidence report (post-report)")
                    insufficient_report_path = self.s.output_dir / "insufficient_evidence_report.md"
                    insufficient_content = [
                        "# Insufficient Evidence Report",
                        "",
                        f"## Topic: {self.s.topic}",
                        "",
                        "## Quality Gate Failures",
                        "",
                        failure_details,
                        "",
                        "## Metrics Summary",
                        "",
                        f"- Triangulation Rate: {triangulation_rate:.1%} (target: {thresholds.get('triangulation', 0.35):.1%})",
                        f"- Primary Source Share: {primary_share:.1%} (target: {thresholds.get('primary_source', 0.40):.1%})",
                        f"- Domain Concentration: {domain_concentration:.1%} (max: {thresholds.get('domain_concentration', 0.30):.1%})",
                        f"- Evidence Cards: {len(cards)}",
                        "",
                        "## Next Steps",
                        "",
                        "1. Expand search parameters to find more sources",
                        "2. Wait for additional sources to become available",  
                        "3. Try different query formulations",
                        "4. Consider relaxing strict mode requirements",
                        "",
                        "Note: The main report has been generated but should be interpreted with caution."
                    ]
                    insufficient_report_path.write_text("\n".join(insufficient_content), encoding="utf-8")
                    # Raise a proper exception instead of sys.exit
                    raise RuntimeError(f"Strict mode post-report quality gates not met - see insufficient_evidence_report.md")
                else:
                    raise SystemExit(f"STRICT MODE FAIL: {failure_details}")

        # CONTRACT ENFORCEMENT
        missing = [n for n in SEVEN if not (self.s.output_dir/n).exists() or (self.s.output_dir/n).stat().st_size == 0]
        if missing and self.s.strict:
            raise RuntimeError(f"Missing/empty deliverables: {missing}")
        
        # Controversy enforcement in strict mode
        if self.s.strict and detector:
            controversial = detector.get_controversial_claims(threshold=0.3)
            for claim_id, cluster in controversial:
                supporting = [c for c in cluster if c.stance == "supports"]
                disputing = [c for c in cluster if c.stance == "disputes"]
                if detector.controversy_scores.get(claim_id, 0) >= 0.3:
                    if not supporting or not disputing:
                        raise RuntimeError(f"Controversial claim '{cluster[0].claim[:50]}...' missing balanced stances")
        
        # Write run manifest
        (self.s.output_dir / "run_manifest.json").write_text(json.dumps({
            "topic": self.s.topic,
            "discipline": getattr(self, "discipline", "general"),
            "providers": list(sorted({getattr(c,'provider','other') for c in cards})),
            "cards": len(cards),
            "strict": self.s.strict,
        }, indent=2), encoding="utf-8")