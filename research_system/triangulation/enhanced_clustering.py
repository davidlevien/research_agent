"""Enhanced clustering with domain constraints for stats intent."""

import re
import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


@dataclass
class ClusterMember:
    """A member of a cluster."""
    index: int
    text: str
    domain: str
    is_primary: bool
    card: Any


@dataclass 
class Cluster:
    """A cluster of related claims."""
    members: List[ClusterMember]
    representative: Optional[ClusterMember] = None
    domains: Set[str] = None
    primary_domains: Set[str] = None
    
    def __post_init__(self):
        if self.domains is None:
            self.domains = {m.domain for m in self.members}
        if self.primary_domains is None:
            self.primary_domains = {m.domain for m in self.members if m.is_primary}


def normalize(text: str) -> str:
    """Normalize text for clustering."""
    if not text:
        return ""
    
    text = text.lower()
    
    # Normalize years
    text = re.sub(r'\b(19|20)\d{2}\b', 'YEAR', text)
    
    # Normalize percentages
    text = re.sub(r'\d+(?:\.\d+)?%', 'PERCENT', text)
    
    # Normalize numbers
    text = re.sub(r'\b\d+(?:,\d{3})*(?:\.\d+)?\b', 'NUMBER', text)
    
    # Clean punctuation
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # Collapse whitespace
    text = ' '.join(text.split())
    
    return text


def cluster_claims(cards: List[Any], intent: str, threshold: float = 0.40) -> List[Cluster]:
    """
    Cluster claims with intent-aware constraints.
    
    Args:
        cards: List of evidence cards
        intent: Research intent (e.g., "stats")
        threshold: Base similarity threshold
        
    Returns:
        List of Cluster objects
    """
    from research_system.config.settings import Settings
    settings = Settings()
    
    # Adjust threshold for stats
    use_threshold = 0.55 if intent == settings.STATS_INTENT else threshold
    
    # Compile topic regex for stats
    topic_re = None
    if intent == settings.STATS_INTENT:
        topic_re = re.compile(settings.STATS_TOPIC_REGEX, re.I)
    
    # Build cluster members
    members = []
    for i, card in enumerate(cards):
        text = getattr(card, 'claim', '') or getattr(card, 'snippet', '') or getattr(card, 'title', '')
        text = text.strip()
        
        # Filter off-topic for stats
        if intent == settings.STATS_INTENT and topic_re:
            if not topic_re.search(text):
                logger.debug(f"Dropping off-topic card {i}: {text[:50]}...")
                continue
        
        domain = getattr(card, 'source_domain', '').lower()
        is_primary = (
            getattr(card, 'is_primary_source', False) or
            domain in settings.STATS_ALLOWED_PRIMARY_DOMAINS
        )
        
        members.append(ClusterMember(
            index=i,
            text=text,
            domain=domain,
            is_primary=is_primary,
            card=card
        ))
    
    if not members:
        return []
    
    # Get embeddings
    try:
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        texts = [normalize(m.text) for m in members]
        embeddings = model.encode(texts)
    except Exception as e:
        logger.warning(f"SBERT encoding failed: {e}, falling back to keyword clustering")
        return _fallback_clustering(members, intent)
    
    # Hierarchical clustering
    from sklearn.metrics.pairwise import cosine_similarity
    similarities = cosine_similarity(embeddings)
    
    # Build clusters
    clusters = []
    clustered_indices = set()
    
    for i, member in enumerate(members):
        if i in clustered_indices:
            continue
        
        # Start new cluster
        cluster_members = [member]
        clustered_indices.add(i)
        
        # Find similar members
        for j, other in enumerate(members):
            if j <= i or j in clustered_indices:
                continue
            
            # Check similarity
            if similarities[i][j] >= use_threshold:
                cluster_members.append(other)
                clustered_indices.add(j)
        
        # Create cluster
        cluster = Cluster(members=cluster_members)
        
        # Pick representative based on source quality
        cluster.representative = pick_best_representative(cluster, intent, settings)
        
        clusters.append(cluster)
    
    # Filter clusters for stats intent
    if intent == settings.STATS_INTENT:
        clusters = filter_stats_clusters(clusters, settings)
    
    return clusters


