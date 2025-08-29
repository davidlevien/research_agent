PRIMARY_SEEDS = [
    "site:.gov", "site:.int", "site:.edu",
    "site:oecd.org", "site:worldbank.org", "site:imf.org",
    "site:ec.europa.eu", "site:eurostat.ec.europa.eu",
    "site:who.int", "site:un.org"
]

def normalize_site(token: str) -> str:
    t = token.lower()
    # Avoid site:*.gov etc. which many engines mishandle
    if t in ("*.gov","site:*.gov","site:gov"): return "site:.gov"
    if t in ("*.int","site:*.int","site:int"): return "site:.int"
    if t in ("*.edu","site:*.edu","site:edu"): return "site:.edu"
    return t if t.startswith("site:") else f"site:{t}"

def build_queries(topic: str):
    t = topic.strip()
    qs = [
        t,
        f"{t} statistics",
        f"{t} data",
        f"{t} filetype:pdf 2010..2035",
    ]
    qs += [f"{t} {normalize_site(s)}" for s in PRIMARY_SEEDS]
    return qs