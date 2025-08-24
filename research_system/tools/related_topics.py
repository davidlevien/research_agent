"""Phrase-level related topic extraction from evidence content."""

import re
from collections import Counter
from typing import List, Dict, Any

STOP = set("""the a an and or but nor so yet to of in on at by for with from into over under within without across per via is are was were be been being this that those these it its their our your""".split())

def candidate_ngrams(text: str, n=(2,3)):
    toks = [t.lower() for t in re.findall(r"[A-Za-z][A-Za-z\-]+", text)]
    toks = [t for t in toks if t not in STOP and len(t) >= 3]
    for k in range(n[0], n[1]+1):
        for i in range(len(toks)-k+1):
            yield " ".join(toks[i:i+k])

def top_phrases(corpus: str, k=10):
    cnt = Counter(candidate_ngrams(corpus))
    out = []
    for phrase, c in cnt.most_common(100):
        if any(len(t) < 3 for t in phrase.split()): continue
        out.append((phrase, c))
        if len(out) >= k: break
    return out

def extract_related_topics(cards: List[Any], max_topics: int = 10) -> List[Dict[str, Any]]:
    """Extract phrase-level related topics from evidence cards."""
    if not cards:
        return []
    
    # Collect all text content into a corpus
    corpus_parts = []
    for card in cards:
        text_parts = []
        if hasattr(card, 'title') and card.title:
            text_parts.append(card.title)
        if hasattr(card, 'snippet') and card.snippet:
            text_parts.append(card.snippet)
        if hasattr(card, 'quote_span') and card.quote_span:
            if isinstance(card.quote_span, list):
                text_parts.extend(card.quote_span)
            else:
                text_parts.append(card.quote_span)
        if hasattr(card, 'text') and card.text:
            text_parts.append(card.text[:500])  # Limit to avoid noise
        
        if text_parts:
            corpus_parts.append(' '.join(text_parts))
    
    if not corpus_parts:
        return []
    
    # Create single corpus for phrase extraction
    corpus = ' '.join(corpus_parts)
    
    # Extract top phrases
    phrases = top_phrases(corpus, k=max_topics)
    
    # Convert to expected format
    topics = []
    for phrase, count in phrases:
        # Count supporting sources
        supporting_sources = sum(1 for text in corpus_parts if phrase.lower() in text.lower())
        
        topics.append({
            "phrase": phrase,
            "frequency": count,
            "supporting_sources": supporting_sources,
            "relevance_score": min(1.0, count / max(len(cards), 1))
        })
    
    return topics