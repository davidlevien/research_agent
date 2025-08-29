import re
from ..guardrails import load_guardrails

_URL_DOM_RE = re.compile(r"https?://([^/]+)/", re.I)

def domain_of(url: str) -> str:
    m = _URL_DOM_RE.match(url or "")
    return (m.group(1).lower() if m else "").strip()

def guess_content_type(card) -> str:
    """
    Heuristic, topic-agnostic. You can augment with ML later.
    """
    dom = (getattr(card, "source_domain", "") or domain_of(getattr(card, "url",""))).lower()
    title = (getattr(card, "title", "") or "").lower()
    text = (getattr(card, "text", "") or "").lower()

    if any(dom.endswith(tld) for tld in (".gov",".int")) or any(k in dom for k in ("oecd.org","imf.org","worldbank.org","ec.europa.eu","who.int","un.org")):
        if "dataset" in title or "data" in title or "table" in title:
            return "dataset"
        return "gov_brief"

    if any(s in dom for s in ("nature.com","sciencedirect.com","wiley.com","springer.com","oup.com","tandfonline.com","pnas.org","jamanetwork.com")):
        return "peer_reviewed_article"

    if "dataset" in title or "database" in title:
        return "dataset"

    if "press release" in title or "press-release" in getattr(card, "url",""):
        return "press_release"

    if "opinion" in title or "op-ed" in title or "oped" in title or "blog" in dom:
        return "op_ed"

    return "statistical_report" if re.search(r"\b(method|sample|regression|confidence|p-?value|standard error)\b", text) else "technical_note"

def is_rhetorical(card) -> bool:
    g = load_guardrails()
    text = (getattr(card, "text","") or "").lower()
    if not text:
        return False
    if any(tok in text for tok in g["lexicons"]["rhetorical_markers"]):
        return True
    if any(f" {w} " in f" {text} " for w in g["lexicons"]["stance_verbs"]):
        return True
    if any(f" {w} " in f" {text} " for w in g["lexicons"]["subjective_adjectives"]):
        return True
    return False

def passes_content_policy(card) -> bool:
    g = load_guardrails()
    ct = guess_content_type(card)
    if ct in set(g["text_types"]["block_content_types"]):
        return False
    if g["text_types"]["allow_content_types"] and ct not in set(g["text_types"]["allow_content_types"]):
        # fail-closed to allowed list if provided
        return False
    return not is_rhetorical(card)