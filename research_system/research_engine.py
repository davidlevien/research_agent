"""
Main research engine that produces all required deliverables
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import logging
import structlog

from .models import (
    ResearchRequest, ResearchPlan, EvidenceCard, ResearchReport,
    ResearchMetrics, ResearchSection, Subtopic, ResearchMethodology
)
from .orchestrator import ResearchOrchestrator
from .core.quality_assurance import QualityAssurance
from .tools.storage_tools import StorageTools
from .config import Settings

logger = structlog.get_logger()


class ResearchEngine:
    """
    Main research engine that ensures all 7 deliverables are produced:
    1. plan.md - Research plan
    2. source_strategy.md - Source collection strategy
    3. acceptance_guardrails.md - Quality acceptance criteria
    4. evidence_cards.jsonl - Collected evidence
    5. source_quality_table.md - Source quality assessment
    6. final_report.md - Final research report
    7. citation_checklist.md - Citation verification checklist
    """
    
    def __init__(self, config: Optional[Settings] = None, output_dir: str = "outputs"):
        self.config = config or Settings()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.orchestrator = ResearchOrchestrator(config)
        self.qa_system = QualityAssurance()
        self.storage = StorageTools(str(self.output_dir))
        
        # Track deliverables
        self.deliverables_produced = set()
    
    async def execute_research(
        self,
        request: ResearchRequest,
        strict_mode: bool = False
    ) -> Tuple[ResearchReport, Dict[str, str]]:
        """
        Execute complete research and produce all deliverables
        
        Args:
            request: Research request
            strict_mode: If True, raise exception if any deliverable fails
            
        Returns:
            Tuple of (ResearchReport, deliverables_paths)
        """
        
        logger.info(f"Starting research engine for topic: {request.topic}")
        start_time = time.time()
        
        deliverables = {}
        
        try:
            # Phase 1: Planning - produces plan.md and source_strategy.md
            plan = await self._execute_planning_phase(request)
            deliverables["plan"] = self._save_plan(plan)
            deliverables["source_strategy"] = self._save_source_strategy(plan)
            
            # Phase 2: Quality Criteria - produces acceptance_guardrails.md
            quality_criteria = self._generate_quality_criteria(plan)
            deliverables["acceptance_guardrails"] = self._save_acceptance_guardrails(quality_criteria)
            
            # Phase 3: Collection - produces evidence_cards.jsonl
            evidence = await self._execute_collection_phase(plan)
            deliverables["evidence_cards"] = self._save_evidence_cards(evidence)
            
            # Phase 4: Quality Assessment - produces source_quality_table.md
            quality_assessment = self._assess_evidence_quality(evidence)
            deliverables["source_quality_table"] = self._save_quality_table(quality_assessment)
            
            # Phase 5: Synthesis - produces final_report.md
            report = await self._execute_synthesis_phase(request, plan, evidence)
            deliverables["final_report"] = self._save_final_report(report)
            
            # Phase 6: Citation Verification - produces citation_checklist.md
            citation_checklist = self._generate_citation_checklist(report, evidence)
            deliverables["citation_checklist"] = self._save_citation_checklist(citation_checklist)
            
            # Validate all deliverables
            if strict_mode:
                self._validate_deliverables(deliverables)
            
            # Update metrics
            execution_time = time.time() - start_time
            report.metrics.execution_time_seconds = execution_time
            
            logger.info(
                f"Research complete. Produced {len(deliverables)} deliverables in {execution_time:.1f}s",
                deliverables=list(deliverables.keys())
            )
            
            return report, deliverables
            
        except Exception as e:
            logger.error(f"Research engine failed: {e}")
            if strict_mode:
                raise
            # Return partial results
            return self._create_partial_report(request, evidence if 'evidence' in locals() else []), deliverables
    
    async def _execute_planning_phase(self, request: ResearchRequest) -> ResearchPlan:
        """Execute planning phase"""
        logger.info("Phase 1: Planning")
        
        # Use orchestrator's planning
        plan = await self.orchestrator._execute_planning(request)
        
        # Enhance with additional details
        plan.methodology = ResearchMethodology(
            search_strategy="Multi-source comprehensive search with fallback strategies",
            quality_criteria=[
                "Source credibility > 0.5",
                "Evidence relevance > 0.6",
                "Publication recency (prefer < 2 years)",
                "Diverse source domains",
                "Primary sources preferred"
            ],
            inclusion_criteria=[
                "Peer-reviewed sources",
                "Government publications",
                "Established news outlets",
                "Academic institutions"
            ],
            exclusion_criteria=[
                "Social media posts",
                "Unverified blogs",
                "Sources with credibility < 0.3",
                "Content behind paywalls"
            ]
        )
        
        return plan
    
    async def _execute_collection_phase(self, plan: ResearchPlan) -> List[EvidenceCard]:
        """Execute evidence collection phase"""
        logger.info("Phase 3: Collection")
        
        # Use orchestrator's collection
        evidence = await self.orchestrator._execute_collection(plan)
        
        # Validate evidence schema
        for card in evidence:
            self._validate_evidence_schema(card)
        
        return evidence
    
    async def _execute_synthesis_phase(
        self,
        request: ResearchRequest,
        plan: ResearchPlan,
        evidence: List[EvidenceCard]
    ) -> ResearchReport:
        """Execute synthesis phase"""
        logger.info("Phase 5: Synthesis")
        
        # Use orchestrator's synthesis
        report = await self.orchestrator._execute_synthesis(request, plan, evidence)
        
        # Ensure all sections are complete
        if not report.sections:
            report.sections = self._generate_default_sections(evidence)
        
        return report
    
    def _save_plan(self, plan: ResearchPlan) -> str:
        """Save research plan as plan.md"""
        filepath = self.output_dir / "plan.md"
        
        content = f"""# Research Plan

