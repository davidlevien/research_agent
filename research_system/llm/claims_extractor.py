"""
LLM Claims Extractor - PE-Grade Atomic Claims Extraction

Extracts atomic, grounded claims from evidence cards using LLM or rules-based fallback.
"""

import hashlib
import json
import re
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
import logging

from research_system.llm.claims_schema import (
    AtomicClaim, ClaimSet, ClaimExtractionRequest, GroundednessCheck
)
from research_system.models import EvidenceCard
from research_system.config.settings import Settings

logger = logging.getLogger(__name__)

class ClaimsExtractor:
    """Extract atomic claims from evidence cards"""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.llm_available = self._check_llm_availability()
        
    def _check_llm_availability(self) -> bool:
        """Check if LLM is configured and available"""
        if not getattr(self.settings, 'USE_LLM_CLAIMS', False):
            return False
        
        # Check for API keys
        if self.settings.LLM_PROVIDER == "openai" and self.settings.OPENAI_API_KEY:
            return True
        elif self.settings.LLM_PROVIDER == "anthropic" and self.settings.ANTHROPIC_API_KEY:
            return True
        
        return False
    
    def extract_claims(
        self,
        cards: List[EvidenceCard],
        use_llm: Optional[bool] = None
    ) -> ClaimSet:
        """Extract atomic claims from evidence cards"""
        if use_llm is None:
            use_llm = self.llm_available
        
        if use_llm and self.llm_available:
            try:
                return self._extract_claims_llm(cards)
            except Exception as e:
                logger.warning(f"LLM extraction failed, falling back to rules: {e}")
                return self._extract_claims_rules(cards)
        else:
            return self._extract_claims_rules(cards)
    
    def _extract_claims_rules(self, cards: List[EvidenceCard]) -> ClaimSet:
        """Extract claims using rules-based approach"""
        claims = []
        claim_map = {}  # For deduplication
        
        for card in cards:
            # Extract from multiple fields
            text_sources = []
            
            # Primary text sources
            if card.quote_span:
                text_sources.append(("quote", card.quote_span))
            if card.snippet:
                text_sources.append(("snippet", card.snippet))
            if card.supporting_text:
                text_sources.append(("supporting", card.supporting_text))
            
            for source_type, text in text_sources:
                # Extract sentence-level claims
                sentences = self._extract_sentences(text)
                
                for sent in sentences:
                    if self._is_claim_worthy(sent):
                        # Generate claim ID
                        claim_id = self._generate_claim_id(sent)
                        
                        # Check for duplicates/near-duplicates
                        if claim_id in claim_map:
                            # Add support to existing claim
                            claim_map[claim_id]["card_ids"].add(card.id)
                            claim_map[claim_id]["quotes"].append(sent)
                        else:
                            # Create new claim
                            claim_data = {
                                "text": self._normalize_claim_text(sent),
                                "card_ids": {card.id},
                                "quotes": [sent],
                                "confidence": self._calculate_confidence(sent, source_type),
                                "type": self._classify_claim_type(sent),
                                "entities": self._extract_entities(sent),
                                "metrics": self._extract_metrics(sent)
                            }
                            claim_map[claim_id] = claim_data
        
        # Convert to AtomicClaim objects
        for claim_id, data in claim_map.items():
            claim = AtomicClaim(
                id=claim_id,
                normalized_text=data["text"],
                support_card_ids=list(data["card_ids"]),
                support_quotes=data["quotes"][:3],  # Limit quotes
                confidence=data["confidence"],
                claim_type=data["type"],
                entities=data["entities"],
                metrics=data["metrics"]
            )
            claims.append(claim)
        
        # Sort by confidence and support
        claims.sort(key=lambda c: (len(c.support_card_ids), c.confidence), reverse=True)
        
        return ClaimSet(
            claims=claims,
            total_evidence_cards=len(cards),
            extraction_method="rules"
        )
    
    def _extract_claims_llm(self, cards: List[EvidenceCard]) -> ClaimSet:
        """Extract claims using LLM"""
        from research_system.llm.llm_client import LLMClient
        
        client = LLMClient(self.settings)
        
        # Prepare evidence for LLM
        evidence_data = []
        for card in cards[:50]:  # Limit to prevent token overflow
            evidence_data.append({
                "id": card.id,
                "title": card.title or card.source_title,
                "snippet": card.snippet,
                "quote": card.quote_span,
                "supporting_text": card.supporting_text,
                "url": card.url
            })
        
        # Create extraction prompt
        prompt = self._create_extraction_prompt(evidence_data)
        
        # Call LLM
        response = client.extract_claims(prompt)
        
        # Parse and validate response
        claims = self._parse_llm_response(response, cards)
        
        # Perform groundedness check
        validated_claims = self._validate_groundedness(claims, cards)
        
        return ClaimSet(
            claims=validated_claims,
            total_evidence_cards=len(cards),
            extraction_method="llm",
            model_used=client.model_name
        )
    
    def _extract_sentences(self, text: str) -> List[str]:
        """Extract sentences from text"""
        if not text:
            return []
        
        # Simple sentence splitting (can be enhanced with spaCy if available)
        sentences = re.split(r'[.!?]\s+', text)
        
        # Clean and filter
        clean_sentences = []
        for sent in sentences:
            sent = sent.strip()
            if len(sent) > 20 and len(sent) < 500:  # Reasonable sentence length
                clean_sentences.append(sent)
        
        return clean_sentences
    
    def _is_claim_worthy(self, sentence: str) -> bool:
        """Determine if sentence contains a claim worth extracting"""
        # Must have some substance
        if len(sentence) < 30:
            return False
        
        # Should contain factual indicators
        factual_patterns = [
            r'\d+',  # Numbers
            r'\b(is|are|was|were|will|would|has|have|had)\b',  # State verbs
            r'\b(study|research|report|analysis|survey|data|evidence)\b',  # Research terms
            r'\b(found|showed|demonstrated|indicated|revealed|suggests)\b',  # Finding verbs
            r'\b(increase|decrease|growth|decline|rise|fall)\b',  # Change terms
            r'\b(percent|%|billion|million|thousand)\b',  # Quantifiers
        ]
        
        matches = sum(1 for pattern in factual_patterns if re.search(pattern, sentence, re.IGNORECASE))
        return matches >= 2
    
    def _normalize_claim_text(self, text: str) -> str:
        """Normalize claim text for consistency"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove citation markers
        text = re.sub(r'\[\d+\]', '', text)
        text = re.sub(r'\(\d{4}\)', '', text)
        
        # Ensure ends with period
        if text and text[-1] not in '.!?':
            text += '.'
        
        return text
    
    def _generate_claim_id(self, text: str) -> str:
        """Generate stable ID for claim"""
        normalized = self._normalize_claim_text(text).lower()
        # Remove non-essential words for better matching
        normalized = re.sub(r'\b(the|a|an|and|or|but|in|on|at|to|for)\b', '', normalized)
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return hashlib.md5(normalized.encode()).hexdigest()[:16]
    
    def _calculate_confidence(self, text: str, source_type: str) -> float:
        """Calculate confidence score for claim"""
        base_confidence = {
            "quote": 0.9,
            "snippet": 0.7,
            "supporting": 0.6
        }.get(source_type, 0.5)
        
        # Adjust based on claim characteristics
        if re.search(r'\b(approximately|about|around|roughly|estimated)\b', text, re.IGNORECASE):
            base_confidence *= 0.9
        
        if re.search(r'\b(may|might|could|possibly|potentially)\b', text, re.IGNORECASE):
            base_confidence *= 0.8
        
        if re.search(r'\d+\.?\d*\s*%', text):  # Contains percentage
            base_confidence *= 1.1
        
        if re.search(r'\b(study|research|survey|analysis)\b', text, re.IGNORECASE):
            base_confidence *= 1.1
        
        return min(1.0, max(0.1, base_confidence))
    
    def _classify_claim_type(self, text: str) -> str:
        """Classify the type of claim"""
        lower_text = text.lower()
        
        if re.search(r'\d+\.?\d*\s*(%|percent|billion|million)', lower_text):
            return "statistical"
        elif re.search(r'\b(cause|because|due to|result|effect|impact)\b', lower_text):
            return "causal"
        elif re.search(r'\b(compare|versus|than|relative to|contrast)\b', lower_text):
            return "comparative"
        elif re.search(r'\b(will|forecast|predict|expect|project|outlook)\b', lower_text):
            return "predictive"
        else:
            return "factual"
    
    def _extract_entities(self, text: str) -> List[str]:
        """Extract named entities from text"""
        entities = []
        
        # Extract capitalized sequences
        cap_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        entities.extend(re.findall(cap_pattern, text))
        
        # Extract acronyms
        acronym_pattern = r'\b[A-Z]{2,}\b'
        entities.extend(re.findall(acronym_pattern, text))
        
        # Deduplicate
        return list(set(entities))[:5]  # Limit to 5 entities
    
    def _extract_metrics(self, text: str) -> Dict[str, Any]:
        """Extract numerical metrics from text"""
        metrics = {}
        
        # Extract percentages
        percent_pattern = r'(\d+\.?\d*)\s*(%|percent)'
        for match in re.finditer(percent_pattern, text, re.IGNORECASE):
            metrics["percentage"] = float(match.group(1))
        
        # Extract large numbers
        billion_pattern = r'(\d+\.?\d*)\s*billion'
        for match in re.finditer(billion_pattern, text, re.IGNORECASE):
            metrics["value_billions"] = float(match.group(1))
        
        million_pattern = r'(\d+\.?\d*)\s*million'
        for match in re.finditer(million_pattern, text, re.IGNORECASE):
            metrics["value_millions"] = float(match.group(1))
        
        # Extract years
        year_pattern = r'\b(19|20)\d{2}\b'
        years = re.findall(year_pattern, text)
        if years:
            metrics["years"] = years
        
        return metrics
    
    def _create_extraction_prompt(self, evidence_data: List[Dict]) -> str:
        """Create prompt for LLM claim extraction"""
        prompt = """Extract atomic claims from the following evidence. 
        
