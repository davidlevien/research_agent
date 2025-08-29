from datetime import datetime, timezone

def safe_strftime(ts, fmt="%Y%m%d_%H%M%S"):
    """
    Accepts datetime, seconds since epoch, or string; returns formatted string.
    """
    if isinstance(ts, datetime):
        dt = ts
    elif isinstance(ts, (int, float)):
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    elif isinstance(ts, str):
        # best effort parse of a common ISO-like shape
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            dt = datetime.utcnow().replace(tzinfo=timezone.utc)
    else:
        dt = datetime.utcnow().replace(tzinfo=timezone.utc)
    return dt.strftime(fmt)