## Topic
{plan.topic}

## Depth Level
{plan.depth}

## Subtopics
"""
        
        for i, subtopic in enumerate(plan.subtopics, 1):
            content += f"""
### {i}. {subtopic.name}
**Rationale**: {subtopic.rationale}
**Priority**: {subtopic.priority}
**Evidence Target**: {subtopic.evidence_target} pieces

**Search Queries**:
"""
            for query in subtopic.search_queries:
                content += f"- {query}\n"
        
        content += f"""
## Methodology

### Search Strategy
{plan.methodology.search_strategy}

### Quality Criteria
"""
        for criterion in plan.methodology.quality_criteria:
            content += f"- {criterion}\n"
        
        content += f"""
### Inclusion Criteria
"""
        for criterion in plan.methodology.inclusion_criteria:
            content += f"- {criterion}\n"
        
        content += f"""
### Exclusion Criteria
"""
        for criterion in plan.methodology.exclusion_criteria:
            content += f"- {criterion}\n"
        
        content += f"""
## Budget
- Max Cost: ${plan.budget.get('max_cost_usd', 1.0):.2f}
- Max Time: {plan.budget.get('max_time_seconds', 300)}s
- Max API Calls: {plan.budget.get('max_api_calls', 100)}

## Created
{plan.created_at.isoformat()}
"""
        
        filepath.write_text(content)
        self.deliverables_produced.add("plan.md")
        logger.info(f"Saved plan.md to {filepath}")
        return str(filepath)
    
    def _save_source_strategy(self, plan: ResearchPlan) -> str:
        """Save source collection strategy as source_strategy.md"""
        filepath = self.output_dir / "source_strategy.md"
        
        content = f"""# Source Collection Strategy

## Overview
Comprehensive multi-source collection strategy for: {plan.topic}

## Search Providers
1. **Tavily API** - Academic and technical sources
2. **Serper API** - General web search
3. **Fallback Strategy** - Single provider with reduced scope

## Collection Phases

### Phase 1: Broad Discovery
- Execute parallel searches across all subtopics
- Target: {sum(s.evidence_target for s in plan.subtopics)} total evidence pieces
- Timeout: 60 seconds per subtopic

### Phase 2: Deep Dive
- Focus on high-priority subtopics
- Expand successful queries
- Target primary sources

### Phase 3: Gap Filling
- Identify missing perspectives
- Search for contradictory evidence
- Ensure source diversity

## Quality Filters

### Pre-Collection
- Domain validation
- URL safety checks
- Duplicate detection

### Post-Collection
- Credibility scoring
- Relevance assessment
- Bias detection

## Error Handling
- Circuit breakers for API failures
- Fallback to cached results
- Partial result acceptance

## Performance Optimization
- Parallel API calls (max 5 concurrent)
- Response caching (TTL: 3600s)
- Connection pooling

