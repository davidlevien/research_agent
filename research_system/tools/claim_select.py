from __future__ import annotations
import re
from typing import List

try:
    from nltk.tokenize import sent_tokenize
    USE_NLTK = True
except ImportError:
    USE_NLTK = False

_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9(])')

# Expanded metric hints for tourism domain
METRIC_HINTS = tuple(m.lower() for m in [
    "arrival","international tourist","occupancy","spend","expenditure",
    "revenue","gdp","passenger","traffic","capacity","load factor","visitation",
    "tourism","visitor","recovery","growth","decline","increase","decrease"
])

# Expanded period patterns
PERIOD_RX = r"\b(20\d{2}|Q[1-4]\s*20\d{2}|H[12]\s*20\d{2}|FY\s*20\d{2}|first quarter of 20\d{2}|second quarter of 20\d{2}|third quarter of 20\d{2}|fourth quarter of 20\d{2})\b"

def select_claim_sentences(text: str, max_sentences: int = 2, max_len: int = 240) -> List[str]:
    if not text:
        return []
    
    # Use NLTK if available for better sentence splitting
    if USE_NLTK:
        try:
            candidates = sent_tokenize(text.strip())[:15]
        except:
            candidates = _SENTENCE_SPLIT.split(text.strip())[:15]
    else:
        candidates = _SENTENCE_SPLIT.split(text.strip())[:15]
    
    if not candidates:
        return []
    
    def score(s: str) -> int:
        sc = 0
        ls = s.lower()
        if re.search(r"\d", s): 
            sc += 1
        if re.search(PERIOD_RX, ls, re.I): 
            sc += 1
        if any(h in ls for h in METRIC_HINTS): 
            sc += 1
        return sc
    
    ranked = sorted(candidates, key=score, reverse=True)
    best = [x for x in ranked if score(x) >= 2][:max_sentences]
    if not best:
        # Fallback to sentences with at least numbers
        best = [x for x in ranked if re.search(r"\d", x)][:1]
    
    out = []
    for s in best:
        s = s.strip()
        if s:
            out.append(s[:max_len])
        if len(out) >= max_sentences:
            break
    
    return out