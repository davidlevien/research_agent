"""OECD provider for economic statistics and datasets."""

from __future__ import annotations
from typing import List, Dict, Any
from .http import http_json
import logging

logger = logging.getLogger(__name__)

# OECD SDMX-JSON: list dataflows (datasets) and filter by query
_DATAFLOW = "https://stats.oecd.org/SDMX-JSON/dataflow/ALL"

def _dataflows() -> Dict[str, Dict[str, Any]]:
    """Fetch OECD dataflows catalog."""
    try:
        data = http_json("GET", _DATAFLOW)
        
        # Shape varies; normalize
        if "data" in data and "dataflows" in data["data"]:
            return data["data"]["dataflows"]
        
        if "Dataflows" in data and "Dataflow" in data["Dataflows"]:
            out = {}
            for df in data["Dataflows"]["Dataflow"]:
                key = df.get("Key") or df.get("@id") or df.get("id")
                name = ""
                nm = df.get("Name") or df.get("name")
                if isinstance(nm, list) and nm:
                    name = nm[0].get("$") or nm[0].get("value") or ""
                elif isinstance(nm, str):
                    name = nm
                out[str(key)] = {"name": name}
            return out
        
        return {}
    except Exception as e:
        logger.warning(f"OECD dataflows fetch failed: {e}")
        return {}

def search_oecd(query: str, limit: int = 25) -> List[Dict[str, Any]]:
    """Search OECD datasets by relevance to query."""
    q = (query or "").lower()
    dfs = _dataflows()
    items = []
    
    for code, meta in dfs.items():
        name = (meta.get("name") or "").lower()
        score = sum(name.count(t) for t in q.split()) + (2 if code.lower() in q else 0)
        if score > 0:
            items.append({"code": code, "name": meta.get("name"), "score": score})
    
    items.sort(key=lambda x: x["score"], reverse=True)
    return items[:limit]

def to_cards(rows: List[Dict[str, Any]]) -> List[dict]:
    """Convert OECD datasets to evidence cards."""
    cards = []
    for r in rows:
        code = r.get("code")
        title = r.get("name") or code
        # Link to dataset landing page in OECD stats
        url = f"https://stats.oecd.org/Index.aspx?DataSetCode={code}" if code else "https://stats.oecd.org/"
        
        cards.append({
            "title": f"OECD: {title}",
            "url": url,
            "snippet": f"OECD dataset {code}",
            "source_domain": "oecd.org",
            "metadata": {
                "provider": "oecd",
                "dataset_code": code,
                "license": "OECD Terms and Conditions"
            }
        })
    return cards