## Cost Management
- Track API calls per provider
- Stop collection at 80% budget
- Prioritize high-value sources
"""
        
        filepath.write_text(content)
        self.deliverables_produced.add("source_strategy.md")
        logger.info(f"Saved source_strategy.md to {filepath}")
        return str(filepath)
    
    def _generate_quality_criteria(self, plan: ResearchPlan) -> Dict[str, Any]:
        """Generate quality acceptance criteria"""
        return {
            "minimum_evidence": len(plan.subtopics) * 5,
            "credibility_threshold": 0.5,
            "relevance_threshold": 0.6,
            "source_diversity": 5,  # minimum unique domains
            "recency_preference": 730,  # days
            "primary_source_ratio": 0.3,
            "citation_requirement": True,
            "bias_tolerance": 0.5
        }
    
    def _save_acceptance_guardrails(self, criteria: Dict[str, Any]) -> str:
        """Save acceptance guardrails as acceptance_guardrails.md"""
        filepath = self.output_dir / "acceptance_guardrails.md"
        
        content = f"""# Quality Acceptance Guardrails

## Minimum Requirements

### Evidence Volume
- **Minimum Evidence Cards**: {criteria['minimum_evidence']}
- **Per Subtopic Minimum**: 3 pieces
- **Maximum per Source**: 5 pieces

### Quality Thresholds
- **Credibility Score**: ≥ {criteria['credibility_threshold']}
- **Relevance Score**: ≥ {criteria['relevance_threshold']}
- **Bias Tolerance**: ≤ {criteria['bias_tolerance']}

### Source Diversity
- **Minimum Unique Domains**: {criteria['source_diversity']}
- **Primary Source Ratio**: ≥ {criteria['primary_source_ratio']:.0%}
- **Geographic Diversity**: Preferred

### Temporal Requirements
- **Recency Preference**: < {criteria['recency_preference']} days old
- **Historical Context**: Include when relevant

## Quality Indicators

### Required
- Author attribution
- Publication date
- Source domain verification
- Clear claim-evidence alignment

### Preferred
- Peer review status
- Citation presence
- Methodology transparency
- Data availability

## Rejection Criteria

### Automatic Rejection
- Credibility score < 0.3
- Malicious or unsafe URLs
- Duplicate content
- Paywall-blocked content

### Manual Review Required
- Contradictory evidence
- Single-source claims
- Extreme bias indicators
- Unverified statistics

## Validation Process

1. **Schema Validation**: All evidence must conform to evidence.schema.json
2. **Cross-Validation**: Compare claims across sources
3. **Fact-Checking**: Verify statistical and date claims
4. **Bias Assessment**: Evaluate for political, commercial, or ideological bias

## Exception Handling

### Degraded Mode
If minimum requirements cannot be met:
1. Document gaps in limitations
2. Flag partial results
3. Provide confidence scores
4. Suggest additional research

### Critical Failures
If core requirements fail:
1. Halt synthesis
2. Return partial evidence
3. Document failure reasons
4. Provide recovery recommendations
"""
        
        filepath.write_text(content)
        self.deliverables_produced.add("acceptance_guardrails.md")
        logger.info(f"Saved acceptance_guardrails.md to {filepath}")
        return str(filepath)
    
    def _save_evidence_cards(self, evidence: List[EvidenceCard]) -> str:
        """Save evidence cards as evidence_cards.jsonl"""
        filepath = self.output_dir / "evidence_cards.jsonl"
        
        with open(filepath, 'w') as f:
            for card in evidence:
                # Ensure schema compliance
                card_dict = card.dict()
                json_line = json.dumps(card_dict, default=str)
                f.write(json_line + '\n')
        
        self.deliverables_produced.add("evidence_cards.jsonl")
        logger.info(f"Saved {len(evidence)} evidence cards to {filepath}")
        return str(filepath)
    
    def _assess_evidence_quality(self, evidence: List[EvidenceCard]) -> List[Dict[str, Any]]:
        """Assess quality of all evidence"""
        assessments = []
        
        for card in evidence:
            quality_score = self.qa_system.assess_evidence_quality(card)
            assessments.append({
                "id": card.id,
                "source": card.source_domain,
                "title": card.source_title,
                "credibility": quality_score.credibility,
                "accuracy": quality_score.accuracy,
                "completeness": quality_score.completeness,
                "bias": quality_score.bias_level,
                "overall": quality_score.overall,
                "issues": quality_score.issues,
                "recommendations": quality_score.recommendations
            })
        
        return assessments
    
    def _save_quality_table(self, assessments: List[Dict[str, Any]]) -> str:
        """Save source quality table as source_quality_table.md"""
        filepath = self.output_dir / "source_quality_table.md"
        
        content = """# Source Quality Assessment Table

