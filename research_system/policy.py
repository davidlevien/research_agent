from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List
from .models import Discipline

@dataclass
class Policy:
    connectors: List[str]
    anchor_templates: List[str]
    domain_priors: Dict[str, float]
    triangulation_min: float
    primary_share_min: float
    reachability_min: float

DEFAULT_PRIORS = {
    "doi.org":0.95,"arxiv.org":0.9,"nature.com":0.92,"science.org":0.92,
    "who.int":0.95,"cdc.gov":0.95,"fda.gov":0.94,"nih.gov":0.93,
    "oecd.org":0.9,"eurostat.ec.europa.eu":0.9,"imf.org":0.9,"fred.stlouisfed.org":0.9,
    "sec.gov":0.95,"edgar.sec.gov":0.95,
    "law.cornell.edu":0.9,"eur-lex.europa.eu":0.94,"courtlistener.com":0.88,
    "wttc.org":0.9,"iata.org":0.9,"unwto.org":0.92,"str.com":0.88,"costar.com":0.88,
    "nvd.nist.gov":0.95,"mitre.org":0.9
}

POLICIES: Dict[Discipline, Policy] = {
    Discipline.GENERAL: Policy(["crossref","openalex","gdelt"], [
        "{topic} site:doi.org", "{topic} 2024..2025 filetype:pdf", "{topic} site:.gov"
    ], DEFAULT_PRIORS, 0.35, 0.40, 0.90),
    Discipline.SCIENCE: Policy(["crossref","openalex"], [
        "{topic} site:arxiv.org", "{topic} site:doi.org", "{topic} replication dataset"
    ], DEFAULT_PRIORS, 0.45, 0.60, 0.90),
    Discipline.MEDICINE: Policy(["pubmed"], [
        "{topic} site:pubmed.ncbi.nlm.nih.gov", "{topic} randomized controlled trial 2020..2025",
        "{topic} site:who.int OR site:cdc.gov"
    ], DEFAULT_PRIORS, 0.50, 0.70, 0.95),
    Discipline.LAW_POLICY: Policy(["eurlex","courtlistener"], [
        "{topic} site:eur-lex.europa.eu", "{topic} site:law.cornell.edu", "{topic} \"Official Journal\" 2020..2025"
    ], DEFAULT_PRIORS, 0.40, 0.60, 0.95),
    Discipline.FINANCE_ECON: Policy(["fred","oecd","edgar"], [
        "{topic} site:fred.stlouisfed.org", "{topic} site:oecd.org 2024..2025 filetype:pdf", "{topic} site:sec.gov (10-k OR 10-q OR 8-k)"
    ], DEFAULT_PRIORS, 0.40, 0.60, 0.95),
    Discipline.TECH_SOFTWARE: Policy(["github","rfc"], [
        "{topic} site:github.com release notes", "{topic} site:ietf.org rfc", "{topic} site:pypi.org OR site:npmjs.com"
    ], DEFAULT_PRIORS, 0.30, 0.40, 0.90),
    Discipline.SECURITY: Policy(["nvd","cvefeed"], [
        "{topic} site:nvd.nist.gov", "{topic} CVE- 2024..2025", "{topic} site:mitre.org CWE"
    ], DEFAULT_PRIORS, 0.50, 0.70, 0.95),
    Discipline.TRAVEL_TOURISM: Policy(["unwto","wttc","iata","gdelt"], [
        "{topic} site:unwto.org barometer", "{topic} site:wttc.org economic impact 2025", "{topic} site:iata.org air passenger market analysis pdf"
    ], DEFAULT_PRIORS, 0.35, 0.50, 0.80),
    Discipline.CLIMATE_ENV: Policy(["noaa","nasa"], [
        "{topic} site:ipcc.ch", "{topic} site:noaa.gov 2024..2025", "{topic} site:data.giss.nasa.gov"
    ], DEFAULT_PRIORS, 0.45, 0.60, 0.95),
}

def get_policy(discipline: Discipline) -> Policy:
    """Get the policy for a given discipline"""
    return POLICIES.get(discipline, POLICIES[Discipline.GENERAL])