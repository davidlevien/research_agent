"""Source-aware clustering that prevents mixing advocacy with statistical sources."""

from typing import List, Dict, Any, Tuple, Set
from enum import Enum
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class ClaimType(Enum):
    """Type of claim for clustering."""
    NUMERIC_MEASURE = "numeric_measure"
    MECHANISM_OR_THEORY = "mechanism_or_theory"
    OPINION_ADVOCACY = "opinion_advocacy"
    NEWS_CONTEXT = "news_context"


class SourceClass(Enum):
    """Source classification for clustering."""
    OFFICIAL_STATS = "official_stats"
    PEER_REVIEW = "peer_review"
    GOV_MEMO = "gov_memo"
    THINK_TANK = "think_tank"
    MEDIA = "media"
    BLOG = "blog"


def classify_card_source(card: Any) -> SourceClass:
    """Classify a card's source type."""
    domain = getattr(card, 'source_domain', '').lower()
    
    # Official statistics
    OFFICIAL_DOMAINS = {
        "irs.gov", "treasury.gov", "cbo.gov", "bls.gov", "census.gov",
        "oecd.org", "imf.org", "worldbank.org", "europa.eu", "eurostat.ec.europa.eu",
        "fred.stlouisfed.org", "federalreserve.gov", "stats.oecd.org"
    }
    
    # Academic
    ACADEMIC_PATTERNS = [".edu", "arxiv.org", "ssrn.com", "nber.org", "jstor.org"]
    
    # Government
    GOV_PATTERNS = [".gov", ".gov.uk", ".gc.ca", ".gov.au"]
    
    # Think tanks (mixed partisan)
    THINK_TANKS = {
        "brookings.edu", "rand.org", "urban.org", "aei.org", "heritage.org",
        "cato.org", "cbpp.org", "epi.org", "americanprogress.org", "taxfoundation.org"
    }
    
    # Check classifications
    if any(d in domain for d in OFFICIAL_DOMAINS):
        return SourceClass.OFFICIAL_STATS
    
    if any(p in domain for p in ACADEMIC_PATTERNS):
        return SourceClass.PEER_REVIEW
    
    if domain in THINK_TANKS:
        return SourceClass.THINK_TANK
    
    if any(p in domain for p in GOV_PATTERNS):
        return SourceClass.GOV_MEMO
    
    return SourceClass.MEDIA


def classify_card_claim_type(card: Any) -> ClaimType:
    """Classify the type of claim in a card."""
    text = (getattr(card, 'claim', '') or 
            getattr(card, 'snippet', '') or 
            getattr(card, 'title', '')).lower()
    
    # Numeric indicators
    import re
    NUMERIC_PATTERN = re.compile(r'\d+(?:\.\d+)?%|\$[\d,]+|\d+(?:\.\d+)?\s*(?:percent|billion|million|trillion)')
    
    # Opinion/advocacy indicators
    OPINION_WORDS = {
        "should", "must", "need to", "ought", "believe", "argue", "contend",
        "advocate", "recommend", "suggest", "propose"
    }
    
    # Theory/mechanism indicators
    THEORY_WORDS = {
        "because", "causes", "leads to", "results in", "explains", "due to",
        "correlation", "relationship", "impact", "effect"
    }
    
    # Check patterns
    has_numbers = bool(NUMERIC_PATTERN.search(text))
    has_opinion = any(word in text for word in OPINION_WORDS)
    has_theory = any(word in text for word in THEORY_WORDS)
    
    # Classify based on patterns
    if has_numbers and not has_opinion:
        return ClaimType.NUMERIC_MEASURE
    elif has_opinion:
        return ClaimType.OPINION_ADVOCACY
    elif has_theory:
        return ClaimType.MECHANISM_OR_THEORY
    else:
        return ClaimType.NEWS_CONTEXT