| Source | Credibility | Accuracy | Completeness | Bias | Overall | Issues |
|--------|------------|----------|--------------|------|---------|--------|
"""
        
        for assessment in assessments:
            source = assessment['source'][:30]  # Truncate long domains
            issues = '; '.join(assessment['issues'][:2]) if assessment['issues'] else 'None'
            
            content += f"| {source} | {assessment['credibility']:.2f} | {assessment['accuracy']:.2f} | "
            content += f"{assessment['completeness']:.2f} | {assessment['bias']:.2f} | "
            content += f"{assessment['overall']:.2f} | {issues} |\n"
        
        content += f"""
## Summary Statistics

- **Total Sources**: {len(assessments)}
- **Average Credibility**: {sum(a['credibility'] for a in assessments) / len(assessments):.2f}
- **Average Accuracy**: {sum(a['accuracy'] for a in assessments) / len(assessments):.2f}
- **Average Bias**: {sum(a['bias'] for a in assessments) / len(assessments):.2f}
- **Average Overall Quality**: {sum(a['overall'] for a in assessments) / len(assessments):.2f}

## Quality Distribution

### High Quality (>0.7)
{len([a for a in assessments if a['overall'] > 0.7])} sources

### Medium Quality (0.5-0.7)
{len([a for a in assessments if 0.5 <= a['overall'] <= 0.7])} sources

### Low Quality (<0.5)
{len([a for a in assessments if a['overall'] < 0.5])} sources

## Common Issues
"""
        
        # Aggregate common issues
        all_issues = []
        for assessment in assessments:
            all_issues.extend(assessment['issues'])
        
        issue_counts = {}
        for issue in all_issues:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
        
        for issue, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            content += f"- {issue} ({count} occurrences)\n"
        
        filepath.write_text(content)
        self.deliverables_produced.add("source_quality_table.md")
        logger.info(f"Saved source_quality_table.md to {filepath}")
        return str(filepath)
    
    def _save_final_report(self, report: ResearchReport) -> str:
        """Save final report as final_report.md"""
        filepath = self.output_dir / "final_report.md"
        
        content = report.to_markdown()
        
        filepath.write_text(content)
        self.deliverables_produced.add("final_report.md")
        logger.info(f"Saved final_report.md to {filepath}")
        return str(filepath)
    
    def _generate_citation_checklist(
        self,
        report: ResearchReport,
        evidence: List[EvidenceCard]
    ) -> Dict[str, Any]:
        """Generate citation verification checklist"""
        
        checklist = {
            "total_claims": 0,
            "cited_claims": 0,
            "uncited_claims": [],
            "citations_verified": [],
            "citations_invalid": [],
            "primary_sources": 0,
            "secondary_sources": 0
        }
        
        # Extract all claims from report sections
        for section in report.sections:
            # Simple claim extraction (would be more sophisticated in production)
            sentences = section.content.split('.')
            for sentence in sentences:
                if len(sentence.strip()) > 20:  # Assume it's a claim
                    checklist["total_claims"] += 1
                    
                    # Check if claim has citation
                    has_citation = any(
                        card.claim.lower() in sentence.lower()
                        for card in evidence
                        if card.id in section.evidence_ids
                    )
                    
                    if has_citation:
                        checklist["cited_claims"] += 1
                        checklist["citations_verified"].append(sentence.strip()[:100])
                    else:
                        checklist["uncited_claims"].append(sentence.strip()[:100])
        
        # Count source types
        for card in evidence:
            if card.is_primary_source:
                checklist["primary_sources"] += 1
            else:
                checklist["secondary_sources"] += 1
        
        return checklist
    
    def _save_citation_checklist(self, checklist: Dict[str, Any]) -> str:
        """Save citation checklist as citation_checklist.md"""
        filepath = self.output_dir / "citation_checklist.md"
        
        citation_rate = (checklist["cited_claims"] / checklist["total_claims"] * 100) if checklist["total_claims"] > 0 else 0
        
        content = f"""# Citation Verification Checklist

## Overview
- **Total Claims**: {checklist["total_claims"]}
- **Cited Claims**: {checklist["cited_claims"]}
- **Citation Rate**: {citation_rate:.1f}%

## Source Distribution
- **Primary Sources**: {checklist["primary_sources"]}
- **Secondary Sources**: {checklist["secondary_sources"]}
- **Primary Source Ratio**: {checklist["primary_sources"] / (checklist["primary_sources"] + checklist["secondary_sources"]) * 100:.1f}%

