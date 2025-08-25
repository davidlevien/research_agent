from __future__ import annotations
import re
import yaml
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

# Load indicator aliases from YAML configuration
def _load_aliases():
    yaml_path = Path(__file__).parent.parent / "resources" / "indicator_aliases.yaml"
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

_ALIASES = _load_aliases()

_YEAR = re.compile(r"\b(19|20)\d{2}\b")

@dataclass(frozen=True)
class StructuredKey:
    indicator: str   # canonical indicator key, e.g., "gdp_current_usd"
    period: str      # e.g., "2024" or "2024-Q1"
    entity: str      # e.g., "world" unless a country is extracted

def identify_indicator(text: str, provider: str, code_hint: Optional[str]=None) -> Optional[str]:
    t = (text or "").lower()
    # 1) code match
    for canon, m in _ALIASES.items():
        for c in m.get(provider, []):
            if c.lower() in t or (code_hint and c.lower() in code_hint.lower()):
                return canon
    # 2) alias phrase match
    for canon, m in _ALIASES.items():
        for phr in m.get("aliases", []):
            if phr in t:
                return canon
    return None

def extract_period(text: str) -> Optional[str]:
    # year or quarter; expand as needed
    m = _YEAR.search(text or "")
    return m.group(0) if m else None

def to_structured_key(card) -> Optional[StructuredKey]:
    text = " ".join(filter(None, [getattr(card, "claim", None), getattr(card, "snippet", None), getattr(card, "title", None)]))
    provider = (getattr(card, "provider", "") or "").lower()
    meta = getattr(card, "metadata", {}) or {}
    code_hint = meta.get("indicator") or meta.get("dataset_code")
    ind = identify_indicator(text, provider, code_hint=code_hint)
    if not ind:
        return None
    period = extract_period(text) or meta.get("year") or meta.get("period") or "unknown"
    return StructuredKey(indicator=ind, period=period, entity="world")