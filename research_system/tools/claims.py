"""
Claim canonicalization and semantic clustering for improved triangulation
"""

from __future__ import annotations
import re
import hashlib
from typing import Optional, List, Set
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import AgglomerativeClustering

_STOP = set("""
the a an of for with from into about across among between against toward upon
and or but nor so yet to in on at by as per via vs versus report index trend
global market travel tourism tech technology airline hotel flight booking
""".split())

_MONTHS = r"(jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|jun(e)?|jul(y)?|aug(ust)?|sep(t|tember)?|oct(ober)?|nov(ember)?|dec(ember)?)"

def _normalize_text(t: str) -> str:
    """Normalize text for claim matching"""
    t = t.lower()
    # Normalize numbers and money/percent units
    t = re.sub(r"\$?\b(\d{1,3}(?:[,.\s]\d{3})+|\d+(?:\.\d+)?)\s*(billion|bn)\b", " NUM_B ", t, flags=re.IGNORECASE)
    t = re.sub(r"\$?\b(\d{1,3}(?:[,.\s]\d{3})+|\d+(?:\.\d+)?)\s*(million|mn|m)\b", " NUM_M ", t, flags=re.IGNORECASE)
    t = re.sub(r"\$?\b(\d{1,3}(?:[,.\s]\d{3})+|\d+(?:\.\d+)?)\b", " NUM ", t)
    t = re.sub(r"\b(\d{1,2})\s*%\b", " NUM_PCT ", t)
    # Collapse dates to years; drop day+month noise
    t = re.sub(rf"\b\d{{1,2}}\s+{_MONTHS}\s+\d{{4}}\b", " YEAR ", t, flags=re.IGNORECASE)
    t = re.sub(rf"\b{_MONTHS}\s+\d{{4}}\b", " YEAR ", t, flags=re.IGNORECASE)
    t = re.sub(r"\bq[1-4]\s*20\d{2}\b", " YEAR_Q ", t, flags=re.IGNORECASE)
    t = re.sub(r"\b20\d{2}\b", " YEAR ", t)
    # Remove punctuation
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    # Drop stopwords, collapse whitespace
    toks = [w for w in t.split() if w not in _STOP and len(w) > 2]
    return " ".join(toks)

def canonical_claim_key(text: str, max_len: int = 240) -> Optional[str]:
    """
    Generate a stable key for a claim by normalizing numbers/dates and
    trimming boilerplate. Same fact across sources → same key.
    """
    if not text:
        return None
    norm = _normalize_text(text)[:max_len]
    if not norm.strip():
        return None
    # Hash to fixed-length key (compare by hash + prefix to reduce collisions)
    prefix = norm[:64]
    digest = hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}|{digest}"

def cluster_claims_sbert(texts: List[str], min_size: int = 2, cos_threshold: float = 0.86) -> List[Set[int]]:
    """
    Cluster claims using SBERT embeddings for semantic similarity.
    Returns list of sets, where each set contains indices of similar claims.
    """
    if not texts or len(texts) < 2:
        return []
    
    try:
        # Use a lightweight model for fast inference
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        
        # Calculate pairwise cosine similarity
        similarity_matrix = cosine_similarity(embeddings)
        
        # Convert cosine threshold to distance threshold for clustering
        distance_threshold = 1 - cos_threshold
        distance_matrix = 1 - similarity_matrix
        
        # Perform agglomerative clustering
        clustering = AgglomerativeClustering(
            n_clusters=None,
            metric="precomputed",
            linkage="average",
            distance_threshold=distance_threshold
        )
        
        labels = clustering.fit_predict(distance_matrix)
        
        # Group indices by cluster label
        clusters = {}
        for idx, label in enumerate(labels):
            clusters.setdefault(label, set()).add(idx)
        
        # Return only clusters with minimum size
        return [indices for indices in clusters.values() if len(indices) >= min_size]
        
    except Exception as e:
        # Fallback to empty clusters if SBERT fails
        print(f"SBERT clustering failed: {e}")
        return []