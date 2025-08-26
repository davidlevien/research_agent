"""
PE-Grade Generalized Topic Router

Domain-agnostic routing system with YAML-driven configuration.
No hard-coded verticals, fully extensible topic packs.
"""

from __future__ import annotations
import re
import math
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Iterable, Set
from pathlib import Path
import yaml
import logging

logger = logging.getLogger(__name__)

def _load_yaml(name: str) -> dict:
    """Load YAML configuration with error handling."""
    try:
        # Use path-based loading
        config_path = Path(__file__).resolve().parents[1] / "resources" / name
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"Failed to load {name}: {e}")
        return {}

# Load configurations at module level for performance
TOPIC_PACKS = _load_yaml("topic_packs.yaml")
PROVIDER_CAPS = _load_yaml("provider_capabilities.yaml")
PROVIDERS_CONFIG = PROVIDER_CAPS.get("providers", {})
SELECTION_STRATEGIES = PROVIDER_CAPS.get("selection_strategies", {})

def _norm(s: str) -> str:
    """Normalize string for consistent matching."""
    return unicodedata.normalize("NFKC", s or "").lower().strip()

@dataclass(frozen=True)
class TopicMatch:
    """Result of topic classification."""
    topic_key: str
    score: float
    anchors_hit: int
    matched_aliases: List[str]
    confidence: float

@dataclass(frozen=True)
class RouterDecision:
    """Complete routing decision with rationale."""
    topic_match: TopicMatch
    providers: List[str]
    strategy_used: str
    query_refinements: Dict[str, str]
    reasoning: str

def classify_topic_multi(user_query: str, confidence_threshold: float = 0.55) -> Set[str]:
    """
    Classify user query against all topic packs, returning multiple matching packs.
    
    Returns set of matching topic keys that exceed confidence threshold.
    Supports multi-pack classification for cross-domain queries.
    """
    if not user_query or not TOPIC_PACKS:
        return {"general"}
    
    q_norm = _norm(user_query)
    matches = []
    
    for topic_key, pack in TOPIC_PACKS.items():
        # Get normalized aliases and anchors
        aliases = {_norm(alias) for alias in pack.get("aliases", [])}
        anchors = {_norm(anchor) for anchor in pack.get("anchors", [])}
        
        # Count alias hits (full word matches)
        alias_hits = []
        for alias in aliases:
            if alias and alias in q_norm:
                alias_hits.append(alias)
        
        # Count anchor hits (weighted more heavily)
        anchor_hits = 0
        for anchor in anchors:
            if anchor and anchor in q_norm:
                anchor_hits += 1
        
        # Calculate composite score
        alias_score = len(alias_hits)
        anchor_score = anchor_hits * 1.5  # Anchors weighted 1.5x
        total_score = alias_score + anchor_score
        
        # Calculate confidence based on query coverage
        query_words = set(re.findall(r'\b\w+\b', q_norm))
        matched_words = {word for alias in alias_hits for word in alias.split()}
        matched_words.update({word for anchor in anchors if anchor in q_norm for word in anchor.split()})
        
        coverage = len(matched_words & query_words) / max(len(query_words), 1) if query_words else 0
        confidence = min(1.0, (total_score * 0.3) + (coverage * 0.7))
        
        if confidence >= confidence_threshold:
            matches.append((topic_key, confidence, total_score))
    
    # Sort by confidence and score
    matches.sort(key=lambda x: (x[1], x[2]), reverse=True)
    
    # Return top matches, with special handling for complementary packs
    if not matches:
        return {"general"}
    
    selected_packs = {matches[0][0]}  # Always include top match
    
    # Check for complementary packs
    COMPLEMENTARY = {
        ("policy", "health"), ("policy", "finance"), ("policy", "education"),
        ("policy", "defense"), ("policy", "energy"), ("science", "policy"),
        ("health", "science"), ("finance", "macro"), ("climate_energy", "policy")
    }
    
    for pack_key, conf, score in matches[1:]:
        # Add if complementary to any already selected
        for selected in selected_packs:
            if (pack_key, selected) in COMPLEMENTARY or (selected, pack_key) in COMPLEMENTARY:
                selected_packs.add(pack_key)
                break
    
    return selected_packs