Rules:
1. Each claim must be a single, verifiable statement
2. Claims must be directly supported by the evidence text
3. Do not infer or add information not present in the evidence
4. Extract specific numbers, dates, and entities when present
5. Normalize similar claims into a single canonical form

Evidence:
"""
        
        for i, evidence in enumerate(evidence_data, 1):
            prompt += f"\n[Card {i}] ID: {evidence['id']}\n"
            prompt += f"Title: {evidence['title']}\n"
            if evidence.get('quote'):
                prompt += f"Quote: {evidence['quote']}\n"
            elif evidence.get('snippet'):
                prompt += f"Snippet: {evidence['snippet']}\n"
            prompt += "\n"
        
        prompt += """
Output format (JSON):
{
  "claims": [
    {
      "normalized_text": "The claim text",
      "support_card_ids": ["card_id_1", "card_id_2"],
      "support_quotes": ["exact quote 1", "exact quote 2"],
      "confidence": 0.85,
      "claim_type": "factual|statistical|causal|comparative|predictive",
      "entities": ["Entity1", "Entity2"],
      "metrics": {"percentage": 45.2, "year": 2024}
    }
  ]
}
"""
        
        return prompt
    
    def _parse_llm_response(
        self,
        response: str,
        cards: List[EvidenceCard]
    ) -> List[AtomicClaim]:
        """Parse and validate LLM response"""
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except:
                    logger.error("Failed to parse LLM response as JSON")
                    return []
            else:
                return []
        
        # Create card ID lookup
        card_ids = {card.id for card in cards}
        
        claims = []
        for claim_data in data.get("claims", []):
            try:
                # Validate card IDs exist
                support_ids = claim_data.get("support_card_ids", [])
                valid_ids = [cid for cid in support_ids if cid in card_ids]
                
                if not valid_ids:
                    continue
                
                # Generate claim ID
                claim_id = self._generate_claim_id(claim_data["normalized_text"])
                
                claim = AtomicClaim(
                    id=claim_id,
                    normalized_text=claim_data["normalized_text"],
                    support_card_ids=valid_ids,
                    support_quotes=claim_data.get("support_quotes", []),
                    confidence=claim_data.get("confidence", 0.7),
                    claim_type=claim_data.get("claim_type", "factual"),
                    entities=claim_data.get("entities", []),
                    metrics=claim_data.get("metrics", {})
                )
                claims.append(claim)
            except Exception as e:
                logger.warning(f"Failed to parse claim: {e}")
                continue
        
        return claims
    
    def _validate_groundedness(
        self,
        claims: List[AtomicClaim],
        cards: List[EvidenceCard]
    ) -> List[AtomicClaim]:
        """Validate that claims are grounded in evidence"""
        # Create text lookup for cards
        card_texts = {}
        for card in cards:
            texts = []
            if card.quote_span:
                texts.append(card.quote_span.lower())
            if card.snippet:
                texts.append(card.snippet.lower())
            if card.supporting_text:
                texts.append(card.supporting_text.lower())
            card_texts[card.id] = " ".join(texts)
        
        validated_claims = []
        for claim in claims:
            # Check if claim text appears in supporting cards
            claim_lower = claim.normalized_text.lower()
            claim_words = set(re.findall(r'\b\w+\b', claim_lower))
            
            grounded = False
            for card_id in claim.support_card_ids:
                if card_id in card_texts:
                    card_words = set(re.findall(r'\b\w+\b', card_texts[card_id]))
                    overlap = len(claim_words & card_words) / len(claim_words)
                    if overlap > 0.5:  # At least 50% word overlap
                        grounded = True
                        break
            
            if grounded:
                validated_claims.append(claim)
            else:
                logger.debug(f"Claim not grounded: {claim.normalized_text[:50]}...")
        
        return validated_claims

def merge_similar_claims(
    claims: List[AtomicClaim],
    threshold: float = 0.85
) -> List[AtomicClaim]:
    """Merge similar claims into canonical forms"""
    try:
        from sentence_transformers import SentenceTransformer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np
        
        if not claims:
            return claims
        
        # Load model
        model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Encode all claims
        texts = [c.normalized_text for c in claims]
        embeddings = model.encode(texts)
        
        # Calculate similarity matrix
        sim_matrix = cosine_similarity(embeddings)
        
        # Group similar claims
        merged = []
        processed = set()
        
        for i, claim in enumerate(claims):
            if i in processed:
                continue
            
            # Find similar claims
            similar_indices = np.where(sim_matrix[i] > threshold)[0]
            
            if len(similar_indices) > 1:
                # Merge claims
                merged_claim = claim.model_copy()
                
                # Combine support from all similar claims
                all_card_ids = set(claim.support_card_ids)
                all_quotes = list(claim.support_quotes)
                all_entities = set(claim.entities)
                
                for j in similar_indices:
                    if j != i:
                        processed.add(j)
                        all_card_ids.update(claims[j].support_card_ids)
                        all_quotes.extend(claims[j].support_quotes)
                        all_entities.update(claims[j].entities)
                
                # Update merged claim
                merged_claim.support_card_ids = list(all_card_ids)
                merged_claim.support_quotes = list(set(all_quotes))[:5]  # Limit quotes
                merged_claim.entities = list(all_entities)[:10]
                merged_claim.confidence = max(c.confidence for j, c in enumerate(claims) if j in similar_indices)
                
                merged.append(merged_claim)
            else:
                merged.append(claim)
            
            processed.add(i)
        
        return merged
        
    except ImportError:
        logger.warning("sentence-transformers not available, skipping claim merging")
        return claims