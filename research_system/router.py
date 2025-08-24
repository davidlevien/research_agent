from __future__ import annotations
import re
from .models import Discipline

_PATTERNS = [
    (Discipline.MEDICINE, r"\b(pubmed|pmid|who|cdc|fda|clinical|trial|efficacy)\b"),
    (Discipline.SCIENCE, r"\b(arxiv|doi|preprint|journal|dataset|replication)\b"),
    (Discipline.LAW_POLICY, r"\b(eur-lex|usc\b|§|directive|regulation|case law)\b"),
    (Discipline.FINANCE_ECON, r"\b(sec\.gov|10-k|10-q|edgar|fred|oecd|gdp|cpi|yoy|qoq)\b"),
    (Discipline.TECH_SOFTWARE, r"\b(github|rfc|ietf|api|release notes|benchmark)\b"),
    (Discipline.SECURITY, r"\b(cve-\d{4}-\d+|cwe-\d+|nvd|mitre)\b"),
    (Discipline.TRAVEL_TOURISM, r"\b(unwto|iata|wttc|occupancy|tourism|airline|str\b)\b"),
    (Discipline.CLIMATE_ENV, r"\b(ipcc|noaa|nasa|emissions|ppm|ghg|cop\d+)\b"),
]

def route_topic(topic: str) -> Discipline:
    t = (topic or "").lower()
    for disc, pat in _PATTERNS:
        if re.search(pat, t):
            return disc
    return Discipline.GENERAL