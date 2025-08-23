from __future__ import annotations
from typing import List
from pathlib import Path
import json
from jsonschema import validate, ValidationError
from research_system.models import EvidenceCard

def _load_schema() -> dict:
    # Load schema from file system
    schema_path = Path(__file__).parent.parent / "resources" / "schemas" / "evidence.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)

_SCHEMA = _load_schema()

def validate_evidence_dict(data: dict) -> None:
    try:
        validate(instance=data, schema=_SCHEMA)
    except ValidationError as e:
        raise ValueError(f"Evidence schema validation failed: {e.message}")

def write_jsonl(path: str, items: List[EvidenceCard]) -> None:
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for item in items:
            doc = item.model_dump()
            validate_evidence_dict(doc)
            f.write(json.dumps(doc) + "\n")

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