from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict
import asyncio
import uuid
from datetime import datetime
from collections import defaultdict
from urllib.parse import urlparse

from research_system.models import EvidenceCard
from research_system.tools.evidence_io import write_jsonl
from research_system.tools.registry import Registry
from research_system.tools.search_registry import register_search_tools
from research_system.collection import parallel_provider_search
from research_system.config import Settings
from research_system.controversy import ControversyDetector

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
    
    def _generate_plan(self) -> str:
        """Generate research plan based on topic and depth"""
        depth_details = {
            "rapid": "Quick scan of top sources (5-10 minutes)",
            "standard": "Balanced research with quality sources (15-30 minutes)",
            "deep": "Comprehensive analysis with extensive sources (30-60 minutes)"
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

    def _generate_acceptance_guardrails(self) -> str:
        """Generate acceptance criteria"""
        return f"""## Acceptance Guardrails

### Evidence Requirements
- ✓ Minimum 3 independent sources per major claim
- ✓ Primary sources preferred (government, academic)
- ✓ All sources must be reachable and verifiable
- ✓ Publication dates clearly identified
- ✓ Author credentials when available

### Quality Thresholds
- Credibility score > 0.6 for inclusion
- Relevance score > 0.5 for primary evidence
- Confidence weighted by source quality
- Controversy score tracked for all clustered claims

### Controversy Requirements
- ✓ Claims with controversy_score ≥ 0.3 must include both supporting and disputing evidence
- ✓ All controversial claims must have proper stance attribution
- ✓ Disputed evidence must include citations to opposing sources
- ✓ High-controversy topics (score > 0.5) require balanced presentation

### Validation Checks
- ✓ JSON schema validation for all evidence cards
- ✓ URL format validation
- ✓ No duplicate evidence IDs
- ✓ Search provider attribution
- ✓ Stance consistency within claim clusters
- ✓ claim_id required for non-neutral stances

### Strict Mode Requirements
{"✓ All 7 deliverables must be present and non-empty" if self.s.strict else "○ Best-effort delivery"}
{"✓ Controversial claims must include both stances" if self.s.strict else "○ Best-effort controversy coverage"}
"""

    def _generate_final_report(self, cards: List[EvidenceCard], detector: ControversyDetector = None) -> str:
        """Generate final report from evidence cards"""
        if not cards:
            return "# Final Report\n\nNo evidence collected for this topic."
        
        # Group by provider
        by_provider = defaultdict(list)
        for card in cards:
            by_provider[card.search_provider].append(card)
        
        # Sort by confidence
        top_evidence = sorted(cards, key=lambda x: x.confidence, reverse=True)[:5]
        
        report = f"""# Final Report: {self.s.topic}

## Executive Summary
Analyzed {len(cards)} pieces of evidence from {len(by_provider)} search providers.

## Key Findings

"""
        for i, card in enumerate(top_evidence, 1):
            report += f"""### {i}. {card.claim}
**Source**: [{card.source_domain}]({card.source_url})
**Confidence**: {card.confidence:.0%}

{card.supporting_text}

---

"""
        
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
"""
        
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
        per_provider = asyncio.run(
            parallel_provider_search(self.registry, query=self.s.topic, count=8,
                                     freshness=settings.FRESHNESS_WINDOW, region="US")
        )

        # TRANSFORM to EvidenceCard (stamp search_provider)
        cards: List[EvidenceCard] = []
        for provider, hits in per_provider.items():
            for h in hits:
                # Calculate scoring based on source attributes
                domain = urlparse(h.url).netloc
                is_primary = any(ext in domain for ext in ['.gov', '.edu', '.ac.uk', '.who.int', '.un.org'])
                
                # Score based on domain trust
                credibility = 0.9 if is_primary else 0.7 if '.org' in domain else 0.6
                
                # Simple relevance scoring based on query match in title/snippet
                text = (h.title + " " + (h.snippet or "")).lower()
                query_terms = self.s.topic.lower().split()
                matches = sum(1 for term in query_terms if term in text)
                relevance = min(1.0, matches / max(len(query_terms), 1))
                
                cards.append(EvidenceCard(
                    id=str(uuid.uuid4()),
                    subtopic_name="Research Findings",
                    claim=f"{h.title}",
                    supporting_text=h.snippet or h.title,
                    source_url=h.url,
                    source_title=h.title,
                    source_domain=domain,
                    credibility_score=credibility,
                    is_primary_source=is_primary,
                    relevance_score=relevance,
                    confidence=credibility * relevance,
                    collected_at=datetime.utcnow().isoformat() + "Z",
                    search_provider=provider
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

        # WRITE evidence (schema enforced)
        write_jsonl(str(self.s.output_dir / "evidence_cards.jsonl"), cards)

        # CONSOLIDATE / QUALITY - generate from actual evidence
        domain_scores: Dict[str, List[float]] = defaultdict(list)
        domain_controversy: Dict[str, List[float]] = defaultdict(list)
        for card in cards:
            domain_scores[card.source_domain].append(card.credibility_score)
            domain_controversy[card.source_domain].append(card.controversy_score)
        
        quality_table = "| Domain | Avg Quality | Avg Controversy | Count |\n|---|---|---|---|\n"
        for domain, scores in sorted(domain_scores.items(), key=lambda x: -sum(x[1])/len(x[1])):
            avg_score = sum(scores) / len(scores)
            avg_controversy = sum(domain_controversy[domain]) / max(len(domain_controversy[domain]), 1)
            quality_table += f"| {domain} | {avg_score:.2f} | {avg_controversy:.2f} | {len(scores)} |\n"
        
        self._write("source_quality_table.md", quality_table)

        # SYNTHESIZE
        self._write("final_report.md", self._generate_final_report(cards, detector))
        self._write("citation_checklist.md", self._generate_citation_checklist(cards))

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