def classify_topic(user_query: str) -> TopicMatch:
    """
    Legacy single-topic classification for backward compatibility.
    """
    packs = classify_topic_multi(user_query)
    
    # Get detailed match for the primary pack
    primary_pack = list(packs)[0] if packs else "general"
    
    if not user_query or not TOPIC_PACKS:
        return TopicMatch("general", 0.0, 0, [], 0.0)
    
    q_norm = _norm(user_query)
    pack = TOPIC_PACKS.get(primary_pack, {})
    
    # Get normalized aliases and anchors
    aliases = {_norm(alias) for alias in pack.get("aliases", [])}
    anchors = {_norm(anchor) for anchor in pack.get("anchors", [])}
    
    # Count alias hits
    alias_hits = [alias for alias in aliases if alias and alias in q_norm]
    
    # Count anchor hits
    anchor_hits = sum(1 for anchor in anchors if anchor and anchor in q_norm)
    
    # Calculate scores
    alias_score = len(alias_hits)
    anchor_score = anchor_hits * 1.5
    total_score = alias_score + anchor_score
    
    # Calculate confidence
    query_words = set(re.findall(r'\b\w+\b', q_norm))
    matched_words = {word for alias in alias_hits for word in alias.split()}
    matched_words.update({word for anchor in anchors if anchor in q_norm for word in anchor.split()})
    coverage = len(matched_words & query_words) / max(len(query_words), 1) if query_words else 0
    confidence = min(1.0, (total_score * 0.3) + (coverage * 0.7))
    
    return TopicMatch(primary_pack, total_score, anchor_hits, alias_hits, confidence)

def providers_for_topic(topic_key: str, strategy: str = "broad_coverage") -> List[str]:
    """
    Select providers for a topic using specified strategy.
    
    Args:
        topic_key: The classified topic
        strategy: Selection strategy (high_precision, broad_coverage, academic_focus, real_time)
    
    Returns:
        Ordered list of provider names
    """
    if not PROVIDERS_CONFIG:
        logger.warning("No provider configuration loaded, using fallback")
        return ["brave", "tavily", "wikipedia"]
    
    # Get strategy configuration
    strategy_config = SELECTION_STRATEGIES.get(strategy, SELECTION_STRATEGIES.get("broad_coverage", {}))
    provider_order = strategy_config.get("provider_order", list(PROVIDERS_CONFIG.keys()))
    max_providers = strategy_config.get("max_providers", 8)
    
    # Filter providers that support this topic
    eligible_providers = []
    for provider_name in provider_order:
        provider_config = PROVIDERS_CONFIG.get(provider_name, {})
        supported_topics = provider_config.get("topics", [])
        
        # Include if topic matches or provider supports general
        if topic_key in supported_topics or "general" in supported_topics:
            eligible_providers.append(provider_name)
            
        # Stop when we reach max providers
        if len(eligible_providers) >= max_providers:
            break
    
    # Fallback to ensure we always return some providers
    if not eligible_providers:
        fallback_providers = ["brave", "tavily", "serpapi", "wikipedia"]
        eligible_providers = [p for p in fallback_providers if p in PROVIDERS_CONFIG][:max_providers]
    
    return eligible_providers

def refine_query(user_query: str, provider: str, topic_key: str) -> str:
    """
    Refine query for specific provider and topic.
    
    Applies topic-specific expansions and provider-specific refiners.
    """
    if not user_query:
        return user_query
        
    refined_query = user_query
    
    # Apply topic pack expansions
    topic_pack = TOPIC_PACKS.get(topic_key, {})
    expansions = topic_pack.get("query_expansions", [])
    
    if expansions:
        # Create expansion clause
        expansion_clause = ' OR '.join(f'"{exp}"' for exp in expansions)
        refined_query = f'({user_query}) AND ({expansion_clause})'
    
    # Apply provider-specific refiners
    provider_config = PROVIDERS_CONFIG.get(provider, {})
    refiners = provider_config.get("query_refiners", [])
    
    if refiners:
        refiner_clause = ' '.join(refiners)
        refined_query = f'{refined_query} {refiner_clause}'
    
    return refined_query.strip()

def jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    """Calculate Jaccard similarity coefficient between two sets."""
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)

