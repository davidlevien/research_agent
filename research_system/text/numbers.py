import re
import math
from ..guardrails import load_guardrails

NUM_PAT = re.compile(
    r"""
    (?P<prefix>\$|€|£)?\s*
    (?P<val>[+-]?\d{1,3}(?:,\d{3})*(?:\.\d+)?|[+-]?\d+(?:\.\d+)?)
    \s*(?P<unit>%|pp|ppt|bps|per\s?100k|per\s?capita|million|billion|trillion|m|bn|t)?\b
    """,
    re.I | re.VERBOSE,
)

RANGE_PAT = re.compile(
    r"(?P<a>\d+(?:\.\d+)?)\s*[-–]\s*(?P<b>\d+(?:\.\d+)?)\s*(?P<unit>%|pp|bps|m|bn|t)?",
    re.I
)

def _norm_val(s: str) -> float:
    return float(s.replace(",", ""))

def extract_numbers(text: str):
    if not text:
        return []
    out = []
    for m in NUM_PAT.finditer(text):
        prefix = (m.group("prefix") or "").strip()
        val = _norm_val(m.group("val"))
        unit = (m.group("unit") or "").lower().replace("bn","billion").replace("m","million").replace("t","trillion")
        out.append({"value": val, "unit": unit, "currency": prefix})
    for m in RANGE_PAT.finditer(text):
        a, b = float(m.group("a")), float(m.group("b"))
        unit = (m.group("unit") or "").lower()
        out.append({"value_min": min(a,b), "value_max": max(a,b), "unit": unit})
    return out

def pick_salient_numbers(nums):
    # magnitude-first, then presence of unit/currency
    def score(n):
        v = abs(n.get("value", (n.get("value_min",0)+n.get("value_max",0))/2))
        u = 0.5 if n.get("unit") else 0.0
        c = 0.25 if n.get("currency") else 0.0
        return (v, u, c)
    return sorted(nums, key=score, reverse=True)

def as_markdown_bullets(claims, max_items=None):
    g = load_guardrails()
    cap = max_items or int(g["numerics"]["max_items"])
    items = []
    seen = set()
    for c in claims:
        nums = pick_salient_numbers(extract_numbers(getattr(c,"text","") or ""))
        if not nums:
            continue
        src = getattr(c,"source",{}) or {}
        url = src.get("url") or getattr(c,"url","") or ""
        if not url:
            continue
        head = " ".join((getattr(c,"text","") or "").split())[:220]
        key = (head.lower(), tuple((n.get("value"), n.get("unit")) for n in nums[:2]))
        if key in seen:
            continue
        seen.add(key)
        lead = nums[0]
        num_str = (
            f"{lead.get('currency','')}{lead['value']:.6g} {lead.get('unit','')}".strip()
            if "value" in lead else
            f"{lead.get('value_min'):.6g}–{lead.get('value_max'):.6g} {lead.get('unit','')}".strip()
        )
        items.append(f"- **{num_str}** — {head} [[source]({url})]")
        if len(items) >= cap:
            break
    return "\n".join(items) if items else "- _No reliable numeric statements passed filters._"