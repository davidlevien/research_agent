import re
from collections import defaultdict
from typing import List, Dict, Any

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
    
    texts_raw = [getattr(c, "quote_span", None) or c.claim or c.snippet or c.title or "" for c in cards]
    texts = [_norm_for_para(t) for t in texts_raw]
    idx_map = list(range(len(texts)))
    clusters = []
    
    logger.info(f"\n=== TRIANGULATION DEBUG ===")
    logger.info(f"Processing {len(cards)} cards for triangulation")
    
    # Log sample texts and domains
    for i, card in enumerate(cards[:5]):
        logger.info(f"Card {i}: domain={card.source_domain}, text='{texts_raw[i][:100]}...'")
        logger.info(f"  Normalized: '{texts[i][:100]}...'")

    try:
        # Try SBERT for semantic similarity
        from sentence_transformers import SentenceTransformer, util
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        emb = model.encode(texts, normalize_embeddings=True, batch_size=64, show_progress_bar=False)
        sim = util.cos_sim(emb, emb).cpu().numpy()
        
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

        # Threshold for similarity (tuned for tourism domain)
        TH = 0.40
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
                if sim[i, j] >= TH:
                    union(i, j)
                    high_sim_pairs.append((i, j, sim[i,j]))
                elif sim[i, j] >= 0.30:  # Log near-misses
                    logger.info(f"Near-miss similarity {sim[i,j]:.3f} between cards {i} and {j}")
        
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
            
            doms = {cards[i].source_domain for i in members}
            logger.info(f"Group {gidx}: {len(members)} members from domains {doms}")
            
            if len(doms) < 2: 
                logger.info(f"  -> Skipping: single-domain cluster (all from {list(doms)[0]})")
                continue  # Skip single-domain clusters
            
            logger.info(f"  -> Multi-domain cluster found!")
            
            # Get representative claim (highest credibility)
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