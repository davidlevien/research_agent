from __future__ import annotations
from typing import List
from pathlib import Path
import json
from jsonschema import validate, ValidationError
from research_system.models import EvidenceCard

# Required fields that MUST be present and valid
REQUIRED_FIELDS = [
    "title", "url", "snippet", "provider", 
    "credibility_score", "relevance_score", "confidence"
]

def _load_schema() -> dict:
    # Load schema from file system
    schema_path = Path(__file__).parent.parent / "resources" / "schemas" / "evidence.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)

_SCHEMA = _load_schema()

def validate_evidence_dict(data: dict) -> None:
    """Enhanced validation with strict field requirements"""
    # JSONSchema validation (existing)
    try:
        validate(instance=data, schema=_SCHEMA)
    except ValidationError as e:
        raise ValueError(f"Evidence schema validation failed: {e.message}")
    
    # Additional hard checks (strong guardrail)
    missing = [k for k in REQUIRED_FIELDS if not data.get(k)]
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

def write_jsonl(path: str, items: List[EvidenceCard]) -> None:
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for item in items:
            # Use canonical output format with blueprint fields
            doc = item.to_jsonl_dict() if hasattr(item, 'to_jsonl_dict') else item.model_dump()
            validate_evidence_dict(doc)
            f.write(json.dumps(doc, default=str) + "\n")

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