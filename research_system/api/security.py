from fastapi import Header, HTTPException, status
from typing import Optional
import hmac
import os

API_KEY_HEADER = "x-api-key"

def require_api_key(x_api_key: Optional[str] = Header(default=None)):
    """Validate API key with constant-time comparison."""
    expected = os.getenv("API_GATEWAY_KEY", "")
    if not expected or not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")