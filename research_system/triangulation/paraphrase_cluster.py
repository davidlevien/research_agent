import re
import os
from collections import defaultdict
from typing import List, Dict, Any, Set

# Global threshold that can be adjusted
# v8.21.0: Lower default threshold for better broad topic triangulation
THRESHOLD = float(os.getenv("TRI_PARA_THRESHOLD", "0.35"))

def set_threshold(v: float):
    """Set the global paraphrase clustering threshold."""
    global THRESHOLD
    THRESHOLD = v

def _numeric_tokens(text: str) -> Set[str]:
    """v8.21.0: Extract numeric/year tokens for enhanced clustering."""
    if not text:
        return set()
    # Find years, percentages, and significant numbers
    return set(re.findall(r"\b(?:\d+(?:\.\d+)?%?|\d{4})\b", text))

def _norm_for_para(s: str) -> str:
    """Normalize text for paraphrase detection"""
    if not s: return ""
    s = s.lower()
    # Normalize temporal expressions
    s = re.sub(r"\b(20\d{2})\b", " YEAR ", s)
    s = re.sub(r"\bq([1-4])\s*20\d{2}\b", r" Q\1 YEAR ", s)
    s = re.sub(r"\bh([12])\s*20\d{2}\b", r" H\1 YEAR ", s)
    s = re.sub(r"\bfy\s*20\d{2}\b", " FY YEAR ", s)
    # Normalize percentages and numbers
    s = re.sub(r"\b\d+(?:\.\d+)?\s*%\b", " PCT ", s)
    s = re.sub(r"\b\d+(?:\.\d+)?\b", " NUM ", s)
    # Clean up non-alphanumeric
    s = re.sub(r"[^a-z0-9%\- ]+", " ", s)
    return " ".join(s.split())

