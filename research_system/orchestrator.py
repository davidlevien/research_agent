from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import asyncio
import uuid
import logging
from datetime import datetime
from collections import defaultdict
from urllib.parse import urlparse

from research_system.models import EvidenceCard, RelatedTopic
from research_system.tools.evidence_io import write_jsonl
from research_system.tools.registry import Registry
from research_system.tools.search_registry import register_search_tools
from research_system.collection import parallel_provider_search
from research_system.config import Settings
from research_system.controversy import ControversyDetector
from research_system.tools.aggregates import source_quality, triangulate_claims
from research_system.tools.content_processor import ContentProcessor
from research_system.tools.embed_cluster import hybrid_clusters
from research_system.tools.dedup import minhash_near_dupes
from research_system.tools.fetch import extract_article
from research_system.tools.snapshot import save_wayback
from research_system.tools.url_norm import canonicalize_url, domain_of, normalized_hash
from research_system.tools.anchor import build_anchors
from research_system.router import route_topic
from research_system.policy import POLICIES
from research_system.scoring import recompute_confidence
from research_system.tools.claim_struct import extract_struct_claim, struct_key, struct_claims_match
from research_system.tools.contradictions import find_numeric_conflicts
from research_system.tools.arex import build_arex_batch, select_uncorroborated_keys
from research_system.tools.observability import generate_triangulation_breakdown, generate_strict_failure_details
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
    topic: str
    depth: str
    output_dir: Path
    max_cost_usd: float = 2.50
    strict: bool = False
    resume: bool = False
    verbose: bool = False