def pick_best_representative(cluster: Cluster, intent: str, settings) -> ClusterMember:
    """
    Pick the best representative for a cluster.
    
    For stats intent, prefer primary/allowed domains and ban certain domains.
    """
    if intent != settings.STATS_INTENT:
        # For non-stats, prefer primary sources
        primary = [m for m in cluster.members if m.is_primary]
        if primary:
            return primary[0]
        return cluster.members[0]
    
    # For stats: strict representative selection
    
    # First try: allowed primary domains
    allowed = [
        m for m in cluster.members 
        if m.domain in settings.STATS_ALLOWED_PRIMARY_DOMAINS
    ]
    if allowed:
        # Sort by credibility if available
        allowed.sort(key=lambda m: getattr(m.card, 'credibility_score', 0.5), reverse=True)
        return allowed[0]
    
    # Second try: non-banned domains
    non_banned = [
        m for m in cluster.members
        if m.domain not in settings.STATS_BANNED_REPRESENTATIVE_DOMAINS
    ]
    if non_banned:
        # Prefer primary sources
        primary = [m for m in non_banned if m.is_primary]
        if primary:
            return primary[0]
        return non_banned[0]
    
    # Last resort: any member
    logger.warning(f"No suitable representative for cluster, using first member")
    return cluster.members[0]


def filter_stats_clusters(clusters: List[Cluster], settings) -> List[Cluster]:
    """
    Filter clusters for stats intent quality.
    
    Requires clusters to have ≥2 distinct primary domains.
    """
    filtered = []
    
    for cluster in clusters:
        # Count primary domains
        primary_domains = {
            m.domain for m in cluster.members
            if m.domain in settings.STATS_ALLOWED_PRIMARY_DOMAINS
        }
        
        if len(primary_domains) >= settings.STATS_CLUSTER_PRIMARY_DOMAINS_MIN:
            filtered.append(cluster)
        else:
            logger.debug(
                f"Dropping cluster with insufficient primary domains: "
                f"{len(primary_domains)} < {settings.STATS_CLUSTER_PRIMARY_DOMAINS_MIN}"
            )
    
    return filtered


def _fallback_clustering(members: List[ClusterMember], intent: str) -> List[Cluster]:
    """
    Fallback clustering using keyword overlap.
    """
    clusters = []
    clustered = set()
    
    for i, member in enumerate(members):
        if i in clustered:
            continue
        
        # Start new cluster
        cluster_members = [member]
        clustered.add(i)
        
        # Find similar by keyword overlap
        member_words = set(normalize(member.text).split())
        
        for j, other in enumerate(members):
            if j <= i or j in clustered:
                continue
            
            other_words = set(normalize(other.text).split())
            
            # Jaccard similarity
            intersection = len(member_words & other_words)
            union = len(member_words | other_words)
            
            if union > 0 and intersection / union >= 0.5:
                cluster_members.append(other)
                clustered.add(j)
        
        # Only keep multi-member clusters
        if len(cluster_members) >= 2:
            cluster = Cluster(members=cluster_members)
            clusters.append(cluster)
    
    return clusters


def sanitize_clusters(clusters: List[Cluster], intent: str) -> List[Cluster]:
    """
    Post-process clusters to ensure quality.
    
    For stats intent, enforces primary domain requirements.
    """
    from research_system.config.settings import Settings
    settings = Settings()
    
    kept = []
    
    for cluster in clusters:
        if intent == settings.STATS_INTENT:
            # Count primary domains
            primary_domains = {
                m.domain for m in cluster.members
                if m.domain in settings.STATS_ALLOWED_PRIMARY_DOMAINS
            }
            
            if len(primary_domains) < settings.STATS_CLUSTER_PRIMARY_DOMAINS_MIN:
                logger.debug(
                    f"Sanitizing: dropping cluster lacking primary domains "
                    f"({len(primary_domains)} < {settings.STATS_CLUSTER_PRIMARY_DOMAINS_MIN})"
                )
                continue
        
        kept.append(cluster)
    
    return kept