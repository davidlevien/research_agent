from pydantic import BaseModel
from typing import Optional

class SearchRequest(BaseModel):
    query: str
    count: int = 8
    freshness_window: Optional[str] = None
    region: Optional[str] = None

class SearchHit(BaseModel):
    title: str
    url: str
    snippet: Optional[str] = None
    date: Optional[str] = None
    provider: str