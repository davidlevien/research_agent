import re
from ..guardrails import load_guardrails
from ..text.texttype import passes_content_policy, guess_content_type, domain_of

def pick_representative(cards):
    g = load_guardrails()
    best = None
    for c in cards:
        if not passes_content_policy(c):
            continue
        txt = (getattr(c,"text","") or "")
        if not re.search(r"\d|percent|percentage|rate|ratio|index|coefficient|odds|hazard", txt, re.I):
            continue
        dom = (getattr(c,"source_domain","") or domain_of(getattr(c,"url",""))).lower()
        primary = any(dom.endswith(tld) for tld in (".gov",".int",".edu")) or any(k in dom for k in g["credibility"]["primary_domains"])
        score = getattr(c,"triangulation_strength",0.0) + getattr(c,"cred_score",0.0) + (g["credibility"]["prefer_primary_boost"] if primary else 0.0)
        if (best is None) or (score > best[0]):
            best = (score, c)
    return best[1] if best else None