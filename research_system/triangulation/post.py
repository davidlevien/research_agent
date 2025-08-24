"""Post-processing utilities for triangulation results."""


def sanitize_paraphrase_clusters(clusters, cards, max_frac=0.5):
    """
    Sanitize paraphrase clusters to prevent over-merging and ensure quality.
    
    Args:
        clusters: List of paraphrase clusters
        cards: List of evidence cards
        max_frac: Maximum fraction of cards that can be in a single cluster
        
    Returns:
        List of sanitized clusters
    """
    N = len(cards)
    out = []
    
    for c in clusters or []:
        idx = c.get("indices", [])
        
        # Extract domains for this cluster
        doms = {cards[i].source_domain for i in idx if i < len(cards)}
        
        # Must be multi-domain
        if len(doms) < 2:
            continue
            
        # Cap giant clusters
        if len(idx) > max(2, int(max_frac * N)):
            continue
            
        out.append(c)
        
    return out