"""Structured claim schema for evidence extraction.

v8.21.0: Implements structured claims with metric/unit/period/geo keys
for precise triangulation and numeric tolerance checking.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field, validator
import re
import math

@dataclass(frozen=True)
class ClaimKey:
    """Immutable key for uniquely identifying a claim."""
    metric: str           # e.g., "international_tourist_arrivals"
    unit: str             # e.g., "persons", "percent", "index"
    period: str           # ISO period label, e.g., "2025-Q1" or "2024"
    geo: str              # ISO3 or "EU27" or "WORLD"

    def __str__(self) -> str:
        return f"{self.metric}/{self.geo}/{self.period}"

class Claim(BaseModel):
    """Structured claim extracted from evidence."""
    key: ClaimKey
    value: float
    method: Optional[str] = None  # e.g., "yoy_change", "absolute"
    source_url: str
    quote_span: Optional[str] = None  # Exact quote from source
    source_domain: Optional[str] = None
    is_primary: bool = False  # From primary/authoritative source

    class Config:
        arbitrary_types_allowed = True

    @validator("value")
    def finite(cls, v):
        """Ensure value is finite and valid."""
        if v is None or not math.isfinite(v):
            raise ValueError("value must be finite")
        return float(v)
    
    def dict(self, **kwargs) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = super().dict(**kwargs)
        # Convert ClaimKey to dict
        d["key"] = {
            "metric": self.key.metric,
            "unit": self.key.unit,
            "period": self.key.period,
            "geo": self.key.geo
        }
        return d