def is_off_topic(content_dict: dict, topic_key: str) -> bool:
    """
    Universal off-topic filter using Jaccard similarity and required terms.
    
    Args:
        content_dict: Content with 'title', 'snippet', etc.
        topic_key: Classified topic key
    
    Returns:
        True if content should be filtered as off-topic
    """
    topic_pack = TOPIC_PACKS.get(topic_key, {})
    off_topic_config = topic_pack.get("off_topic", {})
    
    # Extract text content
    title = content_dict.get("title", "")
    snippet = content_dict.get("snippet", "")
    text_content = _norm(f"{title} {snippet}")
    
    if not text_content:
        return True  # Empty content is off-topic
    
    # Check required terms (must_contain_any)
    required_terms = off_topic_config.get("must_contain_any", [])
    if required_terms:
        required_terms_norm = {_norm(term) for term in required_terms}
        if not any(term in text_content for term in required_terms_norm):
            return True
    
    # Check Jaccard similarity threshold
    min_jaccard = off_topic_config.get("min_jaccard", 0.05)
    if min_jaccard > 0:
        # Extract words from content
        content_words = set(re.findall(r'\b\w+\b', text_content))
        
        # Get topic aliases as reference vocabulary
        topic_aliases = topic_pack.get("aliases", [])
        topic_words = set()
        for alias in topic_aliases:
            topic_words.update(re.findall(r'\b\w+\b', _norm(alias)))
        
        if topic_words:  # Only check if we have topic words
            similarity = jaccard_similarity(content_words, topic_words)
            if similarity < min_jaccard:
                return True
    
    return False

def route_query(user_query: str, strategy: str = "broad_coverage") -> RouterDecision:
    """
    Complete routing pipeline: classify topic -> select providers -> refine queries.
    
    Args:
        user_query: User's research query
        strategy: Provider selection strategy
        
    Returns:
        Complete routing decision with all details
    """
    # Step 1: Classify topic
    topic_match = classify_topic(user_query)
    
    # Step 2: Select providers
    providers = providers_for_topic(topic_match.topic_key, strategy)
    
    # Step 3: Generate query refinements per provider
    query_refinements = {}
    for provider in providers:
        refined = refine_query(user_query, provider, topic_match.topic_key)
        if refined != user_query:  # Only store if actually refined
            query_refinements[provider] = refined
    
    # Step 4: Build reasoning
    reasoning = (
        f"Topic: {topic_match.topic_key} (score: {topic_match.score:.2f}, "
        f"confidence: {topic_match.confidence:.2f}, "
        f"anchors: {topic_match.anchors_hit}, "
        f"aliases: {len(topic_match.matched_aliases)}). "
        f"Strategy: {strategy}. "
        f"Providers: {len(providers)} selected. "
        f"Refinements: {len(query_refinements)} applied."
    )
    
    return RouterDecision(
        topic_match=topic_match,
        providers=providers,
        strategy_used=strategy,
        query_refinements=query_refinements,
        reasoning=reasoning
    )

# Backward compatibility with existing codebase
def choose_providers(topic: str) -> RouterDecision:
    """Legacy interface for backward compatibility."""
    decision = route_query(topic, strategy="broad_coverage")
    
    # Create legacy RouterDecision format
    from research_system.routing.provider_router import RouterDecision as LegacyDecision
    return LegacyDecision(
        categories=[decision.topic_match.topic_key],
        providers=decision.providers,
        reason=decision.reasoning
    )

def route_topic(topic: str):
    """Legacy route_topic function for policy compatibility."""
    from research_system.models import Discipline
    
    # Map new topic keys to old Discipline enum
    topic_match = classify_topic(topic)
    topic_key = topic_match.topic_key
    
    discipline_mapping = {
        "health": Discipline.MEDICINE,
        "science": Discipline.SCIENCE, 
        "policy": Discipline.LAW_POLICY,
        "macroeconomics": Discipline.FINANCE_ECON,
        "technology": Discipline.TECH_SOFTWARE,
        "corporate": Discipline.FINANCE_ECON,
        "climate": Discipline.SCIENCE,
        "geospatial": Discipline.SCIENCE,
        "travel_tourism": Discipline.FINANCE_ECON,
        "news": Discipline.GENERAL,
        "general": Discipline.GENERAL
    }
    
    return discipline_mapping.get(topic_key, Discipline.GENERAL)