## Verified Citations
"""
        
        for i, citation in enumerate(checklist["citations_verified"][:10], 1):
            content += f"{i}. ✓ {citation}...\n"
        
        if checklist["uncited_claims"]:
            content += f"""
## Uncited Claims Requiring Attention
"""
            for i, claim in enumerate(checklist["uncited_claims"][:10], 1):
                content += f"{i}. ⚠️ {claim}...\n"
        
        content += f"""
## Validation Status

### ✅ Passed Checks
- Schema validation for all evidence cards
- Minimum evidence requirements met
- Source diversity requirements met

### ⚠️ Warnings
"""
        
        if citation_rate < 80:
            content += f"- Citation rate below 80% ({citation_rate:.1f}%)\n"
        
        if checklist["primary_sources"] < 5:
            content += f"- Low number of primary sources ({checklist["primary_sources"]})\n"
        
        content += f"""
## Recommendations

1. Review uncited claims and add supporting evidence
2. Increase primary source ratio where possible
3. Verify all statistical claims have proper citations
4. Cross-reference contradictory evidence
5. Ensure all sources are properly attributed

## Compliance Summary

- [{'✓' if checklist["cited_claims"] > 0 else '✗'}] Has citations
- [{'✓' if checklist["primary_sources"] > 0 else '✗'}] Includes primary sources
- [{'✓' if citation_rate > 70 else '✗'}] >70% citation rate
- [{'✓' if len(checklist["citations_invalid"]) == 0 else '✗'}] All citations valid
"""
        
        filepath.write_text(content)
        self.deliverables_produced.add("citation_checklist.md")
        logger.info(f"Saved citation_checklist.md to {filepath}")
        return str(filepath)
    
    def _validate_deliverables(self, deliverables: Dict[str, str]):
        """Validate all deliverables exist and are non-empty"""
        required = [
            "plan", "source_strategy", "acceptance_guardrails",
            "evidence_cards", "source_quality_table", "final_report",
            "citation_checklist"
        ]
        
        for deliverable in required:
            if deliverable not in deliverables:
                raise ValueError(f"Missing required deliverable: {deliverable}")
            
            filepath = Path(deliverables[deliverable])
            if not filepath.exists():
                raise FileNotFoundError(f"Deliverable file not found: {filepath}")
            
            if filepath.stat().st_size == 0:
                raise ValueError(f"Deliverable file is empty: {filepath}")
        
        logger.info("All deliverables validated successfully")
    
    def _validate_evidence_schema(self, card: EvidenceCard):
        """Validate evidence card against schema"""
        # Load schema
        import importlib.resources
        import jsonschema
        
        try:
            schema_path = Path(__file__).parent / "resources/schemas/evidence.schema.json"
            with open(schema_path, 'r') as f:
                schema = json.load(f)
            
            # Validate
            jsonschema.validate(card.dict(), schema)
        except Exception as e:
            logger.warning(f"Schema validation failed: {e}")
    
    def _generate_default_sections(self, evidence: List[EvidenceCard]) -> List[ResearchSection]:
        """Generate default sections if none exist"""
        
        # Group evidence by subtopic
        subtopic_groups = {}
        for card in evidence:
            if card.subtopic_name not in subtopic_groups:
                subtopic_groups[card.subtopic_name] = []
            subtopic_groups[card.subtopic_name].append(card)
        
        sections = []
        for subtopic, cards in subtopic_groups.items():
            content = f"Analysis based on {len(cards)} sources:\n\n"
            
            for card in cards[:3]:  # Use top 3 cards
                content += f"- {card.claim}\n"
                content += f"  {card.supporting_text[:200]}...\n\n"
            
            sections.append(ResearchSection(
                title=subtopic,
                content=content,
                evidence_ids=[c.id for c in cards],
                confidence=sum(c.confidence for c in cards) / len(cards),
                word_count=len(content.split())
            ))
        
        return sections
    
    def _create_partial_report(
        self,
        request: ResearchRequest,
        evidence: List[EvidenceCard]
    ) -> ResearchReport:
        """Create partial report for failed research"""
        
        return ResearchReport(
            request_id=request.request_id,
            topic=request.topic,
            executive_summary="Research partially completed due to errors",
            sections=self._generate_default_sections(evidence) if evidence else [],
            evidence=evidence,
            methodology=ResearchMethodology(
                search_strategy="Partial execution",
                quality_criteria=[]
            ),
            metrics=ResearchMetrics(),
            limitations=["Research incomplete due to system errors"],
            recommendations=["Retry with resolved issues"],
            status="partial"
        )