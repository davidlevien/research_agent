"""Intent classification for research queries with hybrid approach."""

from enum import Enum
import re
import os
import logging
from typing import Tuple, List, Optional

logger = logging.getLogger(__name__)


class Intent(Enum):
    """Research query intent types."""
    ENCYCLOPEDIA = "encyclopedia"
    NEWS = "news"
    PRODUCT = "product"
    LOCAL = "local"
    ACADEMIC = "academic"
    STATS = "stats"
    HOWTO = "howto"
    TRAVEL = "travel"
    REGULATORY = "regulatory"
    MEDICAL = "medical"
    GENERIC = "generic"


# Intent detection rules (order matters - more specific first)
_RULES: List[Tuple[Intent, str]] = [
    # Medical patterns (check first as health queries need special handling)
    (Intent.MEDICAL, r"\b(symptoms?|treatment|diagnosis|side effects?|contraindications?|disease|cure|therapy|medical|health condition)\b"),
    # Travel patterns (check before local to catch "beaches in Thailand" etc.)
    (Intent.TRAVEL, r"\b(itinerary|visa|travel|tourist|vacation|trip|where to stay|things to do|destination|beaches? in \w+|resorts?|tourism)\b"),
    # Local intent - location-based searches (after travel to avoid false positives)
    (Intent.LOCAL, r"\b(near me|hours|open now|closest|nearby|local)\b|\b(restaurants?|cafes?|hotels?|shops?|stores?|parks|attractions?) in\b"),
    # Academic patterns
    (Intent.ACADEMIC, r"\b(systematic review|meta-analysis|peer[- ]reviewed|doi:|arxiv:|journal|research paper|study|academic)\b"),
    # Regulatory/compliance patterns
    (Intent.REGULATORY, r"\b(10-[kq]|8-k|regulation|sec\.gov|compliance|filing|disclosure|earnings report)\b"),
    # Stats and data patterns
    (Intent.STATS, r"\b(dataset|time series|statistics|GDP|CPI|index|indicator|metric|data analysis|growth rate)\b"),
    # How-to patterns
    (Intent.HOWTO, r"\b(how to|tutorial|step by step|guide|instructions|diy|make|build|setup)\b"),
    # Product/shopping patterns
    (Intent.PRODUCT, r"\b(best|top|vs|versus|review|buy|price|budget|under \$\d+|cheapest|worth it|comparison|recommend)\b"),
    # News patterns
    (Intent.NEWS, r"\b(today|yesterday|this week|latest|breaking|current|recent|news|update)\b"),
    # Encyclopedia patterns
    (Intent.ENCYCLOPEDIA, r"\b(history of|what is|who is|origins? of|biography|timeline|evolution of|definition)\b"),
]


def _classify_rules(query: str) -> Optional[Intent]:
    """
    Stage A: Rule-based classification.
    
    Args:
        query: The search query to classify
        
    Returns:
        Intent enum value or None if no rules matched
    """
    q = query.lower()
    
    # Check rules in order
    for intent, pattern in _RULES:
        if re.search(pattern, q):
            logger.debug(f"Rules: Query matched {intent.value}")
            return intent
    
    return None


def _classify_semantic(query: str, min_confidence: float = 0.6) -> Optional[Intent]:
    """
    Stage B: Semantic classification using SentenceTransformers.
    
    Args:
        query: The search query to classify
        min_confidence: Minimum confidence threshold
        
    Returns:
        Intent enum value or None if confidence too low
    """
    try:
        from . import semantic
        
        # Initialize if needed
        semantic.init()
        
        # Get prediction
        label, confidence, _ = semantic.predict(query)
        
        if confidence >= min_confidence and label != "generic":
            logger.debug(f"Semantic: {label} (confidence: {confidence:.2f})")
            return Intent(label)
        else:
            logger.debug(f"Semantic: Low confidence {confidence:.2f} for {label}")
            return None
            
    except Exception as e:
        logger.debug(f"Semantic classification unavailable: {e}")
        return None


def _classify_nli(query: str, min_confidence: float = 0.5) -> Optional[Intent]:
    """
    Stage C: Zero-shot NLI classification.
    
    Args:
        query: The search query to classify
        min_confidence: Minimum confidence threshold
        
    Returns:
        Intent enum value or None if confidence too low
    """
    try:
        from . import nli_fallback
        
        # Initialize if needed
        nli_fallback.init()
        
        # Get prediction
        label, confidence, _ = nli_fallback.predict(query)
        
        if confidence >= min_confidence and label != "generic":
            logger.debug(f"NLI: {label} (confidence: {confidence:.2f})")
            return Intent(label)
        else:
            logger.debug(f"NLI: Low confidence {confidence:.2f} for {label}")
            return None
            
    except Exception as e:
        logger.debug(f"NLI classification unavailable: {e}")
        return None


