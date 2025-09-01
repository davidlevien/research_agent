"""
LLM Synthesizer - PE-Grade Report Synthesis

Generates executive-grade synthesis from atomic claims with strict grounding.
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict, Counter

from research_system.llm.claims_schema import (
    AtomicClaim, ClaimSet, SynthesisSection, SynthesisBundle, SynthesisRequest
)
from research_system.models import EvidenceCard
from research_system.config.settings import Settings

logger = logging.getLogger(__name__)

class Synthesizer:
    """Generate synthesis from atomic claims"""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.llm_available = self._check_llm_availability()
        
    def _check_llm_availability(self) -> bool:
        """Check if LLM is configured and available"""
        if not getattr(self.settings, 'USE_LLM_SYNTH', False):
            return False
        
        if self.settings.LLM_PROVIDER == "openai" and self.settings.OPENAI_API_KEY:
            return True
        elif self.settings.LLM_PROVIDER == "anthropic" and self.settings.ANTHROPIC_API_KEY:
            return True
        
        return False
    
    def synthesize(
        self,
        claims: List[AtomicClaim],
        topic: str,
        use_llm: Optional[bool] = None,
        cards: Optional[List[EvidenceCard]] = None
    ) -> SynthesisBundle:
        """Generate synthesis from claims"""
        if use_llm is None:
            use_llm = self.llm_available
        
        if use_llm and self.llm_available:
            try:
                return self._synthesize_llm(claims, topic, cards)
            except Exception as e:
                logger.warning(f"LLM synthesis failed, falling back to rules: {e}")
                return self._synthesize_rules(claims, topic, cards)
        else:
            return self._synthesize_rules(claims, topic, cards)
    
    def _synthesize_rules(
        self,
        claims: List[AtomicClaim],
        topic: str,
        cards: Optional[List[EvidenceCard]] = None
    ) -> SynthesisBundle:
        """Generate synthesis using rules-based approach"""
        
        # Group claims by type and confidence
        grouped = self._group_claims(claims)
        
        # Generate executive summary
        executive_summary = self._generate_executive_summary_rules(claims, grouped)
        
        # Generate key numbers section
        key_numbers = self._generate_key_numbers_rules(claims, grouped)
        
        # Generate trends section
        trends = self._generate_trends_rules(claims, grouped)
        
        # Generate risks section
        risks = self._generate_risks_rules(claims, grouped)
        
        # Generate outlook section
        outlook = self._generate_outlook_rules(claims, grouped)
        
        # Identify contradictions
        contradictions = self._generate_contradictions_rules(claims)
        
        # Identify gaps
        gaps = self._generate_gaps_rules(claims, topic)
        
        return SynthesisBundle(
            executive_summary=executive_summary,
            key_numbers=key_numbers if key_numbers.bullets else None,
            trends=trends if trends.bullets else None,
            risks=risks if risks.bullets else None,
            outlook=outlook if outlook.bullets else None,
            contradictions=contradictions if contradictions.bullets else None,
            gaps=gaps if gaps.bullets else None,
            total_claims_used=len(claims)
        )
    
    def _synthesize_llm(
        self,
        claims: List[AtomicClaim],
        topic: str,
        cards: Optional[List[EvidenceCard]] = None
    ) -> SynthesisBundle:
        """Generate synthesis using LLM"""
        from research_system.llm.llm_client import LLMClient
        
        client = LLMClient(self.settings)
        
        # Prepare claims for LLM
        claims_data = []
        for claim in claims[:100]:  # Limit to prevent token overflow
            claims_data.append({
                "id": claim.id,
                "text": claim.normalized_text,
                "confidence": claim.confidence,
                "type": claim.claim_type,
                "support_count": len(claim.support_card_ids),
                "metrics": claim.metrics
            })
        
        # Create synthesis prompt
        prompt = self._create_synthesis_prompt(claims_data, topic)
        
        # Call LLM
        response = client.synthesize(prompt)
        
        # Parse and validate response
        synthesis = self._parse_llm_synthesis(response, claims)
        
        return synthesis
    
    def _group_claims(self, claims: List[AtomicClaim]) -> Dict[str, List[AtomicClaim]]:
        """Group claims by various criteria"""
        grouped = defaultdict(list)
        
        # By type
        for claim in claims:
            grouped[f"type_{claim.claim_type}"].append(claim)
        
        # By confidence level
        for claim in claims:
            if claim.confidence >= 0.8:
                grouped["high_confidence"].append(claim)
            elif claim.confidence >= 0.6:
                grouped["medium_confidence"].append(claim)
            else:
                grouped["low_confidence"].append(claim)
        
        # By support level
        for claim in claims:
            support_count = len(claim.support_card_ids)
            if support_count >= 3:
                grouped["strong_support"].append(claim)
            elif support_count >= 2:
                grouped["moderate_support"].append(claim)
            else:
                grouped["single_source"].append(claim)
        
        # Statistical claims
        for claim in claims:
            if claim.metrics:
                grouped["has_metrics"].append(claim)
        
        return dict(grouped)
    
    def _generate_executive_summary_rules(
        self,
        claims: List[AtomicClaim],
        grouped: Dict[str, List[AtomicClaim]]
    ) -> SynthesisSection:
        """Generate executive summary from claims"""
        bullets = []
        
        # Start with highest confidence, multi-source claims
        strong_claims = grouped.get("strong_support", [])
        strong_claims.sort(key=lambda c: c.confidence, reverse=True)
        
        # Add top factual claims
        for claim in strong_claims[:3]:
            bullets.append({
                "text": claim.normalized_text,
                "claim_ids": [claim.id],
                "confidence": claim.confidence
            })
        
        # Add key statistical claims
        statistical = grouped.get("type_statistical", [])
        statistical.sort(key=lambda c: (len(c.support_card_ids), c.confidence), reverse=True)
        
        for claim in statistical[:2]:
            if not any(claim.id in b["claim_ids"] for b in bullets):
                bullets.append({
                    "text": claim.normalized_text,
                    "claim_ids": [claim.id],
                    "confidence": claim.confidence
                })
        
        # Add important causal claims
        causal = grouped.get("type_causal", [])
        causal.sort(key=lambda c: c.confidence, reverse=True)
        
        for claim in causal[:2]:
            if not any(claim.id in b["claim_ids"] for b in bullets):
                bullets.append({
                    "text": claim.normalized_text,
                    "claim_ids": [claim.id],
                    "confidence": claim.confidence
                })
        
        # Limit to 7 bullets
        bullets = bullets[:7]
        
        # Calculate overall confidence
        avg_confidence = sum(b["confidence"] for b in bullets) / len(bullets) if bullets else 0
        
        return SynthesisSection(
            title="Executive Summary",
            bullets=bullets,
            confidence=avg_confidence
        )
    
    def _generate_key_numbers_rules(
        self,
        claims: List[AtomicClaim],
        grouped: Dict[str, List[AtomicClaim]]
    ) -> SynthesisSection:
        """Extract key numbers from claims"""
        bullets = []
        
        # Get claims with metrics
        metric_claims = grouped.get("has_metrics", [])
        metric_claims.sort(key=lambda c: (c.confidence, len(c.support_card_ids)), reverse=True)
        
        for claim in metric_claims[:5]:
            # Format with emphasis on numbers
            text = claim.normalized_text
            
            # Highlight percentages
            if "percentage" in claim.metrics:
                pct = claim.metrics["percentage"]
                text = f"{pct}% - {text}"
            elif "value_billions" in claim.metrics:
                val = claim.metrics["value_billions"]
                text = f"${val}B - {text}"
            elif "value_millions" in claim.metrics:
                val = claim.metrics["value_millions"]
                text = f"${val}M - {text}"
            
            bullets.append({
                "text": text,
                "claim_ids": [claim.id],
                "confidence": claim.confidence
            })
        
        avg_confidence = sum(b["confidence"] for b in bullets) / len(bullets) if bullets else 0
        
        return SynthesisSection(
            title="Key Numbers",
            bullets=bullets,
            confidence=avg_confidence
        )
    
    def _generate_trends_rules(
        self,
        claims: List[AtomicClaim],
        grouped: Dict[str, List[AtomicClaim]]
    ) -> SynthesisSection:
        """Identify trends from claims"""
        bullets = []
        
        # Look for comparative and temporal claims
        trend_claims = []
        
        # Comparative claims often indicate trends
        comparative = grouped.get("type_comparative", [])
        trend_claims.extend(comparative)
        
        # Look for growth/decline language
        for claim in claims:
            text_lower = claim.normalized_text.lower()
            if any(word in text_lower for word in [
                "increase", "decrease", "growth", "decline", "rise", "fall",
                "growing", "shrinking", "expanding", "contracting", "trend"
            ]):
                trend_claims.append(claim)
        
        # Deduplicate and sort
        seen_ids = set()
        unique_trends = []
        for claim in trend_claims:
            if claim.id not in seen_ids:
                seen_ids.add(claim.id)
                unique_trends.append(claim)
        
        unique_trends.sort(key=lambda c: (c.confidence, len(c.support_card_ids)), reverse=True)
        
        for claim in unique_trends[:5]:
            bullets.append({
                "text": claim.normalized_text,
                "claim_ids": [claim.id],
                "confidence": claim.confidence
            })
        
        avg_confidence = sum(b["confidence"] for b in bullets) / len(bullets) if bullets else 0
        
        return SynthesisSection(
            title="Trends",
            bullets=bullets,
            confidence=avg_confidence
        )
    
    def _generate_risks_rules(
        self,
        claims: List[AtomicClaim],
        grouped: Dict[str, List[AtomicClaim]]
    ) -> SynthesisSection:
        """Identify risks and challenges from claims"""
        bullets = []
        
        risk_claims = []
        
        # Look for risk-related language
        for claim in claims:
            text_lower = claim.normalized_text.lower()
            if any(word in text_lower for word in [
                "risk", "challenge", "threat", "concern", "problem", "issue",
                "negative", "adverse", "decline", "failure", "crisis", "vulnerable",
                "uncertainty", "volatility", "disruption"
            ]):
                risk_claims.append(claim)
        
        # Sort by confidence and support
        risk_claims.sort(key=lambda c: (c.confidence, len(c.support_card_ids)), reverse=True)
        
        for claim in risk_claims[:5]:
            bullets.append({
                "text": claim.normalized_text,
                "claim_ids": [claim.id],
                "confidence": claim.confidence
            })
        
        avg_confidence = sum(b["confidence"] for b in bullets) / len(bullets) if bullets else 0
        
        return SynthesisSection(
            title="Risks & Challenges",
            bullets=bullets,
            confidence=avg_confidence
        )
    
    def _generate_outlook_rules(
        self,
        claims: List[AtomicClaim],
        grouped: Dict[str, List[AtomicClaim]]
    ) -> SynthesisSection:
        """Generate outlook section from predictive claims"""
        bullets = []
        
        # Get predictive claims
        predictive = grouped.get("type_predictive", [])
        
        # Also look for future-oriented language
        future_claims = []
        for claim in claims:
            text_lower = claim.normalized_text.lower()
            if any(word in text_lower for word in [
                "will", "expect", "forecast", "predict", "project", "outlook",
                "future", "upcoming", "next year", "2025", "2026", "ahead"
            ]):
                future_claims.append(claim)
        
        # Combine and deduplicate
        all_future = list(predictive)
        seen_ids = {c.id for c in predictive}
        
        for claim in future_claims:
            if claim.id not in seen_ids:
                all_future.append(claim)
                seen_ids.add(claim.id)
        
        # Sort by confidence and support
        all_future.sort(key=lambda c: (c.confidence, len(c.support_card_ids)), reverse=True)
        
        for claim in all_future[:5]:
            bullets.append({
                "text": claim.normalized_text,
                "claim_ids": [claim.id],
                "confidence": claim.confidence
            })
        
        avg_confidence = sum(b["confidence"] for b in bullets) / len(bullets) if bullets else 0
        
        return SynthesisSection(
            title="Outlook",
            bullets=bullets,
            confidence=avg_confidence
        )
    
    def _generate_contradictions_rules(
        self,
        claims: List[AtomicClaim]
    ) -> SynthesisSection:
        """Identify contradictory claims"""
        bullets = []
        contradictions = []
        
        # Simple contradiction detection based on opposing terms
        for i, claim1 in enumerate(claims):
            for claim2 in claims[i+1:]:
                if self._are_contradictory(claim1, claim2):
                    contradictions.append((claim1, claim2))
        
        # Format contradictions
        for claim1, claim2 in contradictions[:3]:
            text = f"Conflicting evidence: '{claim1.normalized_text[:100]}...' vs '{claim2.normalized_text[:100]}...'"
            bullets.append({
                "text": text,
                "claim_ids": [claim1.id, claim2.id],
                "confidence": min(claim1.confidence, claim2.confidence)
            })
        
        avg_confidence = sum(b["confidence"] for b in bullets) / len(bullets) if bullets else 0
        
        return SynthesisSection(
            title="Contradictions",
            bullets=bullets,
            confidence=avg_confidence
        )
    
    def _are_contradictory(self, claim1: AtomicClaim, claim2: AtomicClaim) -> bool:
        """Check if two claims are contradictory"""
        text1_lower = claim1.normalized_text.lower()
        text2_lower = claim2.normalized_text.lower()
        
        # Check for opposing directional terms
        opposites = [
            ("increase", "decrease"),
            ("growth", "decline"),
            ("rise", "fall"),
            ("positive", "negative"),
            ("success", "failure"),
            ("improve", "worsen"),
            ("expand", "contract")
        ]
        
        for term1, term2 in opposites:
            if (term1 in text1_lower and term2 in text2_lower) or \
               (term2 in text1_lower and term1 in text2_lower):
                # Check if they're about the same subject
                entities1 = set(claim1.entities)
                entities2 = set(claim2.entities)
                if entities1 & entities2:  # Common entities
                    return True
        
        # Check for conflicting numbers about same metric
        if claim1.metrics and claim2.metrics:
            for key in claim1.metrics:
                if key in claim2.metrics:
                    val1 = claim1.metrics[key]
                    val2 = claim2.metrics[key]
                    if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                        # Significant difference (>20%)
                        if abs(val1 - val2) / max(val1, val2) > 0.2:
                            return True
        
        return False
    
    def _generate_gaps_rules(
        self,
        claims: List[AtomicClaim],
        topic: str
    ) -> SynthesisSection:
        """Identify information gaps"""
        bullets = []
        
        # Analyze claim coverage
        claim_types = Counter(c.claim_type for c in claims)
        total_claims = len(claims)
        
        # Check for missing claim types
        expected_types = ["factual", "statistical", "causal", "comparative", "predictive"]
        missing_types = [t for t in expected_types if claim_types.get(t, 0) < total_claims * 0.1]
        
        if missing_types:
            bullets.append({
                "text": f"Limited {', '.join(missing_types)} evidence available",
                "claim_ids": [],
                "confidence": 0.5
            })
        
        # Check for low confidence areas
        low_confidence_claims = [c for c in claims if c.confidence < 0.6]
        if len(low_confidence_claims) > total_claims * 0.3:
            bullets.append({
                "text": "High uncertainty in available evidence (>30% low confidence)",
                "claim_ids": [c.id for c in low_confidence_claims[:3]],
                "confidence": 0.5
            })
        
        # Check for single-source dominance
        single_source = [c for c in claims if len(c.support_card_ids) == 1]
        if len(single_source) > total_claims * 0.5:
            bullets.append({
                "text": "Majority of claims from single sources - limited corroboration",
                "claim_ids": [c.id for c in single_source[:3]],
                "confidence": 0.5
            })
        
        # Check for temporal gaps
        years_mentioned = set()
        for claim in claims:
            if claim.metrics and "years" in claim.metrics:
                years_mentioned.update(claim.metrics["years"])
        
        if years_mentioned:
            years_list = sorted([int(y) for y in years_mentioned if y.isdigit()])
            if years_list:
                gaps = []
                for i in range(len(years_list) - 1):
                    if years_list[i+1] - years_list[i] > 2:
                        gaps.append(f"{years_list[i]+1}-{years_list[i+1]-1}")
                
                if gaps:
                    bullets.append({
                        "text": f"Data gaps for years: {', '.join(gaps)}",
                        "claim_ids": [],
                        "confidence": 0.5
                    })
        
        avg_confidence = sum(b["confidence"] for b in bullets) / len(bullets) if bullets else 0
        
        return SynthesisSection(
            title="Information Gaps",
            bullets=bullets,
            confidence=avg_confidence
        )
    
    def _create_synthesis_prompt(
        self,
        claims_data: List[Dict],
        topic: str
    ) -> str:
        """Create prompt for LLM synthesis"""
        prompt = f"""Synthesize the following claims about "{topic}" into an executive summary.

