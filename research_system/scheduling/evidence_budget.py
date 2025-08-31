"""Evidence collection budgeting and quota management.

v8.21.0: Manages quotas per capability topic to ensure sufficient evidence
while avoiding over-collection and early termination when critical sources fail.
"""

from typing import List, Dict, Optional
from research_system.providers.intent_registry import CAPABILITY_MATRIX

class EvidenceBudget:
    """Manages evidence collection quotas per capability topic."""
    
    def __init__(self, topics: List[str]):
        """
        Initialize budget for given topics.
        
        Args:
            topics: List of capability topics to budget for
        """
        self.topics = topics
        
        # Set quotas per topic
        self.quota = {}
        for t in topics:
            self.quota[t] = {
                "fetch": 8,      # Max documents to fetch
                "extract": 4,    # Max to extract claims from
                "claims": 2      # Min claims needed
            }
    
    def providers(self) -> List[str]:
        """
        Get all providers needed for budgeted topics.
        
        Returns:
            Deduplicated list of providers
        """
        providers = []
        seen = set()
        
        for topic in self.topics:
            if topic in CAPABILITY_MATRIX:
                for provider in CAPABILITY_MATRIX[topic]["providers"]:
                    if provider not in seen:
                        providers.append(provider)
                        seen.add(provider)
        
        return providers
    
    def met(self, topic: str, claims_seen: int) -> bool:
        """
        Check if quota is met for a topic.
        
        Args:
            topic: Topic to check
            claims_seen: Number of claims collected so far
            
        Returns:
            True if quota is met
        """
        if topic not in self.quota:
            return True  # Unknown topic, consider met
        
        return claims_seen >= self.quota[topic]["claims"]
    
    def get_fetch_limit(self, topic: str) -> int:
        """
        Get fetch limit for a topic.
        
        Args:
            topic: Topic to get limit for
            
        Returns:
            Maximum documents to fetch
        """
        if topic not in self.quota:
            return 8  # Default
        
        return self.quota[topic]["fetch"]

def insufficient_evidence(topics: List[str], coverage: Dict[str, int]) -> bool:
    """
    Check if evidence is insufficient based on coverage.
    
    Args:
        topics: List of capability topics
        coverage: Dict mapping topic to number of sources that provided data
        
    Returns:
        True if evidence is insufficient
    """
    for topic in topics:
        if topic not in CAPABILITY_MATRIX:
            continue
        
        min_sources = CAPABILITY_MATRIX[topic]["min_sources"]
        actual_sources = coverage.get(topic, 0)
        
        if actual_sources < min_sources:
            return True
    
    return False

def plan_evidence_collection(query: str) -> Dict[str, any]:
    """
    Plan evidence collection for a query.
    
    Args:
        query: User query
        
    Returns:
        Collection plan with topics, providers, and quotas
    """
    from research_system.providers.intent_registry import plan_capabilities
    
    # Get capability topics for query
    topics = plan_capabilities(query)
    
    # Create budget
    budget = EvidenceBudget(topics)
    
    # Get providers
    providers = budget.providers()
    
    return {
        "topics": topics,
        "providers": providers,
        "budget": budget,
        "min_evidence": {
            t: CAPABILITY_MATRIX.get(t, {}).get("min_sources", 1)
            for t in topics
        }
    }