from __future__ import annotations
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import json
from jsonschema import validate, ValidationError
from research_system.models import EvidenceCard
try:
    from importlib import resources
except ImportError:
    import importlib_resources as resources

# Required fields that MUST be present and valid
REQUIRED_FIELDS = [
    "title", "url", "snippet", "provider", 
    "credibility_score", "relevance_score", "confidence"
]

def _load_schema() -> dict:
    """
    Load JSON schema from installed package data (works in dev, sdist, wheel).
    Falls back to repo-relative path in editable installs.
    """
    try:
        pkg = "research_system.resources.schemas"
        with resources.files(pkg).joinpath("evidence.schema.json").open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # Fallback for editable layout
        schema_path = Path(__file__).parent.parent / "resources" / "schemas" / "evidence.schema.json"
        with open(schema_path, "r", encoding="utf-8") as f:
            return json.load(f)

# Lazy load to avoid import-time issues
_SCHEMA = None

def _schema():
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = _load_schema()
    return _SCHEMA

def _repair_minimal(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Minimal self-healing before schema validation"""
    # Fix supporting_text if empty
    if not doc.get("supporting_text"):
        doc["supporting_text"] = (doc.get("snippet") or doc.get("title") or "").strip()[:5000]
    
    # Fix claim if empty
    if not doc.get("claim"):
        doc["claim"] = (doc.get("title") or doc.get("snippet") or "")[:200]
    
    return doc

def validate_evidence_dict(data: dict) -> None:
    """Enhanced validation with strict field requirements"""
    # JSONSchema validation (existing)
    try:
        validate(instance=data, schema=_schema())
    except ValidationError as e:
        raise ValueError(f"Evidence schema validation failed: {e.message}")
    
    # Additional hard checks (strong guardrail)
    missing = [k for k in REQUIRED_FIELDS if k not in data]
    if missing:
        raise ValueError(f"Evidence missing required fields: {missing}")
    
    # Validate score bounds
    if not (0 <= data.get("relevance_score", 0) <= 1):
        raise ValueError("relevance_score out of bounds [0,1]")
    if not (0 <= data.get("credibility_score", 0) <= 1):
        raise ValueError("credibility_score out of bounds [0,1]")
    if not (0 <= data.get("confidence", 0) <= 1):
        raise ValueError("confidence out of bounds [0,1]")
    
    # Ensure snippet is non-empty
    if not data.get("snippet", "").strip():
        raise ValueError("snippet cannot be empty")

def write_jsonl(path: str, items: List[EvidenceCard], *, skip_invalid: bool = True, 
                errors_path: Optional[str] = None) -> Tuple[int, int]:
    """
    Write evidence cards to JSONL, with resilience against invalid cards.
    
    Args:
        path: Output JSONL path
        items: List of EvidenceCard objects
        skip_invalid: If True, skip invalid cards instead of raising
        errors_path: Optional path to write error details
        
    Returns:
        Tuple of (successful_count, failed_count)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    
    # Setup error file if requested
    err_fp = Path(errors_path) if errors_path else None
    if err_fp:
        err_fp.parent.mkdir(parents=True, exist_ok=True)
        ef = err_fp.open("w", encoding="utf-8")
    else:
        ef = None
    
    ok = 0
    bad = 0
    
    with p.open("w", encoding="utf-8") as f:
        for i, item in enumerate(items):
            # Use canonical output format with blueprint fields
            doc = item.to_jsonl_dict() if hasattr(item, 'to_jsonl_dict') else item.model_dump()
            
            # Apply minimal repairs
            doc = _repair_minimal(doc)
            
            # Validate against schema + required fields
            try:
                validate_evidence_dict(doc)
            except (ValueError, ValidationError) as e:
                bad += 1
                error_msg = str(e)
                logger.warning(f"Validation failed for card {i+1}/{len(items)}: {error_msg}")
                logger.warning(f"Card ID: {doc.get('id', 'unknown')}, URL: {doc.get('url', 'unknown')}")
                
                if ef:
                    ef.write(json.dumps({
                        "id": doc.get("id"), 
                        "url": doc.get("url"), 
                        "error": error_msg
                    }) + "\n")
                
                if not skip_invalid:
                    raise
                continue
            
            f.write(json.dumps(doc, default=str) + "\n")
            ok += 1
    
    if ef:
        ef.close()
    
    logger.info(f"JSONL write complete: {ok} successful, {bad} failed")
    return ok, bad

def read_jsonl(path: str) -> List[EvidenceCard]:
    p = Path(path); 
    if not p.exists(): 
        return []
    out: List[EvidenceCard] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            obj = json.loads(line)
            validate_evidence_dict(obj)
            out.append(EvidenceCard(**obj))
    return out