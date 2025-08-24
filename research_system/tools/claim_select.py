from __future__ import annotations
import re
from typing import List

_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9(])')

# Prefer sentences with numbers, %, quarters, years — these cluster best.
_PRIORITY_PAT = re.compile(
    r'\b(\d{4}|20\d{2}|q[1-4]|quarter|percent|%|billion|million|bn|mn|m|k)\b',
    re.I
)

def select_claim_sentences(text: str, max_sentences: int = 2, max_len: int = 240) -> List[str]:
    if not text:
        return []
    sents = _SENTENCE_SPLIT.split(text.strip())
    if not sents:
        return []
    # Rank: priority token presence → length within reasonable bounds (40..240)
    ranked = sorted(
        sents,
        key=lambda s: (
            0 if _PRIORITY_PAT.search(s or "") else 1,
            abs(len(s) - 140)  # center around tweet-length for good clustering
        )
    )
    out = []
    for s in ranked:
        s = s.strip()
        if not s:
            continue
        out.append(s[:max_len])
        if len(out) >= max_sentences:
            break
    if not out:
        out = [sents[0][:max_len]]
    return out