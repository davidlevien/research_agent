import re
from ..guardrails import load_guardrails
from .numbers import extract_numbers

def _sign(x):
    return 1 if x > 0 else (-1 if x < 0 else 0)

def _has_sign_conflict(a_text, b_text):
    g = load_guardrails()
    nums_a = extract_numbers(a_text)
    nums_b = extract_numbers(b_text)
    if not nums_a or not nums_b: 
        return False
    # Compare first scalars only (simple heuristic)
    va = nums_a[0].get("value")
    vb = nums_b[0].get("value")
    if va is None or vb is None:
        return False
    return _sign(va) != 0 and _sign(va) != _sign(vb)

def _has_antonym_conflict(a_text, b_text):
    g = load_guardrails()
    ta, tb = a_text.lower(), b_text.lower()
    for x, y in g["contradiction"]["antonym_pairs"]:
        if (x in ta and y in tb) or (y in ta and x in tb):
            return True
    return False

def prune_conflicts(cards, keep=6):
    kept = []
    for c in sorted(cards, key=lambda c: (getattr(c,"domain_count",1), getattr(c,"cred_score",0.0)), reverse=True):
        t = getattr(c,"text","") or ""
        if any(_has_antonym_conflict(t, k.text) or _has_sign_conflict(t, k.text) for k in kept):
            continue
        kept.append(c)
        if len(kept) >= keep:
            break
    return kept