Rules:
1. Only use information from the provided claims
2. Every bullet point must reference specific claim IDs
3. Group related claims into coherent narrative points
4. Identify contradictions and gaps
5. Maintain objectivity - report what the evidence shows

Claims:
"""
        
        for claim in claims_data:
            prompt += f"\n[{claim['id']}] ({claim['confidence']:.2f} confidence, {claim['support_count']} sources)\n"
            prompt += f"  {claim['text']}\n"
            if claim.get('metrics'):
                prompt += f"  Metrics: {claim['metrics']}\n"
        
        prompt += """

Generate synthesis in this JSON format:
{
  "executive_summary": {
    "bullets": [
      {"text": "Summary point", "claim_ids": ["claim_id1", "claim_id2"]}
    ]
  },
  "key_numbers": {
    "bullets": [
      {"text": "45% increase in...", "claim_ids": ["claim_id3"]}
    ]
  },
  "trends": {
    "bullets": [
      {"text": "Growing trend in...", "claim_ids": ["claim_id4"]}
    ]
  },
  "risks": {
    "bullets": [
      {"text": "Risk of...", "claim_ids": ["claim_id5"]}
    ]
  },
  "outlook": {
    "bullets": [
      {"text": "Expected to...", "claim_ids": ["claim_id6"]}
    ]
  },
  "contradictions": {
    "bullets": [
      {"text": "Conflicting evidence on...", "claim_ids": ["claim_id7", "claim_id8"]}
    ]
  }
}
"""
        
        return prompt
    
    def _parse_llm_synthesis(
        self,
        response: str,
        claims: List[AtomicClaim]
    ) -> SynthesisBundle:
        """Parse and validate LLM synthesis response"""
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except:
                    logger.error("Failed to parse LLM synthesis as JSON")
                    # Fall back to rules-based
                    return self._synthesize_rules(claims, "", None)
            else:
                return self._synthesize_rules(claims, "", None)
        
        # Create claim ID lookup
        claim_ids = {c.id for c in claims}
        
        # Parse sections
        sections = {}
        
        for section_name in ["executive_summary", "key_numbers", "trends", 
                            "risks", "outlook", "contradictions"]:
            if section_name in data:
                section_data = data[section_name]
                bullets = []
                
                for bullet_data in section_data.get("bullets", []):
                    # Validate claim IDs
                    referenced_ids = bullet_data.get("claim_ids", [])
                    valid_ids = [cid for cid in referenced_ids if cid in claim_ids]
                    
                    if valid_ids or section_name == "gaps":  # Gaps might not reference claims
                        bullets.append({
                            "text": bullet_data["text"],
                            "claim_ids": valid_ids,
                            "confidence": 0.8  # Default confidence for LLM output
                        })
                
                if bullets:
                    sections[section_name] = SynthesisSection(
                        title=section_name.replace("_", " ").title(),
                        bullets=bullets,
                        confidence=0.8
                    )
        
        return SynthesisBundle(
            executive_summary=sections.get("executive_summary", 
                                          self._generate_executive_summary_rules(claims, {})),
            key_numbers=sections.get("key_numbers"),
            trends=sections.get("trends"),
            risks=sections.get("risks"),
            outlook=sections.get("outlook"),
            contradictions=sections.get("contradictions"),
            gaps=None,  # Generate gaps using rules
            total_claims_used=len(claims),
            model_used=getattr(self.settings, 'LLM_MODEL', 'unknown')
        )