def classify(query: str, use_hybrid: bool = None) -> Intent:
    """
    Classify the intent of a research query using hybrid approach.
    
    Pipeline:
    1. Rule-based patterns (fast, high precision)
    2. Semantic similarity (if rules don't match)
    3. Zero-shot NLI (if semantic is low confidence)
    4. Generic fallback
    
    Args:
        query: The search query to classify
        use_hybrid: Whether to use hybrid approach (defaults to env var or True)
        
    Returns:
        Intent enum value
    """
    if use_hybrid is None:
        use_hybrid = os.getenv("INTENT_USE_HYBRID", "true").lower() == "true"
    
    # Stage A: Try rule-based classification first
    intent = _classify_rules(query)
    if intent is not None:
        logger.info(f"Query '{query[:50]}...' classified as {intent.value} (rules)")
        return intent
    
    if not use_hybrid:
        # If hybrid disabled, return generic
        logger.info(f"Query '{query[:50]}...' classified as GENERIC (rules failed, hybrid disabled)")
        return Intent.GENERIC
    
    # Stage B: Try semantic classification
    intent = _classify_semantic(query)
    if intent is not None:
        logger.info(f"Query '{query[:50]}...' classified as {intent.value} (semantic)")
        return intent
    
    # Stage C: Try NLI classification
    intent = _classify_nli(query)
    if intent is not None:
        logger.info(f"Query '{query[:50]}...' classified as {intent.value} (NLI)")
        return intent
    
    # Stage D: Default fallback
    logger.info(f"Query '{query[:50]}...' classified as GENERIC (all stages failed)")
    return Intent.GENERIC


def detect_geographic_ambiguity(query: str) -> Optional[List[str]]:
    """
    Detect potential geographic ambiguity in queries.
    
    Args:
        query: The search query
        
    Returns:
        List of potential locations if ambiguous, None otherwise
    """
    # Common ambiguous cities
    ambiguous_cities = {
        "portland": ["Portland, OR", "Portland, ME"],
        "springfield": ["Springfield, IL", "Springfield, MA", "Springfield, MO"],
        "columbus": ["Columbus, OH", "Columbus, GA"],
        "jackson": ["Jackson, MS", "Jackson, WY", "Jackson, MI"],
        "aurora": ["Aurora, CO", "Aurora, IL"],
        "richmond": ["Richmond, VA", "Richmond, CA"],
        "arlington": ["Arlington, TX", "Arlington, VA"],
        "cambridge": ["Cambridge, MA", "Cambridge, UK"],
        "oxford": ["Oxford, UK", "Oxford, MS"],
        "paris": ["Paris, France", "Paris, TX"],
    }
    
    q_lower = query.lower()
    for city, locations in ambiguous_cities.items():
        # Check if the city is mentioned
        if city in q_lower:
            # Check if any state/country identifier is present (with word boundaries)
            state_patterns = [
                r"\b(or|oregon)\b", r"\b(me|maine)\b", r"\b(ma|massachusetts)\b", 
                r"\b(il|illinois)\b", r"\b(mo|missouri)\b", r"\b(oh|ohio)\b",
                r"\b(ga|georgia)\b", r"\b(ms|mississippi)\b", r"\b(wy|wyoming)\b",
                r"\b(mi|michigan)\b", r"\b(co|colorado)\b", r"\b(va|virginia)\b",
                r"\b(ca|california)\b", r"\b(tx|texas)\b", r"\buk\b", r"\bfrance\b"
            ]
            has_state = any(re.search(pattern, q_lower) for pattern in state_patterns)
            if not has_state:
                logger.info(f"Geographic ambiguity detected: {city} -> {locations}")
                return locations
    
    return None


def get_confidence_threshold(intent: Intent) -> Tuple[float, int]:
    """
    Get triangulation threshold and minimum sources for an intent.
    
    Args:
        intent: The classified intent
        
    Returns:
        Tuple of (min_triangulation_rate, min_sources)
    """
    thresholds = {
        Intent.PRODUCT: (0.20, 3),
        Intent.LOCAL: (0.15, 2),
        Intent.ACADEMIC: (0.35, 3),
        Intent.STATS: (0.30, 3),
        Intent.NEWS: (0.30, 4),
        Intent.ENCYCLOPEDIA: (0.25, 2),
        Intent.TRAVEL: (0.25, 3),
        Intent.HOWTO: (0.20, 2),
        Intent.REGULATORY: (0.30, 3),
        Intent.MEDICAL: (0.35, 3),
        Intent.GENERIC: (0.25, 2),
    }
    return thresholds.get(intent, (0.25, 2))