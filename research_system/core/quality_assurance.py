"""
Quality assurance system for fact-checking and bias detection
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import logging
from datetime import datetime

from ..models import EvidenceCard, BiasIndicators, QualityIndicators

logger = logging.getLogger(__name__)


@dataclass
class QualityScore:
    """Quality assessment score"""
    credibility: float
    accuracy: float
    completeness: float
    bias_level: float
    overall: float
    issues: List[str]
    recommendations: List[str]


class QualityAssurance:
    """Quality assurance and fact-checking system"""
    
    def __init__(self):
        self.fact_patterns = self._load_fact_patterns()
        self.bias_indicators = self._load_bias_indicators()
        self.credibility_rules = self._load_credibility_rules()
    
    def _load_fact_patterns(self) -> Dict[str, Any]:
        """Load fact-checking patterns"""
        return {
            "statistical_claims": r'\d+(?:\.\d+)?%|\d+(?:,\d{3})+',
            "date_claims": r'\b(?:19|20)\d{2}\b|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',
            "citation_patterns": r'\[\d+\]|\(\w+(?:\s+et\s+al\.)?,?\s+\d{4}\)',
            "absolute_claims": r'\b(?:always|never|all|none|every|no one|everyone|nobody)\b',
            "superlative_claims": r'\b(?:best|worst|most|least|biggest|smallest|fastest|slowest)\b'
        }
    
    def _load_bias_indicators(self) -> Dict[str, List[str]]:
        """Load bias detection indicators"""
        return {
            "emotional_language": [
                "shocking", "devastating", "amazing", "horrible", "terrible",
                "fantastic", "disgusting", "outrageous", "incredible", "unbelievable"
            ],
            "political_terms": [
                "left-wing", "right-wing", "liberal", "conservative", "radical",
                "extremist", "socialist", "capitalist", "fascist", "communist"
            ],
            "loaded_words": [
                "clearly", "obviously", "undeniably", "certainly", "definitely",
                "proven", "debunked", "exposed", "revealed", "admitted"
            ],
            "hedge_words": [
                "maybe", "perhaps", "possibly", "might", "could", "seems",
                "appears", "suggests", "indicates", "reportedly"
            ]
        }
    
    def _load_credibility_rules(self) -> Dict[str, float]:
        """Load source credibility rules"""
        return {
            # Domain patterns and their credibility weights
            r'\.gov$': 0.9,
            r'\.edu$': 0.85,
            r'\.org$': 0.7,
            r'\.com$': 0.6,
            r'wikipedia\.org': 0.75,
            r'arxiv\.org': 0.85,
            r'nature\.com': 0.95,
            r'science\.org': 0.95,
            r'pubmed\.ncbi': 0.9,
            r'reuters\.com': 0.85,
            r'apnews\.com': 0.85,
            r'bbc\.com': 0.8,
            r'npr\.org': 0.8
        }
    
    def assess_evidence_quality(self, evidence: EvidenceCard) -> QualityScore:
        """Comprehensive quality assessment of evidence"""
        
        issues = []
        recommendations = []
        
        # Assess credibility
        credibility_score = self._assess_credibility(evidence, issues)
        
        # Check for factual accuracy indicators
        accuracy_score = self._assess_accuracy(evidence, issues)
        
        # Evaluate completeness
        completeness_score = self._assess_completeness(evidence, issues)
        
        # Detect bias
        bias_score = self._detect_bias(evidence, issues)
        
        # Calculate overall score
        overall_score = (
            credibility_score * 0.3 +
            accuracy_score * 0.3 +
            completeness_score * 0.2 +
            (1 - bias_score) * 0.2  # Lower bias is better
        )
        
        # Generate recommendations
        if credibility_score < 0.5:
            recommendations.append("Seek more authoritative sources")
        if accuracy_score < 0.5:
            recommendations.append("Verify factual claims with primary sources")
        if completeness_score < 0.5:
            recommendations.append("Gather additional context and details")
        if bias_score > 0.5:
            recommendations.append("Balance with alternative perspectives")
        
        return QualityScore(
            credibility=credibility_score,
            accuracy=accuracy_score,
            completeness=completeness_score,
            bias_level=bias_score,
            overall=overall_score,
            issues=issues,
            recommendations=recommendations
        )
    
    def _assess_credibility(self, evidence: EvidenceCard, issues: List[str]) -> float:
        """Assess source credibility"""
        
        score = 0.5  # Base score
        
        # Check domain credibility
        domain = evidence.source_domain
        for pattern, weight in self.credibility_rules.items():
            if re.search(pattern, domain, re.IGNORECASE):
                score = max(score, weight)
                break
        
        # Check for author information
        if evidence.author:
            score += 0.1
        else:
            issues.append("No author information provided")
        
        # Check publication date
        if evidence.publication_date:
            # Penalize old content
            if hasattr(evidence.publication_date, 'year'):
                age_years = datetime.now().year - evidence.publication_date.year
                if age_years > 5:
                    score -= 0.1
                    issues.append(f"Content is {age_years} years old")
        else:
            issues.append("No publication date available")
        
        # Check for quality indicators (if available)
        if hasattr(evidence, 'quality_indicators') and evidence.quality_indicators:
            qi = evidence.quality_indicators
            if qi.get('has_citations'):
                score += 0.1
            if qi.get('peer_reviewed'):
                score += 0.15
            if qi.get('has_methodology'):
                score += 0.1
        
        return min(max(score, 0), 1)
    
    def _assess_accuracy(self, evidence: EvidenceCard, issues: List[str]) -> float:
        """Assess factual accuracy indicators"""
        
        score = 0.7  # Base score
        text = evidence.supporting_text
        # Also check the claim if present
        full_text = text
        if evidence.claim:
            full_text = f"{evidence.claim} {text}"
        
        # Check for citations
        citations = re.findall(self.fact_patterns["citation_patterns"], text)
        if citations:
            score += 0.1
        
        # Check for statistical claims without sources
        stats = re.findall(self.fact_patterns["statistical_claims"], text)
        if stats and not citations:
            score -= 0.2
            issues.append("Statistical claims without citations")
        
        # Check for absolute claims (check both claim and supporting text)
        absolutes = re.findall(self.fact_patterns["absolute_claims"], full_text, re.IGNORECASE)
        if absolutes:
            score -= 0.1
            issues.append(f"Contains absolute claims: {', '.join(set(absolutes))}")
        
        # Check for superlatives without evidence
        superlatives = re.findall(self.fact_patterns["superlative_claims"], text, re.IGNORECASE)
        if superlatives and not citations:
            score -= 0.1
            issues.append("Superlative claims without supporting evidence")
        
        return min(max(score, 0), 1)
    
    def _assess_completeness(self, evidence: EvidenceCard, issues: List[str]) -> float:
        """Assess information completeness"""
        
        score = 0.5  # Base score
        
        # Check text length
        text_length = len(evidence.supporting_text)
        if text_length < 100:
            score -= 0.2
            issues.append("Very brief content")
        elif text_length > 500:
            score += 0.2
        
        # Check claim support
        if evidence.claim and evidence.supporting_text:
            if evidence.claim.lower() in evidence.supporting_text.lower():
                score += 0.1
            else:
                score -= 0.1
                issues.append("Claim not directly supported by text")
        
        # Check for context (if entities available)
        if hasattr(evidence, 'entities') and evidence.entities:
            entity_count = sum(len(v) for v in evidence.entities.__dict__.values() if isinstance(v, list))
            if entity_count > 5:
                score += 0.1
            elif entity_count < 2:
                score -= 0.1
                issues.append("Limited contextual information")
        
        return min(max(score, 0), 1)
    
    def _detect_bias(self, evidence: EvidenceCard, issues: List[str]) -> float:
        """Detect bias in evidence"""
        
        bias_score = 0.0
        text = evidence.supporting_text.lower()
        
        # Check emotional language
        emotional_count = sum(1 for word in self.bias_indicators["emotional_language"] if word in text)
        if emotional_count > 0:
            bias_score += min(emotional_count * 0.1, 0.3)
            issues.append(f"Contains emotional language ({emotional_count} instances)")
        
        # Check political terms
        political_count = sum(1 for term in self.bias_indicators["political_terms"] if term in text)
        if political_count > 0:
            bias_score += min(political_count * 0.15, 0.3)
            issues.append("Contains political terminology")
        
        # Check loaded words
        loaded_count = sum(1 for word in self.bias_indicators["loaded_words"] if word in text)
        if loaded_count > 0:
            bias_score += min(loaded_count * 0.05, 0.2)
        
        # Check hedge words (too many can indicate uncertainty)
        hedge_count = sum(1 for word in self.bias_indicators["hedge_words"] if word in text)
        if hedge_count > 5:
            bias_score += 0.1
            issues.append("Excessive hedging language")
        
        # Use bias indicators if available
        if hasattr(evidence, 'bias_indicators') and evidence.bias_indicators:
            bi = evidence.bias_indicators
            if bi.sentiment != "neutral":
                bias_score += 0.1
            if bi.subjectivity > 0.7:
                bias_score += 0.2
                issues.append("Highly subjective content")
            if bi.commercial_intent:
                bias_score += 0.2
                issues.append("Commercial intent detected")
        
        return min(bias_score, 1.0)
    
    def cross_validate_evidence(self, evidence_list: List[EvidenceCard]) -> Dict[str, Any]:
        """Cross-validate multiple evidence pieces"""
        
        validation_results = {
            "consensus_level": 0.0,
            "contradictions": [],
            "corroborations": [],
            "unique_claims": [],
            "confidence": 0.0
        }
        
        if len(evidence_list) < 2:
            return validation_results
        
        # Extract all claims
        claims = {}
        for i, evidence in enumerate(evidence_list):
            claims[i] = {
                "claim": evidence.claim,
                "source": evidence.source_domain,
                "credibility": evidence.credibility_score
            }
        
        # Find corroborations and contradictions
        for i in range(len(evidence_list)):
            for j in range(i + 1, len(evidence_list)):
                similarity = self._calculate_claim_similarity(
                    evidence_list[i].claim,
                    evidence_list[j].claim
                )
                
                if similarity > 0.8:
                    validation_results["corroborations"].append({
                        "claims": [i, j],
                        "similarity": similarity
                    })
                elif similarity < 0.2:
                    # Check if they're about the same topic but contradictory
                    if self._are_contradictory(evidence_list[i], evidence_list[j]):
                        validation_results["contradictions"].append({
                            "claims": [i, j],
                            "description": f"Conflicting claims about similar topic"
                        })
        
        # Calculate consensus level
        if validation_results["corroborations"]:
            validation_results["consensus_level"] = len(validation_results["corroborations"]) / (len(evidence_list) * 0.5)
        
        # Calculate confidence based on validation
        confidence = 0.5
        confidence += len(validation_results["corroborations"]) * 0.1
        confidence -= len(validation_results["contradictions"]) * 0.15
        validation_results["confidence"] = min(max(confidence, 0), 1)
        
        return validation_results
    
    def _calculate_claim_similarity(self, claim1: str, claim2: str) -> float:
        """Calculate similarity between two claims"""
        from research_system.text import calculate_claim_similarity
        
        # Use unified similarity calculation
        return calculate_claim_similarity(claim1, claim2)
    
    def _are_contradictory(self, evidence1: EvidenceCard, evidence2: EvidenceCard) -> bool:
        """Check if two evidence pieces are contradictory"""
        
        # Check for opposing sentiment about same entities
        if evidence1.entities and evidence2.entities:
            common_entities = set()
            for attr in ['people', 'organizations', 'topics']:
                e1 = getattr(evidence1.entities, attr, [])
                e2 = getattr(evidence2.entities, attr, [])
                if e1 and e2:
                    common_entities.update(set(e1) & set(e2))
            
            if common_entities:
                # Check if sentiments are opposite
                if evidence1.bias_indicators and evidence2.bias_indicators:
                    s1 = evidence1.bias_indicators.sentiment
                    s2 = evidence2.bias_indicators.sentiment
                    if (s1 == "positive" and s2 == "negative") or (s1 == "negative" and s2 == "positive"):
                        return True
        
        # Check for contradictory keywords
        text1 = evidence1.claim.lower()
        text2 = evidence2.claim.lower()
        
        contradictory_pairs = [
            ("increase", "decrease"),
            ("rise", "fall"),
            ("growth", "decline"),
            ("success", "failure"),
            ("confirmed", "denied")
        ]
        
        for word1, word2 in contradictory_pairs:
            if (word1 in text1 and word2 in text2) or (word2 in text1 and word1 in text2):
                return True
        
        return False