def source_aware_cluster_paraphrases(
    cards: List[Any], 
    similarity_threshold: float = 0.40,
    strict_numeric: bool = True
) -> List[Dict[str, Any]]:
    """
    Cluster cards with source-aware constraints.
    
    Args:
        cards: List of evidence cards
        similarity_threshold: Similarity threshold for clustering
        strict_numeric: Use stricter threshold (0.62) for numeric claims
        
    Returns:
        List of clusters, each containing indices, domains, source_classes, claim_types
    """
    if not cards:
        return []
    
    # Import SBERT for similarity
    try:
        from research_system.tools.embed_cluster import embed_batch, cosine_similarity
    except ImportError:
        logger.warning("SBERT not available for clustering")
        return []
    
    # Classify all cards
    card_metadata = []
    for i, card in enumerate(cards):
        source_class = classify_card_source(card)
        claim_type = classify_card_claim_type(card)
        text = (getattr(card, 'claim', '') or 
                getattr(card, 'snippet', '') or 
                getattr(card, 'title', ''))
        domain = getattr(card, 'source_domain', 'unknown')
        
        card_metadata.append({
            'index': i,
            'text': text,
            'source_class': source_class,
            'claim_type': claim_type,
            'domain': domain
        })
    
    # Get embeddings
    texts = [m['text'] for m in card_metadata]
    embeddings = embed_batch(texts)
    
    # Group by claim type first
    type_groups = defaultdict(list)
    for i, meta in enumerate(card_metadata):
        type_groups[meta['claim_type']].append(i)
    
    # Cluster within each claim type
    clusters = []
    
    for claim_type, indices in type_groups.items():
        # Adjust threshold for numeric claims
        if claim_type == ClaimType.NUMERIC_MEASURE and strict_numeric:
            threshold = 0.62  # Stricter for numbers
        else:
            threshold = similarity_threshold
        
        # Hierarchical clustering within type
        type_clusters = []
        clustered = set()
        
        for i in indices:
            if i in clustered:
                continue
            
            cluster = [i]
            clustered.add(i)
            
            # Find similar cards of same type
            for j in indices:
                if j in clustered:
                    continue
                
                # Check source compatibility
                source_i = card_metadata[i]['source_class']
                source_j = card_metadata[j]['source_class']
                
                # Don't mix official stats with think tanks for numeric claims
                if claim_type == ClaimType.NUMERIC_MEASURE:
                    if (source_i == SourceClass.OFFICIAL_STATS and 
                        source_j == SourceClass.THINK_TANK):
                        continue
                    if (source_j == SourceClass.OFFICIAL_STATS and 
                        source_i == SourceClass.THINK_TANK):
                        continue
                
                # Check similarity
                sim = cosine_similarity(embeddings[i], embeddings[j])
                if sim >= threshold:
                    cluster.append(j)
                    clustered.add(j)
            
            # Only keep multi-card clusters or important singles
            if len(cluster) >= 2:
                type_clusters.append(cluster)
            elif card_metadata[i]['source_class'] in [SourceClass.OFFICIAL_STATS, SourceClass.PEER_REVIEW]:
                # Keep high-value singletons
                type_clusters.append(cluster)
        
        # Convert to cluster format
        for cluster_indices in type_clusters:
            domains = [card_metadata[i]['domain'] for i in cluster_indices]
            source_classes = [card_metadata[i]['source_class'].value for i in cluster_indices]
            
            clusters.append({
                'indices': cluster_indices,
                'size': len(cluster_indices),
                'domains': list(set(domains)),
                'source_classes': list(set(source_classes)),
                'claim_type': claim_type.value,
                'is_triangulated': len(set(domains)) >= 2
            })
    
    # Sort by quality score
    clusters.sort(key=lambda c: _score_cluster_quality(c), reverse=True)
    
    return clusters


def _score_cluster_quality(cluster: Dict[str, Any]) -> float:
    """Score a cluster based on quality factors."""
    score = 0.0
    
    # Size bonus
    score += cluster['size'] * 1.0
    
    # Domain diversity bonus
    score += len(cluster['domains']) * 2.0
    
    # Source quality bonus
    if 'official_stats' in cluster['source_classes']:
        score += 5.0
    if 'peer_review' in cluster['source_classes']:
        score += 3.0
    
    # Triangulation bonus
    if cluster['is_triangulated']:
        score += 3.0
    
    # Numeric claim bonus
    if cluster['claim_type'] == 'numeric_measure':
        score += 2.0
    
    return score


def filter_clusters_for_findings(
    clusters: List[Dict[str, Any]], 
    cards: List[Any],
    require_primary: bool = True
) -> List[Dict[str, Any]]:
    """
    Filter clusters suitable for Key Findings.
    
    Args:
        clusters: List of clusters from source_aware_cluster_paraphrases
        cards: Original evidence cards
        require_primary: Require at least one primary source
        
    Returns:
        Filtered list of high-quality clusters
    """
    filtered = []
    
    for cluster in clusters:
        # Skip opinion/advocacy for Key Findings
        if cluster['claim_type'] == 'opinion_advocacy':
            # Only allow if it has official sources too
            if 'official_stats' not in cluster['source_classes']:
                continue
        
        # Require triangulation for numeric claims
        if cluster['claim_type'] == 'numeric_measure':
            if not cluster['is_triangulated']:
                continue
        
        # Check for primary sources if required
        if require_primary:
            has_primary = any(
                getattr(cards[i], 'is_primary_source', False)
                for i in cluster['indices']
            )
            if not has_primary and 'official_stats' not in cluster['source_classes']:
                continue
        
        filtered.append(cluster)
    
    return filtered


def extract_cluster_representative(cluster: Dict[str, Any], cards: List[Any]) -> str:
    """
    Extract a representative claim from a cluster.
    
    Prefers claims from official sources and with numbers.
    """
    # Sort cards in cluster by source quality
    cluster_cards = [(i, cards[i]) for i in cluster['indices']]
    
    def card_priority(item):
        i, card = item
        score = 0
        
        # Prefer official sources
        source_class = classify_card_source(card)
        if source_class == SourceClass.OFFICIAL_STATS:
            score += 10
        elif source_class == SourceClass.PEER_REVIEW:
            score += 5
        
        # Prefer cards with numbers
        text = getattr(card, 'claim', '') or getattr(card, 'snippet', '')
        import re
        if re.search(r'\d+(?:\.\d+)?%|\$[\d,]+', text):
            score += 3
        
        # Prefer higher credibility
        score += getattr(card, 'credibility_score', 0.5) * 2
        
        return -score  # Negative for descending sort
    
    cluster_cards.sort(key=card_priority)
    
    # Get text from best card
    best_card = cluster_cards[0][1]
    text = (getattr(best_card, 'claim', '') or 
            getattr(best_card, 'snippet', '') or
            getattr(best_card, 'title', ''))
    
    return text.strip()