def cluster_paraphrases(cards: List[Any]) -> List[Dict[str, Any]]:
    """
    Cluster evidence cards by paraphrase similarity
    Returns list of clusters with indices and domains
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Define what looks like a claim (has numbers, dates, or percentages)
    CLAIMISH = re.compile(r'\b(?:\d{1,3}(?:\.\d+)?%|\d{4}|Q[1-4]\s*\d{4}|million|billion|trillion)\b', re.I)
    
    def is_claimish(text: str) -> bool:
        """Check if text contains claim-like patterns."""
        return bool(text and CLAIMISH.search(text))
    
    # Extract texts, preferring quote spans
    texts_raw = []
    valid_indices = []
    
    for i, c in enumerate(cards):
        text = getattr(c, "quote_span", None) or c.claim or c.snippet or c.title or ""
        if is_claimish(text):
            texts_raw.append(text)
            valid_indices.append(i)
    
    # Normalize texts
    texts = [_norm_for_para(t) for t in texts_raw]
    clusters = []
    
    logger.info(f"\n=== TRIANGULATION DEBUG ===")
    logger.info(f"Processing {len(cards)} cards, {len(valid_indices)} with claim-like text")
    
    # Log sample texts and domains
    for j, i in enumerate(valid_indices[:5]):
        card = cards[i]
        logger.info(f"Card {i}: domain={card.source_domain}, text='{texts_raw[j][:100]}...'")
        logger.info(f"  Normalized: '{texts[j][:100]}...'")

    try:
        # Use cached embeddings model
        from .embeddings import encode
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity
        
        # Encode all texts at once using cached model
        emb = encode(texts, normalize=True)
        sim = cosine_similarity(emb)
        
        # Union-find for clustering
        parent = list(range(len(texts)))
        def find(x):
            while parent[x] != x: 
                parent[x] = parent[parent[x]]  # Path compression
                x = parent[x]
            return x
        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb: parent[rb] = ra

        # Calculate adaptive threshold based on similarity distribution
        def calculate_adaptive_threshold():
            # Get all non-diagonal similarity values
            n = len(texts)
            if n <= 1:
                return THRESHOLD
            
            sim_values = []
            for i in range(n):
                for j in range(i+1, n):
                    sim_values.append(sim[i,j])
            
            if not sim_values:
                return THRESHOLD
            
            # Use percentile-based threshold (70th percentile)
            import numpy as np
            percentile_70 = float(np.percentile(sim_values, 70))
            
            # Bound between 0.32 and 0.48 for stability
            adaptive_threshold = max(0.32, min(0.48, percentile_70))
            
            logger.info(f"Adaptive threshold: {adaptive_threshold:.3f} (70th percentile of similarities)")
            return adaptive_threshold
        
        # Use adaptive threshold or fallback to global
        TH = calculate_adaptive_threshold() if len(texts) > 5 else THRESHOLD
        n = len(texts)
        
        logger.info(f"\nUsing SBERT with threshold {TH}")
        logger.info(f"Similarity matrix sample (first 5x5):")
        for i in range(min(5, n)):
            sim_row = [f"{sim[i,j]:.3f}" for j in range(min(5, n))]
            logger.info(f"  Row {i}: {' '.join(sim_row)}")
        
        # Find high similarity pairs
        high_sim_pairs = []
        for i in range(n):
            for j in range(i+1, n):
                similarity = sim[i, j]
                
                # v8.21.0: Numeric/keyword boost for near-misses
                if similarity < TH and similarity >= 0.25:
                    # Check if texts share significant numeric tokens
                    ni = _numeric_tokens(texts_raw[i])
                    nj = _numeric_tokens(texts_raw[j])
                    shared_nums = len(ni.intersection(nj))
                    
                    if shared_nums >= 2:
                        # Boost similarity to threshold if they share key numbers/years
                        logger.info(f"Boosting similarity {similarity:.3f} -> {TH} for cards {i},{j} (shared {shared_nums} numeric tokens)")
                        similarity = TH
                
                if similarity >= TH:
                    union(i, j)
                    high_sim_pairs.append((i, j, similarity))
                elif similarity >= 0.30:  # Log near-misses
                    logger.info(f"Near-miss similarity {similarity:.3f} between cards {i} and {j}")
        
        logger.info(f"Found {len(high_sim_pairs)} pairs above threshold {TH}")
        for i, j, score in high_sim_pairs[:5]:
            logger.info(f"  Pair ({i},{j}): similarity={score:.3f}")
            logger.info(f"    Card {i}: {texts_raw[i][:80]}...")
            logger.info(f"    Card {j}: {texts_raw[j][:80]}...")

        # Group by root
        groups = defaultdict(list)
        for i in range(n): 
            groups[find(i)].append(i)

        # Build clusters (only multi-domain ones matter for triangulation)
        logger.info(f"\nFound {len(groups)} raw groups")
        
        for gidx, members in groups.items():
            if len(members) < 2: 
                logger.debug(f"Skipping group {gidx}: only {len(members)} member")
                continue
            
            # Map back to original card indices
            original_indices = [valid_indices[m] for m in members]
            doms = {cards[idx].source_domain for idx in original_indices}
            logger.info(f"Group {gidx}: {len(members)} members from domains {doms}")
            
            if len(doms) < 2: 
                logger.info(f"  -> Skipping: single-domain cluster (all from {list(doms)[0]})")
                continue  # Skip single-domain clusters
            
            logger.info(f"  -> Multi-domain cluster found!")
            
            # Get representative claim (highest credibility), cleaned of HTML
            best_local_idx = max(members, key=lambda m: cards[valid_indices[m]].credibility_score)
            # Clean HTML tags from representative text
            html_tag_pattern = re.compile(r'<[^>]+>')
            raw_text = texts_raw[best_local_idx]
            clean_text = html_tag_pattern.sub('', raw_text)
            representative = clean_text[:240]
            
            clusters.append({
                "indices": original_indices, 
                "domains": sorted(doms),
                "representative_claim": representative,
                "size": len(original_indices)
            })
        
        logger.info(f"\nFinal triangulation results: {len(clusters)} multi-domain clusters")
        for i, cluster in enumerate(clusters):
            logger.info(f"Cluster {i}: {cluster['size']} cards from {cluster['domains']}")
            logger.info(f"  Representative: {cluster['representative_claim'][:100]}...")
        
        return clusters
        
    except Exception:
        # Fallback: token Jaccard similarity
        def tok(s): return set(s.split())
        def jacc(a, b):
            A, B = tok(a), tok(b)
            if not A or not B: return 0.0
            return len(A & B) / len(A | B)
        
        TH = 0.32  # Lower threshold for token-based
        parent = list(range(len(texts)))
        def find(x):
            while parent[x] != x: 
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb: parent[rb] = ra
            
        n = len(texts)
        for i in range(n):
            for j in range(i+1, n):
                if jacc(texts[i], texts[j]) >= TH:
                    union(i, j)
                    
        groups = defaultdict(list)
        for i in range(n): 
            groups[find(i)].append(i)
            
        clusters = []
        for members in groups.values():
            if len(members) < 2: continue
            doms = {cards[i].source_domain for i in members}
            if len(doms) < 2: continue
            
            best_idx = max(members, key=lambda i: cards[i].credibility_score)
            representative = texts_raw[best_idx][:240]
            
            clusters.append({
                "indices": members, 
                "domains": sorted(doms),
                "representative_claim": representative,
                "size": len(members)
            })
        
        logger.info(f"\nFinal triangulation results: {len(clusters)} multi-domain clusters")
        for i, cluster in enumerate(clusters):
            logger.info(f"Cluster {i}: {cluster['size']} cards from {cluster['domains']}")
            logger.info(f"  Representative: {cluster['representative_claim'][:100]}...")
        
        return clusters