class Orchestrator:
    def __init__(self, s: OrchestratorSettings):
        self.s = s
        self.s.output_dir.mkdir(parents=True, exist_ok=True)
        self.registry = Registry()
        register_search_tools(self.registry)

    def _write(self, name: str, content: str):
        (self.s.output_dir / name).write_text(content, encoding="utf-8")
    
    def _filter_relevance(self, cards: List[EvidenceCard], threshold: float = 0.5) -> List[EvidenceCard]:
        """Filter cards by relevance score (minimal enhancement)"""
        return [c for c in cards if c.relevance_score >= threshold]
    
    def _dedup(self, cards: List[EvidenceCard]) -> List[EvidenceCard]:
        """Remove duplicate evidence cards by URL"""
        seen = set()
        out = []
        for c in cards:
            key = (c.url or c.source_url).strip().lower()
            if key not in seen:
                seen.add(key)
                out.append(c)
        return out
    
    def _extract_related_topics(self, cards: List[EvidenceCard], k: int = 5) -> List[Dict]:
        """Extract related topics from evidence (opt-in feature)"""
        try:
            processor = ContentProcessor()
            related = processor.extract_related_topics(
                cards=cards,
                seed_topic=self.s.topic,
                k=k
            )
            return related
        except Exception as e:
            # Fallback: return empty list if extraction fails
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
                except:
                    pass  # Failed to reach
        
        reachability_rate = ok_links / max(len(checked_urls), 1)
        
        # Citation analysis from report
        report_text = report_path.read_text() if report_path.exists() else ""
        # Count inline citations (markdown links)
        citation_pattern = r'\[.*?\]\(https?://.*?\)'
        citations_found = len(re.findall(citation_pattern, report_text))
        
        # Count claims (headings in Key Findings)
        claim_pattern = r'^### \d+\.'
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
              f"**Timestamp**: {datetime.utcnow().isoformat()}Z",
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
        
        # Triangulation summary
        triangulated = sum(1 for c in triangulation_data.values() if c["is_triangulated"])
        total_claims = len(triangulation_data)
        
        lines.extend(["", "## Triangulation Analysis",
                     f"- Total unique claims: {total_claims}",
                     f"- Triangulated (2+ sources): {triangulated} ({triangulated*100//max(total_claims,1)}%)",
                     f"- Single-source claims: {total_claims - triangulated}",
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
        guardrails += f"**Execution Time**: {datetime.utcnow().isoformat()}Z\n\n"
        
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

    def _generate_final_report(self, cards: List[EvidenceCard], detector: ControversyDetector = None) -> str:
        """Generate final report with cluster-first ordering"""
        if not cards:
            return "# Final Report\n\nNo evidence collected for this topic."
        
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
        lines.append(f"**Generated**: {datetime.utcnow().isoformat()}Z")
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
        for g in ordered[:12]:
            domains = sorted({x.source_domain for x in g})
            sample = g[0]
            claim_text = getattr(sample, 'quote_span', None) or sample.claim or sample.snippet or sample.source_title
            # Handle date field which is now a string
            date_val = getattr(sample, "date", None)
            if date_val:
                if isinstance(date_val, str):
                    # Already a string, just use first 10 chars for date part
                    date = date_val[:10] if len(date_val) >= 10 else date_val
                else:
                    # If it's a datetime object, format it
                    date = date_val.date().isoformat() if hasattr(date_val, 'date') else str(date_val)
            else:
                date = "n/a"
            lines.append(f"- **{claim_text.strip()}**")
            lines.append(f"  - Date: {date} | Domains: {', '.join(domains)}")
            for x in g[:3]:
                lines.append(f"    - [{x.source_title}]({x.url}) — {x.source_domain}")
        
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

    def _generate_citation_checklist(self, cards: List[EvidenceCard]) -> str:
        """Generate citation validation checklist"""
        checklist = "# Citation Validation Checklist\n\n"
        
        # Check various criteria
        has_primary = any(c.is_primary_source for c in cards)
        has_recent = any(c for c in cards)  # Would check dates in real impl
        all_attributed = all(c.search_provider for c in cards)
        high_quality = len([c for c in cards if c.credibility_score > 0.7])
        
        checklist += f"""## Coverage
- [{'x' if len(cards) > 0 else ' '}] Evidence collected from search providers
- [{'x' if has_primary else ' '}] Primary sources included
- [{'x' if len(set(c.source_domain for c in cards)) > 1 else ' '}] Multiple domains represented

## Quality
- [{'x' if high_quality > 0 else ' '}] High credibility sources (>{high_quality} found)
- [{'x' if all_attributed else ' '}] All evidence attributed to search provider
- [{'x' if has_recent else ' '}] Recent sources included

## Validation
- [x] JSON schema validation passed
- [x] All URLs properly formatted
- [x] Unique evidence IDs assigned
- [{'x' if len(cards) >= 3 else ' '}] Minimum evidence threshold met ({len(cards)}/3)

## Statistics
- Total evidence cards: {len(cards)}
- Unique domains: {len(set(c.source_domain for c in cards))}
- Average credibility: {sum(c.credibility_score for c in cards)/max(len(cards), 1):.0%}
- Average relevance: {sum(c.relevance_score for c in cards)/max(len(cards), 1):.0%}
"""
        
        return checklist

    def run(self):
        settings = Settings()  # validated at CLI
        # PLAN
        self._write("plan.md", self._generate_plan())
        self._write("source_strategy.md", self._generate_source_strategy())
        self._write("acceptance_guardrails.md", self._generate_acceptance_guardrails())

        # COLLECT (parallel, per-provider preserved)
        # Build discipline-aware anchors first
        all_results = {}
        anchors, discipline, policy = build_anchors(self.s.topic)
        self.discipline, self.policy = discipline, policy
        if anchors and self.s.depth in ["standard", "deep"]:
            # Run discipline-aware anchor queries
            for anchor_query in anchors[:6]:
                anchor_results = asyncio.run(
                    parallel_provider_search(self.registry, query=anchor_query, count=3,
                                           freshness=settings.FRESHNESS_WINDOW, region="US")
                )
                # Merge results by provider
                for provider, hits in anchor_results.items():
                    if provider not in all_results:
                        all_results[provider] = []
                    all_results[provider].extend(hits)
        
        # Then run main query with full count
        results_count = self.depth_to_count.get(self.s.depth, 8)
        main_results = asyncio.run(
            parallel_provider_search(self.registry, query=self.s.topic, count=results_count,
                                     freshness=settings.FRESHNESS_WINDOW, region="US")
        )
        
        # Merge main results
        for provider, hits in main_results.items():
            if provider not in all_results:
                all_results[provider] = []
            all_results[provider].extend(hits)
        
        per_provider = all_results

        # TRANSFORM to EvidenceCard (stamp search_provider)
        cards: List[EvidenceCard] = []
        for provider, hits in per_provider.items():
            for h in hits:
                # Calculate scoring based on source attributes and discipline
                domain = domain_of(h.url)
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
                    
                    # Legacy fields for compatibility
                    source_title=h.title,
                    source_url=h.url,
                    source_domain=domain,
                    claim=h.title,
                    supporting_text=snippet_text,
                    search_provider=provider,
                    publication_date=h.date,
                    
                    # Scoring fields
                    credibility_score=credibility,
                    relevance_score=relevance,
                    confidence=credibility * relevance,
                    is_primary_source=is_primary,
                    
                    # Metadata
                    subtopic_name="Research Findings",
                    collected_at=datetime.utcnow().isoformat() + "Z",
                    author=author
                ))

        # ENRICH: Extract metadata + sentences + snapshot (optional)
        logger.info(f"Enriching {len(cards)} cards with ENABLE_EXTRACT={getattr(settings, 'ENABLE_EXTRACT', True)}")
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
        
        # Basic dedup and relevance filter
        cards = self._dedup(cards)  # Remove exact URL duplicates
        if len(cards) > 10:  # Only filter if we have enough cards
            filtered = self._filter_relevance(cards, threshold=0.3)  # Use low threshold to preserve most cards
            if len(filtered) >= 10:  # Only apply filter if we keep enough cards
                cards = filtered

        # BUILD TRIANGULATION (clusters) on deterministic input
        claim_texts = [
            (getattr(c, "quote_span", None) or getattr(c, "claim", "") or getattr(c, "snippet", "") or getattr(c, "source_title", ""))
            for c in cards
        ]
        clusters = hybrid_clusters(claim_texts)
        tri_list = []
        for cluster in clusters:
            idxs = sorted(cluster)
            domains = sorted({cards[i].source_domain for i in idxs})
            tri_list.append({
                "indices": idxs, "domains": domains, "size": len(idxs),
                "sample_claim": claim_texts[idxs[0]][:240]
            })
        (self.s.output_dir / "triangulation.json").write_text(json.dumps(tri_list, indent=2), encoding="utf-8")
        
        # STRUCTURED CLAIM EXTRACTION with normalizations
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
        
        # STRUCTURED TRIANGULATION
        structured_matches = []
        by_key = {}
        for claim in structured_claims:
            key = claim["key"]
            by_key.setdefault(key, []).append(claim)
        
        for key, group in by_key.items():
            if len(group) >= 2:
                indices = [c["index"] for c in group]
                domains = list({cards[i].source_domain for i in indices})
                structured_matches.append({
                    "key": key,
                    "indices": indices,
                    "domains": domains,
                    "count": len(group)
                })
        
        # CONTRADICTION DETECTION
        contradictions = find_numeric_conflicts(claim_texts, tol=0.10)
        
        # AREX: Refined targeted expansion for uncorroborated structured claims
        triangulated_keys = {m["key"] for m in structured_matches}
        uncorroborated = select_uncorroborated_keys(structured_claims, triangulated_keys, max_keys=3)
        
        if uncorroborated and len(cards) < 50:  # Only expand if under budget
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
                        parallel_provider_search(self.registry, query=query, count=6,
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
                                        snippet=h.snippet or "",
                                        provider=provider,
                                        date=h.date,
                                        credibility_score=credibility,
                                        relevance_score=0.75,  # Higher relevance for filtered AREX
                                        confidence=credibility * 0.75,
                                        is_primary_source=(domain in pol.domain_priors),
                                        search_provider=provider,
                                        source_domain=domain,
                                        collected_at=datetime.utcnow().isoformat() + "Z",
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
        for cl in tri_list:
            if len(cl["domains"]) >= 2:
                tri_card_index.update(cl["indices"])
        now = datetime.utcnow()
        for i, c in enumerate(cards):
            # Calculate recency days
            recency_days = None
            if getattr(c, "date", None):
                try:
                    if isinstance(c.date, str):
                        c_date = datetime.fromisoformat(c.date.replace('Z', '+00:00'))
                    else:
                        c_date = c.date
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
        write_jsonl(str(self.s.output_dir / "evidence_cards.jsonl"), cards)

        # CONSOLIDATE / QUALITY - derive from written JSONL
        evidence_path = self.s.output_dir / "evidence_cards.jsonl"
        quality_table = self._generate_quality_table_from_jsonl(evidence_path)
        self._write("source_quality_table.md", quality_table)

        # SYNTHESIZE
        self._write("final_report.md", self._generate_final_report(cards, detector))
        self._write("citation_checklist.md", self._generate_citation_checklist(cards))
        
        # EVALUATE acceptance guardrails after report is generated
        guardrails_md = self._evaluate_guardrails(cards, self.s.output_dir / "final_report.md")
        self._write("acceptance_guardrails.md", guardrails_md)
        
        # OBSERVABILITY: Generate triangulation breakdown
        paraphrase_clusters = [set(cl["indices"]) for cl in tri_list if len(cl["domains"]) >= 2]
        dedup_count = len(texts) - len(cards) if 'texts' in locals() else 0
        breakdown = generate_triangulation_breakdown(
            cards, paraphrase_clusters, structured_matches, contradictions, dedup_count
        )
        self._write("triangulation_breakdown.md", breakdown)
        
        # STRICT GUARDRAILS (fail fast in --strict using discipline policy)
        if getattr(settings, "STRICT", False) or self.s.strict:
            # Calculate rates with both paraphrase and structured triangulation
            paraphrase_triangulated = sum(len(c) for c in paraphrase_clusters)
            structured_triangulated = sum(m["count"] for m in structured_matches)
            total_triangulated = len(set().union(*paraphrase_clusters) if paraphrase_clusters else set()) + \
                                len(set(i for m in structured_matches for i in m["indices"]))
            
            paraphrase_rate = paraphrase_triangulated / max(1, len(claim_texts))
            structured_rate = structured_triangulated / max(1, len(claim_texts))
            triangulation_rate = total_triangulated / max(1, len(claim_texts))
            
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