"""
Controversy detection and claim clustering for research evidence
"""

from typing import List, Dict, Tuple, Set
from collections import defaultdict
import hashlib
import re
from difflib import SequenceMatcher

from .models import EvidenceCard


class ControversyDetector:
    """Detects and analyzes controversies in evidence collections"""
    
    def __init__(self, similarity_threshold: float = 0.7):
        self.similarity_threshold = similarity_threshold
        self.claim_clusters: Dict[str, List[EvidenceCard]] = defaultdict(list)
        self.controversy_scores: Dict[str, float] = {}
    
    def normalize_claim(self, claim: str) -> str:
        """Normalize claim text for clustering"""
        # Remove extra whitespace, lowercase, remove punctuation
        normalized = re.sub(r'[^\w\s]', '', claim.lower())
        normalized = ' '.join(normalized.split())
        return normalized
    
    def generate_claim_id(self, claim: str) -> str:
        """Generate a deterministic claim ID from normalized text"""
        normalized = self.normalize_claim(claim)
        # Use first 8 chars of hash for readability
        return hashlib.md5(normalized.encode()).hexdigest()[:8]
    
    def claims_similar(self, claim1: str, claim2: str) -> bool:
        """Check if two claims are similar enough to cluster"""
        norm1 = self.normalize_claim(claim1)
        norm2 = self.normalize_claim(claim2)
        
        # Use sequence matcher for fuzzy matching
        similarity = SequenceMatcher(None, norm1, norm2).ratio()
        return similarity >= self.similarity_threshold
    
    def detect_contradiction(self, card1: EvidenceCard, card2: EvidenceCard) -> bool:
        """Detect if two evidence cards contradict each other"""
        # Check for opposing keywords
        text1 = (card1.claim + " " + card1.supporting_text).lower()
        text2 = (card2.claim + " " + card2.supporting_text).lower()
        
        # Contradiction patterns
        contradictory_patterns = [
            (r'\bnot\b.*\btrue\b', r'\btrue\b'),
            (r'\bfalse\b', r'\btrue\b'),
            (r'\bincreases?\b', r'\bdecreases?\b'),
            (r'\brises?\b', r'\bfalls?\b'),
            (r'\bproven\b', r'\bdisproven\b'),
            (r'\beffective\b', r'\bineffective\b'),
            (r'\bsafe\b', r'\bunsafe\b|dangerous\b'),
            (r'\bcauses?\b', r'\bdoes not cause\b'),
            (r'\bconfirms?\b', r'\bdenies?\b|refutes?\b'),
        ]
        
        for pattern1, pattern2 in contradictory_patterns:
            if ((re.search(pattern1, text1) and re.search(pattern2, text2)) or
                (re.search(pattern2, text1) and re.search(pattern1, text2))):
                return True
        
        # Check for explicit numerical contradictions
        numbers1 = re.findall(r'\b\d+(?:\.\d+)?%?\b', text1)
        numbers2 = re.findall(r'\b\d+(?:\.\d+)?%?\b', text2)
        
        if numbers1 and numbers2 and self.claims_similar(card1.claim, card2.claim):
            # If claims are about the same thing but have very different numbers
            try:
                val1 = float(numbers1[0].rstrip('%'))
                val2 = float(numbers2[0].rstrip('%'))
                # Consider contradictory if values differ by more than 50%
                if abs(val1 - val2) / max(val1, val2) > 0.5:
                    return True
            except (ValueError, ZeroDivisionError):
                pass
        
        return False
    
    def cluster_claims(self, cards: List[EvidenceCard]) -> Dict[str, List[EvidenceCard]]:
        """Cluster evidence cards by similar claims"""
        clusters = defaultdict(list)
        assigned = set()
        
        for i, card in enumerate(cards):
            if i in assigned:
                continue
                
            # Start new cluster with this card
            claim_id = self.generate_claim_id(card.claim)
            cluster = [card]
            assigned.add(i)
            
            # Find similar claims
            for j, other in enumerate(cards[i+1:], i+1):
                if j not in assigned and self.claims_similar(card.claim, other.claim):
                    cluster.append(other)
                    assigned.add(j)
            
            # Assign claim_id to all cards in cluster
            for c in cluster:
                c.claim_id = claim_id
            
            clusters[claim_id] = cluster
        
        self.claim_clusters = clusters
        return clusters
    
    def analyze_stances(self, clusters: Dict[str, List[EvidenceCard]]) -> None:
        """Analyze stances within each claim cluster"""
        for claim_id, cluster in clusters.items():
            if len(cluster) < 2:
                continue
            
            # Check for contradictions within cluster
            for i, card1 in enumerate(cluster):
                disputed_by = []
                
                for j, card2 in enumerate(cluster):
                    if i != j and self.detect_contradiction(card1, card2):
                        # Set stances
                        if card1.stance == "neutral":
                            card1.stance = "supports"
                        if card2.stance == "neutral":
                            card2.stance = "disputes"
                        
                        # Track disputes
                        disputed_by.append(card2.id)
                        if card1.id not in card2.disputed_by:
                            card2.disputed_by.append(card1.id)
                
                if disputed_by:
                    card1.disputed_by.extend(disputed_by)
    
    def calculate_controversy_scores(self, clusters: Dict[str, List[EvidenceCard]]) -> Dict[str, float]:
        """Calculate controversy score for each claim cluster"""
        scores = {}
        
        for claim_id, cluster in clusters.items():
            if len(cluster) < 2:
                scores[claim_id] = 0.0
                continue
            
            # Count stances weighted by credibility
            supports_weight = 0.0
            disputes_weight = 0.0
            neutral_weight = 0.0
            
            for card in cluster:
                weight = card.credibility_score
                if card.stance == "supports":
                    supports_weight += weight
                elif card.stance == "disputes":
                    disputes_weight += weight
                else:
                    neutral_weight += weight
            
            total_weight = supports_weight + disputes_weight + neutral_weight
            
            if total_weight == 0:
                scores[claim_id] = 0.0
            else:
                # Controversy is high when there's significant weight on both sides
                if supports_weight > 0 and disputes_weight > 0:
                    # Calculate as normalized disagreement
                    min_weight = min(supports_weight, disputes_weight)
                    max_weight = max(supports_weight, disputes_weight)
                    # Higher score when weights are balanced
                    scores[claim_id] = (2 * min_weight) / total_weight
                else:
                    scores[claim_id] = 0.0
            
            # Update cards with controversy score
            for card in cluster:
                card.controversy_score = scores[claim_id]
        
        self.controversy_scores = scores
        return scores
    
    def process_evidence(self, cards: List[EvidenceCard]) -> Tuple[Dict[str, List[EvidenceCard]], Dict[str, float]]:
        """Main processing pipeline for controversy detection"""
        # 1. Cluster claims
        clusters = self.cluster_claims(cards)
        
        # 2. Analyze stances
        self.analyze_stances(clusters)
        
        # 3. Calculate controversy scores
        scores = self.calculate_controversy_scores(clusters)
        
        return clusters, scores
    
    def get_controversial_claims(self, threshold: float = 0.3) -> List[Tuple[str, List[EvidenceCard]]]:
        """Get claims with controversy score above threshold"""
        controversial = []
        
        for claim_id, cluster in self.claim_clusters.items():
            if self.controversy_scores.get(claim_id, 0) >= threshold:
                controversial.append((claim_id, cluster))
        
        # Sort by controversy score descending
        controversial.sort(key=lambda x: self.controversy_scores.get(x[0], 0), reverse=True)
        
        return controversial