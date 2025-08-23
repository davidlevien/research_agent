from fastapi import Header, HTTPException, status
from typing import Optional
import os

API_KEY_HEADER = "x-api-key"

def require_api_key(x_api_key: Optional[str] = Header(default=None)):
    expected = os.getenv("API_GATEWAY_KEY")
    if not expected:
        return  # auth disabled if no key set
    if not x_api_key or x_api_key != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")