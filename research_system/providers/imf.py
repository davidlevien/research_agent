"""IMF provider for international financial statistics."""

from __future__ import annotations
from typing import List, Dict, Any
from .http import http_json
import logging

logger = logging.getLogger(__name__)

_DATAFLOW = "https://dataservices.imf.org/REST/SDMX_JSON.svc/Dataflow"

def _dataflows() -> List[Dict[str, Any]]:
    """Fetch IMF dataflows catalog."""
    try:
        data = http_json("GET", _DATAFLOW)
        # Typically {"Structure":{"Dataflows":{"Dataflow":[...]}}}
        flows = (((data.get("Structure") or {}).get("Dataflows") or {}).get("Dataflow")) or []
        out = []
        
        for f in flows:
            key = f.get("Key") or f.get("@id") or f.get("id")
            nm = f.get("Name") or []
            name = ""
            if isinstance(nm, list) and nm:
                name = nm[0].get("$") or nm[0].get("value") or ""
            elif isinstance(nm, str):
                name = nm
            out.append({"code": key, "name": name})
        
        return out
    except Exception as e:
        logger.warning(f"IMF dataflows fetch failed: {e}")
        return []

def search_imf(query: str, limit: int = 25) -> List[Dict[str, Any]]:
    """Search IMF datasets by relevance to query."""
    q = (query or "").lower()
    flows = _dataflows()
    
    for f in flows:
        f["score"] = sum((f.get("name", "") or "").lower().count(t) for t in q.split())
        f["score"] += 2 if (f.get("code", "") or "").lower() in q else 0
    
    flows.sort(key=lambda x: x["score"], reverse=True)
    return [f for f in flows if f["score"] > 0][:limit]

def to_cards(rows: List[Dict[str, Any]]) -> List[dict]:
    """Convert IMF datasets to evidence cards."""
    cards = []
    for r in rows:
        code = r.get("code")
        name = r.get("name") or code
        # IMF dataset landing
        url = f"https://dataservices.imf.org/REST/SDMX_JSON.svc/Dataflow/{code}" if code else "https://dataservices.imf.org/"
        
        cards.append({
            "title": f"IMF: {name}",
            "url": url,
            "snippet": f"IMF dataset {code}: {name}",
            "source_domain": "imf.org",
            "metadata": {
                "provider": "imf",
                "dataset_code": code,
                "license": "IMF Copyright and Usage"
            }
        })
    return cards