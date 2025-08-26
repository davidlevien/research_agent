"""Logging redaction utilities to prevent leaking sensitive data."""

from urllib.parse import urlsplit, parse_qsl, urlencode, urlunsplit
from typing import Any
import re

SENSITIVE_KEYS = {
    "api_key", "apikey", "key", "token", "authorization", 
    "signature", "secret", "password", "pwd", "auth",
    "access_token", "refresh_token", "client_secret",
    "private_key", "api-key", "x-api-key", "bearer"
}

# Patterns for sensitive data in URLs and strings
API_KEY_PATTERNS = [
    r'sk-[A-Za-z0-9_\-]+',  # OpenAI keys
    r'sk-proj-[A-Za-z0-9_\-]+',  # OpenAI project keys
    r'tvly-[A-Za-z0-9_\-]+',  # Tavily keys  
    r'BSA[A-Za-z0-9_\-]+',  # Brave keys
    r'(?:api[_-]?key|token|auth)[=:]\s*["\']?([A-Za-z0-9_\-]{20,})["\']?',
]

def redact_url(url: str) -> str:
    """Redact sensitive parameters from URLs."""
    if not url:
        return url
    
    try:
        parts = urlsplit(url)
        # Redact query parameters
        if parts.query:
            params = []
            for k, v in parse_qsl(parts.query, keep_blank_values=True):
                if k.lower() in SENSITIVE_KEYS:
                    params.append((k, "***REDACTED***"))
                else:
                    # Also check if value looks like a key
                    if len(v) > 20 and any(re.match(p, v) for p in API_KEY_PATTERNS):
                        params.append((k, "***REDACTED***"))
                    else:
                        params.append((k, v))
            redacted = urlunsplit(parts._replace(query=urlencode(params)))
        else:
            redacted = url
        
        # Redact keys in path (e.g., /api/v1/key/abc123...)
        for pattern in API_KEY_PATTERNS:
            redacted = re.sub(pattern, "***REDACTED***", redacted)
        
        return redacted
    except Exception:
        # If parsing fails, do basic pattern replacement
        result = url
        for pattern in API_KEY_PATTERNS:
            result = re.sub(pattern, "***REDACTED***", result)
        return result

def redact_headers(headers: dict) -> dict:
    """Redact sensitive headers."""
    if not headers:
        return headers
    
    redacted = {}
    for k, v in headers.items():
        k_lower = k.lower()
        if any(sensitive in k_lower for sensitive in SENSITIVE_KEYS):
            redacted[k] = "***REDACTED***"
        elif k_lower in {"authorization", "x-api-key", "api-key"}:
            redacted[k] = "***REDACTED***"
        else:
            # Check if value looks sensitive
            if isinstance(v, str) and len(v) > 20:
                if any(re.match(p, v) for p in API_KEY_PATTERNS):
                    redacted[k] = "***REDACTED***"
                else:
                    redacted[k] = v
            else:
                redacted[k] = v
    return redacted

def redact_string(text: str) -> str:
    """Redact sensitive data from arbitrary strings."""
    if not text:
        return text
    
    result = text
    # Replace API keys
    for pattern in API_KEY_PATTERNS:
        result = re.sub(pattern, "***REDACTED***", result, flags=re.IGNORECASE)
    
    # Replace key=value patterns
    result = re.sub(
        r'\b(api[_-]?key|token|auth|password|secret)[=:]\s*["\']?([^"\'\s]{8,})["\']?',
        r'\1=***REDACTED***',
        result,
        flags=re.IGNORECASE
    )
    
    return result

def safe_log_params(params: Any) -> Any:
    """Redact sensitive data from log parameters."""
    if isinstance(params, str):
        return redact_string(params)
    elif isinstance(params, dict):
        return {k: safe_log_params(v) for k, v in params.items()}
    elif isinstance(params, (list, tuple)):
        return [safe_log_params(item) for item in params]
    else:
        return params